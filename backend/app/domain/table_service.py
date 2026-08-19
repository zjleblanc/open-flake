import json
from collections.abc import Sequence
from typing import Any

from sqlalchemy import Boolean, func, select
from sqlalchemy import delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.flake.attachment import (
    _assert_attachment_parent_access,
    delete_attachments_for_parent,
    remove_attachment,
)
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
    DISPLAY_FIELD_BY_TABLE,
    NUMBER_PREFIXES,
    PLATFORM_TABLES,
    POLYMORPHIC_CHILDREN,
    RBAC_RECORD_TABLES,
    REFERENCE_FIELDS,
    REVERSE_REFERENCE_MAP,
    TABLE_MODELS,
    ref_table,
    resolve_table_name,
)
from app.events.bus import RecordEvent, emit
from app.models import NumberSequence, RecordAccessGrant, SysAudit, SysComment, SysUser
from app.query.parser import QueryCondition, apply_condition_groups
from app.utils.ids import new_sys_id

settings = get_settings()

_POLYMORPHIC_CHILD_MODELS: dict[str, Any] = {
    "sys_comment": SysComment,
    "sys_audit": SysAudit,
    "record_access_grant": RecordAccessGrant,
}


def _apply_conditions(query, model, conditions: list[QueryCondition]):
    return apply_condition_groups(query, model, conditions)


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
        if col.name == "attributes" and table == "cmdb_ci":
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
        elif isinstance(val, dict | list):
            data[col.name] = val
        else:
            data[col.name] = str(val)

    if exclude_links:
        for field in refs:
            if data.get(field):
                sys_id = data[field]
                data[field] = {
                    "link": f"{settings.base_url}/api/flake/table/{ref_table(field, table)}/{sys_id}",
                    "value": sys_id,
                }
    return data


async def _resolve_display_labels(
    db: AsyncSession,
    ids_by_target_table: dict[str, set[str]],
) -> dict[str, dict[str, str]]:
    """Batch-resolve `sys_id -> display label` per target table.

    Shared by `attach_reference_display_values` and
    `attach_activity_change_display_values`: both collect the sys_ids they need
    resolved (from record fields or audit change values, respectively) into the
    same `{target_table: {sys_id, ...}}` shape, then call this once to issue a
    single batched query per referenced table instead of one per sys_id.
    """
    labels_by_target_table: dict[str, dict[str, str]] = {}
    for target_table, ids in ids_by_target_table.items():
        if not ids:
            continue
        model = TABLE_MODELS.get(target_table)
        display_field = DISPLAY_FIELD_BY_TABLE.get(target_table)
        if model is None or display_field is None:
            continue
        column = getattr(model, display_field, None)
        if column is None:
            continue
        result = await db.execute(select(model.sys_id, column).where(model.sys_id.in_(ids)))
        labels_by_target_table[target_table] = {row[0]: (row[1] or row[0]) for row in result.all()}
    return labels_by_target_table


async def attach_reference_display_values(
    db: AsyncSession,
    table: str,
    records: list[dict[str, Any]],
) -> None:
    """Populate a `<field>_display_value` key for each populated reference field.

    Frontend views resolve a reference's sys_id to a human-readable label (e.g. a
    user's `user_name` or a group's `name`) using this field instead of showing the
    raw sys_id. Lookups are batched per referenced table to avoid N+1 queries.

    When a reference's target row no longer exists (e.g. the referenced record
    was deleted without clearing this loose reference), the display value
    becomes the `[Deleted]` sentinel and `<field>_deleted` is set so the
    frontend can render a dangling-reference indicator instead of a link.
    """
    refs = REFERENCE_FIELDS.get(table, set())
    if not refs or not records:
        return

    field_target_table: dict[str, str] = {}
    ids_by_target_table: dict[str, set[str]] = {}
    for field in refs:
        target_table = ref_table(field, table)
        if target_table not in DISPLAY_FIELD_BY_TABLE:
            continue
        field_target_table[field] = target_table
        ids = ids_by_target_table.setdefault(target_table, set())
        for record in records:
            value = record.get(field)
            sys_id = value.get("value") if isinstance(value, dict) else value
            if sys_id:
                ids.add(sys_id)

    labels_by_target_table = await _resolve_display_labels(db, ids_by_target_table)

    for field, target_table in field_target_table.items():
        labels = labels_by_target_table.get(target_table, {})
        for record in records:
            value = record.get(field)
            sys_id = value.get("value") if isinstance(value, dict) else value
            if not sys_id:
                continue
            if sys_id in labels:
                record[f"{field}_display_value"] = labels[sys_id]
            else:
                record[f"{field}_display_value"] = "[Deleted]"
                record[f"{field}_deleted"] = True


