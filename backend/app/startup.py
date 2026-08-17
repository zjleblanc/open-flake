import json
import logging
from contextlib import asynccontextmanager

from sqlalchemy import select, text

from app import db
from app.api.flake.attachment import (
    purge_orphan_attachments,
    purge_stale_attachment_files,
    resolve_attachments_path,
)
from app.auth.security import hash_password
from app.config import get_settings
from app.db import Base
from app.domain.registry import PLATFORM_ADMIN_PERMISSIONS, RBAC_RECORD_TABLES
from app.domain.schema_migrations import (
    AUDIT_USERNAME_TABLES,
    MOD_COUNT_COLUMN_MIGRATIONS,
    SCHEMA_COLUMN_MIGRATIONS,
)
from app.models import (
    ChangeRequest,
    ChangeTask,
    CmdbCi,
    CmdbRelType,
    Incident,
    NumberSequence,
    OAuthClient,
    Problem,
    ProblemTask,
    ScReqItem,
    ScRequest,
    ScTask,
    ServiceCatalog,
    ServiceCatalogItem,
    StdChangeProducerVersion,
    SysGroupRole,
    SysRole,
    SysUser,
    SysUserGrMember,
    SysUserGroup,
)
from app.utils.ids import new_sys_id

logger = logging.getLogger(__name__)
settings = get_settings()

RBAC_COLUMN_MIGRATIONS = [
    ("sys_user_group", "owner", "VARCHAR(32)"),
    *[(table, "owner", "VARCHAR(32)") for table in RBAC_RECORD_TABLES],
    *[(table, "owner_group", "VARCHAR(32)") for table in RBAC_RECORD_TABLES],
]

CMDB_COLUMN_MIGRATIONS = [
    ("cmdb_ci", "sys_class_path", "VARCHAR(512)"),
    ("cmdb_ci", "attributes", "JSONB DEFAULT '{}'::jsonb"),
]

RBAC_BACKFILL_MODELS = {
    "incident": Incident,
    "problem": Problem,
    "problem_task": ProblemTask,
    "change_request": ChangeRequest,
    "change_task": ChangeTask,
    "cmdb_ci": CmdbCi,
    "sc_request": ScRequest,
    "sc_req_item": ScReqItem,
    "sc_task": ScTask,
}


async def _migrate_service_catalog_item_table(conn) -> None:
    """Rename legacy service_catalog_item table to sc_cat_item when upgrading."""
    result = await conn.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'service_catalog_item'"
        )
    )
    if result.scalar_one_or_none() is None:
        return
    existing = await conn.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'sc_cat_item'"
        )
    )
    if existing.scalar_one_or_none() is not None:
        return
    await conn.execute(text("ALTER TABLE service_catalog_item RENAME TO sc_cat_item"))
    logger.info("Renamed service_catalog_item -> sc_cat_item")


async def _migrate_legacy_item_webhooks(conn) -> None:
    """Split embedded sc_cat_item_webhook destinations into standalone sc_webhook rows."""
    tables = await conn.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'sc_cat_item_webhook'"
        )
    )
    if tables.scalar_one_or_none() is None:
        return

    url_col = await conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'public' "
            "AND table_name = 'sc_cat_item_webhook' "
            "AND column_name = 'url'"
        )
    )
    if url_col.scalar_one_or_none() is None:
        return

    await conn.execute(
        text(
            "CREATE TABLE IF NOT EXISTS sc_webhook ("
            "sys_id VARCHAR(32) PRIMARY KEY, "
            "name VARCHAR(256), "
            "url VARCHAR(1024), "
            "method VARCHAR(8) DEFAULT 'POST', "
            "headers JSONB DEFAULT '{}'::jsonb, "
            "secret VARCHAR(256), "
            "active BOOLEAN DEFAULT TRUE, "
            "description TEXT, "
            "other JSONB DEFAULT '{}'::jsonb, "
            "sys_created_on TIMESTAMPTZ DEFAULT now(), "
            "sys_updated_on TIMESTAMPTZ DEFAULT now(), "
            "sys_created_by VARCHAR(128), "
            "sys_updated_by VARCHAR(128)"
            ")"
        )
    )
    await conn.execute(
        text("ALTER TABLE sc_cat_item_webhook ADD COLUMN IF NOT EXISTS webhook VARCHAR(32)")
    )

    rows = await conn.execute(
        text(
            "SELECT sys_id, name, url, method, headers, secret, active "
            "FROM sc_cat_item_webhook "
            "WHERE (webhook IS NULL OR webhook = '') AND COALESCE(url, '') != ''"
        )
    )
    migrated = 0
    for row in rows.mappings().all():
        webhook_id = new_sys_id()
        headers = row["headers"] if isinstance(row["headers"], dict) else {}
        await conn.execute(
            text(
                "INSERT INTO sc_webhook "
                "(sys_id, name, url, method, headers, secret, active) "
                "VALUES (:sys_id, :name, :url, :method, CAST(:headers AS jsonb), "
                ":secret, :active)"
            ),
            {
                "sys_id": webhook_id,
                "name": row["name"] or "Migrated webhook",
                "url": row["url"],
                "method": row["method"] or "POST",
                "headers": json.dumps(headers),
                "secret": row["secret"],
                "active": True if row["active"] is None else bool(row["active"]),
            },
        )
        await conn.execute(
            text("UPDATE sc_cat_item_webhook SET webhook = :webhook_id WHERE sys_id = :sys_id"),
            {"webhook_id": webhook_id, "sys_id": row["sys_id"]},
        )
        migrated += 1
    if migrated:
        logger.info("Migrated %s legacy catalog item webhooks to sc_webhook", migrated)


