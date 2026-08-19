#!/usr/bin/env python3
"""Regenerate `backend/app/domain/cmdb/base_hierarchy_data.py` from the
human-edited spec at `backend/tools/cmdb_base_hierarchy.yaml`.

Maintainer-only, dev-time tooling: `backend/tools/` is never copied by
`deploy/Containerfile.backend` and is outside `pyproject.toml`'s package
discovery (`include = ["app*"]`), so neither this script nor the YAML spec
ships in the production image -- only the generated Python module does.

Usage (from the repo root or `backend/`):
    python backend/tools/generate_base_hierarchy.py

Then run `ruff format` on the output (the Makefile target does this for you):
    make generate-cmdb-hierarchy
"""

from __future__ import annotations

import pprint
import sys
from pathlib import Path
from typing import Any

import yaml

TOOLS_DIR = Path(__file__).resolve().parent
SPEC_PATH = TOOLS_DIR / "cmdb_base_hierarchy.yaml"
OUTPUT_PATH = TOOLS_DIR.parent / "app" / "domain" / "cmdb" / "base_hierarchy_data.py"

HEADER = '''"""Default CMDB class hierarchy, shipped with every backend image.

GENERATED FILE -- DO NOT EDIT BY HAND.

Source of truth: `backend/tools/cmdb_base_hierarchy.yaml`.
Regenerate with: `make generate-cmdb-hierarchy`
(or: `python backend/tools/generate_base_hierarchy.py` then `ruff format` it).

Each entry has the same shape as a `docs/class-hierarchy/*.json` export
(`target_table` / `inheritance_path` / `fields`, plus an optional `label`
for the target class itself) that
`app.domain.cmdb.importer._import_export()` already knows how to consume --
this module just supplies them as a Python literal instead of files read off
disk, so the base hierarchy needs no data files shipped in the image.
"""

from __future__ import annotations

from typing import Any

'''


def _walk(name: str, node: dict[str, Any], ancestors: list[str]) -> list[dict[str, Any]]:
    inheritance_path = [*ancestors, name]
    fields = [
        {
            "name": field["name"],
            "label": field.get("label") or field["name"],
            "type": field.get("type", "string"),
            "source_table": name,
        }
        for field in node.get("fields") or []
    ]
    exports = [
        {
            "target_table": name,
            "inheritance_path": inheritance_path,
            "label": node.get("label") or name,
            "fields": fields,
        }
    ]
    for child_name, child_node in (node.get("children") or {}).items():
        exports.extend(_walk(child_name, child_node or {}, inheritance_path))
    return exports


def build_exports(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Expand the nested YAML spec into a flat list of hierarchy exports.

    Every node (leaf or intermediate) gets its own export entry so
    `_import_export()` registers it directly; re-registering shared
    ancestors across sibling exports is a harmless no-op (`ensure_class` is
    idempotent).
    """
    seen: set[str] = set()
    exports: list[dict[str, Any]] = []
    for name, node in spec.items():
        for export in _walk(name, node or {}, ["cmdb", "cmdb_ci"]):
            target = export["target_table"]
            if target in seen:
                raise ValueError(f"Duplicate class name in spec: '{target}'")
            seen.add(target)
            exports.append(export)
    return exports


def render_module(exports: list[dict[str, Any]]) -> str:
    body = pprint.pformat(exports, width=99, sort_dicts=False)
    return f"{HEADER}BASE_HIERARCHY: list[dict[str, Any]] = {body}\n"


def generate() -> str:
    """Return the generated module source (used by the drift-check test too)."""
    spec = yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))
    exports = build_exports(spec)
    return render_module(exports)


def main() -> int:
    module_source = generate()
    OUTPUT_PATH.write_text(module_source, encoding="utf-8")
    exports = yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))
    count = len(build_exports(exports))
    print(f"Wrote {count} class definitions to {OUTPUT_PATH}")
    print("Run `ruff format` on the output file to match project style.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
