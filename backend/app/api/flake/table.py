from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import AuthContext, authenticate_request
from app.db import get_db
from app.domain.cmdb.ci_service import class_filter_conditions
from app.domain.registry import resolve_table_name
from app.domain.table_service import (
    create_record,
    delete_record,
    get_record_by_sys_id,
    list_records,
    update_record,
)
from app.query.parser import QueryCondition, parse_sysparm_query

router = APIRouter(prefix="/api/flake/table", tags=["table-api"])


def _resolve_table(table: str) -> tuple[str, str | None]:
    resolved = resolve_table_name(table)
    if not resolved:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown table: {table}")
    return resolved


def _exclude_links(request: Request) -> bool:
    val = request.query_params.get("sysparm_exclude_reference_link", "true")
    return val.lower() != "false"


def _query_params_to_conditions(request: Request, sysparm_query: str | None) -> list[QueryCondition]:
    conditions = parse_sysparm_query(sysparm_query)
    reserved = {
        "sysparm_query",
        "sysparm_limit",
        "sysparm_offset",
        "sysparm_exclude_reference_link",
        "sysparm_fields",
        "sysparm_display_value",
        "sysparm_suppress_pagination_header",
    }
    for key, value in request.query_params.items():
        if key not in reserved and value:
            conditions.append(QueryCondition(field=key, operator="=", value=value))
    return conditions


def _merge_class_conditions(
    conditions: list[QueryCondition], query_class: str | None
) -> list[QueryCondition]:
    if not query_class:
        return conditions
    return [*class_filter_conditions(query_class), *conditions]


@router.get("/{table}")
async def table_list(
    table: str,
    request: Request,
    response: Response,
    sysparm_query: str | None = Query(default=None),
    sysparm_limit: int = Query(default=1000),
    sysparm_offset: int = Query(default=0),
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    internal_table, query_class = _resolve_table(table)
    conditions = _merge_class_conditions(
        _query_params_to_conditions(request, sysparm_query), query_class
    )
    exclude = _exclude_links(request)
    records, total = await list_records(
        db,
        internal_table,
        conditions,
        sysparm_limit,
        sysparm_offset,
        exclude,
        auth=auth,
        query_class=query_class,
    )
    response.headers["x-total-count"] = str(total)
    return {"result": records}


@router.get("/{table}/{sys_id}")
async def table_get(
    table: str,
    sys_id: str,
    request: Request,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    internal_table, query_class = _resolve_table(table)
    exclude = _exclude_links(request)
    record = await get_record_by_sys_id(
        db, internal_table, sys_id, exclude, auth=auth, query_class=query_class
    )
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Record not found")
    return {"result": record}


@router.post("/{table}", status_code=status.HTTP_201_CREATED)
async def table_create(
    table: str,
    payload: dict[str, Any],
    request: Request,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    internal_table, query_class = _resolve_table(table)
    if query_class:
        payload = {**payload, "sys_class_name": query_class}
    exclude = _exclude_links(request)
    record = await create_record(
        db,
        internal_table,
        payload,
        auth.user_sys_id,
        exclude,
        auth=auth,
        class_name=query_class,
    )
    return {"result": record}


@router.patch("/{table}/{sys_id}")
async def table_update(
    table: str,
    sys_id: str,
    payload: dict[str, Any],
    request: Request,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    internal_table, query_class = _resolve_table(table)
    existing = await get_record_by_sys_id(
        db,
        internal_table,
        sys_id,
        exclude_links=False,
        auth=auth,
        skip_auth=True,
        query_class=query_class,
    )
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Record not found")
    exclude = _exclude_links(request)
    record = await update_record(
        db,
        internal_table,
        sys_id,
        payload,
        auth.user_sys_id,
        exclude,
        auth=auth,
        query_class=query_class,
    )
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Record not found")
    return {"result": record}


@router.delete("/{table}/{sys_id}", status_code=status.HTTP_204_NO_CONTENT)
async def table_delete(
    table: str,
    sys_id: str,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    internal_table, query_class = _resolve_table(table)
    existing = await get_record_by_sys_id(
        db,
        internal_table,
        sys_id,
        exclude_links=False,
        auth=auth,
        skip_auth=True,
        query_class=query_class,
    )
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Record not found")
    deleted = await delete_record(
        db, internal_table, sys_id, auth=auth, query_class=query_class
    )
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Record not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
