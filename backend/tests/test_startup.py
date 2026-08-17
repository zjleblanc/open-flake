from unittest.mock import AsyncMock, MagicMock

import pytest
from app.startup import run_migrations


@pytest.mark.asyncio
async def test_run_migrations_creates_schema_from_metadata():
    """On a fresh database, `run_migrations` should do nothing more than run
    `Base.metadata.create_all` -- no hand-rolled column migrations remain."""
    conn = AsyncMock()
    engine_ctx = MagicMock()
    engine_ctx.__aenter__ = AsyncMock(return_value=conn)
    engine_ctx.__aexit__ = AsyncMock(return_value=None)
    engine = MagicMock()
    engine.begin = MagicMock(return_value=engine_ctx)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.startup.db.engine", engine)
        await run_migrations()

    conn.run_sync.assert_awaited_once()
    from app.db import Base

    assert conn.run_sync.await_args.args[0] == Base.metadata.create_all
