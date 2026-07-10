"""Optional lab environment seed — realistic ITIL demo data for local development."""

from __future__ import annotations

import argparse
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import delete, or_, select

from app import db, startup
from app.config import DEFAULT_LAB_ENV_FILE, Settings, resolve_env_file, settings_from_env_file
from app.domain.registry import TABLE_MODELS
from app.domain.table_service import _model_to_dict, create_record
from app.models import (
    ChangeRequest,
    ChangeTask,
    CmdbCi,
    CmdbRelCi,
    CmdbRelType,
    Incident,
    ItemOptionNew,
    Problem,
    ProblemTask,
    RecordAccessGrant,
    ScReqItem,
    ScRequest,
    ScTask,
    ServiceCatalog,
    ServiceCatalogItem,
    StdChangeProducerVersion,
    SysAttachment,
    SysComment,
    SysUser,
    SysUserGrMember,
    SysUserGroup,
)
from app.startup import run_migrations, seed_data
from app.utils.ids import new_sys_id

logger = logging.getLogger(__name__)

settings: Settings | None = None

LAB_MARKER_GROUP = "Service Desk"
LAB_USER_PASSWORD = "lab123"
LAB_PREFIX = "[LAB]"
LAB_CI_NAME_PREFIX = "lab-"

LAB_GROUP_NAMES = frozenset(
    {
        LAB_MARKER_GROUP,
        "Infrastructure & Operations",
        "Network Operations",
        "Server Engineering",
        "Application Support",
        "Change Advisory Board",
        "Security Operations",
    }
)

LAB_USER_NAMES = frozenset(
    {
        "jsmith",
        "mwilson",
        "lchen",
        "rpatel",
        "tchen",
        "drossi",
    }
)

_LAB_TICKET_MODELS: tuple[tuple[str, type[Any]], ...] = (
    ("sc_task", ScTask),
    ("sc_req_item", ScReqItem),
    ("sc_request", ScRequest),
    ("change_task", ChangeTask),
    ("change_request", ChangeRequest),
    ("problem_task", ProblemTask),
    ("problem", Problem),
    ("incident", Incident),
)


@dataclass
class LabContext:
    admin_id: str
    groups: dict[str, str] = field(default_factory=dict)
    users: dict[str, str] = field(default_factory=dict)
    cis: dict[str, str] = field(default_factory=dict)
    rel_types: dict[str, str] = field(default_factory=dict)
    std_change_id: str | None = None
    problems: dict[str, str] = field(default_factory=dict)
    changes: dict[str, str] = field(default_factory=dict)


async def is_lab_seeded() -> bool:
    """True when the full lab dataset (marker group + sample user) is present."""
    async with db.async_session_factory() as session:
        group = await session.execute(
            select(SysUserGroup).where(SysUserGroup.name == LAB_MARKER_GROUP)
        )
        if group.scalar_one_or_none() is None:
            return False
        user = await session.execute(select(SysUser).where(SysUser.user_name == "jsmith"))
        return user.scalar_one_or_none() is not None


async def _purge_lab_data(session) -> None:
    """Remove all records created by the lab seed (requires --force --hard)."""
    lab_user_ids = set(
        (
            await session.execute(
                select(SysUser.sys_id).where(SysUser.user_name.in_(LAB_USER_NAMES))
            )
        )
        .scalars()
        .all()
    )
    lab_group_ids = set(
        (
            await session.execute(
                select(SysUserGroup.sys_id).where(SysUserGroup.name.in_(LAB_GROUP_NAMES))
            )
        )
        .scalars()
        .all()
    )
    lab_ci_ids = set(
        (
            await session.execute(
                select(CmdbCi.sys_id).where(CmdbCi.name.like(f"{LAB_CI_NAME_PREFIX}%"))
            )
        )
        .scalars()
        .all()
    )

    records_by_table: dict[str, list[str]] = {}
    if lab_ci_ids:
        records_by_table["cmdb_ci"] = list(lab_ci_ids)

    for table_name, model in _LAB_TICKET_MODELS:
        sys_ids = (
            (
                await session.execute(
                    select(model.sys_id).where(model.short_description.like(f"{LAB_PREFIX}%"))
                )
            )
            .scalars()
            .all()
        )
        if sys_ids:
            records_by_table[table_name] = list(sys_ids)

    for table_name, sys_ids in records_by_table.items():
        await session.execute(
            delete(SysComment).where(
                SysComment.table_name == table_name,
                SysComment.record_sys_id.in_(sys_ids),
            )
        )
        await session.execute(
            delete(SysAttachment).where(
                SysAttachment.table_name == table_name,
                SysAttachment.table_sys_id.in_(sys_ids),
            )
        )
        await session.execute(
            delete(RecordAccessGrant).where(
                RecordAccessGrant.table_name == table_name,
                RecordAccessGrant.record_sys_id.in_(sys_ids),
            )
        )

    for _table_name, model in _LAB_TICKET_MODELS:
        await session.execute(delete(model).where(model.short_description.like(f"{LAB_PREFIX}%")))

    if lab_ci_ids:
        await session.execute(
            delete(CmdbRelCi).where(
                or_(CmdbRelCi.parent.in_(lab_ci_ids), CmdbRelCi.child.in_(lab_ci_ids))
            )
        )
        await session.execute(delete(CmdbCi).where(CmdbCi.sys_id.in_(lab_ci_ids)))

    membership_filters = []
    if lab_user_ids:
        membership_filters.append(SysUserGrMember.user_sys_id.in_(lab_user_ids))
    if lab_group_ids:
        membership_filters.append(SysUserGrMember.group_sys_id.in_(lab_group_ids))
    if membership_filters:
        await session.execute(delete(SysUserGrMember).where(or_(*membership_filters)))

    if lab_user_ids:
        await session.execute(delete(SysUser).where(SysUser.sys_id.in_(lab_user_ids)))
    if lab_group_ids:
        await session.execute(delete(SysUserGroup).where(SysUserGroup.sys_id.in_(lab_group_ids)))

    await session.flush()
    logger.info(
        "Purged lab seed data (%s CIs, %s users, %s groups)",
        len(lab_ci_ids),
        len(lab_user_ids),
        len(lab_group_ids),
    )


