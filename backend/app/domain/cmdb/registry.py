"""In-memory cache of CMDB class hierarchy loaded from the database."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.cmdb.constants import CMDB_ROOT, LOGICAL_ROOT
from app.models import CmdbClass, CmdbClassField


@dataclass(frozen=True)
class FieldMeta:
    field_name: str
    label: str | None
    sn_type: str | None
    defined_on: str
    storage: str


@dataclass
class _RegistrySnapshot:
    classes: dict[str, CmdbClass]
    fields_by_class: dict[str, list[FieldMeta]]
    children: dict[str, set[str]]


_snapshot: _RegistrySnapshot | None = None


def clear_cache() -> None:
    global _snapshot
    _snapshot = None


async def refresh_cache(db: AsyncSession) -> None:
    global _snapshot
    classes_result = await db.execute(select(CmdbClass))
    classes = {row.name: row for row in classes_result.scalars().all()}

    fields_result = await db.execute(select(CmdbClassField))
    fields_by_class: dict[str, list[FieldMeta]] = {}
    for row in fields_result.scalars().all():
        fields_by_class.setdefault(row.class_name, []).append(
            FieldMeta(
                field_name=row.field_name,
                label=row.label,
                sn_type=row.sn_type,
                defined_on=row.class_name,
                storage=row.storage,
            )
        )

    children: dict[str, set[str]] = {name: set() for name in classes}
    for name, cls in classes.items():
        if cls.super_class:
            children.setdefault(cls.super_class, set()).add(name)

    _snapshot = _RegistrySnapshot(classes=classes, fields_by_class=fields_by_class, children=children)


def _require_snapshot() -> _RegistrySnapshot:
    if _snapshot is None:
        raise RuntimeError("CMDB class registry not loaded; call refresh_cache first")
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
) -> CmdbClass:
    existing = await db.get(CmdbClass, class_name)
    if existing:
        return existing

    if super_class:
        parent = await db.get(CmdbClass, super_class)
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

    record = CmdbClass(
        name=class_name,
        super_class=super_class,
        label=label or class_name,
        is_logical=is_logical,
    )
    db.add(record)
    await db.flush()
    return record
