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
from app.models import SysDbObject

HIERARCHY_DIR = Path(__file__).resolve().parent / "fixtures" / "class-hierarchy"


def _load_snapshot() -> None:
    from app.domain.cmdb import registry

    classes = {
        "cmdb": SysDbObject(
            sys_id="cmdb", name="cmdb", super_class=None, label="cmdb", is_logical=True
        ),
        CMDB_ROOT: SysDbObject(
            sys_id=CMDB_ROOT,
            name=CMDB_ROOT,
            super_class="cmdb",
            label=CMDB_ROOT,
            is_logical=False,
        ),
        "cmdb_ci_hardware": SysDbObject(
            sys_id="cmdb_ci_hardware",
            name="cmdb_ci_hardware",
            super_class=CMDB_ROOT,
            label="cmdb_ci_hardware",
            is_logical=False,
        ),
        "cmdb_ci_computer": SysDbObject(
            sys_id="cmdb_ci_computer",
            name="cmdb_ci_computer",
            super_class="cmdb_ci_hardware",
            label="cmdb_ci_computer",
            is_logical=False,
        ),
        "cmdb_ci_server": SysDbObject(
            sys_id="cmdb_ci_server",
            name="cmdb_ci_server",
            super_class="cmdb_ci_computer",
            label="cmdb_ci_server",
            is_logical=False,
        ),
        "cmdb_ci_linux_server": SysDbObject(
            sys_id="cmdb_ci_linux_server",
            name="cmdb_ci_linux_server",
            super_class="cmdb_ci_server",
            label="cmdb_ci_linux_server",
            is_logical=False,
        ),
        "cmdb_ci_vm_object": SysDbObject(
            sys_id="cmdb_ci_vm_object",
            name="cmdb_ci_vm_object",
            super_class=CMDB_ROOT,
            label="cmdb_ci_vm_object",
            is_logical=False,
        ),
        "cmdb_ci_vm_instance": SysDbObject(
            sys_id="cmdb_ci_vm_instance",
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

    existing = SysDbObject(
        sys_id="cmdb_ci_linux_server",
        name="cmdb_ci_linux_server",
        super_class="cmdb_ci",
        label="cmdb_ci_linux_server",
        is_logical=False,
    )
    db = AsyncMock()
    execute_result = AsyncMock()
    execute_result.scalar_one_or_none = lambda: existing
    db.execute = AsyncMock(return_value=execute_result)
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


@pytest.mark.asyncio
async def test_ensure_class_skips_user_defined_class_and_records_warning():
    from unittest.mock import AsyncMock

    from app.domain.cmdb import registry
    from app.domain.cmdb.registry import ensure_class

    registry.clear_import_warnings()
    existing = SysDbObject(
        sys_id="cmdb_ci_router",
        name="cmdb_ci_router",
        super_class="cmdb_ci",
        label="My Custom Router",
        is_logical=False,
        user_defined=True,
    )
    db = AsyncMock()
    execute_result = AsyncMock()
    execute_result.scalar_one_or_none = lambda: existing
    db.execute = AsyncMock(return_value=execute_result)
    db.flush = AsyncMock()

    result = await ensure_class(
        db,
        "cmdb_ci_router",
        super_class="cmdb_ci_netgear",
        label="Router",
        update=True,
        skip_if_user_defined=True,
    )

    assert result is existing
    assert existing.super_class == "cmdb_ci"  # untouched
    assert existing.label == "My Custom Router"  # untouched
    db.flush.assert_not_awaited()
    warnings = registry.get_import_warnings()
    assert len(warnings) == 1
    assert warnings[0]["class_name"] == "cmdb_ci_router"
    registry.clear_import_warnings()


@pytest.mark.asyncio
async def test_upsert_field_skips_user_defined_field_and_records_warning():
    from unittest.mock import AsyncMock

    from app.domain.cmdb import registry
    from app.domain.cmdb.registry import upsert_field
    from app.models import SysDictionary

    registry.clear_import_warnings()
    existing = SysDictionary(
        sys_id="f1",
        name="cmdb_ci_server",
        element="host_name",
        column_label="My Custom Label",
        internal_type="string",
        storage="column",
        mandatory=False,
        user_defined=True,
    )
    db = AsyncMock()
    execute_result = AsyncMock()
    execute_result.scalar_one_or_none = lambda: existing
    db.execute = AsyncMock(return_value=execute_result)

    result = await upsert_field(
        db,
        "cmdb_ci_server",
        "host_name",
        label="Host Name",
        sn_type="string",
        skip_if_user_defined=True,
    )

    assert result is existing
    assert existing.column_label == "My Custom Label"  # untouched
    warnings = registry.get_import_warnings()
    assert len(warnings) == 1
    assert warnings[0] == {
        "message": (
            "Skipped field definition for 'host_name' on 'cmdb_ci_server': an admin "
            "already customized this field via the admin UI."
        ),
        "class_name": "cmdb_ci_server",
        "field_name": "host_name",
    }
    registry.clear_import_warnings()


@pytest.mark.asyncio
async def test_upsert_field_marks_user_defined_when_admin_edits_existing_field():
    from unittest.mock import AsyncMock

    from app.domain.cmdb.registry import upsert_field
    from app.models import SysDictionary

    existing = SysDictionary(
        sys_id="f1",
        name="cmdb_ci_server",
        element="host_name",
        column_label="Host Name",
        internal_type="string",
        storage="column",
        mandatory=False,
        user_defined=False,
    )
    db = AsyncMock()
    execute_result = AsyncMock()
    execute_result.scalar_one_or_none = lambda: existing
    db.execute = AsyncMock(return_value=execute_result)

    result = await upsert_field(
        db,
        "cmdb_ci_server",
        "host_name",
        label="My Custom Label",
        sn_type="string",
        user_defined=True,
    )

    assert result is existing
    assert existing.column_label == "My Custom Label"
    assert existing.user_defined is True
