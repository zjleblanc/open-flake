from unittest.mock import AsyncMock

import pytest
from app.auth.deps import AuthContext
from app.domain.table_service import (
    _audit_stringify,
    _resolve_audit_username,
    create_record,
    update_record,
)
from app.models import CmdbCi, Incident, LifecycleMixin, SysAudit, SysComment, SysUser


@pytest.mark.asyncio
async def test_resolve_audit_username_prefers_auth():
    db = AsyncMock()
    auth = AuthContext(user_sys_id="abc123", user_name="admin", auth_method="basic")
    assert await _resolve_audit_username(db, "other_id", auth) == "admin"
    db.get.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_audit_username_looks_up_user_sys_id():
    db = AsyncMock()
    user = SysUser(
        sys_id="abc123",
        user_name="admin",
        user_password="hash",
        active="true",
    )
    db.get = AsyncMock(return_value=user)
    assert await _resolve_audit_username(db, "abc123", None) == "admin"
    db.get.assert_awaited_once_with(SysUser, "abc123")


@pytest.mark.asyncio
async def test_create_record_sets_username_audit_fields():
    db = AsyncMock()
    auth = AuthContext(user_sys_id="abc123", user_name="admin", auth_method="basic")
    db.get = AsyncMock(return_value=None)

    added = []

    def capture_add(record):
        added.append(record)

    db.add = capture_add
    db.flush = AsyncMock()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.domain.table_service.TABLE_MODELS",
            {"cmdb_ci": CmdbCi},
        )
        mp.setattr("app.domain.table_service.next_number", AsyncMock(return_value=None))
        mp.setattr("app.domain.table_service.emit", AsyncMock())
        mp.setattr(
            "app.domain.table_service.assert_can_create_record",
            AsyncMock(),
        )
        mp.setattr(
            "app.domain.cmdb.ci_service._ensure_class_for_write",
            AsyncMock(),
        )
        mp.setattr(
            "app.domain.cmdb.ci_service.split_payload",
            lambda _class, payload: (
                {k: v for k, v in payload.items() if k != "sys_class_name"},
                {},
            ),
        )
        mp.setattr(
            "app.domain.cmdb.ci_service.compute_class_path",
            lambda _class: "/cmdb/cmdb_ci/cmdb_ci_linux_server",
        )
        mp.setattr(
            "app.domain.cmdb.ci_service.refresh_cache",
            AsyncMock(),
        )
        result = await create_record(
            db,
            "cmdb_ci",
            {"name": "test-host", "sys_class_name": "cmdb_ci_linux_server"},
            auth.user_sys_id,
            auth=auth,
        )

    assert len(added) == 1
    assert added[0].sys_created_by == "admin"
    assert added[0].sys_updated_by == "admin"
    assert added[0].owner == "abc123"
    assert result["sys_created_by"] == "admin"
    assert result["sys_updated_by"] == "admin"


@pytest.mark.asyncio
async def test_update_record_sets_username_sys_updated_by():
    db = AsyncMock()
    auth = AuthContext(user_sys_id="user2", user_name="jsmith", auth_method="basic")
    record = CmdbCi(
        sys_id="ci1",
        name="test-host",
        sys_class_name="cmdb_ci_linux_server",
        sys_created_by="admin",
        sys_updated_by="admin",
    )
    db.get = AsyncMock(return_value=record)
    db.flush = AsyncMock()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.domain.table_service.TABLE_MODELS",
            {"cmdb_ci": CmdbCi},
        )
        mp.setattr("app.domain.table_service.emit", AsyncMock())
        mp.setattr(
            "app.domain.cmdb.ci_service.assert_record_action",
            AsyncMock(),
        )
        mp.setattr(
            "app.domain.cmdb.ci_service.split_payload",
            lambda _class, payload: (payload, {}),
        )
        result = await update_record(
            db,
            "cmdb_ci",
            "ci1",
            {"short_description": "updated"},
            auth.user_sys_id,
            auth=auth,
        )

    assert record.sys_updated_by == "jsmith"
    assert result["sys_updated_by"] == "jsmith"
    assert result["sys_created_by"] == "admin"


def test_audit_stringify_handles_various_types():
    assert _audit_stringify(None) is None
    assert _audit_stringify(True) == "true"
    assert _audit_stringify(False) == "false"
    assert _audit_stringify({"a": 1}) == '{"a": 1}'
    assert _audit_stringify("abc") == "abc"


@pytest.mark.asyncio
async def test_update_record_logs_field_audit_for_rbac_table():
    db = AsyncMock()
    auth = AuthContext(user_sys_id="user2", user_name="jsmith", auth_method="basic")
    record = Incident(
        sys_id="inc1",
        number="INC0000001",
        short_description="original",
        state="1",
    )
    db.get = AsyncMock(return_value=record)
    db.flush = AsyncMock()

    added = []
    db.add = lambda obj: added.append(obj)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.domain.table_service.TABLE_MODELS", {"incident": Incident})
        mp.setattr("app.domain.table_service.emit", AsyncMock())
        mp.setattr("app.domain.table_service.assert_record_action", AsyncMock())
        result = await update_record(
            db,
            "incident",
            "inc1",
            {"short_description": "updated", "state": "2"},
            auth.user_sys_id,
            auth=auth,
        )

    audit_rows = [obj for obj in added if isinstance(obj, SysAudit)]
    assert len(audit_rows) == 2
    assert len({row.batch_id for row in audit_rows}) == 1
    changes = {row.field_name: (row.old_value, row.new_value) for row in audit_rows}
    assert changes["short_description"] == ("original", "updated")
    assert changes["state"] == ("1", "2")
    assert all(row.user == "jsmith" for row in audit_rows)
    assert result["short_description"] == "updated"


