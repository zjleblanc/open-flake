"""Unit tests for named secret storage and {{secret:name}} resolution."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.flake.catalog_admin import _secret_dict
from app.domain.secrets import (
    SecretResolutionError,
    extract_secret_names,
    load_secret_values,
    resolve_headers,
    resolve_secret_refs,
    substitute_secrets,
    validate_secret_name,
)
from app.models import SysSecret


def test_validate_secret_name_accepts_slug_forms():
    assert validate_secret_name("aap_token") == "aap_token"
    assert validate_secret_name("My-Key_1") == "My-Key_1"
    assert validate_secret_name("  trimmed  ") == "trimmed"


def test_validate_secret_name_rejects_invalid():
    with pytest.raises(ValueError, match="required"):
        validate_secret_name("")
    with pytest.raises(ValueError, match="required"):
        validate_secret_name("   ")
    with pytest.raises(ValueError, match="letters"):
        validate_secret_name("bad name")
    with pytest.raises(ValueError, match="letters"):
        validate_secret_name("has.dot")
    with pytest.raises(ValueError, match="letters"):
        validate_secret_name("has/slash")


def test_extract_secret_names_unique_and_ordered():
    text = "Bearer {{secret:aap_token}} X-Key: {{secret:other}} again {{secret:aap_token}}"
    assert extract_secret_names(text) == ["aap_token", "other"]
    assert extract_secret_names("") == []
    assert extract_secret_names("no refs here") == []
    assert extract_secret_names("{{secret:bad name}}") == []  # space not allowed in name


def test_substitute_secrets_replaces_all_refs():
    text = "Bearer {{secret:aap_token}} / {{secret:aap_token}}"
    assert (
        substitute_secrets(text, {"aap_token": "tok-123"})
        == "Bearer tok-123 / tok-123"
    )


def test_substitute_secrets_multiple_distinct():
    text = "{{secret:user}}:{{secret:pass}}"
    assert (
        substitute_secrets(text, {"user": "alice", "pass": "s3cret"})
        == "alice:s3cret"
    )


def test_substitute_secrets_missing_raises():
    with pytest.raises(SecretResolutionError, match="missing"):
        substitute_secrets("{{secret:missing}}", {})


def test_secret_dict_never_exposes_value():
    secret = SysSecret(
        sys_id="sec1",
        name="aap_token",
        value="super-secret",
        description="AAP token",
        active=True,
    )
    data = _secret_dict(secret)
    assert data == {
        "sys_id": "sec1",
        "name": "aap_token",
        "description": "AAP token",
        "active": True,
        "has_value": True,
    }
    assert "value" not in data
    assert "super-secret" not in data.values()


def test_secret_dict_empty_value_and_description():
    secret = SysSecret(
        sys_id="sec2",
        name="emptyish",
        value="",
        description=None,
        active=False,
    )
    data = _secret_dict(secret)
    assert data["has_value"] is False
    assert data["description"] == ""
    assert data["active"] is False


@pytest.mark.asyncio
async def test_load_secret_values_empty_names_short_circuits():
    session = AsyncMock()
    assert await load_secret_values(session, []) == {}
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_load_secret_values_returns_active_map():
    secret = SysSecret(sys_id="s1", name="aap_token", value="tok", active=True)
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [secret]
    session.execute = AsyncMock(return_value=result)

    values = await load_secret_values(session, ["aap_token", "other"])
    assert values == {"aap_token": "tok"}
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_resolve_secret_refs_passthrough_without_refs():
    session = AsyncMock()
    assert await resolve_secret_refs(session, "Bearer static") == "Bearer static"
    assert await resolve_secret_refs(session, "") == ""
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_resolve_secret_refs_substitutes_loaded_values():
    secret = SysSecret(sys_id="s1", name="aap_token", value="tok-xyz", active=True)
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [secret]
    session.execute = AsyncMock(return_value=result)

    resolved = await resolve_secret_refs(
        session, "Bearer {{secret:aap_token}}"
    )
    assert resolved == "Bearer tok-xyz"


@pytest.mark.asyncio
async def test_resolve_secret_refs_missing_raises():
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=result)

    with pytest.raises(SecretResolutionError, match="missing"):
        await resolve_secret_refs(session, "Bearer {{secret:missing}}")


@pytest.mark.asyncio
async def test_resolve_headers_none_and_non_dict():
    session = AsyncMock()
    assert await resolve_headers(session, None) == {}
    assert await resolve_headers(session, "not-a-dict") == {}  # type: ignore[arg-type]
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_resolve_headers_static_and_templated():
    secret = SysSecret(sys_id="s1", name="aap_token", value="tok-xyz", active=True)
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [secret]
    session.execute = AsyncMock(return_value=result)

    resolved = await resolve_headers(
        session,
        {
            "X-Static": "plain",
            "Authorization": "Bearer {{secret:aap_token}}",
        },
    )
    assert resolved == {
        "X-Static": "plain",
        "Authorization": "Bearer tok-xyz",
    }


@pytest.mark.asyncio
async def test_resolve_headers_fails_when_any_ref_missing():
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=result)

    with pytest.raises(SecretResolutionError, match="gone"):
        await resolve_headers(
            session,
            {"Authorization": "Bearer {{secret:gone}}"},
        )
