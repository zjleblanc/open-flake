from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import AuthContext, authenticate_request
from app.config import get_settings
from app.db import get_db
from app.domain.table_service import (
    _model_to_dict,
    create_record,
    delete_record,
    get_record_by_sys_id,
    list_records,
    update_record,
)
from app.models import CmdbCi, CmdbRelCi
from app.query.parser import QueryCondition, parse_sysparm_query
from app.utils.ids import new_sys_id

router = APIRouter(prefix="/api/now/cmdb/instance", tags=["cmdb-api"])
settings = get_settings()


def _ci_query_for_class(sys_class_name: str):
    def _cond(model, conditions):
        from app.domain.table_service import _apply_conditions

        q = select(CmdbCi).where(CmdbCi.sys_class_name == sys_class_name)
        return _apply_conditions(q, CmdbCi, conditions)

    return _cond


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
    conditions.append(QueryCondition(field="sys_class_name", operator="=", value=sys_class_name))
    records, total = await list_records(
        db, "cmdb_ci", conditions, sysparm_limit, sysparm_offset, True, auth=auth
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
    record = await get_record_by_sys_id(db, "cmdb_ci", sys_id, auth=auth)
    if not record or record.get("sys_class_name") != sys_class_name:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "CI not found")
    return {"result": record}


@router.post("/{sys_class_name}", status_code=status.HTTP_201_CREATED)
async def cmdb_create(
    sys_class_name: str,
    payload: dict[str, Any],
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    payload["sys_class_name"] = sys_class_name
    record = await create_record(db, "cmdb_ci", payload, auth.user_sys_id, auth=auth)
    return {"result": record}


@router.patch("/{sys_class_name}/{sys_id}")
async def cmdb_update(
    sys_class_name: str,
    sys_id: str,
    payload: dict[str, Any],
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.get(CmdbCi, sys_id)
    if not existing or existing.sys_class_name != sys_class_name:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "CI not found")
    record = await update_record(db, "cmdb_ci", sys_id, payload, auth.user_sys_id, auth=auth)
    return {"result": record}


@router.delete("/{sys_class_name}/{sys_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cmdb_delete(
    sys_class_name: str,
    sys_id: str,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.get(CmdbCi, sys_id)
    if not existing or existing.sys_class_name != sys_class_name:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "CI not found")
    await delete_record(db, "cmdb_ci", sys_id, auth=auth)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{sys_class_name}/{sys_id}/relation")
async def cmdb_list_relations(
    sys_class_name: str,
    sys_id: str,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CmdbRelCi).where(
            (CmdbRelCi.parent == sys_id) | (CmdbRelCi.child == sys_id)
        )
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
    rel_payload = {
        "parent": payload.get("parent", sys_id),
        "child": payload.get("child") or payload.get("target"),
        "type": payload.get("type"),
    }
    if isinstance(rel_payload["child"], dict):
        rel_payload["child"] = rel_payload["child"].get("value")
    if isinstance(rel_payload["type"], dict):
        rel_payload["type"] = rel_payload["type"].get("value")
    record = await create_record(db, "cmdb_rel_ci", rel_payload, auth.user_sys_id)
    return {"result": record}


@router.delete("/{sys_class_name}/{sys_id}/relation/{rel_sys_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cmdb_delete_relation(
    sys_class_name: str,
    sys_id: str,
    rel_sys_id: str,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    await delete_record(db, "cmdb_rel_ci", rel_sys_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
