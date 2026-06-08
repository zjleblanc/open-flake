import logging
from contextlib import asynccontextmanager

from sqlalchemy import select, text

from app.auth.security import hash_password
from app import db
from app.api.snow.attachment import resolve_attachments_path
from app.config import get_settings
from app.db import Base
from app.domain.registry import PLATFORM_ADMIN_PERMISSIONS, RBAC_RECORD_TABLES
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
        for table, column, col_type in RBAC_COLUMN_MIGRATIONS:
            await conn.execute(
                text(f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS "{column}" {col_type}')
            )


async def backfill_owners():
    async with db.async_session_factory() as session:
        updated = False
        for table, model in RBAC_BACKFILL_MODELS.items():
            result = await session.execute(
                select(model).where(model.owner.is_(None), model.sys_created_by.isnot(None))
            )
            for record in result.scalars().all():
                record.owner = record.sys_created_by
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


async def seed_data():
    async with db.async_session_factory() as session:
        result = await session.execute(select(SysUser).where(SysUser.user_name == settings.admin_username))
        if result.scalar_one_or_none():
            await ensure_rbac_roles()
            await backfill_owners()
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
    await seed_data()
    logger.info("OpenFlake backend ready")
    yield
    await db.engine.dispose()
