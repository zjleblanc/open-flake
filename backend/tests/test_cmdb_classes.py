from pathlib import Path

import pytest
from app.domain.cmdb.ci_service import class_filter_conditions, record_in_class_subtree
from app.domain.cmdb.constants import CMDB_ROOT
from app.domain.cmdb.importer import parse_hierarchy_export
from app.domain.cmdb.payload import split_payload
from app.domain.cmdb.registry import (
    FieldMeta,
    _RegistrySnapshot,
    compute_class_path,
    fallback_inheritance_path,
    get_descendants,
    get_merged_fields,
)
from app.domain.errors import InvalidFieldNameError
from app.models import CmdbClass

HIERARCHY_DIR = Path(__file__).resolve().parent / "fixtures" / "class-hierarchy"


def _load_snapshot() -> None:
    from app.domain.cmdb import registry

    classes = {
        "cmdb": CmdbClass(name="cmdb", super_class=None, label="cmdb", is_logical=True),
        CMDB_ROOT: CmdbClass(
            name=CMDB_ROOT, super_class="cmdb", label=CMDB_ROOT, is_logical=False
        ),
        "cmdb_ci_hardware": CmdbClass(
            name="cmdb_ci_hardware",
            super_class=CMDB_ROOT,
            label="cmdb_ci_hardware",
            is_logical=False,
        ),
        "cmdb_ci_computer": CmdbClass(
            name="cmdb_ci_computer",
            super_class="cmdb_ci_hardware",
            label="cmdb_ci_computer",
            is_logical=False,
        ),
        "cmdb_ci_server": CmdbClass(
            name="cmdb_ci_server",
            super_class="cmdb_ci_computer",
            label="cmdb_ci_server",
            is_logical=False,
        ),
        "cmdb_ci_linux_server": CmdbClass(
            name="cmdb_ci_linux_server",
            super_class="cmdb_ci_server",
            label="cmdb_ci_linux_server",
            is_logical=False,
        ),
        "cmdb_ci_vm_object": CmdbClass(
            name="cmdb_ci_vm_object",
            super_class=CMDB_ROOT,
            label="cmdb_ci_vm_object",
            is_logical=False,
        ),
        "cmdb_ci_vm_instance": CmdbClass(
            name="cmdb_ci_vm_instance",
            super_class="cmdb_ci_vm_object",
            label="cmdb_ci_vm_instance",
            is_logical=False,
        ),
    }
    children = {
        "cmdb": {CMDB_ROOT},
        CMDB_ROOT: {"cmdb_ci_hardware", "cmdb_ci_vm_object"},
        "cmdb_ci_hardware": {"cmdb_ci_computer"},
        "cmdb_ci_computer": {"cmdb_ci_server"},
        "cmdb_ci_server": {"cmdb_ci_linux_server"},
        "cmdb_ci_vm_object": {"cmdb_ci_vm_instance"},
    }
    fields = {
        "cmdb_ci_linux_server": [
            FieldMeta(
                "kernel_release", "Kernel Release", "string", "cmdb_ci_linux_server", "attributes"
            )
        ],
        CMDB_ROOT: [
            FieldMeta("name", "Name", "string", CMDB_ROOT, "column"),
            FieldMeta("fqdn", "FQDN", "string", CMDB_ROOT, "column"),
        ],
        "cmdb_ci_server": [
            FieldMeta("host_name", "Host name", "string", "cmdb_ci_server", "column"),
        ],
    }
    registry._snapshot = _RegistrySnapshot(
        classes=classes, fields_by_class=fields, children=children
    )


@pytest.fixture(autouse=True)
def snapshot():
    from app.domain.cmdb import registry

    _load_snapshot()
    yield
    registry.clear_cache()


def test_parse_linux_server_export():
    raw = (HIERARCHY_DIR / "cmdb_ci_linux_server.json").read_text(encoding="utf-8")
    export = parse_hierarchy_export(raw)
    assert export["target_table"] == "cmdb_ci_linux_server"
    assert export["inheritance_path"] == [
        "cmdb",
        "cmdb_ci",
        "cmdb_ci_hardware",
        "cmdb_ci_computer",
        "cmdb_ci_server",
        "cmdb_ci_linux_server",
    ]
    assert any(field["name"] == "kernel_release" for field in export["fields"])


def test_hierarchy_exports_define_full_inheritance_paths():
    expected_paths = {
        "cmdb_ci_linux_server.json": [
            "cmdb",
            "cmdb_ci",
            "cmdb_ci_hardware",
            "cmdb_ci_computer",
            "cmdb_ci_server",
            "cmdb_ci_linux_server",
        ],
        "cmdb_ci_win_server.json": [
            "cmdb",
            "cmdb_ci",
            "cmdb_ci_hardware",
            "cmdb_ci_computer",
            "cmdb_ci_server",
            "cmdb_ci_win_server",
        ],
        "cmdb_ci_router.json": ["cmdb", "cmdb_ci", "cmdb_ci_vm_object", "cmdb_ci_router"],
        "cmdb_ci_switch.json": ["cmdb", "cmdb_ci", "cmdb_ci_vm_object", "cmdb_ci_switch"],
        "cmdb_ci_vm_instance.json": [
            "cmdb",
            "cmdb_ci",
            "cmdb_ci_vm_object",
            "cmdb_ci_vm_instance",
        ],
    }
    for filename, path in expected_paths.items():
        export = parse_hierarchy_export((HIERARCHY_DIR / filename).read_text(encoding="utf-8"))
        assert export["inheritance_path"] == path


