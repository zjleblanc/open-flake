from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.functions import now as sa_now

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class LifecycleMixin:
    """Record lifecycle fields: creation/update timestamps, audit usernames, and mod count."""

    sys_created_on: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=sa_now()
    )
    sys_updated_on: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        server_default=sa_now(),
    )
    sys_created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sys_updated_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sys_mod_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class OwnershipMixin:
    """Record ownership fields: individual owner and owning group references."""

    owner: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    owner_group: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)


class TaskFieldsMixin:
    """Common ServiceNow task table fields shared by ITSM record types."""

    active: Mapped[str] = mapped_column(String(8), default="true")
    work_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    opened_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    closed_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resolved_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    due_date: Mapped[str | None] = mapped_column(String(64), nullable=True)
    business_service: Mapped[str | None] = mapped_column(String(32), nullable=True)
    escalation: Mapped[str | None] = mapped_column(String(8), nullable=True)


class NumberSequence(Base):
    __tablename__ = "number_sequence"

    prefix: Mapped[str] = mapped_column(String(16), primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class SysUser(Base, LifecycleMixin):
    __tablename__ = "sys_user"

    sys_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    user_password: Mapped[str] = mapped_column(String(256))
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mobile_phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    department: Mapped[str | None] = mapped_column(String(128), nullable=True)
    title: Mapped[str | None] = mapped_column(String(128), nullable=True)
    location: Mapped[str | None] = mapped_column(String(256), nullable=True)
    company: Mapped[str | None] = mapped_column(String(128), nullable=True)
    manager: Mapped[str | None] = mapped_column(String(32), nullable=True)
    time_zone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    vip: Mapped[str | None] = mapped_column(String(8), nullable=True)
    employee_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    active: Mapped[str] = mapped_column(String(8), default="true")
    preferences: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    other: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class SysUserGroup(Base, LifecycleMixin):
    __tablename__ = "sys_user_group"

    sys_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    active: Mapped[str] = mapped_column(String(8), default="true")
    email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    manager: Mapped[str | None] = mapped_column(String(32), nullable=True)
    parent: Mapped[str | None] = mapped_column(String(32), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    other: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class SysRole(Base):
    __tablename__ = "sys_role"

    sys_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    suffix: Mapped[str | None] = mapped_column(String(64), nullable=True)
    permissions: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")


class SysGroupRole(Base):
    __tablename__ = "sys_group_role"

    sys_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    group_sys_id: Mapped[str] = mapped_column(String(32), index=True)
    role_sys_id: Mapped[str] = mapped_column(String(32), index=True)


class RecordAccessGrant(Base, LifecycleMixin):
    __tablename__ = "record_access_grant"

    sys_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    table_name: Mapped[str] = mapped_column(String(128), index=True)
    record_sys_id: Mapped[str] = mapped_column(String(32), index=True)
    user_sys_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    group_sys_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    access_level: Mapped[str] = mapped_column(String(16))  # view | comment
    granted_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="manual")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SysComment(Base, LifecycleMixin):
    __tablename__ = "sys_comment"

    sys_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    table_name: Mapped[str] = mapped_column(String(128), index=True)
    record_sys_id: Mapped[str] = mapped_column(String(32), index=True)
    comment: Mapped[str] = mapped_column(Text, default="")


class SysAudit(Base):
    """Field-level change log entry, written by `update_record()` for RBAC record
    tables. Rows sharing a `batch_id` were all written by the same create/update
    call, letting the activity feed group them into a single timeline entry."""

    __tablename__ = "sys_audit"

    sys_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    table_name: Mapped[str] = mapped_column(String(128), index=True)
    record_sys_id: Mapped[str] = mapped_column(String(32), index=True)
    batch_id: Mapped[str] = mapped_column(String(32), index=True)
    field_name: Mapped[str] = mapped_column(String(128))
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    user: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sys_created_on: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=sa_now()
    )


class SysUserGrMember(Base, LifecycleMixin):
    __tablename__ = "sys_user_grmember"

    sys_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_sys_id: Mapped[str] = mapped_column(String(32), index=True)
    group_sys_id: Mapped[str] = mapped_column(String(32), index=True)
    other: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class OAuthClient(Base):
    __tablename__ = "oauth_client"

    sys_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    client_secret: Mapped[str] = mapped_column(String(256))
    name: Mapped[str] = mapped_column(String(128))
    active: Mapped[bool] = mapped_column(default=True)


