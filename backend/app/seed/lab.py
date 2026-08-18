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
            "std_change_producer_version": ctx.std_change_id,
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
            "cmdb_ci": ctx.cis["lab-fw-01"],
        },
        ctx.admin_id,
    )
    ctx.changes["firewall"] = fw_change["sys_id"]

    await ensure_record(
        session,
        "change_task",
        {"short_description": f"{LAB_PREFIX} Apply temporary ACL on lab-fw-01"},
        {
            "short_description": f"{LAB_PREFIX} Apply temporary ACL on lab-fw-01",
            "description": "Add scoped allow rule for vendor support IP range.",
            "state": "-5",
            "change_request": ctx.changes["firewall"],
            "change_task_type": "implementation",
            "cmdb_ci": ctx.cis["lab-fw-01"],
            "assigned_to": ctx.users["lchen"],
            "assignment_group": network,
        },
        ctx.admin_id,
    )

    switch_change = await ensure_record(
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
            "cmdb_ci": ctx.cis["lab-sw-access-02"],
        },
        ctx.admin_id,
    )
    ctx.changes["switch"] = switch_change["sys_id"]

    await ensure_record(
        session,
        "change_task",
        {"short_description": f"{LAB_PREFIX} Swap failed access switch hardware"},
        {
            "short_description": f"{LAB_PREFIX} Swap failed access switch hardware",
            "description": "Physically replace lab-sw-access-02 and restore saved config.",
            "state": "3",
            "change_request": ctx.changes["switch"],
            "change_task_type": "implementation",
            "cmdb_ci": ctx.cis["lab-sw-access-02"],
            "assigned_to": ctx.users["lchen"],
            "assignment_group": network,
        },
        ctx.admin_id,
    )

    cab_change = await ensure_record(
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
            "cmdb_ci": ctx.cis["lab-sw-core-01"],
        },
        ctx.admin_id,
    )
    ctx.changes["cab"] = cab_change["sys_id"]

    await ensure_record(
        session,
        "change_task",
        {"short_description": f"{LAB_PREFIX} Schedule core switch firmware maintenance window"},
        {
            "short_description": f"{LAB_PREFIX} Schedule core switch firmware maintenance window",
            "description": "Coordinate with network operations to book a Q3 maintenance window.",
            "state": "-5",
            "change_request": ctx.changes["cab"],
            "change_task_type": "planning",
            "cmdb_ci": ctx.cis["lab-sw-core-01"],
            "assigned_to": ctx.users["lchen"],
            "assignment_group": cab,
        },
        ctx.admin_id,
    )


def _choices(pairs: list[tuple[str, str]]) -> list[dict]:
    """Build a select_box/multi_select choice_list from (value, label) pairs."""
    return [{"value": value, "label": label} for value, label in pairs]