async def attach_activity_change_display_values(
    db: AsyncSession,
    table: str,
    activity: list[dict[str, Any]],
) -> None:
    """Populate `old_display_value`/`new_display_value` on audit changes.

    Field-history entries in the activity feed store raw `old_value`/`new_value`
    strings from `sys_audit`, which for a reference field is a sys_id -- not
    something a user can recognize. This mirrors `attach_reference_display_values`
    but resolves values embedded in audit change rows instead of top-level record
    fields, batching lookups per referenced table across every change in the feed.
    """
    refs = REFERENCE_FIELDS.get(table, set())
    if not refs:
        return

    field_target_table: dict[str, str] = {}
    ids_by_target_table: dict[str, set[str]] = {}
    changes: list[dict[str, Any]] = []
    for entry in activity:
        for change in entry.get("changes") or []:
            field = change.get("field")
            if field not in refs:
                continue
            changes.append(change)
            target_table = field_target_table.get(field)
            if target_table is None:
                target_table = ref_table(field, table)
                if target_table not in DISPLAY_FIELD_BY_TABLE:
                    continue
                field_target_table[field] = target_table
            ids = ids_by_target_table.setdefault(target_table, set())
            for key in ("old_value", "new_value"):
                sys_id = change.get(key)
                if sys_id:
                    ids.add(sys_id)

    if not field_target_table:
        return

    labels_by_target_table = await _resolve_display_labels(db, ids_by_target_table)

    for change in changes:
        field = change.get("field")
        target_table = field_target_table.get(field) if isinstance(field, str) else None
        if target_table is None:
            continue
        labels = labels_by_target_table.get(target_table, {})
        for key, display_key in (
            ("old_value", "old_display_value"),
            ("new_value", "new_display_value"),
        ):
            sys_id = change.get(key)
            if not sys_id:
                continue
            change[display_key] = labels.get(sys_id, "[Deleted]")


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
            col = TABLE_MODELS[table].__table__.columns.get(key)
            if col is not None and isinstance(col.type, Boolean):
                if isinstance(value, str):
                    value = value.strip().lower() in {"true", "1", "yes"}
                else:
                    value = bool(value)
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
    records: Sequence[Any],
) -> list[Any]:
    if table not in PLATFORM_TABLES:
        return list(records)
    filtered = []
    for record in records:
        try:
            await assert_platform_action(db, auth, table, "read", record=record)
            filtered.append(record)
        except Exception:  # noqa: S112 — skip unauthorized records during list filtering
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


def _resolve_subclass_table(table: str, query_class: str | None) -> tuple[str, str | None]:
    """Resolve a CMDB subclass table name (e.g. `cmdb_ci_server`) to its
    physical storage table plus a class filter, so callers that pass a
    subclass name directly (e.g. a catalog variable's `reference_table`)
    behave the same as going through the `table.py` API route, which
    already resolves subclass names before calling into this module."""
    if query_class is not None:
        return table, query_class
    resolved = resolve_table_name(table)
    return resolved if resolved else (table, None)


async def list_records(
    db: AsyncSession,
    table: str,
    conditions: list[QueryCondition],
    limit: int = 1000,
    offset: int = 0,
    exclude_links: bool = True,
    auth: AuthContext | None = None,
    include_permissions: bool = False,
    query_class: str | None = None,
) -> tuple[list[dict], int]:
    table, query_class = _resolve_subclass_table(table, query_class)
    if table == "cmdb_ci":
        from app.domain.cmdb.ci_service import list_cmdb_ci

        cmdb_records, total = await list_cmdb_ci(
            db,
            conditions,
            limit,
            offset,
            exclude_links,
            auth=auth,
            include_permissions=include_permissions,
            query_class=query_class,
        )
        await attach_reference_display_values(db, table, cmdb_records)
        return cmdb_records, total

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
        out.append(
            await _enrich_with_permissions(db, auth, table, record_dict, include_permissions)
        )
    await attach_reference_display_values(db, table, out)
    return out, total


async def get_record_by_sys_id(
    db: AsyncSession,
    table: str,
    sys_id: str,
    exclude_links: bool = True,
    auth: AuthContext | None = None,
    include_permissions: bool = False,
    skip_auth: bool = False,
    query_class: str | None = None,
) -> dict | None:
    table, query_class = _resolve_subclass_table(table, query_class)
    if table == "cmdb_ci":
        from app.domain.cmdb.ci_service import get_cmdb_ci

        record = await get_cmdb_ci(
            db,
            sys_id,
            exclude_links,
            auth=auth,
            include_permissions=include_permissions,
            skip_auth=skip_auth,
            query_class=query_class,
        )
        if record:
            await attach_reference_display_values(db, table, [record])
        return record

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
        elif table == "record_access_grant" or table == "sys_comment":
            parent_table = getattr(record, "table_name", None)
            parent_id = getattr(record, "record_sys_id", None)
            if parent_table and parent_id:
                parent_model = TABLE_MODELS.get(parent_table)
                if parent_model:
                    parent = await db.get(parent_model, parent_id)
                    if parent:
                        await assert_record_action(db, auth, parent_table, parent, "read")

    record_dict = _model_to_dict(record, table, exclude_links)
    result = await _enrich_with_permissions(db, auth, table, record_dict, include_permissions)
    await attach_reference_display_values(db, table, [result])
    return result