class OAuthToken(Base):
    __tablename__ = "oauth_token"

    sys_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    access_token: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    refresh_token: Mapped[str | None] = mapped_column(String(512), unique=True, nullable=True)
    client_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    user_sys_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    token_type: Mapped[str] = mapped_column(String(32), default="Bearer")


class ApiKey(Base):
    __tablename__ = "api_key"

    sys_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    key_hash: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    user_sys_id: Mapped[str] = mapped_column(String(32))
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Incident(Base, LifecycleMixin, OwnershipMixin, TaskFieldsMixin):
    __tablename__ = "incident"

    sys_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    short_description: Mapped[str] = mapped_column(String(512), default="")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(String(8), default="1")
    impact: Mapped[str] = mapped_column(String(8), default="3")
    urgency: Mapped[str] = mapped_column(String(8), default="3")
    priority: Mapped[str] = mapped_column(String(8), default="4")
    caller_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    assigned_to: Mapped[str | None] = mapped_column(String(32), nullable=True)
    assignment_group: Mapped[str | None] = mapped_column(String(32), nullable=True)
    hold_reason: Mapped[str | None] = mapped_column(String(8), nullable=True)
    close_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    close_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notify: Mapped[str | None] = mapped_column(String(8), nullable=True)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    subcategory: Mapped[str | None] = mapped_column(String(128), nullable=True)
    cmdb_ci: Mapped[str | None] = mapped_column(String(32), nullable=True)
    opened_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    closed_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    parent_incident: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sys_class_name: Mapped[str] = mapped_column(String(64), default="incident")
    other: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class Problem(Base, LifecycleMixin, OwnershipMixin, TaskFieldsMixin):
    __tablename__ = "problem"

    sys_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    short_description: Mapped[str] = mapped_column(String(512), default="")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(String(8), default="1")
    impact: Mapped[str] = mapped_column(String(8), default="3")
    urgency: Mapped[str] = mapped_column(String(8), default="3")
    priority: Mapped[str] = mapped_column(String(8), default="4")
    assigned_to: Mapped[str | None] = mapped_column(String(32), nullable=True)
    assignment_group: Mapped[str | None] = mapped_column(String(32), nullable=True)
    resolution_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    cause_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    fix_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    close_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    duplicate_of: Mapped[str | None] = mapped_column(String(32), nullable=True)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    subcategory: Mapped[str | None] = mapped_column(String(128), nullable=True)
    cmdb_ci: Mapped[str | None] = mapped_column(String(32), nullable=True)
    first_reported_by_task: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sys_class_name: Mapped[str] = mapped_column(String(64), default="problem")
    other: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class ProblemTask(Base, LifecycleMixin, OwnershipMixin, TaskFieldsMixin):
    __tablename__ = "problem_task"

    sys_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    short_description: Mapped[str] = mapped_column(String(512), default="")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(String(8), default="1")
    problem: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("problem.sys_id", ondelete="CASCADE"), nullable=True
    )
    problem_task_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cmdb_ci: Mapped[str | None] = mapped_column(String(32), nullable=True)
    assigned_to: Mapped[str | None] = mapped_column(String(32), nullable=True)
    assignment_group: Mapped[str | None] = mapped_column(String(32), nullable=True)
    priority: Mapped[str] = mapped_column(String(8), default="4")
    impact: Mapped[str | None] = mapped_column(String(8), nullable=True)
    urgency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    close_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    close_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    sys_class_name: Mapped[str] = mapped_column(String(64), default="problem_task")
    other: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class ChangeRequest(Base, LifecycleMixin, OwnershipMixin, TaskFieldsMixin):
    __tablename__ = "change_request"

    sys_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    short_description: Mapped[str] = mapped_column(String(512), default="")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(String(8), default="-5")
    type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    chg_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    impact: Mapped[str] = mapped_column(String(8), default="3")
    urgency: Mapped[str] = mapped_column(String(8), default="3")
    priority: Mapped[str] = mapped_column(String(8), default="4")
    risk: Mapped[str | None] = mapped_column(String(8), nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    requested_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    assigned_to: Mapped[str | None] = mapped_column(String(32), nullable=True)
    assignment_group: Mapped[str | None] = mapped_column(String(32), nullable=True)
    on_hold: Mapped[str] = mapped_column(String(8), default="false")
    on_hold_reason: Mapped[str | None] = mapped_column(String(8), nullable=True)
    close_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    close_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    std_change_producer_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cmdb_ci: Mapped[str | None] = mapped_column(String(32), nullable=True)
    start_date: Mapped[str | None] = mapped_column(String(64), nullable=True)
    end_date: Mapped[str | None] = mapped_column(String(64), nullable=True)
    work_start: Mapped[str | None] = mapped_column(String(64), nullable=True)
    work_end: Mapped[str | None] = mapped_column(String(64), nullable=True)
    justification: Mapped[str | None] = mapped_column(Text, nullable=True)
    implementation_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    backout_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_date: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approval: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sys_class_name: Mapped[str] = mapped_column(String(64), default="change_request")
    other: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class ChangeTask(Base, LifecycleMixin, OwnershipMixin, TaskFieldsMixin):
    __tablename__ = "change_task"

    sys_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    short_description: Mapped[str] = mapped_column(String(512), default="")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(String(8), default="1")
    change_request: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("change_request.sys_id", ondelete="CASCADE"), nullable=True
    )
    change_task_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cmdb_ci: Mapped[str | None] = mapped_column(String(32), nullable=True)
    assigned_to: Mapped[str | None] = mapped_column(String(32), nullable=True)
    assignment_group: Mapped[str | None] = mapped_column(String(32), nullable=True)
    priority: Mapped[str | None] = mapped_column(String(8), nullable=True)
    impact: Mapped[str | None] = mapped_column(String(8), nullable=True)
    urgency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    on_hold: Mapped[str] = mapped_column(String(8), default="false")
    hold_reason: Mapped[str | None] = mapped_column(String(8), nullable=True)
    close_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    close_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    planned_start_date: Mapped[str | None] = mapped_column(String(64), nullable=True)
    planned_end_date: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sys_class_name: Mapped[str] = mapped_column(String(64), default="change_task")
    other: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class CmdbClass(Base):
    __tablename__ = "cmdb_class"

    name: Mapped[str] = mapped_column(String(128), primary_key=True)
    super_class: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("cmdb_class.name", ondelete="CASCADE"), nullable=True, index=True
    )
    label: Mapped[str | None] = mapped_column(String(256), nullable=True)
    is_logical: Mapped[bool] = mapped_column(default=False)