async def ensure_record(
    session,
    table: str,
    lookup: dict[str, str],
    payload: dict,
    admin_id: str,
) -> dict:
    """Return an existing row matching lookup or create it from payload."""
    model = TABLE_MODELS[table]
    query = select(model)
    for key, value in lookup.items():
        query = query.where(getattr(model, key) == value)
    existing = (await session.execute(query)).scalar_one_or_none()
    if existing:
        return _model_to_dict(existing, table, exclude_links=False)
    return await create_record(session, table, {**payload, **lookup}, admin_id)


async def _require_admin(session) -> str:
    result = await session.execute(
        select(SysUser).where(SysUser.user_name == _active_settings().admin_username)
    )
    admin = result.scalar_one_or_none()
    if not admin:
        raise RuntimeError(
            "Base seed data is missing. Start the backend once or run seed_data() "
            "before seeding the lab environment."
        )
    return str(admin.sys_id)


async def _load_rel_types(session) -> dict[str, str]:
    result = await session.execute(select(CmdbRelType))
    return {str(row.sys_name): str(row.sys_id) for row in result.scalars().all()}


async def _load_std_change(session) -> str | None:
    result = await session.execute(
        select(StdChangeProducerVersion).where(
            StdChangeProducerVersion.name == "Standard Server Patch"
        )
    )
    row = result.scalar_one_or_none()
    return row.sys_id if row else None


async def _seed_groups(session, ctx: LabContext) -> None:
    groups = [
        (LAB_MARKER_GROUP, "Tier 1 support — Acme Corp IT service desk"),
        ("Infrastructure & Operations", "Server, storage, and platform engineering"),
        ("Network Operations", "LAN, WAN, firewall, and routing"),
        ("Server Engineering", "Linux and Windows server administration"),
        ("Application Support", "Business application ownership and support"),
        ("Change Advisory Board", "Change review and approval"),
        ("Security Operations", "Security monitoring and incident response"),
    ]
    for name, description in groups:
        record = await ensure_record(
            session,
            "sys_user_group",
            {"name": name},
            {"name": name, "description": description},
            ctx.admin_id,
        )
        ctx.groups[name] = record["sys_id"]


async def _seed_users(session, ctx: LabContext) -> None:
    users = [
        ("jsmith", "Jane", "Smith", "jane.smith@acme.example", "Service Desk"),
        ("mwilson", "Mike", "Wilson", "mike.wilson@acme.example", "Server Engineering"),
        ("lchen", "Lisa", "Chen", "lisa.chen@acme.example", "Network Operations"),
        ("rpatel", "Raj", "Patel", "raj.patel@acme.example", "Application Support"),
        ("tchen", "Tom", "Chen", "tom.chen@acme.example", "Infrastructure & Operations"),
        ("drossi", "Dana", "Rossi", "dana.rossi@acme.example", "Security Operations"),
    ]
    for user_name, first, last, email, group_name in users:
        record = await ensure_record(
            session,
            "sys_user",
            {"user_name": user_name},
            {
                "user_name": user_name,
                "user_password": LAB_USER_PASSWORD,
                "first_name": first,
                "last_name": last,
                "email": email,
                "active": "true",
            },
            ctx.admin_id,
        )
        ctx.users[user_name] = record["sys_id"]
        await ensure_record(
            session,
            "sys_user_grmember",
            {
                "user_sys_id": record["sys_id"],
                "group_sys_id": ctx.groups[group_name],
            },
            {
                "user_sys_id": record["sys_id"],
                "group_sys_id": ctx.groups[group_name],
            },
            ctx.admin_id,
        )

    await ensure_record(
        session,
        "sys_user_grmember",
        {
            "user_sys_id": ctx.admin_id,
            "group_sys_id": ctx.groups["Change Advisory Board"],
        },
        {
            "user_sys_id": ctx.admin_id,
            "group_sys_id": ctx.groups["Change Advisory Board"],
        },
        ctx.admin_id,
    )


