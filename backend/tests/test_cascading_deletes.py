"""Tests for the fresh-schema cascading delete implementation:

- FK ``ON DELETE CASCADE`` wiring for strict parent-child relations.
- Application-layer cleanup of polymorphic children (comments/audit/grants).
- User-chosen handling of loose references on delete (``clear`` vs
  ``cascade``), including the audit trail written when a reference is
  nulled.
- The ``cascade-preview`` endpoint helpers.
- Dangling-reference display when a loosely-referenced row no longer exists.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.api.v1 import router as router_module
from app.domain.registry import (
    PARENT_CHILD_RELATIONS,
    POLYMORPHIC_CHILDREN,
    REVERSE_REFERENCE_MAP,
    _is_parent_child_pair,
    build_reverse_reference_map,
)
from app.domain.table_service import (
    _delete_polymorphic_children,
    attach_reference_display_values,
    cascade_loose_references,
    clear_loose_references,
    delete_record,
)
from app.models import CmdbCi, CmdbRelCi, Incident, SysAudit


def _scalars_result(rows):
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    return result


# --------------------------------------------------------------------------
# Registry: parent-child map, polymorphic children, reverse reference map
# --------------------------------------------------------------------------


def test_parent_child_relations_cover_cmdb_rel_ci():
    assert ("cmdb_rel_ci", "parent") in PARENT_CHILD_RELATIONS["cmdb_ci"]
    assert ("cmdb_rel_ci", "child") in PARENT_CHILD_RELATIONS["cmdb_ci"]


def test_is_parent_child_pair_true_for_registered_pairs():
    assert _is_parent_child_pair("change_task", "change_request") is True
    assert _is_parent_child_pair("cmdb_rel_ci", "parent") is True


def test_is_parent_child_pair_false_for_loose_reference():
    assert _is_parent_child_pair("incident", "cmdb_ci") is False


def test_build_reverse_reference_map_excludes_parent_child_pairs():
    # change_task.change_request cascades via FK, so it must not also appear
    # as a loose reference the user is asked to clear or cascade.
    rebuilt = build_reverse_reference_map()
    assert ("change_task", "change_request") not in rebuilt.get("change_request", [])
    assert ("cmdb_rel_ci", "parent") not in rebuilt.get("cmdb_ci", [])


def test_build_reverse_reference_map_includes_loose_references():
    assert ("incident", "cmdb_ci") in REVERSE_REFERENCE_MAP.get("cmdb_ci", [])
    assert ("problem", "cmdb_ci") in REVERSE_REFERENCE_MAP.get("cmdb_ci", [])


def test_polymorphic_children_list_is_stable():
    assert set(POLYMORPHIC_CHILDREN) == {"sys_comment", "sys_audit", "record_access_grant"}


# --------------------------------------------------------------------------
# _delete_polymorphic_children
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_polymorphic_children_issues_delete_per_child_table():
    db = AsyncMock()
    await _delete_polymorphic_children(db, "cmdb_ci", "ci1")

    assert db.execute.await_count == len(POLYMORPHIC_CHILDREN)
    compiled = [str(call.args[0]) for call in db.execute.await_args_list]
    assert any("sys_comment" in stmt for stmt in compiled)
    assert any("sys_audit" in stmt for stmt in compiled)
    assert any("record_access_grant" in stmt for stmt in compiled)


# --------------------------------------------------------------------------
# clear_loose_references
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clear_loose_references_nulls_field_and_writes_audit_entry(monkeypatch):
    db = AsyncMock()
    referencing_incident = Incident(
        sys_id="inc1", number="INC0000001", short_description="test", cmdb_ci="ci1"
    )
    db.execute = AsyncMock(return_value=_scalars_result([referencing_incident]))

    added = []
    db.add = lambda obj: added.append(obj)
    db.flush = AsyncMock()

    monkeypatch.setattr(
        "app.domain.table_service.REVERSE_REFERENCE_MAP", {"cmdb_ci": [("incident", "cmdb_ci")]}
    )
    monkeypatch.setattr("app.domain.table_service.TABLE_MODELS", {"incident": Incident})

    await clear_loose_references(db, "cmdb_ci", "ci1", "jsmith")

    assert referencing_incident.cmdb_ci is None
    audit_rows = [obj for obj in added if isinstance(obj, SysAudit)]
    assert len(audit_rows) == 1
    audit = audit_rows[0]
    assert audit.table_name == "incident"
    assert audit.record_sys_id == "inc1"
    assert audit.field_name == "cmdb_ci"
    assert audit.old_value == "ci1"
    assert audit.new_value is None
    assert audit.user == "jsmith"


@pytest.mark.asyncio
async def test_clear_loose_references_skips_when_no_referencing_rows(monkeypatch):
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_scalars_result([]))
    db.add = MagicMock()
    db.flush = AsyncMock()

    monkeypatch.setattr(
        "app.domain.table_service.REVERSE_REFERENCE_MAP", {"cmdb_ci": [("incident", "cmdb_ci")]}
    )
    monkeypatch.setattr("app.domain.table_service.TABLE_MODELS", {"incident": Incident})

    await clear_loose_references(db, "cmdb_ci", "ci1", "jsmith")

    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_clear_loose_references_deletes_row_when_column_not_nullable(monkeypatch):
    """A loose-reference column that is NOT NULL can't be left dangling by
    nulling it, so the referencing row is deleted instead."""
    db = AsyncMock()
    referencing_incident = Incident(
        sys_id="inc1", number="INC0000001", short_description="test", cmdb_ci="ci1"
    )
    db.execute = AsyncMock(return_value=_scalars_result([referencing_incident]))

    monkeypatch.setattr(
        "app.domain.table_service.REVERSE_REFERENCE_MAP", {"cmdb_ci": [("incident", "cmdb_ci")]}
    )
    monkeypatch.setattr("app.domain.table_service.TABLE_MODELS", {"incident": Incident})
    delete_record_mock = AsyncMock(return_value=True)
    monkeypatch.setattr("app.domain.table_service.delete_record", delete_record_mock)

    column = Incident.__table__.columns["cmdb_ci"]
    original_nullable = column.nullable
    column.nullable = False
    try:
        await clear_loose_references(db, "cmdb_ci", "ci1", "jsmith")
    finally:
        column.nullable = original_nullable

    delete_record_mock.assert_awaited_once_with(db, "incident", "inc1", auth=None)


# --------------------------------------------------------------------------
# cascade_loose_references
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cascade_loose_references_deletes_every_referencing_row(monkeypatch):
    db = AsyncMock()
    row_a = Incident(sys_id="inc1", number="INC0000001", short_description="a", cmdb_ci="ci1")
    row_b = Incident(sys_id="inc2", number="INC0000002", short_description="b", cmdb_ci="ci1")
    db.execute = AsyncMock(return_value=_scalars_result([row_a, row_b]))

    monkeypatch.setattr(
        "app.domain.table_service.REVERSE_REFERENCE_MAP", {"cmdb_ci": [("incident", "cmdb_ci")]}
    )
    monkeypatch.setattr("app.domain.table_service.TABLE_MODELS", {"incident": Incident})
    delete_record_mock = AsyncMock(return_value=True)
    monkeypatch.setattr("app.domain.table_service.delete_record", delete_record_mock)

    await cascade_loose_references(db, "cmdb_ci", "ci1")

    assert delete_record_mock.await_count == 2
    called_sys_ids = {call.args[2] for call in delete_record_mock.await_args_list}
    assert called_sys_ids == {"inc1", "inc2"}


# --------------------------------------------------------------------------
# delete_record: ref_mode dispatch + polymorphic/attachment cleanup
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_record_clear_mode_calls_clear_loose_references(monkeypatch):
    db = AsyncMock()
    record = Incident(sys_id="inc1", number="INC0000001", short_description="x")
    db.get = AsyncMock(return_value=record)
    db.flush = AsyncMock()

    monkeypatch.setattr("app.domain.table_service.TABLE_MODELS", {"incident": Incident})
    monkeypatch.setattr("app.domain.table_service.emit", AsyncMock())
    clear_mock = AsyncMock()
    cascade_mock = AsyncMock()
    monkeypatch.setattr("app.domain.table_service.clear_loose_references", clear_mock)
    monkeypatch.setattr("app.domain.table_service.cascade_loose_references", cascade_mock)
    monkeypatch.setattr("app.domain.table_service._delete_polymorphic_children", AsyncMock())
    monkeypatch.setattr("app.domain.table_service.delete_attachments_for_parent", AsyncMock())

    result = await delete_record(db, "incident", "inc1", ref_mode="clear")

    assert result is True
    clear_mock.assert_awaited_once_with(db, "incident", "inc1", None, auth=None)
    cascade_mock.assert_not_called()
    db.delete.assert_awaited_once_with(record)


@pytest.mark.asyncio
async def test_delete_record_cascade_mode_calls_cascade_loose_references(monkeypatch):
    db = AsyncMock()
    record = CmdbCi(sys_id="ci1", name="host1", sys_class_name="cmdb_ci_linux_server")
    db.get = AsyncMock(return_value=record)
    db.flush = AsyncMock()

    monkeypatch.setattr("app.domain.table_service.TABLE_MODELS", {"cmdb_ci_shim": CmdbCi})
    monkeypatch.setattr("app.domain.table_service.emit", AsyncMock())
    clear_mock = AsyncMock()
    cascade_mock = AsyncMock()
    monkeypatch.setattr("app.domain.table_service.clear_loose_references", clear_mock)
    monkeypatch.setattr("app.domain.table_service.cascade_loose_references", cascade_mock)
    monkeypatch.setattr("app.domain.table_service._delete_polymorphic_children", AsyncMock())
    monkeypatch.setattr("app.domain.table_service.delete_attachments_for_parent", AsyncMock())

    # Use a non-"cmdb_ci" table name to avoid the special-cased redirect to
    # ci_service.delete_cmdb_ci and exercise the generic delete_record path.
    result = await delete_record(db, "cmdb_ci_shim", "ci1", ref_mode="cascade")

    assert result is True
    cascade_mock.assert_awaited_once_with(db, "cmdb_ci_shim", "ci1", auth=None)
    clear_mock.assert_not_called()


@pytest.mark.asyncio
async def test_delete_record_default_mode_skips_loose_reference_handling(monkeypatch):
    db = AsyncMock()
    record = Incident(sys_id="inc1", number="INC0000001", short_description="x")
    db.get = AsyncMock(return_value=record)
    db.flush = AsyncMock()

    monkeypatch.setattr("app.domain.table_service.TABLE_MODELS", {"incident": Incident})
    monkeypatch.setattr("app.domain.table_service.emit", AsyncMock())
    clear_mock = AsyncMock()
    cascade_mock = AsyncMock()
    monkeypatch.setattr("app.domain.table_service.clear_loose_references", clear_mock)
    monkeypatch.setattr("app.domain.table_service.cascade_loose_references", cascade_mock)
    monkeypatch.setattr("app.domain.table_service._delete_polymorphic_children", AsyncMock())
    monkeypatch.setattr("app.domain.table_service.delete_attachments_for_parent", AsyncMock())

    result = await delete_record(db, "incident", "inc1")

    assert result is True
    clear_mock.assert_not_called()
    cascade_mock.assert_not_called()


@pytest.mark.asyncio
async def test_delete_record_cleans_up_polymorphic_children_and_attachments(monkeypatch):
    db = AsyncMock()
    record = Incident(sys_id="inc1", number="INC0000001", short_description="x")
    db.get = AsyncMock(return_value=record)
    db.flush = AsyncMock()

    monkeypatch.setattr("app.domain.table_service.TABLE_MODELS", {"incident": Incident})
    monkeypatch.setattr("app.domain.table_service.emit", AsyncMock())
    poly_mock = AsyncMock()
    attachments_mock = AsyncMock()
    monkeypatch.setattr("app.domain.table_service._delete_polymorphic_children", poly_mock)
    monkeypatch.setattr("app.domain.table_service.delete_attachments_for_parent", attachments_mock)

    await delete_record(db, "incident", "inc1")

    poly_mock.assert_awaited_once_with(db, "incident", "inc1")
    attachments_mock.assert_awaited_once_with(db, "incident", "inc1")


@pytest.mark.asyncio
async def test_delete_record_returns_false_when_record_missing():
    db = AsyncMock()
    db.get = AsyncMock(return_value=None)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.domain.table_service.TABLE_MODELS", {"incident": Incident})
        result = await delete_record(db, "incident", "missing")

    assert result is False


# --------------------------------------------------------------------------
# Dangling reference display (attach_reference_display_values)
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_attach_reference_display_values_marks_deleted_sentinel():
    db = AsyncMock()

    async def mock_execute(_stmt):
        result = MagicMock()
        result.all.return_value = []  # target row no longer exists
        return result

    db.execute = mock_execute

    records = [{"sys_id": "inc1", "number": "INC0000001", "cmdb_ci": "ci-deleted"}]
    await attach_reference_display_values(db, "incident", records)

    assert records[0]["cmdb_ci_display_value"] == "[Deleted]"
    assert records[0]["cmdb_ci_deleted"] is True


@pytest.mark.asyncio
async def test_attach_reference_display_values_resolves_existing_target():
    db = AsyncMock()

    async def mock_execute(_stmt):
        result = MagicMock()
        result.all.return_value = [("ci1", "lab-srv-01")]
        return result

    db.execute = mock_execute

    records = [{"sys_id": "inc1", "number": "INC0000001", "cmdb_ci": "ci1"}]
    await attach_reference_display_values(db, "incident", records)

    assert records[0]["cmdb_ci_display_value"] == "lab-srv-01"
    assert "cmdb_ci_deleted" not in records[0]


# --------------------------------------------------------------------------
# Cascade preview endpoint helpers (router.py)
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cascade_children_preview_counts_fk_cascaded_children(monkeypatch):
    db = AsyncMock()
    count_result = MagicMock()
    count_result.scalar.return_value = 3
    change_task = MagicMock(sys_id="task1", number="CTASK0000001")
    rows_result = _scalars_result([change_task])
    db.execute = AsyncMock(side_effect=[count_result, rows_result])

    monkeypatch.setattr(
        router_module,
        "PARENT_CHILD_RELATIONS",
        {"change_request": [("change_task", "change_request")]},
    )

    preview = await router_module._cascade_children_preview(db, "change_request", "chg1")

    assert preview == [
        {
            "table": "change_task",
            "label": "Change Tasks",
            "count": 3,
            "records": [{"sys_id": "task1", "label": "CTASK0000001"}],
        }
    ]


@pytest.mark.asyncio
async def test_cascade_children_preview_omits_tables_with_zero_children(monkeypatch):
    db = AsyncMock()
    count_result = MagicMock()
    count_result.scalar.return_value = 0
    db.execute = AsyncMock(return_value=count_result)

    monkeypatch.setattr(
        router_module,
        "PARENT_CHILD_RELATIONS",
        {"change_request": [("change_task", "change_request")]},
    )

    preview = await router_module._cascade_children_preview(db, "change_request", "chg1")

    assert preview == []


@pytest.mark.asyncio
async def test_cmdb_rel_ci_labels_describe_relationship_from_deleted_ci_perspective():
    db = AsyncMock()
    ci_result = MagicMock()
    ci_result.all.return_value = [("core1", "lab-sw-core-01"), ("access1", "lab-sw-access-02")]
    type_result = MagicMock()
    type_result.all.return_value = [("type1", "Depends on")]
    db.execute = AsyncMock(side_effect=[ci_result, type_result])

    outgoing = CmdbRelCi(sys_id="rel1", parent="access1", child="core1", type="type1")
    incoming = CmdbRelCi(sys_id="rel2", parent="core1", child="access1", type="type1")

    records = await router_module._cmdb_rel_ci_labels(db, [outgoing, incoming], "access1")

    assert records == [
        {
            "sys_id": "rel1",
            "label": "lab-sw-core-01",
            "relationship": {"direction": "outgoing", "type": "Depends on"},
        },
        {
            "sys_id": "rel2",
            "label": "lab-sw-core-01",
            "relationship": {"direction": "incoming", "type": "Depends on"},
        },
    ]


@pytest.mark.asyncio
async def test_loose_references_preview_lists_referencing_records(monkeypatch):
    db = AsyncMock()
    incident = Incident(
        sys_id="inc1", number="INC0000001", short_description="down", cmdb_ci="ci1"
    )
    db.execute = AsyncMock(return_value=_scalars_result([incident]))

    monkeypatch.setattr(
        router_module, "REVERSE_REFERENCE_MAP", {"cmdb_ci": [("incident", "cmdb_ci")]}
    )
    monkeypatch.setattr(router_module, "TABLE_MODELS", {"incident": Incident})

    preview = await router_module._loose_references_preview(db, "cmdb_ci", "ci1")

    assert len(preview) == 1
    entry = preview[0]
    assert entry["table"] == "incident"
    assert entry["field"] == "cmdb_ci"
    assert entry["resource"] == "incidents"
    assert entry["records"] == [{"sys_id": "inc1", "label": "INC0000001"}]


@pytest.mark.asyncio
async def test_loose_references_preview_empty_when_no_referencing_rows(monkeypatch):
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_scalars_result([]))

    monkeypatch.setattr(
        router_module, "REVERSE_REFERENCE_MAP", {"cmdb_ci": [("incident", "cmdb_ci")]}
    )
    monkeypatch.setattr(router_module, "TABLE_MODELS", {"incident": Incident})

    preview = await router_module._loose_references_preview(db, "cmdb_ci", "ci1")

    assert preview == []


@pytest.mark.asyncio
async def test_peripheral_preview_counts_comments_audit_grants_and_attachments():
    db = AsyncMock()
    counts = iter([2, 5, 1, 3])

    async def mock_execute(_stmt):
        result = MagicMock()
        result.scalar.return_value = next(counts)
        return result

    db.execute = mock_execute

    peripheral = await router_module._peripheral_preview(db, "cmdb_ci", "ci1")

    assert peripheral == {
        "comments": 2,
        "audit_entries": 5,
        "access_grants": 1,
        "attachments": 3,
    }


@pytest.mark.asyncio
async def test_peripheral_preview_omits_zero_counts():
    db = AsyncMock()
    result = MagicMock()
    result.scalar.return_value = 0
    db.execute = AsyncMock(return_value=result)

    peripheral = await router_module._peripheral_preview(db, "cmdb_ci", "ci1")

    assert peripheral == {}


def test_table_label_uses_registered_label_or_title_case():
    assert router_module._table_label("cmdb_rel_ci") == "CI Relationships"
    assert router_module._table_label("some_unmapped_table") == "Some Unmapped Table"


# --------------------------------------------------------------------------
# DELETE endpoint: ref_mode validation and dispatch
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_resource_rejects_invalid_ref_mode():
    from fastapi import HTTPException

    db = AsyncMock()
    auth = MagicMock()

    with pytest.raises(HTTPException) as exc_info:
        await router_module.delete_resource(
            "configuration-items", "ci1", ref_mode="bogus", auth=auth, db=db
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_delete_resource_passes_ref_mode_to_delete_record(monkeypatch):
    db = AsyncMock()
    auth = MagicMock()
    delete_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(router_module, "delete_record", delete_mock)

    response = await router_module.delete_resource(
        "configuration-items", "ci1", ref_mode="clear", auth=auth, db=db
    )

    delete_mock.assert_awaited_once_with(db, "cmdb_ci", "ci1", auth=auth, ref_mode="clear")
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_resource_404_when_record_missing(monkeypatch):
    from fastapi import HTTPException

    db = AsyncMock()
    auth = MagicMock()
    monkeypatch.setattr(router_module, "delete_record", AsyncMock(return_value=False))

    with pytest.raises(HTTPException) as exc_info:
        await router_module.delete_resource("configuration-items", "ci1", auth=auth, db=db)
    assert exc_info.value.status_code == 404
