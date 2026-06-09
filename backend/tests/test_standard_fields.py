import pytest

from app.domain.table_service import _model_to_dict, _ref_table
from app.models import ChangeRequest, Incident, ScRequest, SysUser, SysUserGroup


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
    assert _ref_table("parent", "sys_user_group") == "sys_user_group"


def test_cmdb_rel_ci_parent_ref_table():
    assert _ref_table("parent", "cmdb_rel_ci") == "cmdb_ci"