class CmdbClassField(Base):
    __tablename__ = "cmdb_class_field"
    __table_args__ = (UniqueConstraint("class_name", "field_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    class_name: Mapped[str] = mapped_column(
        String(128), ForeignKey("cmdb_class.name", ondelete="CASCADE"), index=True
    )
    field_name: Mapped[str] = mapped_column(String(128))
    label: Mapped[str | None] = mapped_column(String(256), nullable=True)
    sn_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    storage: Mapped[str] = mapped_column(String(16), default="attributes")


class CmdbCi(Base, LifecycleMixin, OwnershipMixin):
    __tablename__ = "cmdb_ci"

    sys_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), index=True)
    sys_class_name: Mapped[str] = mapped_column(String(128), default="cmdb_ci", index=True)
    sys_class_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    host_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    fqdn: Mapped[str | None] = mapped_column(String(256), nullable=True)
    short_description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    asset_tag: Mapped[str | None] = mapped_column(String(128), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    install_status: Mapped[str | None] = mapped_column(String(8), nullable=True)
    operational_status: Mapped[str | None] = mapped_column(String(8), nullable=True)
    classification: Mapped[str | None] = mapped_column(String(128), nullable=True)
    environment: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mac_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    vendor: Mapped[str | None] = mapped_column(String(128), nullable=True)
    os: Mapped[str | None] = mapped_column(String(128), nullable=True)
    os_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    assigned_to: Mapped[str | None] = mapped_column(String(32), nullable=True)
    attributes: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class CmdbRelType(Base):
    __tablename__ = "cmdb_rel_type"

    sys_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    sys_name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(256))


