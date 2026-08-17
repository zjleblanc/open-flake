from unittest.mock import AsyncMock, MagicMock

import pytest
from app.startup import _migrate_cmdb_other_to_attributes, _migrate_sys_attachment_mod_count_type


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


@pytest.mark.asyncio
async def test_migrate_sys_attachment_mod_count_skips_when_already_integer():
    conn = AsyncMock()
    type_check = MagicMock()
    type_check.scalar_one_or_none.return_value = "integer"
    conn.execute = AsyncMock(return_value=type_check)

    await _migrate_sys_attachment_mod_count_type(conn)

    assert conn.execute.await_count == 1


@pytest.mark.asyncio
async def test_migrate_sys_attachment_mod_count_skips_when_column_missing():
    conn = AsyncMock()
    type_check = MagicMock()
    type_check.scalar_one_or_none.return_value = None
    conn.execute = AsyncMock(return_value=type_check)

    await _migrate_sys_attachment_mod_count_type(conn)

    assert conn.execute.await_count == 1


@pytest.mark.asyncio
async def test_migrate_sys_attachment_mod_count_converts_varchar_column():
    conn = AsyncMock()
    type_check = MagicMock()
    type_check.scalar_one_or_none.return_value = "character varying"
    conn.execute = AsyncMock(side_effect=[type_check, MagicMock(), MagicMock()])

    await _migrate_sys_attachment_mod_count_type(conn)

    assert conn.execute.await_count == 3
    alter_type_sql = str(conn.execute.await_args_list[1].args[0])
    assert "ALTER TABLE sys_attachment ALTER COLUMN sys_mod_count TYPE INTEGER" in alter_type_sql
    alter_default_sql = str(conn.execute.await_args_list[2].args[0])
    assert "SET DEFAULT 0" in alter_default_sql
