import logging
from contextlib import asynccontextmanager

from sqlalchemy import select

from app.auth.security import hash_password
from app.config import get_settings
from app.db import Base, async_session_factory, engine
from app.models import (
    CmdbRelType,
    NumberSequence,
    OAuthClient,
    ServiceCatalog,
    ServiceCatalogItem,
    StdChangeProducerVersion,
    SysUser,
    SysUserGroup,
    SysUserGrMember,
)
from app.utils.ids import new_sys_id

logger = logging.getLogger(__name__)
settings = get_settings()


async def run_migrations():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def seed_data():
    async with async_session_factory() as session:
        result = await session.execute(select(SysUser).where(SysUser.user_name == settings.admin_username))
        if result.scalar_one_or_none():
            return

        admin_id = new_sys_id()
        admin_group_id = new_sys_id()

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
            )
        )
        session.add(
            SysUserGrMember(
                sys_id=new_sys_id(),
                user_sys_id=admin_id,
                group_sys_id=admin_group_id,
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
    await run_migrations()
    await seed_data()
    logger.info("OpenFlake backend ready")
    yield
    await engine.dispose()