async def _seed_cmdb(session, ctx: LabContext) -> None:
    def ci_fields(
        name: str,
        *,
        os: str = "",
        os_version: str = "",
        vendor: str = "",
        classification: str = "Production",
    ) -> dict[str, str]:
        return {
            "host_name": name,
            "fqdn": f"{name}.lab.example.com",
            "classification": classification,
            "vendor": vendor,
            "os": os,
            "os_version": os_version,
        }

    cis = [
        {
            "key": "lab-web-01",
            "name": "lab-web-01",
            "sys_class_name": "cmdb_ci_linux_server",
            **ci_fields("lab-web-01", os="Linux", os_version="RHEL 9", vendor="Dell Inc."),
            "short_description": "RHEL 9 public web tier",
            "asset_tag": "SRV-LNX-001",
            "serial_number": "LNX9-WEB-88421",
            "install_status": "1",
            "operational_status": "1",
            "environment": "Production",
            "ip_address": "10.10.1.10",
            "mac_address": "00:1A:2B:3C:4D:01",
            "category": "Web",
            "assigned_to": ctx.users["mwilson"],
        },
        {
            "key": "lab-app-01",
            "name": "lab-app-01",
            "sys_class_name": "cmdb_ci_linux_server",
            **ci_fields("lab-app-01", os="Linux", os_version="Ubuntu 22.04", vendor="HPE"),
            "short_description": "Ubuntu 22.04 application server",
            "asset_tag": "SRV-LNX-002",
            "serial_number": "UBT-APP-55210",
            "install_status": "1",
            "operational_status": "1",
            "environment": "Production",
            "ip_address": "10.10.1.20",
            "mac_address": "00:1A:2B:3C:4D:02",
            "category": "Application",
            "assigned_to": ctx.users["mwilson"],
        },
        {
            "key": "lab-db-01",
            "name": "lab-db-01",
            "sys_class_name": "cmdb_ci_linux_server",
            **ci_fields("lab-db-01", os="Linux", os_version="RHEL 9", vendor="Dell Inc."),
            "short_description": "RHEL 9 PostgreSQL database server",
            "asset_tag": "SRV-LNX-003",
            "serial_number": "LNX9-DB-33109",
            "install_status": "1",
            "operational_status": "1",
            "environment": "Production",
            "ip_address": "10.10.1.30",
            "mac_address": "00:1A:2B:3C:4D:03",
            "category": "Database",
            "assigned_to": ctx.users["tchen"],
        },
        {
            "key": "lab-win-dc-01",
            "name": "lab-win-dc-01",
            "sys_class_name": "cmdb_ci_win_server",
            **ci_fields(
                "lab-win-dc-01",
                os="Windows",
                os_version="Windows Server 2022",
                vendor="Microsoft",
            ),
            "short_description": "Windows Server 2022 domain controller",
            "asset_tag": "SRV-WIN-001",
            "serial_number": "WIN-DC-90214",
            "install_status": "1",
            "operational_status": "1",
            "environment": "Production",
            "ip_address": "10.10.2.10",
            "mac_address": "00:1A:2B:3C:4E:01",
            "category": "Directory Services",
            "assigned_to": ctx.users["mwilson"],
        },
        {
            "key": "lab-win-file-01",
            "name": "lab-win-file-01",
            "sys_class_name": "cmdb_ci_win_server",
            **ci_fields(
                "lab-win-file-01",
                os="Windows",
                os_version="Windows Server 2019",
                vendor="Microsoft",
            ),
            "short_description": "Windows Server 2019 file and print server",
            "asset_tag": "SRV-WIN-002",
            "serial_number": "WIN-FILE-44102",
            "install_status": "1",
            "operational_status": "1",
            "environment": "Production",
            "ip_address": "10.10.2.20",
            "mac_address": "00:1A:2B:3C:4E:02",
            "category": "File Services",
            "assigned_to": ctx.users["mwilson"],
        },
        {
            "key": "lab-router-edge-01",
            "name": "lab-router-edge-01",
            "sys_class_name": "cmdb_ci_router",
            **ci_fields("lab-router-edge-01", os="IOS", os_version="17.3", vendor="Cisco"),
            "short_description": "Cisco ISR edge router",
            "asset_tag": "NET-RTR-001",
            "serial_number": "CISCO-ISR-7781",
            "install_status": "1",
            "operational_status": "1",
            "environment": "Production",
            "ip_address": "10.10.0.1",
            "category": "Routing",
            "assigned_to": ctx.users["lchen"],
        },
        {
            "key": "lab-sw-core-01",
            "name": "lab-sw-core-01",
            "sys_class_name": "cmdb_ci_switch",
            **ci_fields("lab-sw-core-01", os="IOS-XE", os_version="17.9", vendor="Cisco"),
            "short_description": "Core datacenter switch stack",
            "asset_tag": "NET-SW-001",
            "serial_number": "CISCO-C9300-2201",
            "install_status": "1",
            "operational_status": "1",
            "environment": "Production",
            "ip_address": "10.10.0.2",
            "category": "Switching",
            "assigned_to": ctx.users["lchen"],
        },
        {
            "key": "lab-fw-01",
            "name": "lab-fw-01",
            "sys_class_name": "cmdb_ci_ip_firewall",
            **ci_fields("lab-fw-01", os="PAN-OS", os_version="11.1", vendor="Palo Alto Networks"),
            "short_description": "Perimeter firewall — HQ datacenter",
            "asset_tag": "NET-FW-001",
            "serial_number": "PA-5220-1104",
            "install_status": "1",
            "operational_status": "1",
            "environment": "Production",
            "ip_address": "10.10.0.254",
            "category": "Security",
            "assigned_to": ctx.users["lchen"],
        },
        {
            "key": "lab-sw-access-02",
            "name": "lab-sw-access-02",
            "sys_class_name": "cmdb_ci_switch",
            **ci_fields("lab-sw-access-02", os="IOS-XE", os_version="17.6", vendor="Cisco"),
            "short_description": "Access layer switch — Building B",
            "asset_tag": "NET-SW-002",
            "serial_number": "CISCO-C9200-8840",
            "install_status": "1",
            "operational_status": "3",
            "environment": "Production",
            "ip_address": "10.10.0.12",
            "category": "Switching",
            "assigned_to": ctx.users["lchen"],
        },
    ]
    for ci in cis:
        key = ci.pop("key")
        name = ci["name"]
        record = await ensure_record(
            session,
            "cmdb_ci",
            {"name": name},
            ci,
            ctx.admin_id,
        )
        ctx.cis[key] = record["sys_id"]


