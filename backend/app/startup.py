import logging
from contextlib import asynccontextmanager

from sqlalchemy import select

from app import db
from app.api.flake.attachment import (
    purge_orphan_attachments,
    purge_stale_attachment_files,
    resolve_attachments_path,
)
from app.auth.security import hash_password
from app.config import get_settings
from app.db import Base
from app.domain.registry import PLATFORM_ADMIN_PERMISSIONS
from app.models import (
    CmdbRelType,
    NumberSequence,
    OAuthClient,
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


async def run_migrations():
    """Build the schema from the current SQLAlchemy models.

    `create_all` is additive only: it creates tables (and their columns,
    types, and FK constraints) that don't exist yet, and leaves existing
    tables untouched. On a fresh database this produces the full schema
    -- including cascading FK constraints -- in one shot.
    """
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


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
