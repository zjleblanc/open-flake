"""Tests for the table/class registry admin API (create/extend/delete classes)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.auth.deps import AuthContext
from app.domain.cmdb.constants import CMDB_ROOT
from app.domain.cmdb.registry import FieldMeta, _RegistrySnapshot
from app.models import SysDbObject
from fastapi import HTTPException


def _auth(user_sys_id: str = "admin1", user_name: str = "admin") -> AuthContext:
    return AuthContext(user_sys_id=user_sys_id, user_name=user_name, auth_method="session")


def _obj(
    name: str, *, super_class: str | None, is_extendable: bool = False, **kwargs
) -> SysDbObject:
    return SysDbObject(
        sys_id=name,
        name=name,
        super_class=super_class,
        label=kwargs.pop("label", name),
        is_logical=kwargs.pop("is_logical", False),
        is_extendable=is_extendable,
        storage_type=kwargs.pop("storage_type", "sti"),
        base_table=kwargs.pop("base_table", CMDB_ROOT),
        user_defined=kwargs.pop("user_defined", False),
    )


def _load_snapshot() -> None:
    from app.domain.cmdb import registry

    classes = {
        "cmdb": _obj(
            "cmdb", super_class=None, is_logical=True, storage_type="physical", base_table=None
        ),
        CMDB_ROOT: _obj(
            CMDB_ROOT,
            super_class="cmdb",
            is_extendable=True,
            storage_type="physical",
            base_table=None,
        ),
        "cmdb_ci_computer": _obj("cmdb_ci_computer", super_class=CMDB_ROOT),
        "cmdb_ci_server": _obj(
            "cmdb_ci_server", super_class="cmdb_ci_computer", is_extendable=True
        ),
        "cmdb_ci_linux_server": _obj("cmdb_ci_linux_server", super_class="cmdb_ci_server"),
        "incident": _obj("incident", super_class=None, storage_type="physical", base_table=None),
    }
    children = {
        "cmdb": {CMDB_ROOT},
        CMDB_ROOT: {"cmdb_ci_computer"},
        "cmdb_ci_computer": {"cmdb_ci_server"},
        "cmdb_ci_server": {"cmdb_ci_linux_server"},
        "cmdb_ci_linux_server": set(),
        "incident": set(),
    }
    fields = {
        CMDB_ROOT: [FieldMeta("name", "Name", "string", CMDB_ROOT, "column")],
        "cmdb_ci_server": [
            FieldMeta("host_name", "Host name", "string", "cmdb_ci_server", "column"),
        ],
    }
    registry._snapshot = _RegistrySnapshot(
        classes=classes, fields_by_class=fields, children=children
    )


@pytest.fixture(autouse=True)
def snapshot():
    from app.domain.cmdb import registry

    _load_snapshot()
    yield
    registry.clear_cache()


@pytest.fixture(autouse=True)
def _bypass_admin_check():
    with patch(
        "app.api.flake.admin_tables._require_table_admin",
        new=AsyncMock(),
    ):
        yield


@pytest.mark.asyncio
async def test_list_tables_returns_full_registry():
    from app.api.flake import admin_tables as admin_api

    result = await admin_api.list_tables(auth=_auth(), db=AsyncMock())
    names = {row["name"] for row in result["result"]}
    assert names == {
        "cmdb",
        "cmdb_ci",
        "cmdb_ci_computer",
        "cmdb_ci_server",
        "cmdb_ci_linux_server",
        "incident",
    }
    server_row = next(row for row in result["result"] if row["name"] == "cmdb_ci_server")
    assert server_row["is_extendable"] is True
    assert server_row["children_count"] == 1
    assert result["import_warnings"] == []


@pytest.mark.asyncio
async def test_list_tables_surfaces_import_warnings():
    from app.api.flake import admin_tables as admin_api
    from app.domain.cmdb import registry

    registry.clear_import_warnings()
    registry.record_import_warning(
        "Skipped hierarchy definition for 'cmdb_ci_router': a table with this name "
        "already exists and was created via the admin UI.",
        class_name="cmdb_ci_router",
    )

    result = await admin_api.list_tables(auth=_auth(), db=AsyncMock())
    assert len(result["import_warnings"]) == 1
    assert result["import_warnings"][0]["class_name"] == "cmdb_ci_router"

    registry.clear_import_warnings()


@pytest.mark.asyncio
async def test_get_table_schema_merges_ancestor_fields():
    from app.api.flake import admin_tables as admin_api

    result = await admin_api.get_table_schema("cmdb_ci_linux_server", auth=_auth(), db=AsyncMock())
    field_names = {f["name"] for f in result["result"]["fields"]}
    assert "name" in field_names
    assert "host_name" in field_names


@pytest.mark.asyncio
async def test_get_table_schema_unknown_table_404():
    from app.api.flake import admin_tables as admin_api

    with pytest.raises(HTTPException) as exc:
        await admin_api.get_table_schema("not_a_table", auth=_auth(), db=AsyncMock())
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_create_table_extends_extendable_class():
    from app.api.flake import admin_tables as admin_api

    db = AsyncMock()
    ensure_mock = AsyncMock(return_value=_obj("cmdb_ci_gpu_server", super_class="cmdb_ci_server"))
    upsert_mock = AsyncMock()
    refresh_mock = AsyncMock()

    with (
        patch("app.api.flake.admin_tables.ensure_class", new=ensure_mock),
        patch("app.api.flake.admin_tables.upsert_field", new=upsert_mock),
        patch("app.api.flake.admin_tables.refresh_cache", new=refresh_mock),
    ):
        result = await admin_api.create_table(
            {
                "name": "cmdb_ci_gpu_server",
                "label": "GPU Server",
                "super_class": "cmdb_ci_server",
                "fields": [{"name": "gpu_count", "type": "integer"}],
            },
            auth=_auth(),
            db=db,
        )

    ensure_mock.assert_awaited_once()
    upsert_mock.assert_awaited_once()
    db.commit.assert_awaited_once()
    refresh_mock.assert_awaited_once_with(db)
    assert result["result"]["class_name"] == "cmdb_ci_gpu_server"


@pytest.mark.asyncio
async def test_create_table_rejects_duplicate_name_of_builtin_class():
    from app.api.flake import admin_tables as admin_api

    with pytest.raises(HTTPException) as exc:
        await admin_api.create_table(
            {"name": "cmdb_ci_server", "super_class": CMDB_ROOT}, auth=_auth(), db=AsyncMock()
        )
    assert exc.value.status_code == 409
    assert "built-in class hierarchy" in exc.value.detail


@pytest.mark.asyncio
async def test_create_table_rejects_duplicate_name_of_custom_table():
    from app.api.flake import admin_tables as admin_api
    from app.domain.cmdb import registry

    registry._snapshot.classes["cmdb_ci_linux_server"].user_defined = True

    with pytest.raises(HTTPException) as exc:
        await admin_api.create_table(
            {"name": "cmdb_ci_linux_server", "super_class": CMDB_ROOT},
            auth=_auth(),
            db=AsyncMock(),
        )
    assert exc.value.status_code == 409
    assert "custom table" in exc.value.detail


@pytest.mark.asyncio
async def test_create_table_rejects_invalid_name():
    from app.api.flake import admin_tables as admin_api

    with pytest.raises(HTTPException) as exc:
        await admin_api.create_table(
            {"name": "CmdbCiBad Name!", "super_class": CMDB_ROOT}, auth=_auth(), db=AsyncMock()
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_create_table_rejects_non_extendable_parent():
    from app.api.flake import admin_tables as admin_api

    with pytest.raises(HTTPException) as exc:
        await admin_api.create_table(
            {"name": "cmdb_ci_new_thing", "super_class": "cmdb_ci_computer"},
            auth=_auth(),
            db=AsyncMock(),
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_create_table_rejects_unknown_parent():
    from app.api.flake import admin_tables as admin_api

    with pytest.raises(HTTPException) as exc:
        await admin_api.create_table(
            {"name": "cmdb_ci_new_thing", "super_class": "cmdb_ci_does_not_exist"},
            auth=_auth(),
            db=AsyncMock(),
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_create_table_rejects_non_cmdb_parent():
    from app.api.flake import admin_tables as admin_api
    from app.domain.cmdb import registry

    registry._snapshot.classes["incident"].is_extendable = True

    with pytest.raises(HTTPException) as exc:
        await admin_api.create_table(
            {"name": "incident_extra", "super_class": "incident"}, auth=_auth(), db=AsyncMock()
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_add_table_field():
    from app.api.flake import admin_tables as admin_api

    db = AsyncMock()
    upsert_mock = AsyncMock()
    refresh_mock = AsyncMock()

    with (
        patch("app.api.flake.admin_tables.upsert_field", new=upsert_mock),
        patch("app.api.flake.admin_tables.refresh_cache", new=refresh_mock),
    ):
        await admin_api.add_table_field(
            "cmdb_ci_server", {"name": "rack_unit", "type": "integer"}, auth=_auth(), db=db
        )

    upsert_mock.assert_awaited_once()
    db.commit.assert_awaited_once()
    refresh_mock.assert_awaited_once_with(db)


@pytest.mark.asyncio
async def test_add_table_field_unknown_table_404():
    from app.api.flake import admin_tables as admin_api

    with pytest.raises(HTTPException) as exc:
        await admin_api.add_table_field(
            "not_a_table", {"name": "field1", "type": "string"}, auth=_auth(), db=AsyncMock()
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_table_rejects_with_children():
    from app.api.flake import admin_tables as admin_api
    from app.domain.cmdb import registry

    registry._snapshot.classes["cmdb_ci_server"].user_defined = True
    with pytest.raises(HTTPException) as exc:
        await admin_api.delete_table("cmdb_ci_server", auth=_auth(), db=AsyncMock())
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_delete_table_rejects_non_user_defined():
    from app.api.flake import admin_tables as admin_api

    with pytest.raises(HTTPException) as exc:
        await admin_api.delete_table("cmdb_ci_linux_server", auth=_auth(), db=AsyncMock())
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_delete_table_rejects_with_existing_records():
    from app.api.flake import admin_tables as admin_api
    from app.domain.cmdb import registry

    registry._snapshot.classes["cmdb_ci_linux_server"].user_defined = True

    db = AsyncMock()
    count_result = MagicMock()
    count_result.scalar.return_value = 3
    db.execute = AsyncMock(return_value=count_result)

    with pytest.raises(HTTPException) as exc:
        await admin_api.delete_table("cmdb_ci_linux_server", auth=_auth(), db=db)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_delete_table_success():
    from app.api.flake import admin_tables as admin_api
    from app.domain.cmdb import registry

    registry._snapshot.classes["cmdb_ci_linux_server"].user_defined = True

    db = AsyncMock()
    count_result = MagicMock()
    count_result.scalar.return_value = 0
    row_result = MagicMock()
    row_result.scalar_one_or_none.return_value = registry._snapshot.classes["cmdb_ci_linux_server"]

    call_count = {"n": 0}

    async def fake_execute(_stmt):
        call_count["n"] += 1
        return count_result if call_count["n"] == 1 else row_result

    db.execute = AsyncMock(side_effect=fake_execute)
    refresh_mock = AsyncMock()

    with patch("app.api.flake.admin_tables.refresh_cache", new=refresh_mock):
        response = await admin_api.delete_table("cmdb_ci_linux_server", auth=_auth(), db=db)

    db.delete.assert_awaited_once()
    db.commit.assert_awaited_once()
    refresh_mock.assert_awaited_once_with(db)
    assert response.status_code == 204