async def _seed_cmdb_relationships(session, ctx: LabContext) -> None:
    runs_on = ctx.rel_types.get("Runs on::Runs")
    depends_on = ctx.rel_types.get("Depends on::Used by")
    contains = ctx.rel_types.get("Contains::Contained by")
    if not runs_on or not depends_on or not contains:
        logger.warning("CMDB relationship types missing; skipping CI relationships")
        return

    relationships = [
        (ctx.cis["lab-web-01"], ctx.cis["lab-app-01"], runs_on),
        (ctx.cis["lab-app-01"], ctx.cis["lab-db-01"], depends_on),
        (ctx.cis["lab-win-file-01"], ctx.cis["lab-win-dc-01"], depends_on),
        (ctx.cis["lab-router-edge-01"], ctx.cis["lab-fw-01"], contains),
        (ctx.cis["lab-fw-01"], ctx.cis["lab-sw-core-01"], contains),
        (ctx.cis["lab-sw-core-01"], ctx.cis["lab-sw-access-02"], contains),
        (ctx.cis["lab-sw-core-01"], ctx.cis["lab-web-01"], contains),
        (ctx.cis["lab-sw-core-01"], ctx.cis["lab-app-01"], contains),
    ]
    for parent, child, rel_type in relationships:
        await ensure_record(
            session,
            "cmdb_rel_ci",
            {"parent": parent, "child": child, "type": rel_type},
            {"parent": parent, "child": child, "type": rel_type},
            ctx.admin_id,
        )


