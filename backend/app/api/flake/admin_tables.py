"""Admin API for the table/class registry: browse the hierarchy and create
new CMDB classes extended from an existing extendable class (e.g.
`cmdb_ci_server`), add fields to them, or remove unused user-defined classes.

Writes go straight to `sys_db_object` / `sys_dictionary` and immediately
call `refresh_cache()` so the in-memory registry (and every dependent API --
reference pickers, `/table/{table}` routing, schema lookups) reflects the
change without a backend restart.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import AuthContext, authenticate_request
from app.auth.rbac import get_user_permissions, has_permission
from app.db import get_db
from app.domain.cmdb.ci_service import schema_for_class
from app.domain.cmdb.constants import CMDB_ROOT
from app.domain.cmdb.registry import (
    _require_snapshot,
    ensure_class,
    get_descendants,
    is_registered,
    refresh_cache,
    upsert_field,
)
from app.models import CmdbCi, SysDbObject

router = APIRouter(prefix="/api/flake/admin/tables", tags=["table-admin-api"])

_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


async def _require_table_admin(db: AsyncSession, auth: AuthContext) -> None:
    perms = await get_user_permissions(db, auth.user_sys_id)
    if not has_permission(perms, "records.*.write"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Table administration requires admin access"
        )


def _db_object_dict(obj: SysDbObject, children_count: int = 0) -> dict[str, Any]:
    return {
        "name": obj.name,
        "label": obj.label,
        "super_class": obj.super_class,
        "is_logical": obj.is_logical,
        "is_extendable": obj.is_extendable,
        "storage_type": obj.storage_type,
        "base_table": obj.base_table,
        "user_defined": obj.user_defined,
        "active": obj.active,
        "children_count": children_count,
    }


@router.get("")
async def list_tables(
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    """Return every registered table/class as a flat, hierarchy-annotated list."""
    await _require_table_admin(db, auth)
    snap = _require_snapshot()
    return {
        "result": [
            _db_object_dict(obj, len(snap.children.get(name, ())))
            for name, obj in sorted(snap.classes.items())
        ]
    }


@router.get("/{name}/schema")
async def get_table_schema(
    name: str,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    """Return the merged (own + inherited) field schema for a registered class."""
    await _require_table_admin(db, auth)
    if not is_registered(name):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Table not found")
    return {"result": schema_for_class(name)}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_table(
    payload: dict[str, Any],
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    """Create a new CMDB class extended from an existing extendable class."""
    await _require_table_admin(db, auth)

    name = (payload.get("name") or "").strip().lower()
    if not name or not _NAME_PATTERN.match(name):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "name must be lowercase snake_case (letters, numbers, underscores)",
        )
    if is_registered(name):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"'{name}' is already registered")

    super_class = (payload.get("super_class") or CMDB_ROOT).strip()
    snap = _require_snapshot()
    parent = snap.classes.get(super_class)
    if not parent:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Parent class '{super_class}' not found")
    if not parent.is_extendable:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"'{super_class}' cannot be extended")
    if super_class not in get_descendants(CMDB_ROOT):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Only CMDB classes (cmdb_ci and its subclasses) can be extended",
        )

    label = (payload.get("label") or name).strip()
    await ensure_class(
        db,
        name,
        super_class=super_class,
        label=label,
        is_extendable=True,
        user_defined=True,
    )

    for field in payload.get("fields") or []:
        field_name = (field.get("name") or "").strip().lower()
        if not field_name or not _NAME_PATTERN.match(field_name):
            continue
        await upsert_field(
            db,
            name,
            field_name,
            label=field.get("label") or field_name,
            sn_type=field.get("type") or "string",
            reference=field.get("reference") or None,
            mandatory=bool(field.get("mandatory", False)),
            user_defined=True,
        )

    await db.commit()
    await refresh_cache(db)
    return {"result": schema_for_class(name)}


@router.put("/{name}/fields", status_code=status.HTTP_201_CREATED)
async def add_table_field(
    name: str,
    payload: dict[str, Any],
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    """Add (or update) a field definition on a registered class."""
    await _require_table_admin(db, auth)
    if not is_registered(name):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Table not found")

    field_name = (payload.get("name") or "").strip().lower()
    if not field_name or not _NAME_PATTERN.match(field_name):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "field name must be lowercase snake_case (letters, numbers, underscores)",
        )

    await upsert_field(
        db,
        name,
        field_name,
        label=payload.get("label") or field_name,
        sn_type=payload.get("type") or "string",
        reference=payload.get("reference") or None,
        mandatory=bool(payload.get("mandatory", False)),
        user_defined=True,
    )
    await db.commit()
    await refresh_cache(db)
    return {"result": schema_for_class(name)}


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_table(
    name: str,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    """Remove a user-defined class with no subclasses and no existing records."""
    await _require_table_admin(db, auth)
    snap = _require_snapshot()
    obj = snap.classes.get(name)
    if not obj:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Table not found")
    if not obj.user_defined:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only user-defined tables can be deleted")
    if len(snap.children.get(name, ())) > 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot delete a class with subclasses")

    count = (
        await db.execute(
            select(func.count()).select_from(CmdbCi).where(CmdbCi.sys_class_name == name)
        )
    ).scalar() or 0
    if count:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Cannot delete a class with existing records"
        )

    row = (
        await db.execute(select(SysDbObject).where(SysDbObject.name == name))
    ).scalar_one_or_none()
    if row:
        await db.delete(row)
        await db.commit()
    await refresh_cache(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
