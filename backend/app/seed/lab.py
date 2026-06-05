"""Optional lab environment seed — realistic ITIL demo data for local development."""

from __future__ import annotations

import argparse
import asyncio
import logging
from dataclasses import dataclass, field

from sqlalchemy import select

from app.config import get_settings
from app.db import async_session_factory
from app.domain.table_service import create_record
from app.models import CmdbRelType, StdChangeProducerVersion, SysUser, SysUserGroup
from app.startup import run_migrations, seed_data

logger = logging.getLogger(__name__)
settings = get_settings()

LAB_MARKER_GROUP = "Service Desk"
LAB_USER_PASSWORD = "lab123"
LAB_PREFIX = "[LAB]"


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
    async with async_session_factory() as session:
        result = await session.execute(
            select(SysUserGroup).where(SysUserGroup.name == LAB_MARKER_GROUP)
        )
        return result.scalar_one_or_none() is not None


async def _require_admin(session) -> str:
    result = await session.execute(
        select(SysUser).where(SysUser.user_name == settings.admin_username)
    )
    admin = result.scalar_one_or_none()
    if not admin:
        raise RuntimeError(
            "Base seed data is missing. Start the backend once or run seed_data() "
            "before seeding the lab environment."
        )
    return admin.sys_id


async def _load_rel_types(session) -> dict[str, str]:
    result = await session.execute(select(CmdbRelType))
    return {row.sys_name: row.sys_id for row in result.scalars().all()}


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
        record = await create_record(
            session,
            "sys_user_group",
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
        record = await create_record(
            session,
            "sys_user",
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
        await create_record(
            session,
            "sys_user_grmember",
            {
                "user_sys_id": record["sys_id"],
                "group_sys_id": ctx.groups[group_name],
            },
            ctx.admin_id,
        )

    await create_record(
        session,
        "sys_user_grmember",
        {
            "user_sys_id": ctx.admin_id,
            "group_sys_id": ctx.groups["Change Advisory Board"],
        },
        ctx.admin_id,
    )


async def _seed_cmdb(session, ctx: LabContext) -> None:
    cis = [
        {
            "key": "lab-web-01",
            "name": "lab-web-01",
            "sys_class_name": "cmdb_ci_linux_server",
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
            "sys_class_name": "cmdb_ci_ip_router",
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
            "sys_class_name": "cmdb_ci_ip_switch",
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
            "sys_class_name": "cmdb_ci_ip_switch",
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
        record = await create_record(session, "cmdb_ci", ci, ctx.admin_id)
        ctx.cis[key] = record["sys_id"]


async def _seed_cmdb_relationships(session, ctx: LabContext) -> None:
    runs_on = ctx.rel_types.get("Runs on::Runs")
    depends_on = ctx.rel_types.get("Depends on::Used by")
    contains = ctx.rel_types.get("Contains::Contained by")
    if not all([runs_on, depends_on, contains]):
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
        await create_record(
            session,
            "cmdb_rel_ci",
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
            "description": "Multiple remote users report VPN disconnects every 15–20 minutes since last firewall policy push.",
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
        await create_record(session, "incident", incident, ctx.admin_id)


async def _seed_problems(session, ctx: LabContext) -> None:
    network = ctx.groups["Network Operations"]
    server = ctx.groups["Server Engineering"]

    vpn_problem = await create_record(
        session,
        "problem",
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

    disk_problem = await create_record(
        session,
        "problem",
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

    await create_record(
        session,
        "problem_task",
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
    await create_record(
        session,
        "problem_task",
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

    patch_change = await create_record(
        session,
        "change_request",
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

    await create_record(
        session,
        "change_task",
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
    await create_record(
        session,
        "change_task",
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

    fw_change = await create_record(
        session,
        "change_request",
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

    await create_record(
        session,
        "change_request",
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

    await create_record(
        session,
        "change_request",
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


async def _seed_service_requests(session, ctx: LabContext) -> None:
    desk = ctx.groups[LAB_MARKER_GROUP]

    laptop_req = await create_record(
        session,
        "sc_request",
        {
            "short_description": f"{LAB_PREFIX} New laptop for sales hire",
            "description": "MacBook Pro 14\" for regional sales representative starting next week.",
            "state": "2",
            "requested_for": ctx.users["rpatel"],
            "requested_by": ctx.users["jsmith"],
            "assignment_group": desk,
            "assigned_to": ctx.users["jsmith"],
        },
        ctx.admin_id,
    )
    await create_record(
        session,
        "sc_task",
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

    vpn_req = await create_record(
        session,
        "sc_request",
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
    await create_record(
        session,
        "sc_task",
        {
            "short_description": f"{LAB_PREFIX} Provision VPN profile",
            "description": "Create contractor AD account and distribute VPN client profile.",
            "state": "1",
            "request": vpn_req["sys_id"],
            "assignment_group": desk,
        },
        ctx.admin_id,
    )


async def seed_lab(*, ensure_base: bool = True, force: bool = False) -> bool:
    """Seed a realistic lab IT environment. Returns True if data was created."""
    if not force and await is_lab_seeded():
        logger.info("Lab environment already seeded (group %r exists); skipping", LAB_MARKER_GROUP)
        return False

    if ensure_base:
        await run_migrations()
        await seed_data()

    async with async_session_factory() as session:
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
        help="Seed even if lab data appears to exist (may create duplicates)",
    )
    parser.add_argument(
        "--skip-base",
        action="store_true",
        help="Do not run base migrations/seed; require admin user to already exist",
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

    created = asyncio.run(seed_lab(ensure_base=not args.skip_base, force=args.force))
    if created:
        print("Lab environment seeded.")
        print(f"  Lab users password: {LAB_USER_PASSWORD}")
        print("  Sample users: jsmith, mwilson, lchen, rpatel")
        print(f"  Records prefixed with: {LAB_PREFIX}")
    else:
        print("Lab seed skipped — data already present. Use --force to seed again.")


if __name__ == "__main__":
    main()