async def _seed_incidents(session, ctx: LabContext) -> None:
    desk = ctx.groups[LAB_MARKER_GROUP]
    network = ctx.groups["Network Operations"]
    server = ctx.groups["Server Engineering"]
    app_support = ctx.groups["Application Support"]

    incidents = [
        {
            "short_description": f"{LAB_PREFIX} VPN connectivity failures for remote users",
            "description": "Multiple remote users report VPN disconnects every 15-20 minutes since last firewall policy push.",
            "state": "2",
            "impact": "2",
            "urgency": "1",
            "priority": "2",
            "caller_id": ctx.users["rpatel"],
            "assigned_to": ctx.users["lchen"],
            "assignment_group": network,
        },
        {
            "short_description": f"{LAB_PREFIX} Corporate email delivery delays",
            "description": "Inbound mail queue backing up on lab-win-dc-01. Affecting executive assistants.",
            "state": "2",
            "impact": "2",
            "urgency": "2",
            "priority": "3",
            "caller_id": ctx.users["jsmith"],
            "assigned_to": ctx.users["mwilson"],
            "assignment_group": server,
        },
        {
            "short_description": f"{LAB_PREFIX} Building B Wi-Fi intermittent drops",
            "description": "Users on floor 3 report frequent disconnects. lab-sw-access-02 shows elevated CPU.",
            "state": "1",
            "impact": "3",
            "urgency": "2",
            "priority": "4",
            "caller_id": ctx.users["jsmith"],
            "assignment_group": network,
        },
        {
            "short_description": f"{LAB_PREFIX} ERP batch job failure overnight",
            "description": "Nightly inventory sync failed on lab-app-01. Finance team blocked for morning close.",
            "state": "3",
            "impact": "1",
            "urgency": "1",
            "priority": "1",
            "caller_id": ctx.users["rpatel"],
            "assigned_to": ctx.users["rpatel"],
            "assignment_group": app_support,
            "hold_reason": "1",
        },
        {
            "short_description": f"{LAB_PREFIX} Public website slow response times",
            "description": "lab-web-01 response time exceeded 5s during peak hours. Resolved after cache flush.",
            "state": "6",
            "impact": "2",
            "urgency": "2",
            "priority": "3",
            "caller_id": ctx.users["tchen"],
            "assigned_to": ctx.users["mwilson"],
            "assignment_group": server,
            "close_code": "Solution provided",
            "close_notes": "Restarted nginx and cleared reverse-proxy cache.",
        },
        {
            "short_description": f"{LAB_PREFIX} New hire laptop provisioning",
            "description": "Standard onboarding request for sales team member.",
            "state": "7",
            "impact": "3",
            "urgency": "3",
            "priority": "4",
            "caller_id": ctx.users["jsmith"],
            "assigned_to": ctx.users["jsmith"],
            "assignment_group": desk,
            "close_code": "Resolved",
            "close_notes": "Laptop imaged and delivered.",
        },
        {
            "short_description": f"{LAB_PREFIX} Printer offline — 4th floor",
            "description": "User cannot print to shared MFP. Ticket canceled — user power-cycled printer.",
            "state": "8",
            "impact": "3",
            "urgency": "3",
            "priority": "4",
            "caller_id": ctx.users["jsmith"],
            "assignment_group": desk,
            "close_code": "Canceled",
            "close_notes": "User resolved locally.",
        },
    ]
    for incident in incidents:
        await ensure_record(
            session,
            "incident",
            {"short_description": incident["short_description"]},
            incident,
            ctx.admin_id,
        )


async def _seed_problems(session, ctx: LabContext) -> None:
    network = ctx.groups["Network Operations"]
    server = ctx.groups["Server Engineering"]

    vpn_problem = await ensure_record(
        session,
        "problem",
        {"short_description": f"{LAB_PREFIX} Recurring VPN session drops"},
        {
            "short_description": f"{LAB_PREFIX} Recurring VPN session drops",
            "description": "Pattern of VPN disconnects correlates with firewall failover events on lab-fw-01.",
            "state": "2",
            "impact": "2",
            "urgency": "2",
            "priority": "3",
            "assigned_to": ctx.users["lchen"],
            "assignment_group": network,
        },
        ctx.admin_id,
    )
    ctx.problems["vpn"] = vpn_problem["sys_id"]

    disk_problem = await ensure_record(
        session,
        "problem",
        {"short_description": f"{LAB_PREFIX} Disk space exhaustion on application servers"},
        {
            "short_description": f"{LAB_PREFIX} Disk space exhaustion on application servers",
            "description": "Log rotation misconfiguration caused /var/log to fill on Linux app tier.",
            "state": "7",
            "impact": "2",
            "urgency": "2",
            "priority": "3",
            "assigned_to": ctx.users["mwilson"],
            "assignment_group": server,
            "resolution_code": "Fix applied",
            "cause_notes": "logrotate config omitted application log paths.",
            "fix_notes": "Updated logrotate.d entries and deployed monitoring alert at 85% utilization.",
            "close_notes": "No recurrence in 30 days.",
        },
        ctx.admin_id,
    )
    ctx.problems["disk"] = disk_problem["sys_id"]

    await ensure_record(
        session,
        "problem_task",
        {"short_description": f"{LAB_PREFIX} Capture firewall logs during VPN failover"},
        {
            "short_description": f"{LAB_PREFIX} Capture firewall logs during VPN failover",
            "description": "Enable verbose logging on lab-fw-01 and collect 48h of session data.",
            "state": "2",
            "problem": ctx.problems["vpn"],
            "problem_task_type": "investigation",
            "cmdb_ci": ctx.cis["lab-fw-01"],
            "assigned_to": ctx.users["lchen"],
            "assignment_group": network,
            "priority": "3",
        },
        ctx.admin_id,
    )
    await ensure_record(
        session,
        "problem_task",
        {"short_description": f"{LAB_PREFIX} Audit logrotate configs on Linux fleet"},
        {
            "short_description": f"{LAB_PREFIX} Audit logrotate configs on Linux fleet",
            "description": "Review logrotate on lab-app-01, lab-web-01, and lab-db-01.",
            "state": "7",
            "problem": ctx.problems["disk"],
            "problem_task_type": "remediation",
            "cmdb_ci": ctx.cis["lab-app-01"],
            "assigned_to": ctx.users["mwilson"],
            "assignment_group": server,
            "priority": "4",
        },
        ctx.admin_id,
    )


