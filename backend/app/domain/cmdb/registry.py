"""In-memory cache of the table/class hierarchy loaded from the database.

Backed by `sys_db_object` (class tree) and `sys_dictionary` (field
definitions) — the same platform-wide metadata tables ServiceNow uses for
every table, not a CMDB-only overlay. The CMDB hierarchy is simply the
subtree rooted at `cmdb_ci`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.cmdb.constants import CMDB_ROOT, LOGICAL_ROOT, PROMOTED_COLUMNS
from app.models import SysDbObject, SysDictionary
from app.utils.ids import new_sys_id

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FieldMeta:
    field_name: str
    label: str | None
    sn_type: str | None
    defined_on: str
    storage: str


@dataclass
class _RegistrySnapshot:
    classes: dict[str, SysDbObject]
    fields_by_class: dict[str, list[FieldMeta]]
    children: dict[str, set[str]]


_snapshot: _RegistrySnapshot | None = None
_EXPORT_INHERITANCE_PATHS: dict[str, list[str]] = {}
_IMPORT_WARNINGS: list[dict[str, Any]] = []


def clear_cache() -> None:
    global _snapshot
    _snapshot = None
    _EXPORT_INHERITANCE_PATHS.clear()


def clear_import_warnings() -> None:
    """Reset the collision-warning list at the start of a fresh import pass."""
    _IMPORT_WARNINGS.clear()


def record_import_warning(message: str, *, class_name: str, field_name: str | None = None) -> None:
    logger.warning("%s", message)
    _IMPORT_WARNINGS.append(
        {"message": message, "class_name": class_name, "field_name": field_name}
    )


def get_import_warnings() -> list[dict[str, Any]]:
    """Collisions skipped during the last hierarchy import (base or extra dir)
    because a `user_defined` class/field already existed with that name --
    surfaced by `GET /admin/tables` so admins see what was skipped and why."""
    return list(_IMPORT_WARNINGS)


def register_export_inheritance_path(class_name: str, path: list[str]) -> None:
    """Remember the full path from a hierarchy JSON export."""
    if not class_name or not path:
        return
    existing = _EXPORT_INHERITANCE_PATHS.get(class_name)
    if not existing or len(path) > len(existing):
        _EXPORT_INHERITANCE_PATHS[class_name] = list(path)


def field_storage(field_name: str) -> str:
    return "column" if field_name in PROMOTED_COLUMNS else "attributes"


async def refresh_cache(db: AsyncSession) -> None:
    global _snapshot
    classes_result = await db.execute(select(SysDbObject))
    classes = {row.name: row for row in classes_result.scalars().all()}

    fields_result = await db.execute(select(SysDictionary))
    fields_by_class: dict[str, list[FieldMeta]] = {}
    for row in fields_result.scalars().all():
        fields_by_class.setdefault(row.name, []).append(
            FieldMeta(
                field_name=row.element,
                label=row.column_label,
                sn_type=row.internal_type,
                defined_on=row.name,
                storage=row.storage,
            )
        )

    children: dict[str, set[str]] = {name: set() for name in classes}
    for name, cls in classes.items():
        if cls.super_class:
            children.setdefault(cls.super_class, set()).add(name)

    _snapshot = _RegistrySnapshot(
        classes=classes, fields_by_class=fields_by_class, children=children
    )


def _require_snapshot() -> _RegistrySnapshot:
    if _snapshot is None:
        raise RuntimeError("Table registry not loaded; call refresh_cache first")
    return _snapshot


def is_registered(class_name: str) -> bool:
    if _snapshot is None:
        return False
    return class_name in _snapshot.classes


def is_cmdb_class_name(table: str) -> bool:
    if table == CMDB_ROOT:
        return True
    if not table.startswith("cmdb_ci_"):
        return False
    return table not in {"cmdb_rel_ci", "cmdb_rel_type"}


def get_super_class(class_name: str) -> str | None:
    snap = _require_snapshot()
    cls = snap.classes.get(class_name)
    return cls.super_class if cls else None


def get_ancestors(class_name: str) -> list[str]:
    snap = _require_snapshot()
    chain: list[str] = []
    current: str | None = class_name
    while current:
        chain.append(current)
        cls = snap.classes.get(current)
        current = cls.super_class if cls else None
    chain.reverse()
    return chain


def _is_ordered_subsequence(shorter: list[str], longer: list[str]) -> bool:
    if not shorter:
        return True
    index = 0
    for item in longer:
        if item == shorter[index]:
            index += 1
        if index == len(shorter):
            return True
    return index == len(shorter)


def _pick_longest_compatible_path(paths: list[list[str]]) -> list[str]:
    valid = [path for path in paths if path]
    if not valid:
        return []
    valid.sort(key=len, reverse=True)
    for candidate in valid:
        if all(
            path is candidate
            or _is_ordered_subsequence(path, candidate)
            or _is_ordered_subsequence(candidate, path)
            for path in valid
        ):
            return candidate
    return valid[0]


def resolve_inheritance_path(class_name: str) -> list[str]:
    """Return the most complete known inheritance path for a class."""
    candidates: list[list[str]] = []
    if is_registered(class_name):
        candidates.append(get_ancestors(class_name))
    export_path = _EXPORT_INHERITANCE_PATHS.get(class_name)
    if export_path:
        candidates.append(export_path)
    if candidates:
        return _pick_longest_compatible_path(candidates)
    return fallback_inheritance_path(class_name)


def get_descendants(class_name: str) -> list[str]:
    snap = _require_snapshot()
    result = [class_name]

    def walk(name: str) -> None:
        for child in sorted(snap.children.get(name, ())):
            result.append(child)
            walk(child)

    walk(class_name)
    return result


def get_merged_fields(class_name: str) -> dict[str, FieldMeta]:
    merged: dict[str, FieldMeta] = {}
    for ancestor in get_ancestors(class_name):
        snap = _require_snapshot()
        for field in snap.fields_by_class.get(ancestor, []):
            merged.setdefault(field.field_name, field)
    return merged


def compute_class_path(class_name: str) -> str:
    ancestors = get_ancestors(class_name)
    if not ancestors:
        return f"/{class_name}"
    return "/" + "/".join(ancestors)


def fallback_inheritance_path(class_name: str) -> list[str]:
    """Best-effort ancestry when a class is not in the registry."""
    if not class_name:
        return []
    if class_name == LOGICAL_ROOT:
        return [LOGICAL_ROOT]
    if class_name == CMDB_ROOT:
        return [LOGICAL_ROOT, CMDB_ROOT]
    if class_name.startswith("cmdb_ci_"):
        return [LOGICAL_ROOT, CMDB_ROOT, class_name]
    return [LOGICAL_ROOT, class_name]


def field_origin(class_name: str, field: FieldMeta) -> str:
    return "Native" if field.defined_on == class_name else "Inherited"


async def ensure_class(
    db: AsyncSession,
    class_name: str,
    *,
    super_class: str | None = CMDB_ROOT,
    label: str | None = None,
    is_logical: bool = False,
    is_extendable: bool = True,
    user_defined: bool = False,
    update: bool = False,
    storage_type: str | None = None,
    base_table: str | None = None,
    skip_if_user_defined: bool = False,
) -> SysDbObject:
    """Create (or optionally update) a `sys_db_object` row.

    By default, storage is derived from the class's position in the CMDB
    tree: the logical root and `cmdb_ci` itself are physically stored
    tables, and every other CMDB class is a single-table-inheritance row on
    `cmdb_ci`. Callers registering a plain physical table (see
    `startup._ensure_physical_table_registry`) pass `storage_type="physical"`
    explicitly to opt out of that inference.

    `skip_if_user_defined` is set only by the base/extra hierarchy import
    path (`app.domain.cmdb.importer`): if a class with this name already
    exists and was created via the admin API (`user_defined=True`), the
    import leaves it untouched and records a warning via
    `record_import_warning()` instead of overwriting an admin's own table.
    """
    if storage_type is None:
        if class_name in (LOGICAL_ROOT, CMDB_ROOT):
            storage_type, base_table = "physical", None
        else:
            storage_type, base_table = "sti", CMDB_ROOT

    existing = (
        await db.execute(select(SysDbObject).where(SysDbObject.name == class_name))
    ).scalar_one_or_none()
    if existing:
        if skip_if_user_defined and existing.user_defined:
            record_import_warning(
                f"Skipped hierarchy definition for '{class_name}': a table with this "
                "name already exists and was created via the admin UI.",
                class_name=class_name,
            )
            return cast(SysDbObject, existing)
        if update:
            changed = existing.super_class != super_class or (
                label is not None and existing.label != label
            )
            if changed:
                logger.info(
                    "CMDB hierarchy import updated '%s': super_class %r -> %r, label %r -> %r",
                    class_name,
                    existing.super_class,
                    super_class,
                    existing.label,
                    label,
                )
            if existing.super_class != super_class:
                existing.super_class = super_class
            if label is not None:
                existing.label = label
            if existing.is_logical != is_logical:
                existing.is_logical = is_logical
            await db.flush()
        return cast(SysDbObject, existing)

    if super_class:
        parent = (
            await db.execute(select(SysDbObject).where(SysDbObject.name == super_class))
        ).scalar_one_or_none()
        if not parent:
            if super_class == CMDB_ROOT:
                await ensure_class(
                    db,
                    LOGICAL_ROOT,
                    super_class=None,
                    label=LOGICAL_ROOT,
                    is_logical=True,
                )
                await ensure_class(
                    db,
                    CMDB_ROOT,
                    super_class=LOGICAL_ROOT,
                    label=CMDB_ROOT,
                )
            elif super_class != LOGICAL_ROOT:
                raise ValueError(
                    f"Parent class '{super_class}' must exist before registering '{class_name}'"
                )

    record = SysDbObject(
        sys_id=new_sys_id(),
        name=class_name,
        super_class=super_class,
        label=label or class_name,
        is_logical=is_logical,
        is_extendable=is_extendable,
        storage_type=storage_type,
        base_table=base_table,
        user_defined=user_defined,
    )
    db.add(record)
    await db.flush()
    return record


async def upsert_field(
    db: AsyncSession,
    class_name: str,
    field_name: str,
    *,
    label: str | None,
    sn_type: str | None,
    reference: str | None = None,
    mandatory: bool = False,
    storage: str | None = None,
    user_defined: bool = False,
    skip_if_user_defined: bool = False,
) -> SysDictionary:
    """Create or update a `sys_dictionary` row for a field on a registered class.

    `skip_if_user_defined` is set only by the base/extra hierarchy import
    path: if this exact (class, field) already exists and was created via
    the admin API (`user_defined=True`), the import leaves it untouched and
    records a warning instead of reverting an admin's customization.
    """
    resolved_storage = storage or field_storage(field_name)
    resolved_type = sn_type or "string"
    result = await db.execute(
        select(SysDictionary).where(
            SysDictionary.name == class_name,
            SysDictionary.element == field_name,
        )
    )
    row = result.scalar_one_or_none()
    if row:
        if skip_if_user_defined and row.user_defined:
            record_import_warning(
                f"Skipped field definition for '{field_name}' on '{class_name}': an "
                "admin already customized this field via the admin UI.",
                class_name=class_name,
                field_name=field_name,
            )
            return row
        row.column_label = label
        row.internal_type = resolved_type
        row.storage = resolved_storage
        row.reference = reference
        row.mandatory = mandatory
        # Only ever set True here (by the admin API, whose calls never pass
        # skip_if_user_defined and always pass user_defined=True) -- import
        # paths that reach this line always had user_defined=False already
        # (a True row would have hit the skip branch above), so this can't
        # revert an admin's own flag back to False.
        if user_defined:
            row.user_defined = True
        return row
    row = SysDictionary(
        sys_id=new_sys_id(),
        name=class_name,
        element=field_name,
        column_label=label,
        internal_type=resolved_type,
        storage=resolved_storage,
        reference=reference,
        mandatory=mandatory,
        user_defined=user_defined,
    )
    db.add(row)
    return row
