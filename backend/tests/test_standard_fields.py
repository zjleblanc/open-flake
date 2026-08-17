from unittest.mock import AsyncMock, MagicMock

import pytest
from app.domain.registry import ref_table
from app.domain.table_service import _model_to_dict, attach_reference_display_values
from app.models import ChangeRequest, Incident, ScRequest, SysUser


@pytest.mark.parametrize(
    "model,table,fields",
    [
        (
            Incident(sys_id="1", number="INC0000001", short_description="test"),
            "incident",
            ["active", "work_notes", "cmdb_ci", "category", "opened_by"],
        ),
        (
            ChangeRequest(sys_id="2", number="CHG0000001", short_description="test"),
            "change_request",
            ["justification", "implementation_plan", "cmdb_ci", "approval"],
        ),
        (
            ScRequest(sys_id="3", number="REQ0000001", short_description="test"),
            "sc_request",
            ["request_state", "delivery_plan", "stage", "approval"],
        ),
        (
            SysUser(sys_id="4", user_name="admin", user_password="x"),
            "sys_user",
            ["phone", "department", "manager", "time_zone"],
        ),
    ],
)
def test_standard_fields_serialized(model, table, fields):
    data = _model_to_dict(model, table)
    for field in fields:
        assert field in data


def test_sys_user_group_parent_ref_table():
    assert ref_table("parent", "sys_user_group") == "sys_user_group"


def test_cmdb_rel_ci_parent_ref_table():
    assert ref_table("parent", "cmdb_rel_ci") == "cmdb_ci"


@pytest.mark.asyncio
async def test_attach_reference_display_values_resolves_group_owner():
    db = AsyncMock()

    async def mock_execute(_stmt):
        result = MagicMock()
        result.all.return_value = [("user1", "jdoe")]
        return result

    db.execute = mock_execute

    records = [{"sys_id": "group1", "name": "Platform Team", "owner": "user1"}]
    await attach_reference_display_values(db, "sys_user_group", records)

    assert records[0]["owner_display_value"] == "jdoe"


@pytest.mark.asyncio
async def test_attach_reference_display_values_skips_empty_fields():
    db = AsyncMock()
    db.execute = AsyncMock()

    records = [{"sys_id": "group1", "name": "Platform Team", "owner": ""}]
    await attach_reference_display_values(db, "sys_user_group", records)

    assert "owner_display_value" not in records[0]
    db.execute.assert_not_called()