async def _migrate_cmdb_other_to_attributes(conn) -> None:
    """Copy legacy cmdb_ci.other JSON into attributes when upgrading older databases."""
    result = await conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'public' "
            "AND table_name = 'cmdb_ci' "
            "AND column_name = 'other'"
        )
    )
    if result.scalar_one_or_none() is None:
        return

    await conn.execute(
        text(
            "UPDATE cmdb_ci SET attributes = other "
            "WHERE (attributes IS NULL OR attributes = '{}'::jsonb) "
            "AND other IS NOT NULL AND other != '{}'::jsonb"
        )
    )


async def _migrate_sys_attachment_mod_count_type(conn) -> None:
    """Convert the legacy VARCHAR sys_attachment.sys_mod_count column to INTEGER."""
    result = await conn.execute(
        text(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_schema = 'public' "
            "AND table_name = 'sys_attachment' "
            "AND column_name = 'sys_mod_count'"
        )
    )
    data_type = result.scalar_one_or_none()
    if data_type is None or data_type == "integer":
        return
    await conn.execute(
        text(
            "ALTER TABLE sys_attachment ALTER COLUMN sys_mod_count TYPE INTEGER "
            "USING COALESCE(NULLIF(sys_mod_count, '')::integer, 0)"
        )
    )
    await conn.execute(text("ALTER TABLE sys_attachment ALTER COLUMN sys_mod_count SET DEFAULT 0"))
    logger.info("Converted sys_attachment.sys_mod_count from VARCHAR to INTEGER")