def _audit_stringify(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    if isinstance(value, dict | list):
        return json.dumps(value)
    return str(value)


async def _record_field_audit(
    db: AsyncSession,
    table: str,
    sys_id: str,
    changes: list[tuple[str, Any, Any]],
    username: str | None,
) -> None:
    """Insert one `SysAudit` row per changed field, all sharing a `batch_id` so the
    activity feed can group every field touched by a single update call together."""
    if not changes:
        return
    batch_id = new_sys_id()
    for field_name, old_value, new_value in changes:
        db.add(
            SysAudit(
                sys_id=new_sys_id(),
                table_name=table,
                record_sys_id=sys_id,
                batch_id=batch_id,
                field_name=field_name,
                old_value=_audit_stringify(old_value),
                new_value=_audit_stringify(new_value),
                user=username,
            )
        )
    await db.flush()


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


async def create_record(
    db: AsyncSession,
    table: str,
    payload: dict[str, Any],
    user_sys_id: str | None = None,
    exclude_links: bool = True,
    auth: AuthContext | None = None,
    class_name: str | None = None,
) -> dict:
    table, class_name = _resolve_subclass_table(table, class_name)
    if table == "cmdb_ci":
        from app.domain.cmdb.ci_service import create_cmdb_ci

        return await create_cmdb_ci(
            db,
            payload,
            class_name=class_name or payload.get("sys_class_name"),
            user_sys_id=user_sys_id,
            exclude_links=exclude_links,
            auth=auth,
        )

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
    flat.pop("sys_mod_count", None)
    audit_username = await _resolve_audit_username(db, user_sys_id, auth)
    if audit_username:
        flat["sys_created_by"] = audit_username
        flat["sys_updated_by"] = audit_username

    if table in RBAC_RECORD_TABLES and user_sys_id and not flat.get("owner"):
        flat["owner"] = user_sys_id

    if table == "record_access_grant" and user_sys_id:
        flat.setdefault("granted_by", user_sys_id)

    column_names = {c.name for c in model.__table__.columns}
    number = await next_number(db, table)
    if number and "number" in column_names:
        flat.setdefault("number", number)
    if "task_effective_number" in column_names:
        flat.setdefault("task_effective_number", flat.get("number"))

    if "other" in flat and isinstance(flat["other"], dict):
        other = flat.pop("other")
    else:
        other = {}

    record = model(**{k: v for k, v in flat.items() if k in column_names})
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
    query_class: str | None = None,
) -> dict | None:
    table, query_class = _resolve_subclass_table(table, query_class)
    if table == "cmdb_ci":
        from app.domain.cmdb.ci_service import update_cmdb_ci

        return await update_cmdb_ci(
            db,
            sys_id,
            payload,
            user_sys_id=user_sys_id,
            exclude_links=exclude_links,
            auth=auth,
            query_class=query_class,
        )

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
                await assert_platform_action(db, auth, table, "write", target_user_sys_id=sys_id)
        elif table == "sys_user_group":
            await assert_platform_action(db, auth, table, "manage", record=record)
        elif table == "sys_user_grmember" or table in PLATFORM_TABLES:
            await assert_platform_action(db, auth, table, "write", record=record)

    flat = _flatten_payload(payload, table)
    if table == "sys_user" and flat.get("user_password"):
        pwd = flat["user_password"]
        if not pwd.startswith("$2"):
            flat["user_password"] = hash_password(pwd)
    flat.pop("sys_id", None)
    flat.pop("sys_mod_count", None)
    audit_username = await _resolve_audit_username(db, user_sys_id, auth)
    if audit_username:
        flat["sys_updated_by"] = audit_username

    track_audit = table in RBAC_RECORD_TABLES
    changes: list[tuple[str, Any, Any]] = []

    other_update = flat.pop("other", None)
    for key, value in flat.items():
        if hasattr(record, key):
            if track_audit and key not in {"sys_updated_by", "sys_mod_count"}:
                old_value = getattr(record, key)
                if old_value != value:
                    changes.append((key, old_value, value))
            setattr(record, key, value)
    if other_update and hasattr(record, "other"):
        current = dict(record.other or {})
        if track_audit:
            for key, value in other_update.items():
                old_value = current.get(key)
                if old_value != value:
                    changes.append((key, old_value, value))
        current.update(other_update)
        record.other = current
    if hasattr(record, "sys_mod_count"):
        record.sys_mod_count = (record.sys_mod_count or 0) + 1

    await db.flush()
    if track_audit:
        await _record_field_audit(db, table, sys_id, changes, audit_username)
    result = _model_to_dict(record, table, exclude_links)
    await emit(RecordEvent(action="update", table=table, sys_id=sys_id, record=result))
    return result


