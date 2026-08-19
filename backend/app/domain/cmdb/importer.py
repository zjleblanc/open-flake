"""Seed the CMDB class hierarchy: the built-in base catalog shipped with
every backend image, plus an optional operator-provided "extra" directory of
JSON exports for classes/fields that add to or override the base set.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.domain.cmdb.base_hierarchy_data import BASE_HIERARCHY
from app.domain.cmdb.constants import CMDB_ROOT, LAB_CLASS_PARENTS, LOGICAL_ROOT
from app.domain.cmdb.registry import (
    clear_import_warnings,
    ensure_class,
    refresh_cache,
    register_export_inheritance_path,
    upsert_field,
)

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[4]


def parse_hierarchy_export(raw: str) -> dict:
    text = raw.strip()
    if "---START_JSON_DATA---" in text:
        text = text.split("---START_JSON_DATA---", 1)[1].strip()
    parsed: dict[str, Any] = json.loads(text)
    return parsed


async def _import_export(
    db: AsyncSession,
    export: dict,
    *,
    skip_if_user_defined: bool = False,
) -> None:
    target_table = export["target_table"]
    inheritance_path: list[str] = export["inheritance_path"]
    fields: list[dict] = export.get("fields", [])
    target_label = export.get("label")
    last_index = len(inheritance_path) - 1

    register_export_inheritance_path(target_table, inheritance_path)

    for index, class_name in enumerate(inheritance_path):
        super_class = inheritance_path[index - 1] if index > 0 else None
        is_logical = class_name == LOGICAL_ROOT
        # Only the export's own target class carries a label here; ancestors
        # get theirs from their own dedicated export, so leaving label=None
        # for them avoids resetting an already-set label back to the raw
        # class name every time a descendant is (re-)imported.
        label = target_label if index == last_index else None
        await ensure_class(
            db,
            class_name,
            super_class=super_class,
            label=label,
            is_logical=is_logical,
            update=True,
            skip_if_user_defined=skip_if_user_defined,
        )

    for field in fields:
        defined_on = field.get("source_table") or target_table
        if defined_on == LOGICAL_ROOT:
            defined_on = CMDB_ROOT
        await upsert_field(
            db,
            defined_on,
            field["name"],
            label=field.get("label"),
            sn_type=field.get("type"),
            skip_if_user_defined=skip_if_user_defined,
        )


async def _import_base_hierarchy(db: AsyncSession) -> int:
    """Seed the built-in catalog shipped with every image.

    No filesystem access -- see `base_hierarchy_data.BASE_HIERARCHY`,
    generated from `backend/tools/cmdb_base_hierarchy.yaml` via
    `make generate-cmdb-hierarchy`.
    """
    for export in BASE_HIERARCHY:
        await _import_export(db, export, skip_if_user_defined=True)
    return len(BASE_HIERARCHY)


async def import_hierarchy_from_directory(
    db: AsyncSession,
    directory: Path,
    *,
    skip_if_user_defined: bool = True,
) -> int:
    """Import every `*.json` hierarchy export in `directory`.

    Used for the optional operator-provided extra directory
    (`settings.cmdb_hierarchy_extra_dir`): classes/fields here can add to or
    override the base catalog, but by default (`skip_if_user_defined=True`)
    never silently clobber a table an admin already created via the admin
    UI -- see `registry.ensure_class`/`upsert_field` and
    `registry.get_import_warnings()`.
    """
    count = 0
    if not directory.is_dir():
        logger.warning("CMDB hierarchy directory not found: %s", directory)
        return count
    for json_file in sorted(directory.glob("*.json")):
        export = parse_hierarchy_export(json_file.read_text(encoding="utf-8"))
        await _import_export(db, export, skip_if_user_defined=skip_if_user_defined)
        count += 1
        logger.info("Imported CMDB class hierarchy from %s", json_file.name)
    return count


def resolve_extra_hierarchy_dir(configured: str | None) -> Path | None:
    """Resolve `settings.cmdb_hierarchy_extra_dir` to an absolute path.

    A relative path is resolved against the repo root -- e.g. the local dev
    default `docs/class-hierarchy` keeps working the same way regardless of
    the process's current working directory.
    """
    if not configured:
        return None
    path = Path(configured)
    return path if path.is_absolute() else (REPO_ROOT / path)


async def ensure_cmdb_hierarchy(db: AsyncSession) -> None:
    """Seed the base hierarchy, then the optional extra directory, then
    refresh the registry cache. Idempotent -- safe to call on every startup,
    including across concurrent replicas (see `startup.lifespan`'s advisory
    lock)."""
    clear_import_warnings()

    # Always bootstrap the logical root and `cmdb_ci` itself so the CMDB
    # tree exists (and `cmdb_ci` is registered as extendable) before
    # anything else is registered underneath it.
    await ensure_class(db, LOGICAL_ROOT, super_class=None, label="CMDB", is_logical=True)
    await ensure_class(db, CMDB_ROOT, super_class=LOGICAL_ROOT, label="Configuration Item")

    base_count = await _import_base_hierarchy(db)
    logger.info("Seeded %d built-in CMDB classes", base_count)

    settings = get_settings()
    extra_dir = resolve_extra_hierarchy_dir(settings.cmdb_hierarchy_extra_dir)
    if extra_dir is not None:
        extra_count = await import_hierarchy_from_directory(db, extra_dir)
        if extra_count:
            logger.info(
                "Imported %d extra CMDB hierarchy definitions from %s",
                extra_count,
                extra_dir,
            )

    for class_name, super_class in LAB_CLASS_PARENTS.items():
        await ensure_class(db, class_name, super_class=super_class, label=class_name)

    await db.commit()
    await refresh_cache(db)
