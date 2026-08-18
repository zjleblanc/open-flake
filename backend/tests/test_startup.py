from unittest.mock import MagicMock, patch

import pytest
from app import db
from app.startup import run_migrations


@pytest.mark.asyncio
async def test_run_migrations_applies_alembic_upgrade_to_head():
    """`run_migrations` should delegate schema changes to Alembic's
    `upgrade head` (against whichever database `db.engine` currently points
    at), not `Base.metadata.create_all`, which can't alter existing tables.
    """
    mock_upgrade = MagicMock()

    with patch("alembic.command.upgrade", mock_upgrade):
        await run_migrations()

    mock_upgrade.assert_called_once()
    cfg, revision = mock_upgrade.call_args.args
    assert revision == "head"
    assert cfg.get_main_option("sqlalchemy.url") == db.engine.url.render_as_string(
        hide_password=False
    )
