"""Drift check: the committed `base_hierarchy_data.BASE_HIERARCHY` module must
match what `backend/tools/generate_base_hierarchy.py` currently produces from
`backend/tools/cmdb_base_hierarchy.yaml`. Fails if someone edits the YAML (or
hand-edits the generated module) without regenerating.
"""

import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import generate_base_hierarchy  # noqa: E402
import yaml  # noqa: E402
from app.domain.cmdb.base_hierarchy_data import BASE_HIERARCHY  # noqa: E402


def test_base_hierarchy_matches_generator_output():
    spec = yaml.safe_load(generate_base_hierarchy.SPEC_PATH.read_text(encoding="utf-8"))
    fresh_exports = generate_base_hierarchy.build_exports(spec)
    assert fresh_exports == BASE_HIERARCHY, (
        "backend/app/domain/cmdb/base_hierarchy_data.py is out of date with "
        "backend/tools/cmdb_base_hierarchy.yaml -- run `make generate-cmdb-hierarchy` "
        "and commit the regenerated module."
    )


def test_base_hierarchy_has_no_duplicate_class_names():
    names = [export["target_table"] for export in BASE_HIERARCHY]
    assert len(names) == len(set(names))


def test_base_hierarchy_every_class_descends_from_cmdb_ci():
    for export in BASE_HIERARCHY:
        path = export["inheritance_path"]
        assert path[:2] == [
            "cmdb",
            "cmdb_ci",
        ], f"{export['target_table']} does not descend from cmdb_ci: {path}"
        assert path[-1] == export["target_table"]