class CmdbRelCi(Base, LifecycleMixin):
    __tablename__ = "cmdb_rel_ci"

    sys_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    parent: Mapped[str] = mapped_column(
        String(32), ForeignKey("cmdb_ci.sys_id", ondelete="CASCADE"), index=True
    )
    child: Mapped[str] = mapped_column(
        String(32), ForeignKey("cmdb_ci.sys_id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(32))
    connection_strength: Mapped[str | None] = mapped_column(String(64), nullable=True)
    other: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class ScRequest(Base, LifecycleMixin, OwnershipMixin, TaskFieldsMixin):
    __tablename__ = "sc_request"

    sys_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    short_description: Mapped[str] = mapped_column(String(512), default="")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(String(8), default="1")
    request_state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    priority: Mapped[str | None] = mapped_column(String(8), nullable=True)
    urgency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    impact: Mapped[str | None] = mapped_column(String(8), nullable=True)
    requested_for: Mapped[str | None] = mapped_column(String(32), nullable=True)
    requested_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    assignment_group: Mapped[str | None] = mapped_column(String(32), nullable=True)
    assigned_to: Mapped[str | None] = mapped_column(String(32), nullable=True)
    opened_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cmdb_ci: Mapped[str | None] = mapped_column(String(32), nullable=True)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    subcategory: Mapped[str | None] = mapped_column(String(128), nullable=True)
    delivery_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_task: Mapped[str | None] = mapped_column(String(256), nullable=True)
    stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approval: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sys_class_name: Mapped[str] = mapped_column(String(64), default="sc_request")
    other: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class ScTask(Base, LifecycleMixin, OwnershipMixin, TaskFieldsMixin):
    __tablename__ = "sc_task"

    sys_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    short_description: Mapped[str] = mapped_column(String(512), default="")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(String(8), default="1")
    request: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("sc_request.sys_id", ondelete="CASCADE"), nullable=True
    )
    assigned_to: Mapped[str | None] = mapped_column(String(32), nullable=True)
    assignment_group: Mapped[str | None] = mapped_column(String(32), nullable=True)
    priority: Mapped[str | None] = mapped_column(String(8), nullable=True)
    urgency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    impact: Mapped[str | None] = mapped_column(String(8), nullable=True)
    cmdb_ci: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cat_item: Mapped[str | None] = mapped_column(String(32), nullable=True)
    request_item: Mapped[str | None] = mapped_column(String(32), nullable=True)
    stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approval: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sys_class_name: Mapped[str] = mapped_column(String(64), default="sc_task")
    other: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class StdChangeProducerVersion(Base):
    __tablename__ = "std_change_producer_version"

    sys_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), unique=True)
    short_description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[str] = mapped_column(String(8), default="true")
    template: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    other: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class SysAttachment(Base, LifecycleMixin):
    __tablename__ = "sys_attachment"

    sys_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    table_name: Mapped[str] = mapped_column(String(128))
    table_sys_id: Mapped[str] = mapped_column(String(32), index=True)
    file_name: Mapped[str] = mapped_column(String(512))
    content_type: Mapped[str] = mapped_column(String(128), default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    storage_path: Mapped[str] = mapped_column(String(1024))
    hash: Mapped[str | None] = mapped_column(String(256), nullable=True)
    state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    other: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class ServiceCatalog(Base):
    __tablename__ = "service_catalog"

    sys_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    title: Mapped[str] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(default=True)


class ServiceCatalogItem(Base):
    """Catalog item definition (ServiceNow sc_cat_item)."""

    __tablename__ = "sc_cat_item"

    sys_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    catalog_sys_id: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(256), index=True)
    short_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    price: Mapped[str] = mapped_column(String(32), default="0")
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    subcategory: Mapped[str | None] = mapped_column(String(128), nullable=True)
    fulfillment_group: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    order: Mapped[int] = mapped_column(Integer, default=100)
    icon: Mapped[str | None] = mapped_column(String(256), nullable=True)
    other: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class ItemOptionNew(Base, LifecycleMixin):
    """Catalog item variable / form field definition."""

    __tablename__ = "item_option_new"

    sys_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    cat_item: Mapped[str] = mapped_column(
        String(32), ForeignKey("sc_cat_item.sys_id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(128), index=True)
    question_text: Mapped[str] = mapped_column(String(512), default="")
    type: Mapped[str] = mapped_column(String(32), default="string")
    mandatory: Mapped[bool] = mapped_column(Boolean, default=False)
    default_value: Mapped[str | None] = mapped_column(String(512), nullable=True)
    order: Mapped[int] = mapped_column(Integer, default=100)
    reference_table: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reference_filter: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_display_field: Mapped[str | None] = mapped_column(String(128), nullable=True)
    choice_list: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    help_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    read_only: Mapped[bool] = mapped_column(Boolean, default=False)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    other: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class ItemOptionNewCondition(Base, LifecycleMixin):
    """Inter-field dependency rules for catalog variables."""

    __tablename__ = "item_option_new_condition"

    sys_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    variable: Mapped[str] = mapped_column(
        String(32), ForeignKey("item_option_new.sys_id", ondelete="CASCADE"), index=True
    )
    condition_type: Mapped[str] = mapped_column(String(32), default="visibility")
    depends_on: Mapped[str] = mapped_column(
        String(32), ForeignKey("item_option_new.sys_id", ondelete="CASCADE"), index=True
    )
    operator: Mapped[str] = mapped_column(String(16), default="=")
    value: Mapped[str | None] = mapped_column(String(512), nullable=True)
    filter_override: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    other: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class ScReqItem(Base, LifecycleMixin, OwnershipMixin, TaskFieldsMixin):
    """Requested catalog item (ServiceNow sc_req_item / RITM)."""

    __tablename__ = "sc_req_item"

    sys_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    request: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("sc_request.sys_id", ondelete="CASCADE"), nullable=True, index=True
    )
    cat_item: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    state: Mapped[str] = mapped_column(String(8), default="1")
    stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    price: Mapped[str | None] = mapped_column(String(32), nullable=True)
    short_description: Mapped[str] = mapped_column(String(512), default="")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_to: Mapped[str | None] = mapped_column(String(32), nullable=True)
    assignment_group: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cmdb_ci: Mapped[str | None] = mapped_column(String(32), nullable=True)
    approval: Mapped[str | None] = mapped_column(String(64), nullable=True)
    priority: Mapped[str | None] = mapped_column(String(8), nullable=True)
    urgency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    impact: Mapped[str | None] = mapped_column(String(8), nullable=True)
    opened_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sys_class_name: Mapped[str] = mapped_column(String(64), default="sc_req_item")
    requested_for: Mapped[str | None] = mapped_column(String(32), nullable=True)
    upon_approval: Mapped[str | None] = mapped_column(String(32), nullable=True, default="proceed")
    upon_reject: Mapped[str | None] = mapped_column(String(32), nullable=True, default="cancel")
    approval_set: Mapped[str | None] = mapped_column(String(64), nullable=True)
    made_sla: Mapped[str | None] = mapped_column(String(8), nullable=True, default="true")
    reassignment_count: Mapped[str | None] = mapped_column(String(8), nullable=True, default="0")
    recurring_price: Mapped[str | None] = mapped_column(String(32), nullable=True, default="0")
    backordered: Mapped[str | None] = mapped_column(String(8), nullable=True, default="false")
    billable: Mapped[str | None] = mapped_column(String(8), nullable=True, default="false")
    knowledge: Mapped[str | None] = mapped_column(String(8), nullable=True, default="false")
    delivery_plan: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sys_domain: Mapped[str | None] = mapped_column(String(64), nullable=True, default="global")
    sys_domain_path: Mapped[str | None] = mapped_column(String(256), nullable=True, default="/")
    task_effective_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    other: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class ScItemOption(Base, LifecycleMixin):
    """Submitted variable value for a requested item."""

    __tablename__ = "sc_item_option"

    sys_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    item_option_new: Mapped[str] = mapped_column(String(32), index=True)
    sc_req_item: Mapped[str] = mapped_column(
        String(32), ForeignKey("sc_req_item.sys_id", ondelete="CASCADE"), index=True
    )
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    other: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class SysSecret(Base, LifecycleMixin):
    """Named credential for outbound integrations (referenced as {{secret:name}})."""

    __tablename__ = "sys_secret"

    sys_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    value: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    other: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class ScWebhook(Base, LifecycleMixin):
    """Standalone outbound webhook destination (reusable across catalog items)."""

    __tablename__ = "sc_webhook"

    sys_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), index=True)
    url: Mapped[str] = mapped_column(String(1024))
    method: Mapped[str] = mapped_column(String(8), default="POST")
    headers: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    secret: Mapped[str | None] = mapped_column(String(256), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    other: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class ScCatItemWebhook(Base, LifecycleMixin):
    """Attaches a standalone webhook to a catalog item with optional payload override."""

    __tablename__ = "sc_cat_item_webhook"

    sys_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    cat_item: Mapped[str] = mapped_column(
        String(32), ForeignKey("sc_cat_item.sys_id", ondelete="CASCADE"), index=True
    )
    webhook: Mapped[str] = mapped_column(
        String(32), ForeignKey("sc_webhook.sys_id", ondelete="CASCADE"), index=True
    )
    payload_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger_on: Mapped[str] = mapped_column(String(32), default="order")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    other: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class ScWebhookLog(Base, LifecycleMixin):
    """Delivery log for catalog item webhooks."""

    __tablename__ = "sc_webhook_log"

    sys_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    webhook_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("sc_webhook.sys_id", ondelete="CASCADE"), index=True
    )
    attachment_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    sc_req_item: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    other: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