async def _upsert_catalog_item(
    session,
    catalog: ServiceCatalog,
    *,
    name: str,
    short_description: str,
    description: str,
    category: str | None,
    subcategory: str | None,
    fulfillment_group: str | None,
    order: int,
    variables: list[dict],
) -> ServiceCatalogItem:
    """Create or update a catalog item and its variables idempotently."""
    existing = await session.execute(
        select(ServiceCatalogItem).where(
            ServiceCatalogItem.catalog_sys_id == catalog.sys_id,
            ServiceCatalogItem.name == name,
        )
    )
    item: ServiceCatalogItem | None = existing.scalar_one_or_none()
    if not item:
        item = ServiceCatalogItem(sys_id=new_sys_id(), catalog_sys_id=catalog.sys_id, name=name)
        session.add(item)

    item.short_description = short_description
    item.description = description
    item.category = category
    item.subcategory = subcategory
    item.fulfillment_group = fulfillment_group
    item.order = order
    item.active = True
    item.price = "0"
    await session.flush()

    for var in variables:
        existing_var = await session.execute(
            select(ItemOptionNew).where(
                ItemOptionNew.cat_item == item.sys_id,
                ItemOptionNew.name == var["name"],
            )
        )
        row = existing_var.scalar_one_or_none()
        fields = {
            "question_text": var["question_text"],
            "type": var["type"],
            "mandatory": var.get("mandatory", False),
            "order": var.get("order", 100),
            "choice_list": var.get("choice_list", []),
            "default_value": var.get("default_value"),
            "reference_table": var.get("reference_table"),
            "help_text": var.get("help_text"),
            "read_only": var.get("read_only", False),
        }
        if row:
            for key, value in fields.items():
                setattr(row, key, value)
            row.active = True
        else:
            session.add(
                ItemOptionNew(
                    sys_id=new_sys_id(),
                    cat_item=item.sys_id,
                    name=var["name"],
                    active=True,
                    **fields,
                )
            )
    await session.flush()
    return item


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

    desk_group = ctx.groups.get(LAB_MARKER_GROUP)
    network_group = ctx.groups.get("Network Operations")
    security_group = ctx.groups.get("Security Operations")
    app_support_group = ctx.groups.get("Application Support")

    other_items: list[dict] = [
        # Uncategorized — no category/subcategory.
        {
            "name": "Password Reset Self-Service",
            "short_description": "Reset your own network or application password",
            "description": (
                "### Reset a forgotten or expired password\n\n"
                "- Identity verified via MFA challenge\n"
                "- Password synced across AD and SSO\n"
                "- Notification sent on completion\n"
            ),
            "category": None,
            "subcategory": None,
            "fulfillment_group": desk_group,
            "order": 5,
            "variables": [
                {
                    "name": "username",
                    "question_text": "Username",
                    "type": "string",
                    "mandatory": True,
                    "order": 100,
                },
                {
                    "name": "reset_reason",
                    "question_text": "Reason for reset",
                    "type": "select_box",
                    "mandatory": True,
                    "order": 200,
                    "choice_list": _choices(
                        [
                            ("forgotten", "Forgotten"),
                            ("compromised", "Compromised"),
                            ("expired", "Expired"),
                            ("other", "Other"),
                        ]
                    ),
                },
                {
                    "name": "notify_email",
                    "question_text": "Alternate notification email",
                    "type": "email",
                    "mandatory": False,
                    "order": 300,
                    "help_text": "Optional address to notify once the reset completes",
                },
            ],
        },
        # Hardware — single item, no subcategory.
        {
            "name": "New Laptop Request",
            "short_description": "Request a new laptop",
            "description": (
                "### Request a standard corporate laptop for a new or existing employee\n\n"
                "- Procured and imaged with the standard build\n"
                "- Enrolled in MDM\n"
                "- Shipped or handed off to the requestor\n"
            ),
            "category": "Hardware",
            "subcategory": None,
            "fulfillment_group": desk_group,
            "order": 10,
            "variables": [
                {
                    "name": "laptop_model",
                    "question_text": "Laptop model",
                    "type": "select_box",
                    "mandatory": True,
                    "order": 100,
                    "choice_list": _choices(
                        [
                            ("mbp14", 'MacBook Pro 14"'),
                            ("mbp16", 'MacBook Pro 16"'),
                            ("thinkpad_x1", "ThinkPad X1 Carbon"),
                            ("dell_xps15", "Dell XPS 15"),
                        ]
                    ),
                },
                {
                    "name": "business_justification",
                    "question_text": "Business justification",
                    "type": "text_area",
                    "mandatory": True,
                    "order": 200,
                },
                {
                    "name": "needed_by",
                    "question_text": "Needed by",
                    "type": "date",
                    "mandatory": True,
                    "order": 300,
                },
                {
                    "name": "include_dock",
                    "question_text": "Include docking station",
                    "type": "boolean",
                    "mandatory": False,
                    "order": 400,
                    "default_value": "false",
                },
                {
                    "name": "ship_to_office",
                    "question_text": "Ship to office (uncheck to ship home)",
                    "type": "boolean",
                    "mandatory": False,
                    "order": 500,
                    "default_value": "true",
                },
            ],
        },
        # Network — multiple items, no subcategories.
        {
            "name": "VPN Access",
            "short_description": "Request VPN access",
            "description": (
                "### Request remote VPN access for corporate network resources\n\n"
                "- Profile provisioned in the VPN concentrator\n"
                "- Access reviewed on the requested expiry date\n"
            ),
            "category": "Network",
            "subcategory": None,
            "fulfillment_group": network_group,
            "order": 10,
            "variables": [
                {
                    "name": "vpn_profile",
                    "question_text": "VPN profile",
                    "type": "select_box",
                    "mandatory": True,
                    "order": 100,
                    "choice_list": _choices(
                        [
                            ("corporate", "Corporate"),
                            ("development", "Development"),
                            ("production", "Production"),
                        ]
                    ),
                },
                {
                    "name": "requestor_email",
                    "question_text": "Requestor email",
                    "type": "email",
                    "mandatory": True,
                    "order": 200,
                },
                {
                    "name": "permanent_access",
                    "question_text": "Permanent access",
                    "type": "boolean",
                    "mandatory": False,
                    "order": 300,
                },
                {
                    "name": "expiry_date",
                    "question_text": "Access expiry date",
                    "type": "date",
                    "mandatory": False,
                    "order": 400,
                    "help_text": "Leave blank for permanent access",
                },
            ],
        },
        {
            "name": "Firewall Rule Change",
            "short_description": "Request a firewall rule addition or change",
            "description": (
                "### Request a firewall rule addition, removal, or modification\n\n"
                "- Reviewed by Network Operations\n"
                "- Applied during the next change window\n"
            ),
            "category": "Network",
            "subcategory": None,
            "fulfillment_group": network_group,
            "order": 20,
            "variables": [
                {
                    "name": "rule_action",
                    "question_text": "Action",
                    "type": "select_box",
                    "mandatory": True,
                    "order": 100,
                    "choice_list": _choices(
                        [
                            ("allow", "Allow"),
                            ("deny", "Deny"),
                            ("modify", "Modify existing"),
                        ]
                    ),
                },
                {
                    "name": "source_cidr",
                    "question_text": "Source CIDR",
                    "type": "string",
                    "mandatory": True,
                    "order": 200,
                },
                {
                    "name": "destination_cidr",
                    "question_text": "Destination CIDR",
                    "type": "string",
                    "mandatory": True,
                    "order": 300,
                },
                {
                    "name": "port_range",
                    "question_text": "Port range",
                    "type": "string",
                    "mandatory": True,
                    "order": 400,
                    "help_text": "e.g. 443 or 8080-8090",
                },
                {
                    "name": "protocol",
                    "question_text": "Protocol",
                    "type": "select_box",
                    "mandatory": True,
                    "order": 500,
                    "choice_list": _choices(
                        [
                            ("tcp", "TCP"),
                            ("udp", "UDP"),
                            ("icmp", "ICMP"),
                        ]
                    ),
                },
                {
                    "name": "change_justification",
                    "question_text": "Change justification",
                    "type": "text_area",
                    "mandatory": True,
                    "order": 600,
                },
            ],
        },
        {
            "name": "Request DNS Record",
            "short_description": "Request a new or updated DNS record",
            "description": (
                "### Request a new or updated DNS record\n\n"
                "- Created in the internal or external DNS zone\n"
                "- Propagation verified before closure\n"
            ),
            "category": "Network",
            "subcategory": None,
            "fulfillment_group": network_group,
            "order": 30,
            "variables": [
                {
                    "name": "record_type",
                    "question_text": "Record type",
                    "type": "select_box",
                    "mandatory": True,
                    "order": 100,
                    "choice_list": _choices(
                        [
                            ("a", "A"),
                            ("aaaa", "AAAA"),
                            ("cname", "CNAME"),
                            ("mx", "MX"),
                            ("txt", "TXT"),
                        ]
                    ),
                },
                {
                    "name": "hostname",
                    "question_text": "Hostname",
                    "type": "string",
                    "mandatory": True,
                    "order": 200,
                },
                {
                    "name": "record_value",
                    "question_text": "Record value",
                    "type": "string",
                    "mandatory": True,
                    "order": 300,
                    "help_text": "IP address or target hostname",
                },
                {
                    "name": "ttl",
                    "question_text": "TTL (seconds)",
                    "type": "integer",
                    "mandatory": False,
                    "order": 400,
                    "default_value": "3600",
                },
            ],
        },
        # Infrastructure > Compute — single subcategory (alongside Provision VM).
        {
            "name": "Create AWS S3 Bucket",
            "short_description": "Provision an S3 bucket for application or team storage",
            "description": (
                "### Provision an S3 bucket in AWS\n\n"
                "- Bucket created with the requested access level\n"
                "- Versioning and lifecycle rules applied as specified\n"
                "- Owner notified once ready\n"
            ),
            "category": "Infrastructure",
            "subcategory": "Compute",
            "fulfillment_group": ctx.groups.get("Infrastructure & Operations"),
            "order": 20,
            "variables": [
                {
                    "name": "bucket_name",
                    "question_text": "Bucket name",
                    "type": "string",
                    "mandatory": True,
                    "order": 100,
                },
                {
                    "name": "aws_region",
                    "question_text": "AWS region",
                    "type": "select_box",
                    "mandatory": True,
                    "order": 200,
                    "choice_list": _choices(
                        [
                            ("us-east-1", "us-east-1"),
                            ("us-east-2", "us-east-2"),
                            ("us-west-1", "us-west-1"),
                            ("eu-west-1", "eu-west-1"),
                        ]
                    ),
                },
                {
                    "name": "access_level",
                    "question_text": "Access level",
                    "type": "select_box",
                    "mandatory": True,
                    "order": 300,
                    "choice_list": _choices(
                        [
                            ("private", "Private"),
                            ("team_ro", "Team read-only"),
                            ("team_rw", "Team read-write"),
                        ]
                    ),
                },
                {
                    "name": "enable_versioning",
                    "question_text": "Enable versioning",
                    "type": "boolean",
                    "mandatory": False,
                    "order": 400,
                    "default_value": "true",
                },
                {
                    "name": "lifecycle_days",
                    "question_text": "Lifecycle expiration (days)",
                    "type": "integer",
                    "mandatory": False,
                    "order": 500,
                    "help_text": "Days before objects expire (0 = never)",
                },
                {
                    "name": "owner_email",
                    "question_text": "Owner email",
                    "type": "email",
                    "mandatory": True,
                    "order": 600,
                },
            ],
        },
        # Security > Access Management — first of two subcategories.
        {
            "name": "Request AD Group Membership",
            "short_description": "Request membership in an Active Directory group",
            "description": (
                "### Request membership in an Active Directory security group\n\n"
                "- Reviewed and approved by the group owner\n"
                "- Access reviewed at the requested duration\n"
            ),
            "category": "Security",
            "subcategory": "Access Management",
            "fulfillment_group": security_group,
            "order": 10,
            "variables": [
                {
                    "name": "target_group",
                    "question_text": "Target group",
                    "type": "reference",
                    "mandatory": True,
                    "order": 100,
                    "reference_table": "sys_user_group",
                },
                {
                    "name": "access_duration",
                    "question_text": "Access duration",
                    "type": "select_box",
                    "mandatory": True,
                    "order": 200,
                    "choice_list": _choices(
                        [
                            ("30d", "30 days"),
                            ("90d", "90 days"),
                            ("1y", "1 year"),
                            ("permanent", "Permanent"),
                        ]
                    ),
                },
                {
                    "name": "manager_approval",
                    "question_text": "Manager approval required",
                    "type": "boolean",
                    "mandatory": False,
                    "order": 300,
                    "default_value": "true",
                    "read_only": True,
                    "help_text": "Manager approval is required for all group access requests",
                },
                {
                    "name": "justification",
                    "question_text": "Business justification",
                    "type": "text_area",
                    "mandatory": True,
                    "order": 400,
                },
            ],
        },
        {
            "name": "Request Elevated Privileges",
            "short_description": "Request temporary elevated system access",
            "description": (
                "### Request temporary elevated privileges\n\n"
                "- Time-boxed to the requested duration\n"
                "- Automatically revoked at expiration\n"
                "- All activity logged for audit\n"
            ),
            "category": "Security",
            "subcategory": "Access Management",
            "fulfillment_group": security_group,
            "order": 20,
            "variables": [
                {
                    "name": "privilege_level",
                    "question_text": "Privilege level",
                    "type": "select_box",
                    "mandatory": True,
                    "order": 100,
                    "choice_list": _choices(
                        [
                            ("sudo", "sudo"),
                            ("root", "root"),
                            ("domain_admin", "Domain admin"),
                            ("database_admin", "Database admin"),
                        ]
                    ),
                },
                {
                    "name": "target_systems",
                    "question_text": "Target systems",
                    "type": "multi_select",
                    "mandatory": True,
                    "order": 200,
                    "choice_list": _choices(
                        [
                            ("prod_servers", "Production servers"),
                            ("staging_servers", "Staging servers"),
                            ("db_cluster", "Database cluster"),
                            ("cicd_pipeline", "CI/CD pipeline"),
                        ]
                    ),
                },
                {
                    "name": "duration_hours",
                    "question_text": "Duration (hours)",
                    "type": "integer",
                    "mandatory": True,
                    "order": 300,
                    "help_text": "Maximum 72 hours",
                },
                {
                    "name": "incident_reference",
                    "question_text": "Related incident number",
                    "type": "string",
                    "mandatory": False,
                    "order": 400,
                    "help_text": "Related INC number if this is an emergency request",
                },
            ],
        },
        # Security > Compliance — second subcategory.
        {
            "name": "Request Security Exception",
            "short_description": "Request a documented exception to a security policy",
            "description": (
                "### Request an exception to a security policy or control\n\n"
                "- Reviewed by Security Operations\n"
                "- Time-boxed with a defined end date\n"
                "- Compensating controls tracked for the exception period\n"
            ),
            "category": "Security",
            "subcategory": "Compliance",
            "fulfillment_group": security_group,
            "order": 10,
            "variables": [
                {
                    "name": "exception_type",
                    "question_text": "Exception type",
                    "type": "select_box",
                    "mandatory": True,
                    "order": 100,
                    "choice_list": _choices(
                        [
                            ("firewall_bypass", "Firewall bypass"),
                            ("encryption_waiver", "Encryption waiver"),
                            ("patch_deferral", "Patch deferral"),
                            ("vendor_access", "Vendor access"),
                        ]
                    ),
                },
                {
                    "name": "risk_level",
                    "question_text": "Risk level",
                    "type": "select_box",
                    "mandatory": True,
                    "order": 200,
                    "choice_list": _choices(
                        [
                            ("low", "Low"),
                            ("medium", "Medium"),
                            ("high", "High"),
                            ("critical", "Critical"),
                        ]
                    ),
                },
                {
                    "name": "exception_start",
                    "question_text": "Exception start date",
                    "type": "date",
                    "mandatory": True,
                    "order": 300,
                },
                {
                    "name": "exception_end",
                    "question_text": "Exception end date",
                    "type": "date",
                    "mandatory": True,
                    "order": 400,
                },
                {
                    "name": "compensating_controls",
                    "question_text": "Compensating controls",
                    "type": "text_area",
                    "mandatory": True,
                    "order": 500,
                },
                {
                    "name": "ciso_aware",
                    "question_text": "CISO notified",
                    "type": "boolean",
                    "mandatory": False,
                    "order": 600,
                    "help_text": "Has the CISO been notified of this exception?",
                },
            ],
        },
        # Software — top-level items (no subcategory) alongside subcategorized items below.
        {
            "name": "Install Licensed Software",
            "short_description": "Install licensed software on a managed device",
            "description": (
                "### Install licensed software on a managed device\n\n"
                "- License allocated from the available pool\n"
                "- Installed remotely via endpoint management\n"
            ),
            "category": "Software",
            "subcategory": None,
            "fulfillment_group": app_support_group,
            "order": 10,
            "variables": [
                {
                    "name": "software_title",
                    "question_text": "Software title",
                    "type": "string",
                    "mandatory": True,
                    "order": 100,
                },
                {
                    "name": "version",
                    "question_text": "Version",
                    "type": "string",
                    "mandatory": False,
                    "order": 200,
                    "help_text": "Leave blank for the latest version",
                },
                {
                    "name": "license_key",
                    "question_text": "License key",
                    "type": "string",
                    "mandatory": False,
                    "order": 300,
                },
                {
                    "name": "install_target",
                    "question_text": "Target device",
                    "type": "reference",
                    "mandatory": True,
                    "order": 400,
                    "reference_table": "cmdb_ci",
                    "help_text": "Configuration item the software will be installed on",
                },
                {
                    "name": "install_date",
                    "question_text": "Preferred install date",
                    "type": "date",
                    "mandatory": False,
                    "order": 500,
                },
            ],
        },
        {
            "name": "Request SaaS License",
            "short_description": "Request a license seat for an approved SaaS application",
            "description": (
                "### Request a license seat for an approved SaaS application\n\n"
                "- Seat assigned and billed to the requested cost center\n"
                "- Manager notified once provisioned\n"
            ),
            "category": "Software",
            "subcategory": None,
            "fulfillment_group": app_support_group,
            "order": 20,
            "variables": [
                {
                    "name": "saas_product",
                    "question_text": "SaaS product",
                    "type": "select_box",
                    "mandatory": True,
                    "order": 100,
                    "choice_list": _choices(
                        [
                            ("jira", "Jira"),
                            ("confluence", "Confluence"),
                            ("github_enterprise", "GitHub Enterprise"),
                            ("figma", "Figma"),
                            ("slack_enterprise", "Slack Enterprise"),
                        ]
                    ),
                },
                {
                    "name": "license_tier",
                    "question_text": "License tier",
                    "type": "select_box",
                    "mandatory": True,
                    "order": 200,
                    "choice_list": _choices(
                        [
                            ("standard", "Standard"),
                            ("professional", "Professional"),
                            ("enterprise", "Enterprise"),
                        ]
                    ),
                },
                {
                    "name": "seat_count",
                    "question_text": "Number of seats",
                    "type": "integer",
                    "mandatory": True,
                    "order": 300,
                    "default_value": "1",
                },
                {
                    "name": "cost_center",
                    "question_text": "Cost center",
                    "type": "string",
                    "mandatory": True,
                    "order": 400,
                },
                {
                    "name": "manager_email",
                    "question_text": "Manager email",
                    "type": "email",
                    "mandatory": True,
                    "order": 500,
                },
                {
                    "name": "billing_url",
                    "question_text": "Vendor billing portal URL",
                    "type": "url",
                    "mandatory": False,
                    "order": 600,
                    "help_text": "Link to the vendor billing portal, if available",
                },
            ],
        },
        # Software > Development Tools — first subcategory.
        {
            "name": "Provision Git Repository",
            "short_description": "Create a new Git repository from a starter template",
            "description": (
                "### Create a new Git repository\n\n"
                "- Repository created with the requested visibility\n"
                "- Starter template applied, if selected\n"
                "- CI pipeline enabled on request\n"
            ),
            "category": "Software",
            "subcategory": "Development Tools",
            "fulfillment_group": app_support_group,
            "order": 10,
            "variables": [
                {
                    "name": "repo_name",
                    "question_text": "Repository name",
                    "type": "string",
                    "mandatory": True,
                    "order": 100,
                },
                {
                    "name": "repo_visibility",
                    "question_text": "Visibility",
                    "type": "select_box",
                    "mandatory": True,
                    "order": 200,
                    "choice_list": _choices(
                        [
                            ("private", "Private"),
                            ("internal", "Internal"),
                            ("public", "Public"),
                        ]
                    ),
                },
                {
                    "name": "template",
                    "question_text": "Starter template",
                    "type": "select_box",
                    "mandatory": False,
                    "order": 300,
                    "choice_list": _choices(
                        [
                            ("blank", "Blank"),
                            ("python_service", "Python microservice"),
                            ("node_api", "Node.js API"),
                            ("react_frontend", "React frontend"),
                            ("go_cli", "Go CLI"),
                        ]
                    ),
                },
                {
                    "name": "enable_ci",
                    "question_text": "Enable CI pipeline",
                    "type": "boolean",
                    "mandatory": False,
                    "order": 400,
                    "default_value": "true",
                },
                {
                    "name": "team_access",
                    "question_text": "Grant access to team",
                    "type": "reference",
                    "mandatory": False,
                    "order": 500,
                    "reference_table": "sys_user_group",
                },
            ],
        },
        # Software > Collaboration — second subcategory.
        {
            "name": "Create Shared Mailbox",
            "short_description": "Create a shared team mailbox",
            "description": (
                "### Create a shared mailbox for a team or function\n\n"
                "- Mailbox created and delegated to the requested group\n"
                "- Optional auto-reply configured\n"
            ),
            "category": "Software",
            "subcategory": "Collaboration",
            "fulfillment_group": app_support_group,
            "order": 10,
            "variables": [
                {
                    "name": "mailbox_address",
                    "question_text": "Mailbox address",
                    "type": "email",
                    "mandatory": True,
                    "order": 100,
                },
                {
                    "name": "display_name",
                    "question_text": "Display name",
                    "type": "string",
                    "mandatory": True,
                    "order": 200,
                },
                {
                    "name": "auto_reply",
                    "question_text": "Enable auto-reply",
                    "type": "boolean",
                    "mandatory": False,
                    "order": 300,
                },
                {
                    "name": "auto_reply_message",
                    "question_text": "Auto-reply message",
                    "type": "text_area",
                    "mandatory": False,
                    "order": 400,
                },
                {
                    "name": "delegate_group",
                    "question_text": "Delegate to group",
                    "type": "reference",
                    "mandatory": True,
                    "order": 500,
                    "reference_table": "sys_user_group",
                },
            ],
        },
    ]

    for spec in other_items:
        await _upsert_catalog_item(
            session,
            catalog,
            name=spec["name"],
            short_description=spec["short_description"],
            description=spec["description"],
            category=spec["category"],
            subcategory=spec["subcategory"],
            fulfillment_group=spec["fulfillment_group"],
            order=spec["order"],
            variables=spec["variables"],
        )


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
        await startup.ensure_table_registry()

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
