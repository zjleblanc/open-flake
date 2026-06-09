"""Table name to SQLAlchemy model mapping."""

from app.models import (
    ChangeRequest,
    ChangeTask,
    CmdbCi,
    CmdbRelCi,
    CmdbRelType,
    Incident,
    Problem,
    ProblemTask,
    RecordAccessGrant,
    ScRequest,
    ScTask,
    StdChangeProducerVersion,
    SysAttachment,
    SysComment,
    SysGroupRole,
    SysRole,
    SysUser,
    SysUserGrMember,
    SysUserGroup,
)

TABLE_MODELS: dict[str, type] = {
    "incident": Incident,
    "problem": Problem,
    "problem_task": ProblemTask,
    "change_request": ChangeRequest,
    "change_task": ChangeTask,
    "cmdb_ci": CmdbCi,
    "sys_user": SysUser,
    "sys_user_group": SysUserGroup,
    "sys_user_grmember": SysUserGrMember,
    "sc_request": ScRequest,
    "sc_task": ScTask,
    "cmdb_rel_type": CmdbRelType,
    "cmdb_rel_ci": CmdbRelCi,
    "std_change_producer_version": StdChangeProducerVersion,
    "sys_attachment": SysAttachment,
    "sys_role": SysRole,
    "sys_group_role": SysGroupRole,
    "record_access_grant": RecordAccessGrant,
    "sys_comment": SysComment,
}

RBAC_RECORD_TABLES = {
    "incident",
    "problem",
    "problem_task",
    "change_request",
    "change_task",
    "cmdb_ci",
    "sc_request",
    "sc_task",
}

PLATFORM_TABLES: dict[str, dict[str, str]] = {
    "sys_user": {
        "read": "users.read",
        "write": "users.write",
        "self_write": "users.write.self",
    },
    "sys_user_group": {
        "read": "groups.read",
        "write": "groups.write",
        "manage": "groups.manage",
    },
    "sys_user_grmember": {
        "read": "groups.read",
        "write": "groups.manage",
    },
}

PLATFORM_ADMIN_PERMISSIONS = [
    "records.*.read",
    "records.*.write",
    "users.read",
    "users.write",
    "users.write.self",
    "groups.read",
    "groups.write",
    "groups.manage",
]

NUMBER_PREFIXES: dict[str, str] = {
    "incident": "INC",
    "problem": "PRB",
    "problem_task": "PTASK",
    "change_request": "CHG",
    "change_task": "CTASK",
    "sc_request": "REQ",
    "sc_task": "SCTASK",
}

def resolve_table_name(table: str) -> tuple[str, str | None] | None:
    """Map a ServiceNow table name to an internal table and optional CMDB class filter."""
    if table in TABLE_MODELS:
        return table, None
    if table.startswith("cmdb_ci_") and table not in {"cmdb_rel_ci", "cmdb_rel_type"}:
        return "cmdb_ci", table
    return None


REFERENCE_FIELDS: dict[str, set[str]] = {
    "incident": {
        "caller_id",
        "assigned_to",
        "assignment_group",
        "owner",
        "owner_group",
        "cmdb_ci",
        "business_service",
        "opened_by",
        "resolved_by",
        "closed_by",
        "parent_incident",
    },
    "problem": {
        "assigned_to",
        "assignment_group",
        "duplicate_of",
        "owner",
        "owner_group",
        "cmdb_ci",
        "business_service",
        "first_reported_by_task",
    },
    "problem_task": {
        "problem",
        "cmdb_ci",
        "assigned_to",
        "assignment_group",
        "owner",
        "owner_group",
        "business_service",
    },
    "change_request": {
        "requested_by",
        "assigned_to",
        "assignment_group",
        "std_change_producer_version",
        "owner",
        "owner_group",
        "cmdb_ci",
        "business_service",
    },
    "change_task": {
        "change_request",
        "cmdb_ci",
        "assigned_to",
        "assignment_group",
        "owner",
        "owner_group",
        "business_service",
    },
    "cmdb_ci": {
        "assigned_to",
        "owner",
        "owner_group",
        "support_group",
        "managed_by",
        "assignment_group",
    },
    "sc_request": {
        "requested_for",
        "requested_by",
        "assignment_group",
        "assigned_to",
        "owner",
        "owner_group",
        "cmdb_ci",
        "business_service",
        "opened_by",
    },
    "sc_task": {
        "request",
        "assigned_to",
        "assignment_group",
        "owner",
        "owner_group",
        "cmdb_ci",
        "business_service",
        "cat_item",
        "request_item",
    },
    "sys_user": {"manager"},
    "sys_user_group": {"owner", "manager", "parent"},
    "sys_user_grmember": {"user_sys_id", "group_sys_id"},
    "cmdb_rel_ci": {"parent", "child", "type"},
    "record_access_grant": {"user_sys_id", "group_sys_id", "granted_by"},
}