async def _seed_changes(session, ctx: LabContext) -> None:
    server = ctx.groups["Server Engineering"]
    network = ctx.groups["Network Operations"]
    cab = ctx.groups["Change Advisory Board"]

    patch_change = await ensure_record(
        session,
        "change_request",
        {"short_description": f"{LAB_PREFIX} Monthly Linux security patching — production"},
        {
            "short_description": f"{LAB_PREFIX} Monthly Linux security patching — production",
            "description": "Apply vendor security updates to lab-web-01, lab-app-01, and lab-db-01.",
            "state": "-2",
            "type": "standard",
            "chg_model": "normal",
            "impact": "2",
            "urgency": "2",
            "priority": "3",
            "risk": "3",
            "category": "Server",
            "requested_by": ctx.users["tchen"],
            "assigned_to": ctx.users["mwilson"],
            "assignment_group": server,
            "std_change_producer_version": ctx.std_change_id or "",
        },
        ctx.admin_id,
    )
    ctx.changes["patch"] = patch_change["sys_id"]

    await ensure_record(
        session,
        "change_task",
        {"short_description": f"{LAB_PREFIX} Patch lab-web-01"},
        {
            "short_description": f"{LAB_PREFIX} Patch lab-web-01",
            "description": "Apply updates and reboot during maintenance window.",
            "state": "1",
            "change_request": ctx.changes["patch"],
            "change_task_type": "implementation",
            "cmdb_ci": ctx.cis["lab-web-01"],
            "assigned_to": ctx.users["mwilson"],
            "assignment_group": server,
            "planned_start_date": "2026-06-14T02:00:00Z",
            "planned_end_date": "2026-06-14T04:00:00Z",
        },
        ctx.admin_id,
    )
    await ensure_record(
        session,
        "change_task",
        {"short_description": f"{LAB_PREFIX} Patch lab-app-01 and lab-db-01"},
        {
            "short_description": f"{LAB_PREFIX} Patch lab-app-01 and lab-db-01",
            "description": "Rolling patch sequence for application tier.",
            "state": "1",
            "change_request": ctx.changes["patch"],
            "change_task_type": "implementation",
            "cmdb_ci": ctx.cis["lab-app-01"],
            "assigned_to": ctx.users["mwilson"],
            "assignment_group": server,
            "planned_start_date": "2026-06-14T04:00:00Z",
            "planned_end_date": "2026-06-14T06:00:00Z",
        },
        ctx.admin_id,
    )

    fw_change = await ensure_record(
        session,
        "change_request",
        {"short_description": f"{LAB_PREFIX} Emergency firewall rule — vendor support access"},
        {
            "short_description": f"{LAB_PREFIX} Emergency firewall rule — vendor support access",
            "description": "Temporary allow rule for vendor IP to access lab-fw-01 management interface.",
            "state": "-5",
            "type": "emergency",
            "chg_model": "emergency",
            "impact": "2",
            "urgency": "1",
            "priority": "2",
            "risk": "2",
            "category": "Network",
            "requested_by": ctx.users["lchen"],
            "assignment_group": network,
        },
        ctx.admin_id,
    )
    ctx.changes["firewall"] = fw_change["sys_id"]

    await ensure_record(
        session,
        "change_request",
        {"short_description": f"{LAB_PREFIX} Replace failed access switch in Building B"},
        {
            "short_description": f"{LAB_PREFIX} Replace failed access switch in Building B",
            "description": "RMA replacement for lab-sw-access-02. Completed during weekend maintenance.",
            "state": "0",
            "type": "normal",
            "chg_model": "normal",
            "impact": "2",
            "urgency": "2",
            "priority": "3",
            "risk": "3",
            "category": "Network",
            "requested_by": ctx.users["lchen"],
            "assigned_to": ctx.users["lchen"],
            "assignment_group": network,
            "close_notes": "Switch replaced; monitoring green for 72 hours.",
        },
        ctx.admin_id,
    )

    await ensure_record(
        session,
        "change_request",
        {"short_description": f"{LAB_PREFIX} CAB review — datacenter network core upgrade"},
        {
            "short_description": f"{LAB_PREFIX} CAB review — datacenter network core upgrade",
            "description": "Proposal to upgrade lab-sw-core-01 firmware during Q3 maintenance window.",
            "state": "-4",
            "type": "normal",
            "chg_model": "normal",
            "impact": "1",
            "urgency": "3",
            "priority": "3",
            "risk": "2",
            "category": "Network",
            "requested_by": ctx.users["tchen"],
            "assignment_group": cab,
        },
        ctx.admin_id,
    )


