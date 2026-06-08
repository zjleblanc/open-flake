from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.flake.attachment import delete_attachments_for_parent, remove_attachment
from app.models import SysAttachment


@pytest.mark.asyncio
async def test_delete_attachments_for_parent_removes_all_records():
    db = AsyncMock()
    record_a = SysAttachment(
        sys_id="att1",
        table_name="incident",
        table_sys_id="inc1",
        file_name="a.txt",
        storage_path="/tmp/att1.txt",
    )
    record_b = SysAttachment(
        sys_id="att2",
        table_name="incident",
        table_sys_id="inc1",
        file_name="b.txt",
        storage_path="/tmp/att2.txt",
    )

    result = MagicMock()
    result.scalars.return_value.all.return_value = [record_a, record_b]
    db.execute.return_value = result

    with patch("app.api.flake.attachment._remove_attachment_file") as remove_file:
        deleted = await delete_attachments_for_parent(db, "incident", "inc1")

    assert deleted == 2
    assert db.delete.await_count == 2
    assert db.flush.await_count == 2
    assert remove_file.call_count == 2


@pytest.mark.asyncio
async def test_remove_attachment_deletes_db_row_and_file():
    db = AsyncMock()
    record = SysAttachment(
        sys_id="att1",
        table_name="incident",
        table_sys_id="inc1",
        file_name="a.txt",
        storage_path="/tmp/att1.txt",
    )

    with patch("app.api.flake.attachment._remove_attachment_file") as remove_file:
        await remove_attachment(db, record)

    remove_file.assert_called_once_with(record)
    db.delete.assert_awaited_once_with(record)
    db.flush.assert_awaited_once()
