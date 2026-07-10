from unittest.mock import AsyncMock, MagicMock

import pytest
from app.startup import _migrate_cmdb_other_to_attributes


@pytest.mark.asyncio
async def test_migrate_cmdb_other_skips_when_column_missing():
    conn = AsyncMock()
    column_check = MagicMock()
    column_check.scalar_one_or_none.return_value = None
    conn.execute = AsyncMock(return_value=column_check)

    await _migrate_cmdb_other_to_attributes(conn)

    assert conn.execute.await_count == 1


@pytest.mark.asyncio
async def test_migrate_cmdb_other_runs_when_column_present():
    conn = AsyncMock()
    column_check = MagicMock()
    column_check.scalar_one_or_none.return_value = 1
    update_result = MagicMock()
    conn.execute = AsyncMock(side_effect=[column_check, update_result])

    await _migrate_cmdb_other_to_attributes(conn)

    assert conn.execute.await_count == 2
    update_sql = str(conn.execute.await_args_list[1].args[0])
    assert "UPDATE cmdb_ci SET attributes = other" in update_sql
