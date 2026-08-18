import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy import select

from app import db
from app.api.flake.attachment import (
    purge_orphan_attachments,
    purge_stale_attachment_files,
    resolve_attachments_path,
)
from app.auth.security import hash_password
from app.config import get_settings
from app.domain.registry import NUMBER_PREFIXES, PLATFORM_ADMIN_PERMISSIONS, TABLE_MODELS
from app.models import (
    CmdbRelType,
    NumberSequence,
    OAuthClient,
    ServiceCatalog,
    ServiceCatalogItem,
    StdChangeProducerVersion,
    SysDbObject,
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
    """Apply pending Alembic migrations up to head.

    Schema changes (new tables, columns, indexes, etc.) are version
    controlled as Alembic revisions under `alembic/versions/`. This runs
    them automatically on startup so the schema is always current before
    seeding begins.

    `command.upgrade` drives its own async engine (see `alembic/env.py`)
    and internally calls `asyncio.run()`, which cannot be invoked from
    within an already-running event loop -- so it's offloaded to a thread.
    """
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    # Target whichever database `db.engine` currently points at, so this
    # respects `configure_database()` overrides (e.g. lab seeding against a
    # custom --env-file) rather than always using the default settings.
    alembic_cfg.set_main_option(
        "sqlalchemy.url", db.engine.url.render_as_string(hide_password=False)
    )
    await asyncio.to_thread(command.upgrade, alembic_cfg, "head")


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


def _humanize_table_name(name: str) -> str:
    return " ".join(word.capitalize() for word in name.split("_"))


async def _ensure_physical_table_registry(session) -> None:
    """Seed one `sys_db_object` row per physical table in `TABLE_MODELS`.

    `cmdb_ci` is skipped: the CMDB hierarchy importer already registers it
    (and its subclasses) as part of loading `docs/class-hierarchy/*.json`.
    """
    from app.domain.cmdb.registry import ensure_class

    for name in sorted(TABLE_MODELS):
        if name == "cmdb_ci":
            continue
        await ensure_class(
            session,
            name,
            super_class=None,
            label=_humanize_table_name(name),
            is_extendable=False,
            storage_type="physical",
            base_table=None,
        )
        prefix = NUMBER_PREFIXES.get(name)
        if prefix:
            obj = (
                await session.execute(select(SysDbObject).where(SysDbObject.name == name))
            ).scalar_one_or_none()
            if obj:
                obj.number_prefix = prefix
    await session.commit()


async def ensure_table_registry():
    """Populate `sys_db_object` / `sys_dictionary` for every table.

    Loads the CMDB class hierarchy (JSON exports under
    `docs/class-hierarchy/`) and registers every other `TABLE_MODELS` entry
    as a plain physical table, then refreshes the in-memory registry cache
    used for reference-field resolution and class-hierarchy APIs.
    """
    from app.domain.cmdb.importer import ensure_cmdb_hierarchy
    from app.domain.cmdb.registry import refresh_cache

    async with db.async_session_factory() as session:
        await ensure_cmdb_hierarchy(session)
        await _ensure_physical_table_registry(session)
        await refresh_cache(session)
    logger.info("Table registry (sys_db_object / sys_dictionary) loaded")


@asynccontextmanager
async def lifespan(app):
    resolve_attachments_path().mkdir(parents=True, exist_ok=True)
    await run_migrations()
    await ensure_table_registry()
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