async def run_migrations():
    async with db.engine.begin() as conn:
        await _migrate_service_catalog_item_table(conn)
        await _migrate_legacy_item_webhooks(conn)
        await conn.run_sync(Base.metadata.create_all)
        for table, column, col_type in [
            *RBAC_COLUMN_MIGRATIONS,
            *CMDB_COLUMN_MIGRATIONS,
            *SCHEMA_COLUMN_MIGRATIONS,
            *MOD_COUNT_COLUMN_MIGRATIONS,
        ]:
            await conn.execute(
                text(f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS "{column}" {col_type}')
            )
        await _migrate_cmdb_other_to_attributes(conn)
        await _migrate_sys_attachment_mod_count_type(conn)
        for table in AUDIT_USERNAME_TABLES:
            for column in ("sys_created_by", "sys_updated_by"):
                await conn.execute(
                    text(f'ALTER TABLE "{table}" ALTER COLUMN "{column}" TYPE VARCHAR(128)')
                )


async def backfill_audit_usernames():
    async with db.engine.begin() as conn:
        for table in AUDIT_USERNAME_TABLES:
            for column in ("sys_created_by", "sys_updated_by"):
                await conn.execute(
                    text(
                        # table/column come from a fixed allowlist, not user input
                        f'UPDATE "{table}" AS t SET "{column}" = u.user_name '  # noqa: S608
                        f'FROM sys_user AS u WHERE t."{column}" = u.sys_id'
                    )
                )
    logger.info("Backfilled audit usernames on timestamped tables")


async def backfill_owners():
    async with db.async_session_factory() as session:
        updated = False
        for _table, model in RBAC_BACKFILL_MODELS.items():
            result = await session.execute(
                select(model, SysUser.sys_id)
                .join(SysUser, SysUser.user_name == model.sys_created_by)
                .where(model.owner.is_(None), model.sys_created_by.isnot(None))
            )
            for record, owner_sys_id in result.all():
                record.owner = owner_sys_id
                updated = True
        if updated:
            await session.commit()
            logger.info("Backfilled owner fields on business records")


async def ensure_rbac_roles():
    async with db.async_session_factory() as session:
        result = await session.execute(select(SysRole).where(SysRole.name == "platform_admin"))
        role = result.scalar_one_or_none()
        if not role:
            role = SysRole(
                sys_id=new_sys_id(),
                name="platform_admin",
                permissions=PLATFORM_ADMIN_PERMISSIONS,
            )
            session.add(role)
            await session.flush()
        else:
            current = list(role.permissions or [])
            missing = [p for p in PLATFORM_ADMIN_PERMISSIONS if p not in current]
            if missing:
                role.permissions = current + missing
                logger.info("Added permissions to platform_admin: %s", ", ".join(missing))

        admin_group = (
            await session.execute(select(SysUserGroup).where(SysUserGroup.name == "admin"))
        ).scalar_one_or_none()
        if admin_group:
            if not admin_group.owner:
                admin_user = (
                    await session.execute(
                        select(SysUser).where(SysUser.user_name == settings.admin_username)
                    )
                ).scalar_one_or_none()
                if admin_user:
                    admin_group.owner = admin_user.sys_id

            existing = (
                await session.execute(
                    select(SysGroupRole).where(
                        SysGroupRole.group_sys_id == admin_group.sys_id,
                        SysGroupRole.role_sys_id == role.sys_id,
                    )
                )
            ).scalar_one_or_none()
            if not existing:
                session.add(
                    SysGroupRole(
                        sys_id=new_sys_id(),
                        group_sys_id=admin_group.sys_id,
                        role_sys_id=role.sys_id,
                    )
                )
        await session.commit()


async def _ensure_number_sequences(session) -> None:
    for prefix in ["INC", "PRB", "PTASK", "CHG", "CTASK", "REQ", "RITM", "SCTASK"]:
        existing = await session.execute(
            select(NumberSequence).where(NumberSequence.prefix == prefix)
        )
        if not existing.scalar_one_or_none():
            session.add(NumberSequence(prefix=prefix, last_value=0))


async def _ensure_cmdb_rel_types(session) -> None:
    rel_types = [
        ("Runs on::Runs", "Runs on"),
        ("Depends on::Used by", "Depends on"),
        ("Contains::Contained by", "Contains"),
    ]
    for sys_name, name in rel_types:
        existing = await session.execute(
            select(CmdbRelType).where(CmdbRelType.sys_name == sys_name)
        )
        if not existing.scalar_one_or_none():
            session.add(CmdbRelType(sys_id=new_sys_id(), sys_name=sys_name, name=name))


async def _ensure_std_change_template(session) -> None:
    existing = await session.execute(
        select(StdChangeProducerVersion).where(
            StdChangeProducerVersion.name == "Standard Server Patch"
        )
    )
    if not existing.scalar_one_or_none():
        session.add(
            StdChangeProducerVersion(
                sys_id=new_sys_id(),
                name="Standard Server Patch",
                short_description="Apply standard OS patches",
            )
        )


async def _ensure_service_catalog(session) -> None:
    existing = await session.execute(
        select(ServiceCatalog).where(ServiceCatalog.title == "IT Services")
    )
    catalog = existing.scalar_one_or_none()
    if not catalog:
        catalog_id = new_sys_id()
        session.add(
            ServiceCatalog(
                sys_id=catalog_id,
                title="IT Services",
                description="Standard IT service catalog",
            )
        )
    else:
        catalog_id = catalog.sys_id

    for item_name, short_desc in (
        ("New Laptop Request", "Request a new laptop"),
        ("VPN Access", "Request VPN access"),
    ):
        existing_item = await session.execute(
            select(ServiceCatalogItem).where(
                ServiceCatalogItem.catalog_sys_id == catalog_id,
                ServiceCatalogItem.name == item_name,
            )
        )
        if not existing_item.scalar_one_or_none():
            session.add(
                ServiceCatalogItem(
                    sys_id=new_sys_id(),
                    catalog_sys_id=catalog_id,
                    name=item_name,
                    short_description=short_desc,
                    price="0",
                )
            )


async def _ensure_oauth_client(session) -> None:
    existing = await session.execute(
        select(OAuthClient).where(OAuthClient.client_id == "openflake")
    )
    if not existing.scalar_one_or_none():
        session.add(
            OAuthClient(
                sys_id=new_sys_id(),
                client_id="openflake",
                client_secret="openflake-secret",
                name="Default OAuth Client",
            )
        )


async def ensure_reference_data():
    """Create reference rows that may be missing on upgraded or partial databases."""
    async with db.async_session_factory() as session:
        await _ensure_number_sequences(session)
        await _ensure_cmdb_rel_types(session)
        await _ensure_std_change_template(session)
        await _ensure_service_catalog(session)
        await _ensure_oauth_client(session)
        await session.commit()


async def seed_data():
    async with db.async_session_factory() as session:
        result = await session.execute(
            select(SysUser).where(SysUser.user_name == settings.admin_username)
        )
        if result.scalar_one_or_none():
            await ensure_rbac_roles()
            await backfill_audit_usernames()
            await backfill_owners()
            await ensure_reference_data()
            return

        admin_id = new_sys_id()
        admin_group_id = new_sys_id()
        admin_role_id = new_sys_id()

        session.add(
            SysUser(
                sys_id=admin_id,
                user_name=settings.admin_username,
                user_password=hash_password(settings.admin_password),
                first_name="System",
                last_name="Administrator",
                email="admin@openflake.local",
                active="true",
            )
        )
        session.add(
            SysUserGroup(
                sys_id=admin_group_id,
                name="admin",
                description="Administrators",
                owner=admin_id,
            )
        )
        session.add(
            SysUserGrMember(
                sys_id=new_sys_id(),
                user_sys_id=admin_id,
                group_sys_id=admin_group_id,
            )
        )
        session.add(
            SysRole(
                sys_id=admin_role_id,
                name="platform_admin",
                permissions=PLATFORM_ADMIN_PERMISSIONS,
            )
        )
        session.add(
            SysGroupRole(
                sys_id=new_sys_id(),
                group_sys_id=admin_group_id,
                role_sys_id=admin_role_id,
            )
        )

        for prefix in ["INC", "PRB", "PTASK", "CHG", "CTASK", "REQ", "RITM", "SCTASK"]:
            session.add(NumberSequence(prefix=prefix, last_value=0))

        session.add(
            StdChangeProducerVersion(
                sys_id=new_sys_id(),
                name="Standard Server Patch",
                short_description="Apply standard OS patches",
            )
        )

        rel_types = [
            ("Runs on::Runs", "Runs on"),
            ("Depends on::Used by", "Depends on"),
            ("Contains::Contained by", "Contains"),
        ]
        for sys_name, name in rel_types:
            session.add(CmdbRelType(sys_id=new_sys_id(), sys_name=sys_name, name=name))

        catalog_id = new_sys_id()
        session.add(
            ServiceCatalog(
                sys_id=catalog_id,
                title="IT Services",
                description="Standard IT service catalog",
            )
        )
        session.add(
            ServiceCatalogItem(
                sys_id=new_sys_id(),
                catalog_sys_id=catalog_id,
                name="New Laptop Request",
                short_description="Request a new laptop",
                description="Request a standard corporate laptop for a new or existing employee.",
                price="0",
            )
        )
        session.add(
            ServiceCatalogItem(
                sys_id=new_sys_id(),
                catalog_sys_id=catalog_id,
                name="VPN Access",
                short_description="Request VPN access",
                description="Request remote VPN access for corporate network resources.",
                price="0",
            )
        )

        session.add(
            OAuthClient(
                sys_id=new_sys_id(),
                client_id="openflake",
                client_secret="openflake-secret",
                name="Default OAuth Client",
            )
        )

        await session.commit()
        logger.info("Seeded default admin user and reference data")


async def ensure_cmdb_class_metadata():
    from app.domain.cmdb.importer import ensure_cmdb_hierarchy

    async with db.async_session_factory() as session:
        await ensure_cmdb_hierarchy(session)
    logger.info("CMDB class hierarchy loaded")


@asynccontextmanager
async def lifespan(app):
    resolve_attachments_path().mkdir(parents=True, exist_ok=True)
    await run_migrations()
    await ensure_cmdb_class_metadata()
    await backfill_audit_usernames()
    await seed_data()
    from app.domain.catalog.webhooks import register_webhook_subscriber

    register_webhook_subscriber()
    async with db.async_session_factory() as session:
        orphans = await purge_orphan_attachments(session)
        stale_files = await purge_stale_attachment_files(session)
        await session.commit()
        if orphans or stale_files:
            logger.info(
                "Purged attachment orphans: %s db row(s), %s file(s)",
                orphans,
                stale_files,
            )
    logger.info("OpenFlake backend ready")
    yield
    await db.engine.dispose()
