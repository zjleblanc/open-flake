"""Import CMDB class hierarchy JSON exports into metadata tables."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.cmdb.constants import CMDB_ROOT, LAB_CLASS_PARENTS, LOGICAL_ROOT, PROMOTED_COLUMNS
from app.domain.cmdb.registry import ensure_class, refresh_cache
from app.models import CmdbClassField

logger = logging.getLogger(__name__)

DEFAULT_HIERARCHY_DIR = Path(__file__).resolve().parents[4] / "docs" / "class-hierarchy"


def parse_hierarchy_export(raw: str) -> dict:
    text = raw.strip()
    if "---START_JSON_DATA---" in text:
        text = text.split("---START_JSON_DATA---", 1)[1].strip()
    return json.loads(text)


def _field_storage(field_name: str) -> str:
    return "column" if field_name in PROMOTED_COLUMNS else "attributes"


async def _upsert_field(
    db: AsyncSession,
    class_name: str,
    field_name: str,
    *,
    label: str | None,
    sn_type: str | None,
) -> None:
    result = await db.execute(
        select(CmdbClassField).where(
            CmdbClassField.class_name == class_name,
            CmdbClassField.field_name == field_name,
        )
    )
    row = result.scalar_one_or_none()
    storage = _field_storage(field_name)
    if row:
        row.label = label
        row.sn_type = sn_type
        row.storage = storage
        return
    db.add(
        CmdbClassField(
            class_name=class_name,
            field_name=field_name,
            label=label,
            sn_type=sn_type,
            storage=storage,
        )
    )


async def _import_export(db: AsyncSession, export: dict) -> None:
    target_table = export["target_table"]
    inheritance_path: list[str] = export["inheritance_path"]
    fields: list[dict] = export.get("fields", [])

    for index, class_name in enumerate(inheritance_path):
        super_class = inheritance_path[index - 1] if index > 0 else None
        is_logical = class_name == LOGICAL_ROOT
        await ensure_class(
            db,
            class_name,
            super_class=super_class,
            label=class_name,
            is_logical=is_logical,
            update=True,
        )

    for field in fields:
        defined_on = field.get("source_table") or target_table
        if defined_on == LOGICAL_ROOT:
            defined_on = CMDB_ROOT
        await _upsert_field(
            db,
            defined_on,
            field["name"],
            label=field.get("label"),
            sn_type=field.get("type"),
        )


async def import_hierarchy_from_directory(
    db: AsyncSession,
    directory: Path | None = None,
) -> int:
    path = directory or DEFAULT_HIERARCHY_DIR
    if not path.is_dir():
        logger.warning("CMDB hierarchy directory not found: %s", path)
        return 0

    count = 0
    for json_file in sorted(path.glob("*.json")):
        export = parse_hierarchy_export(json_file.read_text(encoding="utf-8"))
        await _import_export(db, export)
        count += 1
        logger.info("Imported CMDB class hierarchy from %s", json_file.name)

    for class_name, super_class in LAB_CLASS_PARENTS.items():
        await ensure_class(db, class_name, super_class=super_class, label=class_name)

    await db.commit()
    await refresh_cache(db)
    return count


async def ensure_cmdb_hierarchy(db: AsyncSession) -> None:
    """Load hierarchy JSON and refresh registry cache (idempotent)."""
    await import_hierarchy_from_directory(db)
    await refresh_cache(db)