async def _delete_polymorphic_children(db: AsyncSession, table: str, sys_id: str) -> None:
    """Delete a record's own rows in tables keyed by a `(table_name,
    record_sys_id)` pair rather than a real foreign key -- comments, audit
    history, and access grants. These can't cascade via the database."""
    for child_table in POLYMORPHIC_CHILDREN:
        model = _POLYMORPHIC_CHILD_MODELS[child_table]
        await db.execute(
            sa_delete(model).where(model.table_name == table, model.record_sys_id == sys_id)
        )


async def clear_loose_references(
    db: AsyncSession,
    table: str,
    sys_id: str,
    username: str | None,
    auth: AuthContext | None = None,
) -> None:
    """Null every loose-reference field that points to this record, writing a
    `sys_audit` entry for each cleared field so the change shows up as an
    old-value -> new-value entry in the referencing record's activity stream.

    A reference column that is NOT NULL can't be left dangling by nulling it,
    so rows with a required reference to this record are deleted instead.
    """
    for ref_table_name, ref_col in REVERSE_REFERENCE_MAP.get(table, []):
        model = TABLE_MODELS.get(ref_table_name)
        if model is None:
            continue
        column = getattr(model, ref_col, None)
        if column is None:
            continue
        rows = (await db.execute(select(model).where(column == sys_id))).scalars().all()
        if not rows:
            continue
        col_def = model.__table__.columns.get(ref_col)
        nullable = bool(col_def is not None and col_def.nullable)
        for row in rows:
            if nullable:
                old_value = getattr(row, ref_col)
                setattr(row, ref_col, None)
                await _record_field_audit(
                    db, ref_table_name, row.sys_id, [(ref_col, old_value, None)], username
                )
            else:
                await delete_record(db, ref_table_name, row.sys_id, auth=auth)
    await db.flush()


async def cascade_loose_references(
    db: AsyncSession,
    table: str,
    sys_id: str,
    auth: AuthContext | None = None,
) -> None:
    """Delete every record that loosely references this record."""
    for ref_table_name, ref_col in REVERSE_REFERENCE_MAP.get(table, []):
        model = TABLE_MODELS.get(ref_table_name)
        if model is None:
            continue
        column = getattr(model, ref_col, None)
        if column is None:
            continue
        rows = (await db.execute(select(model).where(column == sys_id))).scalars().all()
        for row in rows:
            await delete_record(db, ref_table_name, row.sys_id, auth=auth)


async def delete_record(
    db: AsyncSession,
    table: str,
    sys_id: str,
    auth: AuthContext | None = None,
    query_class: str | None = None,
    ref_mode: str | None = None,
) -> bool:
    table, query_class = _resolve_subclass_table(table, query_class)
    if table == "cmdb_ci":
        from app.domain.cmdb.ci_service import delete_cmdb_ci

        return await delete_cmdb_ci(
            db, sys_id, auth=auth, query_class=query_class, ref_mode=ref_mode
        )

    model = TABLE_MODELS[table]
    record = await db.get(model, sys_id)
    if not record:
        return False

    if auth:
        if table in RBAC_RECORD_TABLES:
            await assert_record_action(db, auth, table, record, "delete")
        elif table == "sys_user":
            await assert_platform_action(db, auth, table, "write", target_user_sys_id=sys_id)
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
        elif table == "sys_secret":
            await assert_platform_action(db, auth, table, "manage", record=record)
        elif table == "sys_attachment":
            await _assert_attachment_parent_access(
                db,
                auth,
                record.table_name,
                record.table_sys_id,
                "write",
            )
        elif table in PLATFORM_TABLES:
            await assert_platform_action(db, auth, table, "write", record=record)

    if table == "sys_attachment":
        result = _model_to_dict(record, table, exclude_links=False)
        await remove_attachment(db, record)
        await emit(RecordEvent(action="delete", table=table, sys_id=sys_id, record=result))
        return True

    username = auth.user_name if auth else None
    if ref_mode == "clear":
        await clear_loose_references(db, table, sys_id, username, auth=auth)
    elif ref_mode == "cascade":
        await cascade_loose_references(db, table, sys_id, auth=auth)

    result = _model_to_dict(record, table, exclude_links=False)
    await _delete_polymorphic_children(db, table, sys_id)
    await delete_attachments_for_parent(db, table, sys_id)
    await db.delete(record)
    await db.flush()
    await emit(RecordEvent(action="delete", table=table, sys_id=sys_id, record=result))
    return True
