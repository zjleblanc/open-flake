from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import AuthContext, authenticate_request
from app.db import get_db
from app.domain.cmdb.ci_service import (
    class_filter_conditions,
    create_cmdb_ci,
    delete_cmdb_ci,
    get_cmdb_ci,
    list_cmdb_ci,
    update_cmdb_ci,
)
from app.domain.table_service import create_record, delete_record
from app.models import CmdbRelCi
from app.query.parser import parse_sysparm_query

router = APIRouter(prefix="/api/flake/cmdb/instance", tags=["cmdb-api"])


@router.get("/{sys_class_name}")
async def cmdb_list(
    sys_class_name: str,
    request: Request,
    response: Response,
    sysparm_query: str | None = Query(default=None),
    sysparm_limit: int = Query(default=1000),
    sysparm_offset: int = Query(default=0),
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    conditions = parse_sysparm_query(sysparm_query)
    conditions = [*class_filter_conditions(sys_class_name), *conditions]
    records, total = await list_cmdb_ci(
        db,
        conditions,
        sysparm_limit,
        sysparm_offset,
        True,
        auth=auth,
        query_class=sys_class_name,
    )
    response.headers["x-total-count"] = str(total)
    return {"result": records}


@router.get("/{sys_class_name}/{sys_id}")
async def cmdb_get(
    sys_class_name: str,
    sys_id: str,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    record = await get_cmdb_ci(db, sys_id, auth=auth, query_class=sys_class_name)
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "CI not found")
    return {"result": record}


@router.post("/{sys_class_name}", status_code=status.HTTP_201_CREATED)
async def cmdb_create(
    sys_class_name: str,
    payload: dict[str, Any],
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    record = await create_cmdb_ci(
        db,
        payload,
        class_name=sys_class_name,
        user_sys_id=auth.user_sys_id,
        auth=auth,
    )
    return {"result": record}


@router.patch("/{sys_class_name}/{sys_id}")
async def cmdb_update(
    sys_class_name: str,
    sys_id: str,
    payload: dict[str, Any],
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    record = await update_cmdb_ci(
        db,
        sys_id,
        payload,
        user_sys_id=auth.user_sys_id,
        auth=auth,
        query_class=sys_class_name,
    )
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "CI not found")
    return {"result": record}


@router.delete("/{sys_class_name}/{sys_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cmdb_delete(
    sys_class_name: str,
    sys_id: str,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    deleted = await delete_cmdb_ci(db, sys_id, auth=auth, query_class=sys_class_name)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "CI not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{sys_class_name}/{sys_id}/relation")
async def cmdb_list_relations(
    sys_class_name: str,
    sys_id: str,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    record = await get_cmdb_ci(db, sys_id, auth=auth, query_class=sys_class_name)
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "CI not found")
    result = await db.execute(
        select(CmdbRelCi).where((CmdbRelCi.parent == sys_id) | (CmdbRelCi.child == sys_id))
    )
    rels = result.scalars().all()
    return {
        "result": [
            {
                "sys_id": r.sys_id,
                "parent": {"value": r.parent},
                "child": {"value": r.child},
                "type": {"value": r.type},
            }
            for r in rels
        ]
    }


@router.post("/{sys_class_name}/{sys_id}/relation", status_code=status.HTTP_201_CREATED)
async def cmdb_create_relation(
    sys_class_name: str,
    sys_id: str,
    payload: dict[str, Any],
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    record = await get_cmdb_ci(db, sys_id, auth=auth, query_class=sys_class_name)
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "CI not found")
    rel_payload = {
        "parent": payload.get("parent", sys_id),
        "child": payload.get("child") or payload.get("target"),
        "type": payload.get("type"),
    }
    if isinstance(rel_payload["child"], dict):
        rel_payload["child"] = rel_payload["child"].get("value")
    if isinstance(rel_payload["type"], dict):
        rel_payload["type"] = rel_payload["type"].get("value")
    rel_record = await create_record(db, "cmdb_rel_ci", rel_payload, auth.user_sys_id)
    return {"result": rel_record}


@router.delete(
    "/{sys_class_name}/{sys_id}/relation/{rel_sys_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def cmdb_delete_relation(
    sys_class_name: str,
    sys_id: str,
    rel_sys_id: str,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    record = await get_cmdb_ci(db, sys_id, auth=auth, query_class=sys_class_name)
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "CI not found")
    await delete_record(db, "cmdb_rel_ci", rel_sys_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
