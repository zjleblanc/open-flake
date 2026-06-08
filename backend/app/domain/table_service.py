from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import AuthContext
from app.auth.rbac import (
    assert_can_create_record,
    assert_platform_action,
    assert_record_action,
    filter_record_list_query,
    resolve_record_permissions,
)
from app.config import get_settings
from app.domain.errors import validate_other_field_keys
from app.domain.registry import (
    NUMBER_PREFIXES,
    PLATFORM_TABLES,
    RBAC_RECORD_TABLES,
    REFERENCE_FIELDS,
    TABLE_MODELS,
)
from app.api.flake.attachment import delete_attachments_for_parent
from app.events.bus import RecordEvent, emit
from app.models import NumberSequence
from app.query.parser import QueryCondition
from app.utils.ids import new_sys_id

settings = get_settings()


def _model_to_dict(record: Any, table: str, exclude_links: bool = True) -> dict[str, Any]:
    data: dict[str, Any] = {}
    refs = REFERENCE_FIELDS.get(table, set())
    for col in record.__table__.columns:
        val = getattr(record, col.name)
        if col.name == "user_password":
            continue
        if col.name == "other":
            if isinstance(val, dict):
                data.update(val)
            continue
        if col.name == "key_hash":
            continue
        if col.name == "storage_path":
            continue
        if val is None:
            data[col.name] = ""
        elif hasattr(val, "isoformat"):
            data[col.name] = val.isoformat()
        elif isinstance(val, bool):
            data[col.name] = "true" if val else "false"
        else:
            data[col.name] = str(val)

    if exclude_links:
        for field in refs:
            if field in data and data[field]:
                sys_id = data[field]
                data[field] = {
                    "link": f"{settings.base_url}/api/flake/table/{_ref_table(field)}/{sys_id}",
                    "value": sys_id,
                }
    return data


def _ref_table(field: str) -> str:
    mapping = {
        "caller_id": "sys_user",
        "assigned_to": "sys_user",
        "requested_by": "sys_user",
        "requested_for": "sys_user",
        "assignment_group": "sys_user_group",
        "owner": "sys_user",
        "owner_group": "sys_user_group",
        "granted_by": "sys_user",
        "change_request": "change_request",
        "problem": "problem",
        "request": "sc_request",
        "cmdb_ci": "cmdb_ci",
        "duplicate_of": "problem",
        "std_change_producer_version": "std_change_producer_version",
        "user_sys_id": "sys_user",
        "group_sys_id": "sys_user_group",
        "parent": "cmdb_ci",
        "child": "cmdb_ci",
        "type": "cmdb_rel_type",
    }
    return mapping.get(field, "sys_user")


def _flatten_payload(payload: dict[str, Any], table: str) -> dict[str, Any]:
    known_cols = {c.name for c in TABLE_MODELS[table].__table__.columns}
    result: dict[str, Any] = {}
    other: dict[str, Any] = {}
    refs = REFERENCE_FIELDS.get(table, set())

    for key, value in payload.items():
        if isinstance(value, dict) and "value" in value:
            value = value["value"]
        if key == "other" and isinstance(value, dict):
            other.update(value)
            continue
        if key in known_cols and key != "other":
            result[key] = value
        elif key not in known_cols:
            other[key] = value

    if other:
        validate_other_field_keys(other)
        result["other"] = other

    for field in refs:
        if field in payload:
            val = payload[field]
            if isinstance(val, dict) and "value" in val:
                result[field] = val["value"]
            else:
                result[field] = val

    return result


async def _enrich_with_permissions(
    db: AsyncSession,
    auth: AuthContext | None,
    table: str,
    record_dict: dict[str, Any],
    include_permissions: bool,
) -> dict[str, Any]:
    if include_permissions and auth and table in RBAC_RECORD_TABLES:
        perms = await resolve_record_permissions(db, auth, table, record_dict)
        record_dict["_permissions"] = perms.to_dict()
    return record_dict


async def _filter_platform_list(
    db: AsyncSession,
    auth: AuthContext,
    table: str,
    records: list[Any],
) -> list[Any]:
    if table not in PLATFORM_TABLES:
        return records
    filtered = []
    for record in records:
        try:
            await assert_platform_action(db, auth, table, "read", record=record)
            filtered.append(record)
        except Exception:
            continue
    return filtered


async def next_number(db: AsyncSession, table: str) -> str | None:
    prefix = NUMBER_PREFIXES.get(table)
    if not prefix:
        return None
    result = await db.execute(
        select(NumberSequence).where(NumberSequence.prefix == prefix).with_for_update()
    )
    seq = result.scalar_one_or_none()
    if not seq:
        seq = NumberSequence(prefix=prefix, last_value=0)
        db.add(seq)
        await db.flush()
    seq.last_value += 1
    return f"{prefix}{seq.last_value:07d}"