async def _seed_catalog_items(session, ctx: LabContext) -> None:
    """Seed catalog items with form variables (Provision VM demo)."""
    catalog_result = await session.execute(
        select(ServiceCatalog).where(ServiceCatalog.title == "IT Services")
    )
    catalog = catalog_result.scalar_one_or_none()
    if not catalog:
        catalog = ServiceCatalog(
            sys_id=new_sys_id(),
            title="IT Services",
            description="Standard IT service catalog",
            active=True,
        )
        session.add(catalog)
        await session.flush()

    infra_group = ctx.groups.get("Infrastructure & Operations")
    provision_desc = (
        "### Order a virtual machine which will be deployed to AWS\n\n"
        "- EC2 instance created in AWS from RHEL base image\n"
        "- CI created in CMDB\n"
        "- Latest patches applied\n"
        "- Apache httpd installed\n"
        "- Default website deployed\n"
    )

    existing_item = await session.execute(
        select(ServiceCatalogItem).where(
            ServiceCatalogItem.catalog_sys_id == catalog.sys_id,
            ServiceCatalogItem.name == "Provision VM",
        )
    )
    item = existing_item.scalar_one_or_none()
    if not item:
        item = ServiceCatalogItem(
            sys_id=new_sys_id(),
            catalog_sys_id=catalog.sys_id,
            name="Provision VM",
            short_description="Order a virtual machine which will be deployed to AWS",
            description=provision_desc,
            active=True,
            price="0",
            category="Infrastructure",
            subcategory="Compute",
            fulfillment_group=infra_group,
            order=10,
        )
        session.add(item)
        await session.flush()
    else:
        item.short_description = "Order a virtual machine which will be deployed to AWS"
        item.description = provision_desc
        item.fulfillment_group = infra_group
        item.category = "Infrastructure"
        item.subcategory = "Compute"
        item.active = True
        await session.flush()

    variables = [
        {
            "name": "sn_vm_name",
            "question_text": "Name of server",
            "type": "string",
            "mandatory": True,
            "order": 100,
            "choice_list": [],
        },
        {
            "name": "sn_target_platform",
            "question_text": "Target Platform",
            "type": "select_box",
            "mandatory": True,
            "order": 200,
            "choice_list": [
                {"value": "rhel_10", "label": "RHEL 10"},
                {"value": "rhel_9", "label": "RHEL 9"},
                {"value": "windows_22", "label": "Windows Server 2022"},
            ],
        },
        {
            "name": "sn_aws_region",
            "question_text": "AWS Region",
            "type": "select_box",
            "mandatory": True,
            "order": 300,
            "choice_list": [
                {"value": "us-east-2", "label": "us-east-2"},
                {"value": "us-west-1", "label": "us-west-1"},
            ],
        },
    ]
    for var in variables:
        existing_var = await session.execute(
            select(ItemOptionNew).where(
                ItemOptionNew.cat_item == item.sys_id,
                ItemOptionNew.name == var["name"],
            )
        )
        row = existing_var.scalar_one_or_none()
        if row:
            row.question_text = var["question_text"]
            row.type = var["type"]
            row.mandatory = var["mandatory"]
            row.order = var["order"]
            row.choice_list = var["choice_list"]
            row.active = True
        else:
            session.add(
                ItemOptionNew(
                    sys_id=new_sys_id(),
                    cat_item=item.sys_id,
                    name=var["name"],
                    question_text=var["question_text"],
                    type=var["type"],
                    mandatory=var["mandatory"],
                    order=var["order"],
                    choice_list=var["choice_list"],
                    active=True,
                )
            )
    await session.flush()


