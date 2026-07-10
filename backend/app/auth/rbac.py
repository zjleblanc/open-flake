from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import HTTPException, status
from sqlalchemy import and_, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import AuthContext
from app.domain.registry import PLATFORM_TABLES, RBAC_RECORD_TABLES, TABLE_MODELS
from app.models import RecordAccessGrant, SysGroupRole, SysRole, SysUserGrMember, SysUserGroup

RecordAction = Literal["read", "write", "comment", "delete"]
PlatformAction = Literal["read", "write", "manage", "self_write"]


@dataclass
class RecordPermissions:
    read: bool = False
    write: bool = False
    comment: bool = False
    delete: bool = False

    def to_dict(self) -> dict[str, bool]:
        return {
            "read": self.read,
            "write": self.write,
            "comment": self.comment,
            "delete": self.delete,
        }


def _now() -> datetime:
    return datetime.now(timezone.utc)


def has_permission(user_permissions: set[str], required: str) -> bool:
    if required in user_permissions:
        return True
    if required.startswith("records."):
        if required.endswith((".write", ".delete")) and "records.*.write" in user_permissions:
            return True
        if required.endswith(".read") and "records.*.read" in user_permissions:
            return True
    # secrets.admin ⊃ secrets.write ⊃ secrets.read
    if required == "secrets.read":
        if "secrets.write" in user_permissions or "secrets.admin" in user_permissions:
            return True
    if required == "secrets.write":
        if "secrets.admin" in user_permissions:
            return True
    return False


async def get_user_group_ids(db: AsyncSession, user_sys_id: str) -> set[str]:
    result = await db.execute(
        select(SysUserGrMember.group_sys_id).where(SysUserGrMember.user_sys_id == user_sys_id)
    )
    return set(result.scalars().all())


async def get_user_permissions(db: AsyncSession, user_sys_id: str) -> set[str]:
    result = await db.execute(
        select(SysRole.permissions)
        .join(SysGroupRole, SysGroupRole.role_sys_id == SysRole.sys_id)
        .join(SysUserGrMember, SysUserGrMember.group_sys_id == SysGroupRole.group_sys_id)
        .where(SysUserGrMember.user_sys_id == user_sys_id)
    )
    perms: set[str] = set()
    for perm_list in result.scalars().all():
        if isinstance(perm_list, list):
            perms.update(perm_list)
    return perms


async def is_group_owner(db: AsyncSession, user_sys_id: str, group_sys_id: str) -> bool:
    result = await db.execute(
        select(SysUserGroup.owner).where(SysUserGroup.sys_id == group_sys_id)
    )
    owner = result.scalar_one_or_none()
    return owner == user_sys_id


def _record_from_dict(record: dict[str, Any] | Any) -> dict[str, Any]:
    if isinstance(record, dict):
        return record
    data: dict[str, Any] = {}
    for col in record.__table__.columns:
        val = getattr(record, col.name, None)
        if val is None:
            data[col.name] = ""
        elif hasattr(val, "isoformat"):
            data[col.name] = val.isoformat()
        else:
            data[col.name] = str(val)
    return data


def _ref_value(record: dict[str, Any], field: str) -> str | None:
    val = record.get(field, "")
    if isinstance(val, dict):
        val = val.get("value", "")
    if not val:
        return None
    return str(val)


async def _active_grants_for_record(
    db: AsyncSession,
    table: str,
    record_sys_id: str,
    user_sys_id: str,
    group_ids: set[str],
) -> list[str]:
    now = _now()
    conditions = [
        RecordAccessGrant.table_name == table,
        RecordAccessGrant.record_sys_id == record_sys_id,
        or_(
            RecordAccessGrant.expires_at.is_(None),
            RecordAccessGrant.expires_at > now,
        ),
    ]
    grantee = or_(
        RecordAccessGrant.user_sys_id == user_sys_id,
        RecordAccessGrant.group_sys_id.in_(group_ids) if group_ids else False,
    )
    result = await db.execute(
        select(RecordAccessGrant.access_level).where(and_(*conditions, grantee))
    )
    return list(result.scalars().all())


async def resolve_record_permissions(
    db: AsyncSession,
    auth: AuthContext,
    table: str,
    record: dict[str, Any] | Any,
) -> RecordPermissions:
    if table not in RBAC_RECORD_TABLES:
        return RecordPermissions(read=True, write=True, comment=True, delete=True)

    record_dict = _record_from_dict(record)
    user_sys_id = auth.user_sys_id
    perms = await get_user_permissions(db, user_sys_id)
    group_ids = await get_user_group_ids(db, user_sys_id)

    if has_permission(perms, "records.*.write"):
        return RecordPermissions(read=True, write=True, comment=True, delete=True)
    if has_permission(perms, "records.*.read"):
        base = RecordPermissions(read=True, write=False, comment=False, delete=False)
    else:
        base = RecordPermissions()

    owner = _ref_value(record_dict, "owner")
    owner_group = _ref_value(record_dict, "owner_group")

    if owner == user_sys_id or (owner_group and owner_group in group_ids):
        return RecordPermissions(read=True, write=True, comment=True, delete=True)

    assigned_to = _ref_value(record_dict, "assigned_to")
    if assigned_to == user_sys_id:
        base.read = True
        base.write = True
        base.comment = True

    grants = await _active_grants_for_record(
        db, table, record_dict.get("sys_id", ""), user_sys_id, group_ids
    )
    if "comment" in grants:
        base.read = True
        base.comment = True
    elif "view" in grants:
        base.read = True

    return base