def _apply_conditions(query, model, conditions: list[QueryCondition]):
    for cond in conditions:
        col = getattr(model, cond.field, None)
        if col is None:
            continue
        if cond.operator == "=":
            query = query.where(col == cond.value)
        elif cond.operator == "LIKE":
            query = query.where(col.ilike(f"%{cond.value}%"))
    return query


async def list_records(
    db: AsyncSession,
    table: str,
    conditions: list[QueryCondition],
    limit: int = 1000,
    offset: int = 0,
    exclude_links: bool = True,
    auth: AuthContext | None = None,
    include_permissions: bool = False,
) -> tuple[list[dict], int]:
    model = TABLE_MODELS.get(table)
    if not model:
        return [], 0

    count_q = select(func.count()).select_from(model)
    count_q = _apply_conditions(count_q, model, conditions)
    query = select(model)
    query = _apply_conditions(query, model, conditions)

    if auth:
        if table in RBAC_RECORD_TABLES:
            count_q = await filter_record_list_query(db, auth, table, count_q, model)
            query = await filter_record_list_query(db, auth, table, query, model)
        elif table in PLATFORM_TABLES:
            await assert_platform_action(db, auth, table, "read")

    total = (await db.execute(count_q)).scalar() or 0

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    records = result.scalars().all()

    if auth and table in PLATFORM_TABLES:
        records = await _filter_platform_list(db, auth, table, records)
        total = len(records)

    out = []
    for r in records:
        record_dict = _model_to_dict(r, table, exclude_links)
        out.append(await _enrich_with_permissions(db, auth, table, record_dict, include_permissions))
    return out, total


async def get_record_by_sys_id(
    db: AsyncSession,
    table: str,
    sys_id: str,
    exclude_links: bool = True,
    auth: AuthContext | None = None,
    include_permissions: bool = False,
    skip_auth: bool = False,
) -> dict | None:
    model = TABLE_MODELS.get(table)
    if not model:
        return None
    record = await db.get(model, sys_id)
    if not record:
        return None

    if auth and not skip_auth:
        if table in RBAC_RECORD_TABLES:
            await assert_record_action(db, auth, table, record, "read")
        elif table in PLATFORM_TABLES:
            await assert_platform_action(db, auth, table, "read", record=record)
        elif table == "record_access_grant":
            parent_table = getattr(record, "table_name", None)
            parent_id = getattr(record, "record_sys_id", None)
            if parent_table and parent_id:
                parent_model = TABLE_MODELS.get(parent_table)
                if parent_model:
                    parent = await db.get(parent_model, parent_id)
                    if parent:
                        await assert_record_action(db, auth, parent_table, parent, "read")
        elif table == "sys_comment":
            parent_table = getattr(record, "table_name", None)
            parent_id = getattr(record, "record_sys_id", None)
            if parent_table and parent_id:
                parent_model = TABLE_MODELS.get(parent_table)
                if parent_model:
                    parent = await db.get(parent_model, parent_id)
                    if parent:
                        await assert_record_action(db, auth, parent_table, parent, "read")

    record_dict = _model_to_dict(record, table, exclude_links)
    return await _enrich_with_permissions(db, auth, table, record_dict, include_permissions)


