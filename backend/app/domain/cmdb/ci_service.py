"""CMDB configuration item CRUD with class hierarchy semantics."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import AuthContext
from app.auth.rbac import (
    assert_can_create_record,
    assert_record_action,
    filter_record_list_query,
    resolve_record_permissions,
)
from app.domain.cmdb.constants import CMDB_ROOT
from app.domain.cmdb.payload import merge_record, split_payload
from app.domain.cmdb.registry import (
    compute_class_path,
    ensure_class,
    field_origin,
    get_descendants,
    get_merged_fields,
    is_registered,
    refresh_cache,
)
from app.events.bus import RecordEvent, emit
from app.models import CmdbCi, SysUser
from app.query.parser import QueryCondition, apply_condition_groups
from app.utils.ids import new_sys_id


async def _resolve_audit_username(
    db: AsyncSession,
    user_sys_id: str | None,
    auth: AuthContext | None,
) -> str | None:
    if auth:
        return auth.user_name
    if user_sys_id:
        user = await db.get(SysUser, user_sys_id)
        return user.user_name if user else None
    return None


def _apply_conditions(query, conditions: list[QueryCondition]):
    return apply_condition_groups(query, CmdbCi, conditions)


def class_filter_conditions(class_name: str | None) -> list[QueryCondition]:
    if not class_name or class_name == CMDB_ROOT:
        return []
    descendants = get_descendants(class_name)
    if len(descendants) == 1:
        return [QueryCondition(field="sys_class_name", operator="=", value=class_name)]
    return [
        QueryCondition(
            field="sys_class_name",
            operator="IN",
            value=",".join(descendants),
        )
    ]


def record_in_class_subtree(record_class: str, query_class: str | None) -> bool:
    if not query_class or query_class == CMDB_ROOT:
        return True
    return record_class in get_descendants(query_class)


async def _ensure_class_for_write(db: AsyncSession, class_name: str) -> None:
    if is_registered(class_name):
        return
    await ensure_class(db, class_name, super_class=CMDB_ROOT, label=class_name)
    await refresh_cache(db)


async def list_cmdb_ci(
    db: AsyncSession,
    conditions: list[QueryCondition],
    limit: int = 1000,
    offset: int = 0,
    exclude_links: bool = True,
    auth: AuthContext | None = None,
    include_permissions: bool = False,
    query_class: str | None = None,
) -> tuple[list[dict], int]:
    all_conditions = [*class_filter_conditions(query_class), *conditions]

    count_q = select(func.count()).select_from(CmdbCi)
    count_q = _apply_conditions(count_q, all_conditions)
    query = select(CmdbCi)
    query = _apply_conditions(query, all_conditions)

    if auth:
        count_q = await filter_record_list_query(db, auth, "cmdb_ci", count_q, CmdbCi)
        query = await filter_record_list_query(db, auth, "cmdb_ci", query, CmdbCi)

    total = (await db.execute(count_q)).scalar() or 0
    result = await db.execute(query.limit(limit).offset(offset))
    records = result.scalars().all()

    out = []
    for record in records:
        record_dict = merge_record(record, exclude_links=exclude_links)
        if include_permissions and auth:
            perms = await resolve_record_permissions(db, auth, "cmdb_ci", record_dict)
            record_dict["_permissions"] = perms.to_dict()
        out.append(record_dict)
    return out, total


async def get_cmdb_ci(
    db: AsyncSession,
    sys_id: str,
    exclude_links: bool = True,
    auth: AuthContext | None = None,
    include_permissions: bool = False,
    skip_auth: bool = False,
    query_class: str | None = None,
) -> dict | None:
    record = await db.get(CmdbCi, sys_id)
    if not record:
        return None

    if query_class and not record_in_class_subtree(record.sys_class_name, query_class):
        return None

    if auth and not skip_auth:
        await assert_record_action(db, auth, "cmdb_ci", record, "read")

    record_dict = merge_record(record, exclude_links=exclude_links)
    if include_permissions and auth:
        perms = await resolve_record_permissions(db, auth, "cmdb_ci", record_dict)
        record_dict["_permissions"] = perms.to_dict()
    return record_dict


async def create_cmdb_ci(
    db: AsyncSession,
    payload: dict[str, Any],
    class_name: str | None = None,
    user_sys_id: str | None = None,
    exclude_links: bool = True,
    auth: AuthContext | None = None,
) -> dict:
    if auth:
        await assert_can_create_record(db, auth, "cmdb_ci")

    resolved_class = class_name or payload.get("sys_class_name") or CMDB_ROOT
    if resolved_class == CMDB_ROOT and "sys_class_name" not in payload:
        resolved_class = CMDB_ROOT

    await _ensure_class_for_write(db, resolved_class)

    columns, attributes = split_payload(resolved_class, payload)
    sys_id = columns.pop("sys_id", None) or new_sys_id()
    columns["sys_id"] = sys_id
    columns["sys_class_name"] = resolved_class
    columns["sys_class_path"] = compute_class_path(resolved_class)
    columns.pop("sys_mod_count", None)

    audit_username = await _resolve_audit_username(db, user_sys_id, auth)
    if audit_username:
        columns["sys_created_by"] = audit_username
        columns["sys_updated_by"] = audit_username
    if user_sys_id and not columns.get("owner"):
        columns["owner"] = user_sys_id

    model_columns = {c.name for c in CmdbCi.__table__.columns}
    record = CmdbCi(
        **{k: v for k, v in columns.items() if k in model_columns},
        attributes=attributes,
    )
    db.add(record)
    await db.flush()

    result = merge_record(record, exclude_links=exclude_links)
    await emit(RecordEvent(action="create", table="cmdb_ci", sys_id=sys_id, record=result))
    return result


async def update_cmdb_ci(
    db: AsyncSession,
    sys_id: str,
    payload: dict[str, Any],
    user_sys_id: str | None = None,
    exclude_links: bool = True,
    auth: AuthContext | None = None,
    query_class: str | None = None,
) -> dict | None:
    record = await db.get(CmdbCi, sys_id)
    if not record:
        return None
    if query_class and not record_in_class_subtree(record.sys_class_name, query_class):
        return None
    if auth:
        await assert_record_action(db, auth, "cmdb_ci", record, "write")

    class_name = record.sys_class_name
    columns, attributes = split_payload(class_name, payload)
    columns.pop("sys_id", None)
    columns.pop("sys_class_name", None)
    columns.pop("sys_mod_count", None)

    audit_username = await _resolve_audit_username(db, user_sys_id, auth)
    if audit_username:
        columns["sys_updated_by"] = audit_username

    model_columns = {c.name for c in CmdbCi.__table__.columns}
    for key, value in columns.items():
        if key in model_columns:
            setattr(record, key, value)

    if attributes:
        current = dict(record.attributes or {})
        current.update(attributes)
        record.attributes = current

    record.sys_mod_count = (record.sys_mod_count or 0) + 1

    await db.flush()
    result = merge_record(record, exclude_links=exclude_links)
    await emit(RecordEvent(action="update", table="cmdb_ci", sys_id=sys_id, record=result))
    return result


async def delete_cmdb_ci(
    db: AsyncSession,
    sys_id: str,
    auth: AuthContext | None = None,
    query_class: str | None = None,
) -> bool:
    from app.api.flake.attachment import delete_attachments_for_parent

    record = await db.get(CmdbCi, sys_id)
    if not record:
        return False
    if query_class and not record_in_class_subtree(record.sys_class_name, query_class):
        return False
    if auth:
        await assert_record_action(db, auth, "cmdb_ci", record, "delete")

    result = merge_record(record, exclude_links=False)
    await delete_attachments_for_parent(db, "cmdb_ci", sys_id)
    await db.delete(record)
    await db.flush()
    await emit(RecordEvent(action="delete", table="cmdb_ci", sys_id=sys_id, record=result))
    return True


def schema_for_class(class_name: str) -> dict[str, Any]:
    merged = get_merged_fields(class_name)
    fields = []
    for name in sorted(merged):
        field = merged[name]
        fields.append(
            {
                "name": name,
                "label": field.label,
                "type": field.sn_type,
                "defined_on": field.defined_on,
                "origin": field_origin(class_name, field),
                "storage": field.storage,
            }
        )
    return {
        "class_name": class_name,
        "inheritance_path": _ancestors_for_schema(class_name),
        "fields": fields,
        "registered": is_registered(class_name),
    }


def _ancestors_for_schema(class_name: str) -> list[str]:
    from app.domain.cmdb.registry import resolve_inheritance_path

    return resolve_inheritance_path(class_name)


def class_tree() -> list[dict[str, Any]]:
    from app.domain.cmdb.registry import _require_snapshot

    snap = _require_snapshot()

    def node(name: str) -> dict[str, Any]:
        cls = snap.classes[name]
        return {
            "name": name,
            "label": cls.label,
            "super_class": cls.super_class,
            "is_logical": cls.is_logical,
            "children": [node(child) for child in sorted(snap.children.get(name, ()))],
        }

    roots = [name for name, cls in snap.classes.items() if cls.super_class is None]
    return [node(name) for name in sorted(roots)]
