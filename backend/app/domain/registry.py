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
    ScRequest,
    ScTask,
    StdChangeProducerVersion,
    SysAttachment,
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
}

NUMBER_PREFIXES: dict[str, str] = {
    "incident": "INC",
    "problem": "PRB",
    "problem_task": "PTASK",
    "change_request": "CHG",
    "change_task": "CTASK",
    "sc_request": "REQ",
    "sc_task": "SCTASK",
}

REFERENCE_FIELDS: dict[str, set[str]] = {
    "incident": {"caller_id", "assigned_to", "assignment_group"},
    "problem": {"assigned_to", "assignment_group", "duplicate_of"},
    "problem_task": {"problem", "cmdb_ci", "assigned_to", "assignment_group"},
    "change_request": {
        "requested_by",
        "assigned_to",
        "assignment_group",
        "std_change_producer_version",
    },
    "change_task": {"change_request", "cmdb_ci", "assigned_to", "assignment_group"},
    "cmdb_ci": {"assigned_to"},
    "sc_request": {"requested_for", "requested_by", "assignment_group", "assigned_to"},
    "sc_task": {"request", "assigned_to", "assignment_group"},
    "sys_user_grmember": {"user_sys_id", "group_sys_id"},
    "cmdb_rel_ci": {"parent", "child", "type"},
}