def test_parse_vm_instance_export_with_wrapper():
    raw = (HIERARCHY_DIR / "cmdb_ci_vm_instance.json").read_text(encoding="utf-8")
    export = parse_hierarchy_export(raw)
    assert export["target_table"] == "cmdb_ci_vm_instance"
    assert export["inheritance_path"][-1] == "cmdb_ci_vm_instance"


def test_descendants_include_child_classes():
    descendants = get_descendants("cmdb_ci_server")
    assert "cmdb_ci_linux_server" in descendants
    assert "cmdb_ci_server" in descendants


def test_class_filter_uses_in_for_parent_class():
    conditions = class_filter_conditions("cmdb_ci_server")
    assert len(conditions) == 1
    assert conditions[0].operator == "IN"
    assert "cmdb_ci_linux_server" in conditions[0].value


def test_record_in_class_subtree():
    assert record_in_class_subtree("cmdb_ci_linux_server", "cmdb_ci_server")
    assert not record_in_class_subtree("cmdb_ci_vm_instance", "cmdb_ci_server")


def test_compute_class_path():
    path = compute_class_path("cmdb_ci_linux_server")
    assert path.endswith("/cmdb_ci_linux_server")
    assert "/cmdb_ci_server/" in path or path.endswith("/cmdb_ci_server/cmdb_ci_linux_server")


def test_split_payload_registered_class():
    columns, attributes = split_payload(
        "cmdb_ci_linux_server",
        {"name": "host1", "kernel_release": "6.1", "host_name": "host1"},
    )
    assert columns["name"] == "host1"
    assert columns["host_name"] == "host1"
    assert attributes["kernel_release"] == "6.1"


def test_split_payload_accepts_unknown_snake_case_field_for_registered_class():
    columns, attributes = split_payload("cmdb_ci_linux_server", {"cpus": "4"})
    assert columns == {}
    assert attributes["cpus"] == "4"


def test_split_payload_rejects_non_snake_case_field_for_registered_class():
    with pytest.raises(InvalidFieldNameError):
        split_payload("cmdb_ci_linux_server", {"CpuCount": "2"})


def test_split_payload_mixed_known_and_unknown_fields():
    columns, attributes = split_payload(
        "cmdb_ci_linux_server",
        {
            "name": "host1",
            "host_name": "host1",
            "kernel_release": "6.1",
            "vm_inst_id": "i-0a8f894a2cbb88b5b",
            "cpu_count": "1",
        },
    )
    assert columns["name"] == "host1"
    assert columns["host_name"] == "host1"
    assert attributes["kernel_release"] == "6.1"
    assert attributes["vm_inst_id"] == "i-0a8f894a2cbb88b5b"
    assert attributes["cpu_count"] == "1"


def test_split_payload_unregistered_class_is_permissive(monkeypatch):
    from app.domain.cmdb import registry

    registry._snapshot = _RegistrySnapshot(classes={}, fields_by_class={}, children={})
    columns, attributes = split_payload(
        "cmdb_ci_custom_app",
        {"name": "app1", "custom_flag": "true"},
    )
    assert columns["name"] == "app1"
    assert attributes["custom_flag"] == "true"


def test_merged_fields_include_ancestors():
    merged = get_merged_fields("cmdb_ci_linux_server")
    assert "name" in merged
    assert "host_name" in merged
    assert "kernel_release" in merged


def test_fallback_inheritance_path_for_unregistered_class():
    path = fallback_inheritance_path("cmdb_ci_custom_app")
    assert path == ["cmdb", "cmdb_ci", "cmdb_ci_custom_app"]


def test_resolve_inheritance_path_prefers_export_when_registry_chain_is_flat():
    from app.domain.cmdb import registry

    full_path = [
        "cmdb",
        "cmdb_ci",
        "cmdb_ci_hardware",
        "cmdb_ci_computer",
        "cmdb_ci_server",
        "cmdb_ci_linux_server",
    ]
    registry.register_export_inheritance_path("cmdb_ci_linux_server", full_path)
    registry._snapshot.classes["cmdb_ci_linux_server"].super_class = "cmdb_ci"

    path = registry.resolve_inheritance_path("cmdb_ci_linux_server")
    assert path == full_path


@pytest.mark.asyncio
async def test_ensure_class_updates_super_class_when_requested():
    from unittest.mock import AsyncMock

    from app.domain.cmdb.registry import ensure_class

    existing = CmdbClass(
        name="cmdb_ci_linux_server",
        super_class="cmdb_ci",
        label="cmdb_ci_linux_server",
        is_logical=False,
    )
    db = AsyncMock()
    db.get = AsyncMock(return_value=existing)
    db.flush = AsyncMock()

    result = await ensure_class(
        db,
        "cmdb_ci_linux_server",
        super_class="cmdb_ci_server",
        update=True,
    )

    assert result is existing
    assert existing.super_class == "cmdb_ci_server"
    db.flush.assert_awaited_once()
