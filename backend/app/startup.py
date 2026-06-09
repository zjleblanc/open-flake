import logging
from contextlib import asynccontextmanager

from sqlalchemy import select, text

from app.auth.security import hash_password
from app import db
from app.api.flake.attachment import (
    purge_orphan_attachments,
    purge_stale_attachment_files,
    resolve_attachments_path,
)
from app.config import get_settings
from app.db import Base
from app.domain.registry import PLATFORM_ADMIN_PERMISSIONS, RBAC_RECORD_TABLES
from app.domain.schema_migrations import AUDIT_USERNAME_TABLES, SCHEMA_COLUMN_MIGRATIONS
from app.models import (
    ChangeRequest,
    ChangeTask,
    CmdbCi,
    CmdbRelCi,
    CmdbRelType,
    Incident,
    NumberSequence,
    OAuthClient,
    Problem,
    ProblemTask,
    ScRequest,
    ScTask,
    ServiceCatalog,
    ServiceCatalogItem,
    StdChangeProducerVersion,
    SysGroupRole,
    SysRole,
    SysUser,
    SysUserGroup,
    SysUserGrMember,
)
from app.utils.ids import new_sys_id

logger = logging.getLogger(__name__)
settings = get_settings()

RBAC_COLUMN_MIGRATIONS = [
    ("sys_user_group", "owner", "VARCHAR(32)"),
    *[(table, "owner", "VARCHAR(32)") for table in RBAC_RECORD_TABLES],
    *[(table, "owner_group", "VARCHAR(32)") for table in RBAC_RECORD_TABLES],
]

RBAC_BACKFILL_MODELS = {
    "incident": Incident,
    "problem": Problem,
    "problem_task": ProblemTask,
    "change_request": ChangeRequest,
    "change_task": ChangeTask,
    "cmdb_ci": CmdbCi,
    "sc_request": ScRequest,
    "sc_task": ScTask,
}


async def run_migrations():
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for table, column, col_type in [*RBAC_COLUMN_MIGRATIONS, *SCHEMA_COLUMN_MIGRATIONS]:
            await conn.execute(
                text(f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS "{column}" {col_type}')
            )
        for table in AUDIT_USERNAME_TABLES:
            for column in ("sys_created_by", "sys_updated_by"):
                await conn.execute(
                    text(
                        f'ALTER TABLE "{table}" ALTER COLUMN "{column}" TYPE VARCHAR(128)'
                    )
                )


async def backfill_audit_usernames():
    async with db.engine.begin() as conn:
        for table in AUDIT_USERNAME_TABLES:
            for column in ("sys_created_by", "sys_updated_by"):
                await conn.execute(
                    text(
                        f'UPDATE "{table}" AS t SET "{column}" = u.user_name '
                        f'FROM sys_user AS u WHERE t."{column}" = u.sys_id'
                    )
                )
    logger.info("Backfilled audit usernames on timestamped tables")


async def backfill_owners():
    async with db.async_session_factory() as session:
        updated = False
        for table, model in RBAC_BACKFILL_MODELS.items():
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
    for prefix in ["INC", "PRB", "PTASK", "CHG", "CTASK", "REQ", "SCTASK"]:
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
        result = await session.execute(select(SysUser).where(SysUser.user_name == settings.admin_username))
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

        for prefix in ["INC", "PRB", "PTASK", "CHG", "CTASK", "REQ", "SCTASK"]:
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
                price="0",
            )
        )
        session.add(
            ServiceCatalogItem(
                sys_id=new_sys_id(),
                catalog_sys_id=catalog_id,
                name="VPN Access",
                short_description="Request VPN access",
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


@asynccontextmanager
async def lifespan(app):
    resolve_attachments_path().mkdir(parents=True, exist_ok=True)
    await run_migrations()
    await backfill_audit_usernames()
    await seed_data()
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
