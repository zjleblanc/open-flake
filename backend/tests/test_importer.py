"""Tests for CMDB hierarchy import: base catalog seeding, extra-dir path
resolution, and per-target label handling.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from app.domain.cmdb.importer import (
    REPO_ROOT,
    _import_export,
    resolve_extra_hierarchy_dir,
)


def test_resolve_extra_hierarchy_dir_none_when_unset():
    assert resolve_extra_hierarchy_dir(None) is None
    assert resolve_extra_hierarchy_dir("") is None


def test_resolve_extra_hierarchy_dir_relative_resolves_against_repo_root():
    resolved = resolve_extra_hierarchy_dir("docs/class-hierarchy")
    assert resolved == REPO_ROOT / "docs" / "class-hierarchy"


def test_resolve_extra_hierarchy_dir_absolute_passthrough():
    absolute = Path("/etc/openflake/class-hierarchy")
    assert resolve_extra_hierarchy_dir(str(absolute)) == absolute


@pytest.mark.asyncio
async def test_import_export_only_labels_the_target_class():
    """Ancestors in the inheritance_path should get label=None (leave their
    own label alone) -- only the export's own target_table gets the export's
    `label`, so re-importing a descendant never resets an ancestor's label
    back to its raw class name."""
    export = {
        "target_table": "cmdb_ci_server",
        "inheritance_path": ["cmdb", "cmdb_ci", "cmdb_ci_hardware", "cmdb_ci_server"],
        "label": "Server",
        "fields": [{"name": "host_name", "label": "Host Name", "type": "string"}],
    }

    db = AsyncMock()
    ensure_mock = AsyncMock()
    upsert_mock = AsyncMock()
    with (
        patch("app.domain.cmdb.importer.ensure_class", new=ensure_mock),
        patch("app.domain.cmdb.importer.upsert_field", new=upsert_mock),
    ):
        await _import_export(db, export, skip_if_user_defined=True)

    target_call = next(c for c in ensure_mock.call_args_list if c.args[1] == "cmdb_ci_server")
    assert target_call.kwargs["label"] == "Server"
    ancestor_calls = [c for c in ensure_mock.call_args_list if c.args[1] != "cmdb_ci_server"]
    assert ancestor_calls
    assert all(c.kwargs["label"] is None for c in ancestor_calls)
    assert all(c.kwargs["skip_if_user_defined"] is True for c in ensure_mock.call_args_list)

    upsert_mock.assert_awaited_once_with(
        db,
        "cmdb_ci_server",
        "host_name",
        label="Host Name",
        sn_type="string",
        skip_if_user_defined=True,
    )


@pytest.mark.asyncio
async def test_import_base_hierarchy_seeds_every_entry():
    from app.domain.cmdb.base_hierarchy_data import BASE_HIERARCHY
    from app.domain.cmdb.importer import _import_base_hierarchy

    import_export_mock = AsyncMock()
    with patch("app.domain.cmdb.importer._import_export", new=import_export_mock):
        count = await _import_base_hierarchy(AsyncMock())

    assert count == len(BASE_HIERARCHY)
    assert import_export_mock.await_count == len(BASE_HIERARCHY)
    for received, export in zip(import_export_mock.call_args_list, BASE_HIERARCHY, strict=True):
        assert received.args[1] is export
        assert received.kwargs["skip_if_user_defined"] is True