async def create_record(
    db: AsyncSession,
    table: str,
    payload: dict[str, Any],
    user_sys_id: str | None = None,
    exclude_links: bool = True,
    auth: AuthContext | None = None,
) -> dict:
    from app.auth.security import hash_password

    if auth:
        await assert_can_create_record(db, auth, table)
        if table == "record_access_grant":
            parent_table = payload.get("table_name")
            parent_id = payload.get("record_sys_id")
            if isinstance(parent_id, dict):
                parent_id = parent_id.get("value")
            if parent_table and parent_id:
                parent_model = TABLE_MODELS.get(parent_table)
                if parent_model:
                    parent = await db.get(parent_model, parent_id)
                    if parent:
                        await assert_record_action(db, auth, parent_table, parent, "write")
        elif table == "sys_comment":
            parent_table = payload.get("table_name")
            parent_id = payload.get("record_sys_id")
            if isinstance(parent_id, dict):
                parent_id = parent_id.get("value")
            if parent_table and parent_id:
                parent_model = TABLE_MODELS.get(parent_table)
                if parent_model:
                    parent = await db.get(parent_model, parent_id)
                    if parent:
                        await assert_record_action(db, auth, parent_table, parent, "comment")

    model = TABLE_MODELS[table]
    flat = _flatten_payload(payload, table)
    if table == "sys_user" and flat.get("user_password"):
        pwd = flat["user_password"]
        if not pwd.startswith("$2"):
            flat["user_password"] = hash_password(pwd)
    sys_id = flat.pop("sys_id", None) or new_sys_id()
    flat["sys_id"] = sys_id
    if user_sys_id:
        flat["sys_created_by"] = user_sys_id
        flat["sys_updated_by"] = user_sys_id

    if table in RBAC_RECORD_TABLES and user_sys_id and not flat.get("owner"):
        flat["owner"] = user_sys_id

    if table == "record_access_grant" and user_sys_id:
        flat.setdefault("granted_by", user_sys_id)

    number = await next_number(db, table)
    if number and "number" in {c.name for c in model.__table__.columns}:
        flat.setdefault("number", number)

    if "other" in flat and isinstance(flat["other"], dict):
        other = flat.pop("other")
    else:
        other = {}

    record = model(**{k: v for k, v in flat.items() if k in {c.name for c in model.__table__.columns}})
    if hasattr(record, "other"):
        record.other = other
    db.add(record)
    await db.flush()
    result = _model_to_dict(record, table, exclude_links)
    await emit(RecordEvent(action="create", table=table, sys_id=sys_id, record=result))
    return result


async def update_record(
    db: AsyncSession,
    table: str,
    sys_id: str,
    payload: dict[str, Any],
    user_sys_id: str | None = None,
    exclude_links: bool = True,
    auth: AuthContext | None = None,
) -> dict | None:
    from app.auth.security import hash_password

    model = TABLE_MODELS[table]
    record = await db.get(model, sys_id)
    if not record:
        return None

    if auth:
        if table in RBAC_RECORD_TABLES:
            await assert_record_action(db, auth, table, record, "write")
        elif table == "sys_user":
            if sys_id == auth.user_sys_id:
                await assert_platform_action(
                    db, auth, table, "self_write", target_user_sys_id=sys_id
                )
            else:
                await assert_platform_action(
                    db, auth, table, "write", target_user_sys_id=sys_id
                )
        elif table == "sys_user_group":
            await assert_platform_action(db, auth, table, "manage", record=record)
        elif table == "sys_user_grmember":
            await assert_platform_action(db, auth, table, "write", record=record)

    flat = _flatten_payload(payload, table)
    if table == "sys_user" and flat.get("user_password"):
        pwd = flat["user_password"]
        if not pwd.startswith("$2"):
            flat["user_password"] = hash_password(pwd)
    flat.pop("sys_id", None)
    if user_sys_id:
        flat["sys_updated_by"] = user_sys_id

    other_update = flat.pop("other", None)
    for key, value in flat.items():
        if hasattr(record, key):
            setattr(record, key, value)
    if other_update and hasattr(record, "other"):
        current = dict(record.other or {})
        current.update(other_update)
        record.other = current

    await db.flush()
    result = _model_to_dict(record, table, exclude_links)
    await emit(RecordEvent(action="update", table=table, sys_id=sys_id, record=result))
    return result


async def delete_record(
    db: AsyncSession,
    table: str,
    sys_id: str,
    auth: AuthContext | None = None,
) -> bool:
    model = TABLE_MODELS[table]
    record = await db.get(model, sys_id)
    if not record:
        return False

    if auth:
        if table in RBAC_RECORD_TABLES:
            await assert_record_action(db, auth, table, record, "delete")
        elif table == "sys_user":
            await assert_platform_action(
                db, auth, table, "write", target_user_sys_id=sys_id
            )
        elif table == "sys_user_group":
            await assert_platform_action(db, auth, table, "write", record=record)
        elif table == "record_access_grant":
            parent_table = getattr(record, "table_name", None)
            parent_id = getattr(record, "record_sys_id", None)
            if parent_table and parent_id:
                parent_model = TABLE_MODELS.get(parent_table)
                if parent_model:
                    parent = await db.get(parent_model, parent_id)
                    if parent:
                        await assert_record_action(db, auth, parent_table, parent, "write")
        elif table == "sys_user_grmember":
            await assert_platform_action(db, auth, table, "write", record=record)

    result = _model_to_dict(record, table, exclude_links=False)
    await delete_attachments_for_parent(db, table, sys_id)
    await db.delete(record)
    await db.flush()
    await emit(RecordEvent(action="delete", table=table, sys_id=sys_id, record=result))
    return True
