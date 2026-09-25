"""Tests for webhook OAuth client_credentials token resolution."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from app.api.flake.catalog_admin import _webhook_dict
from app.domain.catalog.webhooks import (
    _resolve_oauth_token,
    deliver_webhooks_for_ritm,
)
from app.domain.secrets import SecretResolutionError
from app.models import ScCatItemWebhook, ScWebhook, SysOAuthTokenCache, SysSecret


def _oauth_webhook(**overrides) -> ScWebhook:
    defaults = {
        "sys_id": "wh-oauth",
        "name": "OAuth Webhook",
        "url": "https://target.test/api/hook",
        "method": "POST",
        "headers": {},
        "secret": None,
        "active": True,
        "auth_type": "oauth2_client_credentials",
        "oauth_token_url": "https://auth.test/oauth/token",
        "oauth_client_id": "my-client-id",
        "oauth_client_secret": "aap_client_secret",
        "oauth_scope": None,
    }
    defaults.update(overrides)
    return ScWebhook(**defaults)


# ---------------------------------------------------------------------------
# _webhook_dict — OAuth field serialization (round-trips oauth_client_secret
# by *name*, unlike the HMAC `secret` value which is write-only)
# ---------------------------------------------------------------------------


def test_webhook_dict_round_trips_oauth_client_secret_name():
    webhook = _oauth_webhook(oauth_scope="read write")
    data = _webhook_dict(webhook)

    assert data["auth_type"] == "oauth2_client_credentials"
    assert data["oauth_token_url"] == "https://auth.test/oauth/token"
    assert data["oauth_client_id"] == "my-client-id"
    assert data["oauth_client_secret"] == "aap_client_secret"
    assert data["oauth_scope"] == "read write"
    assert "has_oauth_client_secret" not in data


def test_webhook_dict_defaults_when_oauth_unset():
    webhook = ScWebhook(
        sys_id="wh1",
        name="Plain",
        url="https://example.test/hook",
        method="POST",
        headers={},
        secret=None,
        active=True,
        auth_type="none",
        oauth_token_url=None,
        oauth_client_id=None,
        oauth_client_secret=None,
        oauth_scope=None,
    )
    data = _webhook_dict(webhook)

    assert data["auth_type"] == "none"
    assert data["oauth_token_url"] == ""
    assert data["oauth_client_id"] == ""
    assert data["oauth_client_secret"] == ""
    assert data["oauth_scope"] == ""


# ---------------------------------------------------------------------------
# _resolve_oauth_token — unit tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_oauth_token_returns_none_for_auth_type_none():
    webhook = _oauth_webhook(auth_type="none")
    session = AsyncMock()
    client = AsyncMock()

    result = await _resolve_oauth_token(session, webhook, client)

    assert result is None
    session.execute.assert_not_awaited()
    client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_resolve_oauth_token_uses_cached_token():
    webhook = _oauth_webhook()
    cached = SysOAuthTokenCache(
        sys_id="cache1",
        webhook_id="wh-oauth",
        access_token="cached-tok-123",
        token_type="Bearer",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )

    session = AsyncMock()
    cache_result = MagicMock()
    cache_result.scalar_one_or_none.return_value = cached
    session.execute = AsyncMock(return_value=cache_result)

    client = AsyncMock()

    result = await _resolve_oauth_token(session, webhook, client)

    assert result == "cached-tok-123"
    client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_resolve_oauth_token_fetches_when_cache_expired():
    webhook = _oauth_webhook()
    expired_cache = SysOAuthTokenCache(
        sys_id="cache1",
        webhook_id="wh-oauth",
        access_token="old-token",
        token_type="Bearer",
        expires_at=datetime.now(UTC) - timedelta(minutes=5),
    )
    secret = SysSecret(
        sys_id="sec1",
        name="aap_client_secret",
        value="my-secret-value",
        active=True,
    )

    call_count = {"n": 0}

    async def fake_execute(stmt):
        call_count["n"] += 1
        result = MagicMock()
        if call_count["n"] == 1:
            result.scalar_one_or_none.return_value = expired_cache
        else:
            result.scalars.return_value.all.return_value = [secret]
        return result

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=fake_execute)
    session.flush = AsyncMock()

    token_response = MagicMock()
    token_response.status_code = 200
    token_response.json.return_value = {
        "access_token": "fresh-token-456",
        "token_type": "Bearer",
        "expires_in": 3600,
    }
    token_response.raise_for_status = MagicMock()

    client = AsyncMock()
    client.post = AsyncMock(return_value=token_response)

    result = await _resolve_oauth_token(session, webhook, client)

    assert result == "fresh-token-456"
    assert expired_cache.access_token == "fresh-token-456"
    client.post.assert_awaited_once()
    call_args = client.post.await_args
    assert call_args.args[0] == "https://auth.test/oauth/token"
    form_data = call_args.kwargs["data"]
    assert form_data["grant_type"] == "client_credentials"
    assert form_data["client_id"] == "my-client-id"
    assert form_data["client_secret"] == "my-secret-value"


@pytest.mark.asyncio
async def test_resolve_oauth_token_creates_cache_when_none_exists():
    webhook = _oauth_webhook()
    secret = SysSecret(
        sys_id="sec1",
        name="aap_client_secret",
        value="my-secret-value",
        active=True,
    )

    call_count = {"n": 0}

    async def fake_execute(stmt):
        call_count["n"] += 1
        result = MagicMock()
        if call_count["n"] == 1:
            result.scalar_one_or_none.return_value = None
        else:
            result.scalars.return_value.all.return_value = [secret]
        return result

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=fake_execute)
    session.add = MagicMock()
    session.flush = AsyncMock()

    token_response = MagicMock()
    token_response.status_code = 200
    token_response.json.return_value = {
        "access_token": "new-token-789",
        "token_type": "Bearer",
        "expires_in": 7200,
    }
    token_response.raise_for_status = MagicMock()

    client = AsyncMock()
    client.post = AsyncMock(return_value=token_response)

    result = await _resolve_oauth_token(session, webhook, client)

    assert result == "new-token-789"
    session.add.assert_called_once()
    added = session.add.call_args.args[0]
    assert isinstance(added, SysOAuthTokenCache)
    assert added.access_token == "new-token-789"
    assert added.webhook_id == "wh-oauth"


@pytest.mark.asyncio
async def test_resolve_oauth_token_includes_scope_when_set():
    webhook = _oauth_webhook(oauth_scope="read write")
    secret = SysSecret(
        sys_id="sec1",
        name="aap_client_secret",
        value="my-secret-value",
        active=True,
    )

    call_count = {"n": 0}

    async def fake_execute(stmt):
        call_count["n"] += 1
        result = MagicMock()
        if call_count["n"] == 1:
            result.scalar_one_or_none.return_value = None
        else:
            result.scalars.return_value.all.return_value = [secret]
        return result

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=fake_execute)
    session.add = MagicMock()
    session.flush = AsyncMock()

    token_response = MagicMock()
    token_response.status_code = 200
    token_response.json.return_value = {
        "access_token": "scoped-tok",
        "expires_in": 3600,
    }
    token_response.raise_for_status = MagicMock()

    client = AsyncMock()
    client.post = AsyncMock(return_value=token_response)

    await _resolve_oauth_token(session, webhook, client)

    form_data = client.post.await_args.kwargs["data"]
    assert form_data["scope"] == "read write"


@pytest.mark.asyncio
async def test_resolve_oauth_token_raises_when_secret_missing():
    webhook = _oauth_webhook()

    call_count = {"n": 0}

    async def fake_execute(stmt):
        call_count["n"] += 1
        result = MagicMock()
        if call_count["n"] == 1:
            result.scalar_one_or_none.return_value = None
        else:
            result.scalars.return_value.all.return_value = []
        return result

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=fake_execute)

    client = AsyncMock()

    with pytest.raises(SecretResolutionError, match="aap_client_secret"):
        await _resolve_oauth_token(session, webhook, client)


@pytest.mark.asyncio
async def test_resolve_oauth_token_raises_when_no_secret_name_configured():
    webhook = _oauth_webhook(oauth_client_secret=None)

    session = AsyncMock()
    cache_result = MagicMock()
    cache_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=cache_result)

    client = AsyncMock()

    with pytest.raises(SecretResolutionError, match="oauth_client_secret"):
        await _resolve_oauth_token(session, webhook, client)


@pytest.mark.asyncio
async def test_resolve_oauth_token_raises_when_no_token_url():
    webhook = _oauth_webhook(oauth_token_url=None)

    session = AsyncMock()

    client = AsyncMock()

    with pytest.raises(SecretResolutionError, match="oauth_token_url"):
        await _resolve_oauth_token(session, webhook, client)


# ---------------------------------------------------------------------------
# deliver_webhooks_for_ritm — integration with OAuth
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deliver_webhooks_with_oauth_injects_bearer_header():
    attachment = ScCatItemWebhook(
        sys_id="att1",
        cat_item="item1",
        webhook="wh-oauth",
        payload_template=None,
        trigger_on="order",
        active=True,
    )
    webhook = _oauth_webhook(headers={"X-Custom": "val"})

    db = AsyncMock()
    join_result = MagicMock()
    join_result.all.return_value = [(attachment, webhook)]

    async def fake_execute(stmt):
        return join_result

    db.execute = AsyncMock(side_effect=fake_execute)
    db.add = MagicMock()
    db.flush = AsyncMock()

    response = MagicMock()
    response.status_code = 200
    response.text = "ok"

    mock_client = AsyncMock()
    mock_client.request = AsyncMock(return_value=response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    ritm = {
        "sys_id": "ritm1",
        "number": "RITM0000001",
        "cat_item": "item1",
        "short_description": "Order",
    }

    with patch("app.domain.catalog.webhooks.httpx.AsyncClient", return_value=mock_client):
        with patch(
            "app.domain.catalog.webhooks._load_variables_for_ritm",
            new=AsyncMock(return_value={}),
        ):
            with patch(
                "app.domain.catalog.webhooks._resolve_oauth_token",
                new=AsyncMock(return_value="oauth-tok-abc"),
            ):
                deliveries = await deliver_webhooks_for_ritm(db, ritm, trigger_on="order")

    assert deliveries[0]["success"] is True
    headers = mock_client.request.await_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer oauth-tok-abc"
    assert headers["X-Custom"] == "val"


@pytest.mark.asyncio
async def test_deliver_webhooks_oauth_failure_logs_error_without_crashing():
    attachment = ScCatItemWebhook(
        sys_id="att1",
        cat_item="item1",
        webhook="wh-oauth",
        payload_template=None,
        trigger_on="order",
        active=True,
    )
    webhook = _oauth_webhook()

    db = AsyncMock()
    join_result = MagicMock()
    join_result.all.return_value = [(attachment, webhook)]

    async def fake_execute(stmt):
        return join_result

    db.execute = AsyncMock(side_effect=fake_execute)
    db.add = MagicMock()
    db.flush = AsyncMock()

    mock_client = AsyncMock()
    mock_client.request = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    ritm = {
        "sys_id": "ritm1",
        "number": "RITM0000001",
        "cat_item": "item1",
        "short_description": "Order",
    }

    with patch("app.domain.catalog.webhooks.httpx.AsyncClient", return_value=mock_client):
        with patch(
            "app.domain.catalog.webhooks._load_variables_for_ritm",
            new=AsyncMock(return_value={}),
        ):
            with patch(
                "app.domain.catalog.webhooks._resolve_oauth_token",
                side_effect=SecretResolutionError("secret 'x' not found"),
            ):
                deliveries = await deliver_webhooks_for_ritm(db, ritm, trigger_on="order")

    assert deliveries[0]["success"] is False
    assert "secret" in (deliveries[0]["error_message"] or "").lower()
    mock_client.request.assert_not_awaited()


@pytest.mark.asyncio
async def test_deliver_webhooks_oauth_http_error_logs_without_crashing():
    attachment = ScCatItemWebhook(
        sys_id="att1",
        cat_item="item1",
        webhook="wh-oauth",
        payload_template=None,
        trigger_on="order",
        active=True,
    )
    webhook = _oauth_webhook()

    db = AsyncMock()
    join_result = MagicMock()
    join_result.all.return_value = [(attachment, webhook)]

    async def fake_execute(stmt):
        return join_result

    db.execute = AsyncMock(side_effect=fake_execute)
    db.add = MagicMock()
    db.flush = AsyncMock()

    mock_client = AsyncMock()
    mock_client.request = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    ritm = {
        "sys_id": "ritm1",
        "number": "RITM0000001",
        "cat_item": "item1",
        "short_description": "Order",
    }

    http_error = httpx.HTTPStatusError(
        "401 Unauthorized",
        request=httpx.Request("POST", "https://auth.test/oauth/token"),
        response=httpx.Response(401),
    )

    with patch("app.domain.catalog.webhooks.httpx.AsyncClient", return_value=mock_client):
        with patch(
            "app.domain.catalog.webhooks._load_variables_for_ritm",
            new=AsyncMock(return_value={}),
        ):
            with patch(
                "app.domain.catalog.webhooks._resolve_oauth_token",
                side_effect=http_error,
            ):
                deliveries = await deliver_webhooks_for_ritm(db, ritm, trigger_on="order")

    assert deliveries[0]["success"] is False
    assert "401" in (deliveries[0]["error_message"] or "")
    mock_client.request.assert_not_awaited()
