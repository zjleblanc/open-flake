from unittest.mock import AsyncMock, MagicMock

import pytest
from app.auth.deps import AuthContext
from app.auth.rbac import (
    RecordPermissions,
    assert_platform_action,
    assert_record_action,
    has_permission,
    resolve_record_permissions,
)
from fastapi import HTTPException


def test_has_permission_exact_and_wildcard():
    perms = {"records.*.read", "records.*.write", "users.read"}
    assert has_permission(perms, "records.*.read")
    assert has_permission(perms, "records.incident.read")
    assert has_permission(perms, "records.incident.write")
    assert has_permission(perms, "users.read")
    assert not has_permission(perms, "users.write")


def test_has_permission_write_implies_delete_check():
    perms = {"records.*.write"}
    assert has_permission(perms, "records.incident.delete")


def test_has_permission_secrets_hierarchy():
    assert has_permission({"secrets.read"}, "secrets.read")
    assert not has_permission({"secrets.read"}, "secrets.write")
    assert not has_permission({"secrets.read"}, "secrets.admin")

    assert has_permission({"secrets.write"}, "secrets.read")
    assert has_permission({"secrets.write"}, "secrets.write")
    assert not has_permission({"secrets.write"}, "secrets.admin")

    assert has_permission({"secrets.admin"}, "secrets.read")
    assert has_permission({"secrets.admin"}, "secrets.write")
    assert has_permission({"secrets.admin"}, "secrets.admin")


@pytest.mark.asyncio
async def test_platform_secrets_read_denied_without_permission():
    db = AsyncMock()
    auth = AuthContext(user_sys_id="user1", user_name="alice", auth_method="jwt")

    async def mock_execute(stmt):
        result = MagicMock()
        result.scalars.return_value.all.return_value = [["records.*.write"]]
        return result

    db.execute = mock_execute

    with pytest.raises(HTTPException) as exc:
        await assert_platform_action(db, auth, "sys_secret", "read")
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_platform_secrets_write_allowed_with_write_or_admin():
    db = AsyncMock()
    auth = AuthContext(user_sys_id="user1", user_name="alice", auth_method="jwt")

    async def mock_execute_write(stmt):
        result = MagicMock()
        result.scalars.return_value.all.return_value = [["secrets.write"]]
        return result

    db.execute = mock_execute_write
    await assert_platform_action(db, auth, "sys_secret", "write")

    async def mock_execute_admin(stmt):
        result = MagicMock()
        result.scalars.return_value.all.return_value = [["secrets.admin"]]
        return result

    db.execute = mock_execute_admin
    await assert_platform_action(db, auth, "sys_secret", "write")
    await assert_platform_action(db, auth, "sys_secret", "manage")


@pytest.mark.asyncio
async def test_platform_secrets_manage_denied_with_write_only():
    db = AsyncMock()
    auth = AuthContext(user_sys_id="user1", user_name="alice", auth_method="jwt")

    async def mock_execute(stmt):
        result = MagicMock()
        result.scalars.return_value.all.return_value = [["secrets.write"]]
        return result

    db.execute = mock_execute

    with pytest.raises(HTTPException) as exc:
        await assert_platform_action(db, auth, "sys_secret", "manage")
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_resolve_owner_has_write():
    db = AsyncMock()
    auth = AuthContext(user_sys_id="user1", user_name="alice", auth_method="jwt")

    async def mock_execute(stmt):
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        return result

    db.execute = mock_execute

    record = {"sys_id": "rec1", "owner": "user1", "owner_group": ""}
    perms = await resolve_record_permissions(db, auth, "incident", record)
    assert perms == RecordPermissions(read=True, write=True, comment=True, delete=True)


@pytest.mark.asyncio
async def test_assigned_user_has_write_and_comment():
    db = AsyncMock()
    auth = AuthContext(user_sys_id="tech1", user_name="tech", auth_method="jwt")

    async def mock_execute(stmt):
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        return result

    db.execute = mock_execute

    record = {"sys_id": "rec1", "owner": "other", "owner_group": "", "assigned_to": "tech1"}
    perms = await resolve_record_permissions(db, auth, "incident", record)
    assert perms.read is True
    assert perms.write is True
    assert perms.comment is True
    assert perms.delete is False


@pytest.mark.asyncio
async def test_resolve_view_grant_read_only():
    db = AsyncMock()
    auth = AuthContext(user_sys_id="viewer", user_name="viewer", auth_method="jwt")

    call_count = 0

    async def mock_execute(stmt):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1 or call_count == 2:
            result.scalars.return_value.all.return_value = []
        else:
            result.scalars.return_value.all.return_value = ["view"]
        return result

    db.execute = mock_execute

    record = {"sys_id": "rec1", "owner": "other", "owner_group": ""}
    perms = await resolve_record_permissions(db, auth, "incident", record)
    assert perms.read is True
    assert perms.write is False
    assert perms.comment is False


@pytest.mark.asyncio
async def test_resolve_admin_role_wildcard():
    db = AsyncMock()
    auth = AuthContext(user_sys_id="admin1", user_name="admin", auth_method="jwt")

    call_count = 0

    async def mock_execute(stmt):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1:
            result.scalars.return_value.all.return_value = [
                ["records.*.read", "records.*.write", "users.read", "users.write"]
            ]
        else:
            result.scalars.return_value.all.return_value = []
        return result

    db.execute = mock_execute

    record = {"sys_id": "rec1", "owner": "other", "owner_group": ""}
    perms = await resolve_record_permissions(db, auth, "incident", record)
    assert perms.write is True


@pytest.mark.asyncio
async def test_assert_record_action_denies_read_with_404():
    db = AsyncMock()
    auth = AuthContext(user_sys_id="nope", user_name="nope", auth_method="jwt")

    async def mock_execute(stmt):
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        return result

    db.execute = mock_execute

    record = {"sys_id": "rec1", "owner": "other", "owner_group": ""}
    with pytest.raises(HTTPException) as exc:
        await assert_record_action(db, auth, "incident", record, "read")
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_assert_record_action_denies_write_with_403():
    db = AsyncMock()
    auth = AuthContext(user_sys_id="viewer", user_name="viewer", auth_method="jwt")

    call_count = 0

    async def mock_execute(stmt):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count <= 2:
            result.scalars.return_value.all.return_value = []
        else:
            result.scalars.return_value.all.return_value = ["view"]
        return result

    db.execute = mock_execute

    record = {"sys_id": "rec1", "owner": "other", "owner_group": ""}
    with pytest.raises(HTTPException) as exc:
        await assert_record_action(db, auth, "incident", record, "write")
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_platform_user_write_denied_without_permission():
    db = AsyncMock()
    auth = AuthContext(user_sys_id="user1", user_name="alice", auth_method="jwt")

    async def mock_execute(stmt):
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        return result

    db.execute = mock_execute

    with pytest.raises(HTTPException) as exc:
        await assert_platform_action(
            db, auth, "sys_user", "write", target_user_sys_id="other-user"
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_platform_self_write_allowed():
    db = AsyncMock()
    auth = AuthContext(user_sys_id="user1", user_name="alice", auth_method="jwt")

    async def mock_execute(stmt):
        result = MagicMock()
        result.scalars.return_value.all.return_value = [["users.write.self"]]
        return result

    db.execute = mock_execute

    await assert_platform_action(db, auth, "sys_user", "self_write", target_user_sys_id="user1")