async def assert_record_action(
    db: AsyncSession,
    auth: AuthContext,
    table: str,
    record: dict[str, Any] | Any,
    action: RecordAction,
) -> RecordPermissions:
    resolved = await resolve_record_permissions(db, auth, table, record)
    allowed = {
        "read": resolved.read,
        "write": resolved.write,
        "comment": resolved.comment or resolved.write,
        "delete": resolved.delete,
    }
    if not allowed.get(action, False):
        if action == "read":
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Record not found")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
    return resolved


async def assert_record_action_by_id(
    db: AsyncSession,
    auth: AuthContext,
    table: str,
    sys_id: str,
    action: RecordAction,
) -> RecordPermissions:
    model = TABLE_MODELS.get(table)
    if not model:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Record not found")
    record = await db.get(model, sys_id)
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Record not found")
    return await assert_record_action(db, auth, table, record, action)



async def filter_record_list_query(
    db: AsyncSession, auth: AuthContext, table: str, query, model
):
    if table not in RBAC_RECORD_TABLES:
        return query

    perms = await get_user_permissions(db, auth.user_sys_id)
    if has_permission(perms, "records.*.read"):
        return query

    group_ids = await get_user_group_ids(db, auth.user_sys_id)
    now = _now()

    grant_exists = exists(
        select(RecordAccessGrant.sys_id).where(
            and_(
                RecordAccessGrant.table_name == table,
                RecordAccessGrant.record_sys_id == model.sys_id,
                or_(
                    RecordAccessGrant.expires_at.is_(None),
                    RecordAccessGrant.expires_at > now,
                ),
                or_(
                    RecordAccessGrant.user_sys_id == auth.user_sys_id,
                    RecordAccessGrant.group_sys_id.in_(group_ids) if group_ids else False,
                ),
            )
        )
    )

    conditions = [model.owner == auth.user_sys_id, grant_exists]
    if group_ids:
        conditions.append(model.owner_group.in_(group_ids))

    return query.where(or_(*conditions))


async def assert_platform_action(
    db: AsyncSession,
    auth: AuthContext,
    table: str,
    action: PlatformAction,
    *,
    record: dict[str, Any] | Any | None = None,
    target_user_sys_id: str | None = None,
) -> None:
    if table not in PLATFORM_TABLES:
        return

    perms = await get_user_permissions(db, auth.user_sys_id)
    mapping = PLATFORM_TABLES[table]
    required = mapping.get(action)
    if not required:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")

    if action == "self_write" and target_user_sys_id == auth.user_sys_id:
        if has_permission(perms, mapping["self_write"]) or has_permission(perms, mapping["write"]):
            return
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")

    if action == "write" and table == "sys_user" and target_user_sys_id == auth.user_sys_id:
        if has_permission(perms, mapping["self_write"]) or has_permission(perms, mapping["write"]):
            return

    if action in ("write", "manage") and table == "sys_user_grmember" and record is not None:
        record_dict = _record_from_dict(record)
        group_sys_id = _ref_value(record_dict, "group_sys_id")
        if group_sys_id and await is_group_owner(db, auth.user_sys_id, group_sys_id):
            return

    if action == "manage" and table == "sys_user_group" and record is not None:
        record_dict = _record_from_dict(record)
        group_sys_id = record_dict.get("sys_id")
        if group_sys_id and await is_group_owner(db, auth.user_sys_id, str(group_sys_id)):
            return

    if has_permission(perms, required):
        return

    if action == "read":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Record not found")
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")


async def assert_can_create_record(
    db: AsyncSession,
    auth: AuthContext,
    table: str,
) -> None:
    if table in RBAC_RECORD_TABLES:
        return

    if table in PLATFORM_TABLES:
        await assert_platform_action(db, auth, table, "write")


async def can_read_table(db: AsyncSession, auth: AuthContext, table: str) -> bool:
    """Return True if the user may list/reference the given table."""
    perms = await get_user_permissions(db, auth.user_sys_id)
    if has_permission(perms, "records.*.read") or has_permission(perms, "records.*.write"):
        return True
    if table in RBAC_RECORD_TABLES:
        return False
    if table in PLATFORM_TABLES:
        required = PLATFORM_TABLES[table].get("read")
        return required is not None and has_permission(perms, required)
    return True


async def assert_grant_management(
    db: AsyncSession,
    auth: AuthContext,
    table: str,
    record_sys_id: str,
) -> None:
    await assert_record_action_by_id(db, auth, table, record_sys_id, "write")