@pytest.mark.asyncio
async def test_update_record_skips_audit_when_value_unchanged():
    db = AsyncMock()
    auth = AuthContext(user_sys_id="user2", user_name="jsmith", auth_method="basic")
    record = Incident(
        sys_id="inc1",
        number="INC0000001",
        short_description="same",
        state="1",
    )
    db.get = AsyncMock(return_value=record)
    db.flush = AsyncMock()

    added = []
    db.add = lambda obj: added.append(obj)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.domain.table_service.TABLE_MODELS", {"incident": Incident})
        mp.setattr("app.domain.table_service.emit", AsyncMock())
        mp.setattr("app.domain.table_service.assert_record_action", AsyncMock())
        await update_record(
            db,
            "incident",
            "inc1",
            {"short_description": "same"},
            auth.user_sys_id,
            auth=auth,
        )

    assert [obj for obj in added if isinstance(obj, SysAudit)] == []


@pytest.mark.asyncio
async def test_update_record_skips_audit_for_non_rbac_table():
    db = AsyncMock()
    record = SysComment(
        sys_id="c1",
        table_name="incident",
        record_sys_id="inc1",
        comment="hello",
        sys_mod_count=0,
    )
    db.get = AsyncMock(return_value=record)
    db.flush = AsyncMock()

    added = []
    db.add = lambda obj: added.append(obj)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.domain.table_service.TABLE_MODELS", {"sys_comment": SysComment})
        mp.setattr("app.domain.table_service.emit", AsyncMock())
        await update_record(db, "sys_comment", "c1", {"comment": "updated"})

    assert [obj for obj in added if isinstance(obj, SysAudit)] == []


def test_lifecycle_mixin_sys_mod_count_defaults_to_zero():
    column = CmdbCi.__table__.columns["sys_mod_count"]
    assert column.default.arg == 0
    assert issubclass(CmdbCi, LifecycleMixin)


@pytest.mark.asyncio
async def test_update_record_increments_sys_mod_count_for_non_cmdb_table():
    db = AsyncMock()
    record = SysComment(
        sys_id="c1",
        table_name="incident",
        record_sys_id="inc1",
        comment="hello",
        sys_mod_count=0,
    )
    db.get = AsyncMock(return_value=record)
    db.flush = AsyncMock()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.domain.table_service.TABLE_MODELS",
            {"sys_comment": SysComment},
        )
        mp.setattr("app.domain.table_service.emit", AsyncMock())
        result = await update_record(db, "sys_comment", "c1", {"comment": "updated"})

    assert record.sys_mod_count == 1
    assert result["sys_mod_count"] == "1"


@pytest.mark.asyncio
async def test_update_record_increments_sys_mod_count():
    db = AsyncMock()
    auth = AuthContext(user_sys_id="user2", user_name="jsmith", auth_method="basic")
    record = CmdbCi(
        sys_id="ci1",
        name="test-host",
        sys_class_name="cmdb_ci_linux_server",
        sys_mod_count=2,
    )
    db.get = AsyncMock(return_value=record)
    db.flush = AsyncMock()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.domain.table_service.TABLE_MODELS",
            {"cmdb_ci": CmdbCi},
        )
        mp.setattr("app.domain.table_service.emit", AsyncMock())
        mp.setattr(
            "app.domain.cmdb.ci_service.assert_record_action",
            AsyncMock(),
        )
        mp.setattr(
            "app.domain.cmdb.ci_service.split_payload",
            lambda _class, payload: (payload, {}),
        )
        result = await update_record(
            db,
            "cmdb_ci",
            "ci1",
            {"short_description": "updated"},
            auth.user_sys_id,
            auth=auth,
        )

    assert record.sys_mod_count == 3
    assert result["sys_mod_count"] == "3"


@pytest.mark.asyncio
async def test_update_record_ignores_client_supplied_sys_mod_count():
    db = AsyncMock()
    auth = AuthContext(user_sys_id="user2", user_name="jsmith", auth_method="basic")
    record = CmdbCi(
        sys_id="ci1",
        name="test-host",
        sys_class_name="cmdb_ci_linux_server",
        sys_mod_count=2,
    )
    db.get = AsyncMock(return_value=record)
    db.flush = AsyncMock()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.domain.table_service.TABLE_MODELS",
            {"cmdb_ci": CmdbCi},
        )
        mp.setattr("app.domain.table_service.emit", AsyncMock())
        mp.setattr(
            "app.domain.cmdb.ci_service.assert_record_action",
            AsyncMock(),
        )
        mp.setattr(
            "app.domain.cmdb.ci_service.split_payload",
            lambda _class, payload: (payload, {}),
        )
        await update_record(
            db,
            "cmdb_ci",
            "ci1",
            {"sys_mod_count": 999},
            auth.user_sys_id,
            auth=auth,
        )

    assert record.sys_mod_count == 3
