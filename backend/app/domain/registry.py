"""Table name to SQLAlchemy model mapping."""

from typing import Any

from app.models import (
    ChangeRequest,
    ChangeTask,
    CmdbCi,
    CmdbRelCi,
    CmdbRelType,
    Incident,
    ItemOptionNew,
    ItemOptionNewCondition,
    Problem,
    ProblemTask,
    RecordAccessGrant,
    ScCatItemWebhook,
    ScItemOption,
    ScReqItem,
    ScRequest,
    ScTask,
    ScWebhook,
    ScWebhookLog,
    ServiceCatalogItem,
    StdChangeProducerVersion,
    SysAttachment,
    SysComment,
    SysGroupRole,
    SysRole,
    SysSecret,
    SysUser,
    SysUserGrMember,
    SysUserGroup,
)

TABLE_MODELS: dict[str, type[Any]] = {
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
    "sc_req_item": ScReqItem,
    "sc_task": ScTask,
    "sc_cat_item": ServiceCatalogItem,
    "item_option_new": ItemOptionNew,
    "item_option_new_condition": ItemOptionNewCondition,
    "sc_item_option": ScItemOption,
    "sc_webhook": ScWebhook,
    "sc_cat_item_webhook": ScCatItemWebhook,
    "sc_webhook_log": ScWebhookLog,
    "sys_secret": SysSecret,
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
    "sc_req_item",
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
    "sys_secret": {
        "read": "secrets.read",
        "write": "secrets.write",
        "manage": "secrets.admin",
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
    "secrets.read",
    "secrets.write",
    "secrets.admin",
]

NUMBER_PREFIXES: dict[str, str] = {
    "incident": "INC",
    "problem": "PRB",
    "problem_task": "PTASK",
    "change_request": "CHG",
    "change_task": "CTASK",
    "sc_request": "REQ",
    "sc_req_item": "RITM",
    "sc_task": "SCTASK",
}

from app.domain.cmdb.registry import is_cmdb_class_name, is_registered  # noqa: E402


def resolve_table_name(table: str) -> tuple[str, str | None] | None:
    """Map a table URL name to an internal table and optional CMDB class filter."""
    if table in TABLE_MODELS:
        return table, None
    if is_cmdb_class_name(table):
        return "cmdb_ci", table
    return None


def is_known_cmdb_class(table: str) -> bool:
    if table == "cmdb_ci":
        return True
    return is_cmdb_class_name(table) and (is_registered(table) or table.startswith("cmdb_ci_"))


DISPLAY_FIELD_BY_TABLE: dict[str, str] = {
    "sys_user": "user_name",
    "sys_user_group": "name",
    "cmdb_ci": "name",
    "incident": "number",
    "problem": "number",
    "problem_task": "number",
    "change_request": "number",
    "change_task": "number",
    "sc_request": "number",
    "sc_req_item": "number",
    "sc_task": "number",
    "sc_cat_item": "name",
    "item_option_new": "name",
    "sc_webhook": "name",
    "cmdb_rel_type": "name",
    "std_change_producer_version": "name",
}

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
    "sc_req_item": {
        "request",
        "cat_item",
        "assigned_to",
        "assignment_group",
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
    "sc_cat_item": {
        "fulfillment_group",
    },
    "item_option_new": {
        "cat_item",
    },
    "item_option_new_condition": {
        "variable",
        "depends_on",
    },
    "sc_item_option": {
        "item_option_new",
        "sc_req_item",
    },
    "sc_webhook": set(),
    "sc_cat_item_webhook": {
        "cat_item",
        "webhook",
    },
    "sc_webhook_log": {
        "webhook_id",
        "attachment_id",
        "sc_req_item",
    },
    "sys_secret": set(),
    "sys_user": {"manager"},
    "sys_user_group": {"owner", "manager", "parent"},
    "sys_user_grmember": {"user_sys_id", "group_sys_id"},
    "cmdb_rel_ci": {"parent", "child", "type"},
    "record_access_grant": {"user_sys_id", "group_sys_id", "granted_by"},
}


def ref_table(field: str, table: str | None = None) -> str:
    """Resolve which table a reference field's sys_id points into."""
    if table == "sys_user_group" and field == "parent":
        return "sys_user_group"
    if table == "cmdb_rel_ci" and field in {"parent", "child"}:
        return "cmdb_ci"
    mapping = {
        "caller_id": "sys_user",
        "assigned_to": "sys_user",
        "requested_by": "sys_user",
        "requested_for": "sys_user",
        "opened_by": "sys_user",
        "resolved_by": "sys_user",
        "closed_by": "sys_user",
        "managed_by": "sys_user",
        "manager": "sys_user",
        "assignment_group": "sys_user_group",
        "support_group": "sys_user_group",
        "owner": "sys_user",
        "owner_group": "sys_user_group",
        "granted_by": "sys_user",
        "change_request": "change_request",
        "problem": "problem",
        "request": "sc_request",
        "cat_item": "sc_cat_item",
        "request_item": "sc_req_item",
        "sc_req_item": "sc_req_item",
        "item_option_new": "item_option_new",
        "variable": "item_option_new",
        "depends_on": "item_option_new",
        "webhook_id": "sc_webhook",
        "webhook": "sc_webhook",
        "attachment_id": "sc_cat_item_webhook",
        "fulfillment_group": "sys_user_group",
        "cmdb_ci": "cmdb_ci",
        "business_service": "cmdb_ci",
        "duplicate_of": "problem",
        "parent_incident": "incident",
        "first_reported_by_task": "problem_task",
        "std_change_producer_version": "std_change_producer_version",
        "user_sys_id": "sys_user",
        "group_sys_id": "sys_user_group",
        "type": "cmdb_rel_type",
    }
    return mapping.get(field, "sys_user")


# Strict parent-child ownership: deleting the parent row cascades to these
# children at the database level (see `ForeignKey(..., ondelete="CASCADE")`
# in `app.models`). Kept here too so the cascade-preview endpoint can walk
# the same tree without touching the database schema.
PARENT_CHILD_RELATIONS: dict[str, list[tuple[str, str]]] = {
    "change_request": [("change_task", "change_request")],
    "problem": [("problem_task", "problem")],
    "sc_request": [("sc_req_item", "request"), ("sc_task", "request")],
    "sc_req_item": [("sc_item_option", "sc_req_item")],
    "sc_cat_item": [
        ("item_option_new", "cat_item"),
        ("sc_cat_item_webhook", "cat_item"),
    ],
    "item_option_new": [
        ("item_option_new_condition", "variable"),
        ("item_option_new_condition", "depends_on"),
    ],
    "sc_webhook": [
        ("sc_cat_item_webhook", "webhook"),
        ("sc_webhook_log", "webhook_id"),
    ],
    "cmdb_ci": [("cmdb_rel_ci", "parent"), ("cmdb_rel_ci", "child")],
}

# Polymorphic children keyed by a (table_name, record_sys_id) pair rather than
# a real foreign key, so they can't be expressed as a `ForeignKey` constraint.
# Deleting any record must also delete its own rows in these tables.
POLYMORPHIC_CHILDREN: list[str] = ["sys_comment", "sys_audit", "record_access_grant"]


def _is_parent_child_pair(table: str, field: str) -> bool:
    return any((table, field) in children for children in PARENT_CHILD_RELATIONS.values())


def build_reverse_reference_map() -> dict[str, list[tuple[str, str]]]:
    """Invert `REFERENCE_FIELDS`: for each target table, list every
    `(source_table, source_field)` pair that loosely points to it.

    Excludes pairs already covered by `PARENT_CHILD_RELATIONS`, since those
    cascade automatically via the database FK constraint rather than needing
    a user choice (clear vs. cascade) at delete time.
    """
    reverse: dict[str, list[tuple[str, str]]] = {}
    for source_table, fields in REFERENCE_FIELDS.items():
        for field in fields:
            if _is_parent_child_pair(source_table, field):
                continue
            target = ref_table(field, source_table)
            reverse.setdefault(target, []).append((source_table, field))
    return reverse


REVERSE_REFERENCE_MAP: dict[str, list[tuple[str, str]]] = build_reverse_reference_map()