async def _seed_service_requests(session, ctx: LabContext) -> None:
    desk = ctx.groups[LAB_MARKER_GROUP]

    laptop_req = await ensure_record(
        session,
        "sc_request",
        {"short_description": f"{LAB_PREFIX} New laptop for sales hire"},
        {
            "short_description": f"{LAB_PREFIX} New laptop for sales hire",
            "description": 'MacBook Pro 14" for regional sales representative starting next week.',
            "state": "2",
            "requested_for": ctx.users["rpatel"],
            "requested_by": ctx.users["jsmith"],
            "assignment_group": desk,
            "assigned_to": ctx.users["jsmith"],
        },
        ctx.admin_id,
    )
    await ensure_record(
        session,
        "sc_task",
        {"short_description": f"{LAB_PREFIX} Procure and image laptop"},
        {
            "short_description": f"{LAB_PREFIX} Procure and image laptop",
            "description": "Order hardware, enroll in MDM, install sales tooling.",
            "state": "2",
            "request": laptop_req["sys_id"],
            "assigned_to": ctx.users["jsmith"],
            "assignment_group": desk,
        },
        ctx.admin_id,
    )

    vpn_req = await ensure_record(
        session,
        "sc_request",
        {"short_description": f"{LAB_PREFIX} VPN access for contractor"},
        {
            "short_description": f"{LAB_PREFIX} VPN access for contractor",
            "description": "90-day VPN access for external audit contractor.",
            "state": "1",
            "requested_for": ctx.users["drossi"],
            "requested_by": ctx.users["tchen"],
            "assignment_group": desk,
        },
        ctx.admin_id,
    )
    await ensure_record(
        session,
        "sc_task",
        {"short_description": f"{LAB_PREFIX} Provision VPN profile"},
        {
            "short_description": f"{LAB_PREFIX} Provision VPN profile",
            "description": "Create contractor AD account and distribute VPN client profile.",
            "state": "1",
            "request": vpn_req["sys_id"],
            "assignment_group": desk,
        },
        ctx.admin_id,
    )


def configure_runtime(env_file: str) -> Settings:
    """Load settings from env_file and wire DB/startup to that database."""
    global settings
    settings = settings_from_env_file(env_file)
    db.configure_database(settings.database_url)
    startup.settings = settings
    return settings


def _active_settings() -> Settings:
    if settings is None:
        raise RuntimeError("Call configure_runtime() before seed_lab()")
    return settings


async def seed_lab(*, ensure_base: bool = True, force: bool = False, hard: bool = False) -> bool:
    """Seed a realistic lab IT environment. Returns True if seeding ran."""
    if hard and not force:
        raise ValueError("--hard requires --force")

    if ensure_base:
        await run_migrations()
        await seed_data()
        await startup.ensure_cmdb_class_metadata()

    if not force and await is_lab_seeded():
        logger.info("Lab environment already seeded; skipping")
        return False

    async with db.async_session_factory() as session:
        if hard:
            await _purge_lab_data(session)

        admin_id = await _require_admin(session)
        ctx = LabContext(admin_id=admin_id)
        ctx.rel_types = await _load_rel_types(session)
        ctx.std_change_id = await _load_std_change(session)

        await _seed_groups(session, ctx)
        await _seed_users(session, ctx)
        await _seed_cmdb(session, ctx)
        await _seed_cmdb_relationships(session, ctx)
        await _seed_incidents(session, ctx)
        await _seed_problems(session, ctx)
        await _seed_changes(session, ctx)
        await _seed_catalog_items(session, ctx)
        await _seed_service_requests(session, ctx)

        await session.commit()

    logger.info("Lab environment seeded successfully")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed OpenFlake with a realistic ITIL lab environment (Acme Corp)."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run lab seed even when it appears complete (idempotent — fills gaps, no duplicates)",
    )
    parser.add_argument(
        "--hard",
        action="store_true",
        help="With --force, delete existing lab seed data before re-seeding from scratch",
    )
    parser.add_argument(
        "--skip-base",
        action="store_true",
        help="Do not run base migrations/seed; require admin user to already exist",
    )
    parser.add_argument(
        "--env-file",
        default=str(DEFAULT_LAB_ENV_FILE.name),
        metavar="PATH",
        help=f"Env file to load (default: {DEFAULT_LAB_ENV_FILE.name} under backend/)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    try:
        configure_runtime(args.env_file)
    except FileNotFoundError as exc:
        parser.error(str(exc))

    if args.hard and not args.force:
        parser.error("--hard requires --force")

    logger.info("Using env file: %s", resolve_env_file(args.env_file))

    created = asyncio.run(
        seed_lab(ensure_base=not args.skip_base, force=args.force, hard=args.hard)
    )
    if created:
        print("Lab environment seeded.")
        if args.hard:
            print("  Previous lab data was removed before seeding.")
        print(f"  Lab users password: {LAB_USER_PASSWORD}")
        print("  Sample users: jsmith, mwilson, lchen, rpatel")
        print(f"  Records prefixed with: {LAB_PREFIX}")
    else:
        print("Lab seed skipped — data already present. Use --force to re-run idempotent seed.")
        if not args.force:
            print("  Use --force --hard to wipe lab data and re-seed from scratch.")


if __name__ == "__main__":
    main()
