"""Tests for service catalog lite: variables, ordering, and webhooks."""

from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.domain.catalog.ordering import validate_variables
from app.domain.catalog.webhooks import (
    _render_payload,
    _sign_body,
    default_payload,
    deliver_webhooks_for_ritm,
    preview_payload,
)
from app.models import ItemOptionNew, ScCatItemWebhook, ScWebhook, SysSecret


def _var(**kwargs) -> ItemOptionNew:
    defaults = {
        "sys_id": "var1",
        "cat_item": "item1",
        "name": "field",
        "question_text": "Field",
        "type": "string",
        "mandatory": False,
        "default_value": None,
        "order": 100,
        "reference_table": None,
        "reference_filter": None,
        "choice_list": [],
        "help_text": None,
        "read_only": False,
        "hidden": False,
        "active": True,
    }
    defaults.update(kwargs)
    return ItemOptionNew(**defaults)


def test_validate_variables_requires_mandatory():
    definitions = [_var(name="sn_vm_name", mandatory=True)]
    with pytest.raises(HTTPException) as exc:
        validate_variables(definitions, {})
    assert exc.value.status_code == 400
    assert "required" in exc.value.detail


def test_validate_variables_select_box_choices():
    definitions = [
        _var(
            name="sn_target_platform",
            type="select_box",
            mandatory=True,
            choice_list=[
                {"value": "rhel_10", "label": "RHEL 10"},
                {"value": "rhel_9", "label": "RHEL 9"},
            ],
        )
    ]
    result = validate_variables(definitions, {"sn_target_platform": "rhel_9"})
    assert result == {"sn_target_platform": "rhel_9"}

    with pytest.raises(HTTPException):
        validate_variables(definitions, {"sn_target_platform": "windows_99"})


def test_validate_variables_rejects_unknown():
    definitions = [_var(name="sn_vm_name")]
    with pytest.raises(HTTPException) as exc:
        validate_variables(definitions, {"extra": "x"})
    assert "Unknown variables" in exc.value.detail


def test_validate_variables_boolean_and_integer():
    definitions = [
        _var(name="enabled", type="boolean", mandatory=True),
        _var(name="count", type="integer", mandatory=True),
    ]
    result = validate_variables(definitions, {"enabled": True, "count": "3"})
    assert result == {"enabled": "true", "count": "3"}


def test_sign_body_hmac():
    body = b'{"hello":"world"}'
    signature = _sign_body("secret", body)
    expected = hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    assert signature == expected
    assert _sign_body(None, body) is None


def test_render_payload_default_and_template():
    attachment = ScCatItemWebhook(
        sys_id="att1",
        cat_item="item1",
        webhook="wh1",
        payload_template=None,
        trigger_on="order",
        active=True,
    )
    ritm = {
        "sys_id": "ritm1",
        "number": "RITM0000001",
        "short_description": "Order",
        "state": "1",
        "stage": "fulfillment",
    }
    variables = {"sn_vm_name": "web01"}
    payload = _render_payload(attachment, ritm=ritm, variables=variables)
    assert payload["event"] == "catalog_order"
    assert payload["request_item"]["number"] == "RITM0000001"
    assert payload["variables"]["sn_vm_name"] == "web01"

    attachment.payload_template = (
        '{"host":"$var_sn_vm_name","number":"$number","event":"$event"}'
    )
    rendered = _render_payload(
        attachment, ritm=ritm, variables=variables, event="catalog_order"
    )
    assert rendered == {
        "host": "web01",
        "number": "RITM0000001",
        "event": "catalog_order",
    }

def test_preview_payload_defaults_to_ritm_shape():
    preview = preview_payload(None)
    assert preview["event"] == "catalog_order"
    assert "request_item" in preview
    assert "number" in preview["request_item"]
    custom = preview_payload('{"n":"$number"}')
    assert custom == {"n": "RITM0000001"}


def test_default_payload_shape():
    payload = default_payload(
        {"sys_id": "r1", "number": "RITM1", "short_description": "x"},
        {"a": "b"},
    )
    assert payload["request_item"]["sys_id"] == "r1"
    assert payload["variables"] == {"a": "b"}


@pytest.mark.asyncio
async def test_order_catalog_item_creates_request_and_ritm():
    from app.domain.catalog.ordering import order_catalog_item
    from app.models import ServiceCatalogItem

    item = ServiceCatalogItem(
        sys_id="item1",
        catalog_sys_id="cat1",
        name="Provision VM",
        short_description="Order a VM",
        description="### Order a VM",
        active=True,
        price="0",
        fulfillment_group="group1",
    )
    db = AsyncMock()
    definitions = [
        _var(name="sn_vm_name", mandatory=True),
        _var(
            name="sn_target_platform",
            type="select_box",
            mandatory=True,
            choice_list=[{"value": "rhel_10", "label": "RHEL 10"}],
        ),
        _var(
            name="sn_aws_region",
            type="select_box",
            mandatory=True,
            choice_list=[{"value": "us-east-2", "label": "us-east-2"}],
        ),
    ]

    created = []

    async def fake_create(db_arg, table, payload, user_sys_id, *args, **kwargs):
        record = {
            "sys_id": f"{table}-{len(created)+1}",
            "number": f"{table.upper()}0000001",
            **payload,
        }
        created.append((table, record))
        return record

    with patch(
        "app.domain.catalog.ordering.load_active_variables",
        new=AsyncMock(return_value=definitions),
    ), patch(
        "app.domain.catalog.ordering.create_record",
        new=AsyncMock(side_effect=fake_create),
    ):
        result = await order_catalog_item(
            db,
            item,
            user_sys_id="user1",
            variables={
                "sn_vm_name": "lab-web-99",
                "sn_target_platform": "rhel_10",
                "sn_aws_region": "us-east-2",
            },
            cmdb_ci="ci1",
        )

    tables = [table for table, _ in created]
    assert tables == ["sc_request", "sc_req_item", "sc_item_option", "sc_item_option", "sc_item_option", "sc_task"]
    assert result["request_number"]
    assert result["variables"]["sn_vm_name"] == "lab-web-99"
    assert result["request_item"]["cat_item"] == "item1"
    assert result["request_item"]["cmdb_ci"] == "ci1"


@pytest.mark.asyncio
async def test_deliver_webhooks_for_ritm_posts_signed_payload():
    attachment = ScCatItemWebhook(
        sys_id="att1",
        cat_item="item1",
        webhook="wh1",
        payload_template=None,
        trigger_on="order",
        active=True,
    )
    webhook = ScWebhook(
        sys_id="wh1",
        name="AAP",
        url="https://example.test/hook",
        method="POST",
        headers={"X-Custom": "1"},
        secret="topsecret",
        active=True,
    )

    db = AsyncMock()
    join_result = MagicMock()
    join_result.all.return_value = [(attachment, webhook)]

    async def fake_execute(stmt):
        return join_result

    db.execute = AsyncMock(side_effect=fake_execute)
    db.add = MagicMock()
    db.flush = AsyncMock()

    response = MagicMock()
    response.status_code = 202
    response.text = "accepted"

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
            new=AsyncMock(return_value={"sn_vm_name": "web01"}),
        ):
            deliveries = await deliver_webhooks_for_ritm(db, ritm, trigger_on="order")

    assert len(deliveries) == 1
    assert deliveries[0]["success"] is True
    assert deliveries[0]["status_code"] == 202
    assert deliveries[0]["webhook_id"] == "wh1"
    assert deliveries[0]["attachment_id"] == "att1"
    call_kwargs = mock_client.request.await_args.kwargs
    assert call_kwargs["headers"]["X-Custom"] == "1"
    assert "X-OpenFlake-Signature" in call_kwargs["headers"]
    body = call_kwargs["content"]
    expected = hmac.new(b"topsecret", body, hashlib.sha256).hexdigest()
    assert call_kwargs["headers"]["X-OpenFlake-Signature"] == expected
    payload = json.loads(body.decode("utf-8"))
    assert payload["variables"]["sn_vm_name"] == "web01"
    assert payload["request_item"]["number"] == "RITM0000001"
    db.add.assert_called()


@pytest.mark.asyncio
async def test_deliver_webhooks_resolves_secret_header_templates():
    attachment = ScCatItemWebhook(
        sys_id="att1",
        cat_item="item1",
        webhook="wh1",
        payload_template=None,
        trigger_on="order",
        active=True,
    )
    webhook = ScWebhook(
        sys_id="wh1",
        name="AAP",
        url="https://example.test/hook",
        method="POST",
        headers={"Authorization": "Bearer {{secret:aap_token}}"},
        secret=None,
        active=True,
    )
    secret = SysSecret(
        sys_id="sec1",
        name="aap_token",
        value="super-secret-token",
        active=True,
    )

    db = AsyncMock()
    join_result = MagicMock()
    join_result.all.return_value = [(attachment, webhook)]
    secret_result = MagicMock()
    secret_result.scalars.return_value.all.return_value = [secret]
    call_count = {"n": 0}

    async def fake_execute(stmt):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return join_result
        return secret_result

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
            deliveries = await deliver_webhooks_for_ritm(db, ritm, trigger_on="order")

    assert deliveries[0]["success"] is True
    headers = mock_client.request.await_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer super-secret-token"


@pytest.mark.asyncio
async def test_deliver_webhooks_fails_on_missing_secret_ref():
    attachment = ScCatItemWebhook(
        sys_id="att1",
        cat_item="item1",
        webhook="wh1",
        payload_template=None,
        trigger_on="order",
        active=True,
    )
    webhook = ScWebhook(
        sys_id="wh1",
        name="AAP",
        url="https://example.test/hook",
        method="POST",
        headers={"Authorization": "Bearer {{secret:missing}}"},
        secret=None,
        active=True,
    )

    db = AsyncMock()
    join_result = MagicMock()
    join_result.all.return_value = [(attachment, webhook)]
    secret_result = MagicMock()
    secret_result.scalars.return_value.all.return_value = []
    call_count = {"n": 0}

    async def fake_execute(stmt):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return join_result
        return secret_result

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
            deliveries = await deliver_webhooks_for_ritm(db, ritm, trigger_on="order")

    assert deliveries[0]["success"] is False
    assert "missing" in (deliveries[0]["error_message"] or "")
    mock_client.request.assert_not_awaited()


def test_validate_variables_reference_type():
    definitions = [
        _var(
            name="assigned_user",
            type="reference",
            mandatory=True,
            reference_table="sys_user",
            reference_filter="active=true",
        )
    ]
    result = validate_variables(definitions, {"assigned_user": "user-sys-id-1"})
    assert result == {"assigned_user": "user-sys-id-1"}


def _auth(user_sys_id: str = "admin1", user_name: str = "admin"):
    from app.auth.deps import AuthContext

    return AuthContext(user_sys_id=user_sys_id, user_name=user_name, auth_method="jwt")


@pytest.mark.asyncio
async def test_can_read_table_admin_sees_all():
    from app.auth.rbac import can_read_table

    db = AsyncMock()
    auth = _auth()
    with patch(
        "app.auth.rbac.get_user_permissions",
        new=AsyncMock(return_value={"records.*.read"}),
    ):
        assert await can_read_table(db, auth, "incident") is True
        assert await can_read_table(db, auth, "sys_user") is True
        assert await can_read_table(db, auth, "sc_webhook") is True


@pytest.mark.asyncio
async def test_can_read_table_rbac_table_requires_permission():
    from app.auth.rbac import can_read_table

    db = AsyncMock()
    auth = _auth("user1", "alice")
    with patch(
        "app.auth.rbac.get_user_permissions",
        new=AsyncMock(return_value={"users.read"}),
    ):
        assert await can_read_table(db, auth, "incident") is False
        assert await can_read_table(db, auth, "sys_user") is True


@pytest.mark.asyncio
async def test_can_read_table_platform_table_requires_read():
    from app.auth.rbac import can_read_table

    db = AsyncMock()
    auth = _auth("user1", "alice")
    with patch(
        "app.auth.rbac.get_user_permissions",
        new=AsyncMock(return_value=set()),
    ):
        assert await can_read_table(db, auth, "sys_user") is False
    with patch(
        "app.auth.rbac.get_user_permissions",
        new=AsyncMock(return_value={"users.read"}),
    ):
        assert await can_read_table(db, auth, "sys_user") is True


@pytest.mark.asyncio
async def test_can_read_table_other_tables_accessible():
    from app.auth.rbac import can_read_table

    db = AsyncMock()
    auth = _auth("user1", "alice")
    with patch(
        "app.auth.rbac.get_user_permissions",
        new=AsyncMock(return_value=set()),
    ):
        assert await can_read_table(db, auth, "sc_webhook") is True
        assert await can_read_table(db, auth, "item_option_new") is True


@pytest.mark.asyncio
async def test_get_variable_options_requires_reference_type():
    from app.api.flake import catalog as catalog_api
    from app.models import ServiceCatalogItem

    item = ServiceCatalogItem(
        sys_id="item1",
        catalog_sys_id="cat1",
        name="Item",
        active=True,
    )
    variable = _var(name="field", type="string")

    db = AsyncMock()
    db.get = AsyncMock(return_value=item)
    var_result = MagicMock()
    var_result.scalar_one_or_none.return_value = variable
    db.execute = AsyncMock(return_value=var_result)

    with pytest.raises(HTTPException) as exc:
        await catalog_api.get_variable_options(
            "item1", "field", depends_on=None, auth=_auth(), db=db
        )
    assert exc.value.status_code == 400
    assert "reference" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_get_variable_options_requires_reference_table():
    from app.api.flake import catalog as catalog_api
    from app.models import ServiceCatalogItem

    item = ServiceCatalogItem(
        sys_id="item1",
        catalog_sys_id="cat1",
        name="Item",
        active=True,
    )
    variable = _var(name="assignee", type="reference", reference_table=None)

    db = AsyncMock()
    db.get = AsyncMock(return_value=item)
    var_result = MagicMock()
    var_result.scalar_one_or_none.return_value = variable
    db.execute = AsyncMock(return_value=var_result)

    with pytest.raises(HTTPException) as exc:
        await catalog_api.get_variable_options(
            "item1", "assignee", depends_on=None, auth=_auth(), db=db
        )
    assert exc.value.status_code == 400
    assert "reference_table" in exc.value.detail


@pytest.mark.asyncio
async def test_get_variable_options_applies_base_filter():
    from app.api.flake import catalog as catalog_api
    from app.models import ServiceCatalogItem
    from app.query.parser import QueryCondition

    item = ServiceCatalogItem(
        sys_id="item1",
        catalog_sys_id="cat1",
        name="Item",
        active=True,
    )
    variable = _var(
        name="assignee",
        type="reference",
        reference_table="sys_user",
        reference_filter="active=true",
    )

    db = AsyncMock()
    db.get = AsyncMock(return_value=item)
    var_result = MagicMock()
    var_result.scalar_one_or_none.return_value = variable
    db.execute = AsyncMock(return_value=var_result)

    captured: dict = {}

    async def fake_list_records(db_arg, table, conditions, **kwargs):
        captured["table"] = table
        captured["conditions"] = conditions
        return (
            [{"sys_id": "u1", "user_name": "alice", "name": "Alice"}],
            1,
        )

    with patch(
        "app.api.flake.catalog.list_records",
        new=AsyncMock(side_effect=fake_list_records),
    ):
        result = await catalog_api.get_variable_options(
            "item1", "assignee", depends_on=None, auth=_auth(), db=db
        )

    assert captured["table"] == "sys_user"
    assert any(
        isinstance(c, QueryCondition) and c.field == "active" and c.value == "true"
        for c in captured["conditions"]
    )
    assert result["result"]["options"][0]["value"] == "u1"
    assert result["result"]["options"][0]["label"] == "Alice"


@pytest.mark.asyncio
async def test_get_variable_options_condition_override():
    from app.api.flake import catalog as catalog_api
    from app.models import ItemOptionNewCondition, ServiceCatalogItem

    item = ServiceCatalogItem(
        sys_id="item1",
        catalog_sys_id="cat1",
        name="Item",
        active=True,
    )
    variable = _var(
        sys_id="var-ref",
        name="assignee",
        type="reference",
        reference_table="sys_user",
        reference_filter="active=true",
    )
    depends_var = _var(sys_id="var-dep", name="department", type="string")
    condition = ItemOptionNewCondition(
        sys_id="cond1",
        variable="var-ref",
        condition_type="filter",
        depends_on="var-dep",
        operator="=",
        value="engineering",
        filter_override="department=engineering",
        active=True,
    )

    db = AsyncMock()

    async def fake_get(model, key):
        if model is ServiceCatalogItem:
            return item
        if key == "var-dep":
            return depends_var
        return None

    db.get = AsyncMock(side_effect=fake_get)

    var_result = MagicMock()
    var_result.scalar_one_or_none.return_value = variable
    cond_result = MagicMock()
    cond_result.scalars.return_value.all.return_value = [condition]
    call_count = {"n": 0}

    async def fake_execute(stmt):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return var_result
        return cond_result

    db.execute = AsyncMock(side_effect=fake_execute)

    captured: dict = {}

    async def fake_list_records(db_arg, table, conditions, **kwargs):
        captured["conditions"] = conditions
        return ([{"sys_id": "u1", "user_name": "eng1"}], 1)

    with patch(
        "app.api.flake.catalog.list_records",
        new=AsyncMock(side_effect=fake_list_records),
    ):
        await catalog_api.get_variable_options(
            "item1",
            "assignee",
            depends_on="department=engineering",
            auth=_auth(),
            db=db,
        )

    assert any(c.field == "department" and c.value == "engineering" for c in captured["conditions"])
    assert not any(c.field == "active" for c in captured["conditions"])


@pytest.mark.asyncio
async def test_get_variable_options_condition_operators():
    from app.api.flake import catalog as catalog_api
    from app.models import ItemOptionNewCondition, ServiceCatalogItem

    item = ServiceCatalogItem(
        sys_id="item1",
        catalog_sys_id="cat1",
        name="Item",
        active=True,
    )
    variable = _var(
        sys_id="var-ref",
        name="assignee",
        type="reference",
        reference_table="sys_user",
        reference_filter="active=true",
    )
    depends_var = _var(sys_id="var-dep", name="role", type="string")

    cases = [
        ("=", "admin", "admin", True),
        ("=", "admin", "user", False),
        ("!=", "admin", "user", True),
        ("IN", "admin,itil", "itil", True),
        ("NOT_IN", "admin,itil", "guest", True),
        ("EMPTY", None, "", True),
        ("NOT_EMPTY", None, "x", True),
    ]

    for operator, cond_value, current, should_override in cases:
        condition = ItemOptionNewCondition(
            sys_id="cond1",
            variable="var-ref",
            condition_type="filter",
            depends_on="var-dep",
            operator=operator,
            value=cond_value,
            filter_override="role=matched",
            active=True,
        )

        db = AsyncMock()

        async def fake_get(model, key, _depends=depends_var):
            if model is ServiceCatalogItem:
                return item
            if key == "var-dep":
                return _depends
            return None

        db.get = AsyncMock(side_effect=fake_get)
        var_result = MagicMock()
        var_result.scalar_one_or_none.return_value = variable
        cond_result = MagicMock()
        cond_result.scalars.return_value.all.return_value = [condition]
        call_count = {"n": 0}

        async def fake_execute(stmt):
            call_count["n"] += 1
            return var_result if call_count["n"] == 1 else cond_result

        db.execute = AsyncMock(side_effect=fake_execute)
        captured: dict = {}

        async def fake_list_records(db_arg, table, conditions, **kwargs):
            captured["conditions"] = conditions
            return ([], 0)

        with patch(
            "app.api.flake.catalog.list_records",
            new=AsyncMock(side_effect=fake_list_records),
        ):
            await catalog_api.get_variable_options(
                "item1",
                "assignee",
                depends_on=f"role={current}",
                auth=_auth(),
                db=db,
            )

        fields = {c.field for c in captured["conditions"]}
        if should_override:
            assert "role" in fields, f"operator {operator} should override"
            assert "active" not in fields
        else:
            assert "active" in fields, f"operator {operator} should keep base filter"


@pytest.mark.asyncio
async def test_list_reference_tables():
    from app.api.flake import catalog_admin as admin_api
    from app.domain.registry import TABLE_MODELS

    db = AsyncMock()
    auth = _auth()

    with patch(
        "app.api.flake.catalog_admin._require_catalog_admin",
        new=AsyncMock(),
    ), patch(
        "app.api.flake.catalog_admin.can_read_table",
        new=AsyncMock(return_value=True),
    ):
        result = await admin_api.list_reference_tables(auth=auth, db=db)

    names = [t["name"] for t in result["result"]]
    assert names == sorted(TABLE_MODELS.keys())
    assert "sys_user" in names
    assert "incident" in names


@pytest.mark.asyncio
async def test_list_table_fields():
    from app.api.flake import catalog_admin as admin_api

    db = AsyncMock()
    auth = _auth()

    with patch(
        "app.api.flake.catalog_admin._require_catalog_admin",
        new=AsyncMock(),
    ), patch(
        "app.api.flake.catalog_admin.can_read_table",
        new=AsyncMock(return_value=True),
    ):
        result = await admin_api.list_table_fields("sys_user", auth=auth, db=db)

    names = {f["name"] for f in result["result"]}
    assert "user_name" in names
    assert "sys_id" in names
    assert "user_password" not in names


@pytest.mark.asyncio
async def test_list_table_fields_unknown_table():
    from app.api.flake import catalog_admin as admin_api

    db = AsyncMock()
    auth = _auth()

    with patch(
        "app.api.flake.catalog_admin._require_catalog_admin",
        new=AsyncMock(),
    ):
        with pytest.raises(HTTPException) as exc:
            await admin_api.list_table_fields("not_a_table", auth=auth, db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_list_table_fields_forbidden_without_read():
    from app.api.flake import catalog_admin as admin_api

    db = AsyncMock()
    auth = _auth("user1", "alice")

    with patch(
        "app.api.flake.catalog_admin._require_catalog_admin",
        new=AsyncMock(),
    ), patch(
        "app.api.flake.catalog_admin.can_read_table",
        new=AsyncMock(return_value=False),
    ):
        with pytest.raises(HTTPException) as exc:
            await admin_api.list_table_fields("incident", auth=auth, db=db)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_list_reference_tables_filters_by_rbac():
    from app.api.flake import catalog_admin as admin_api

    db = AsyncMock()
    auth = _auth("user1", "alice")

    async def fake_can_read(_db, _auth, table: str) -> bool:
        return table in {"sys_user", "sc_webhook"}

    with patch(
        "app.api.flake.catalog_admin._require_catalog_admin",
        new=AsyncMock(),
    ), patch(
        "app.api.flake.catalog_admin.can_read_table",
        new=AsyncMock(side_effect=fake_can_read),
    ):
        result = await admin_api.list_reference_tables(auth=auth, db=db)

    names = {t["name"] for t in result["result"]}
    assert names == {"sc_webhook", "sys_user"}


@pytest.mark.asyncio
async def test_options_endpoint_respects_rbac():
    """Confirm auth is forwarded to list_records so RBAC filtering applies."""
    from app.api.flake import catalog as catalog_api
    from app.models import ServiceCatalogItem

    item = ServiceCatalogItem(
        sys_id="item1",
        catalog_sys_id="cat1",
        name="Item",
        active=True,
    )
    variable = _var(
        name="ci",
        type="reference",
        reference_table="cmdb_ci",
        reference_filter="",
    )
    auth = _auth("user1", "alice")

    db = AsyncMock()
    db.get = AsyncMock(return_value=item)
    var_result = MagicMock()
    var_result.scalar_one_or_none.return_value = variable
    db.execute = AsyncMock(return_value=var_result)

    captured: dict = {}

    async def fake_list_records(db_arg, table, conditions, **kwargs):
        captured.update(kwargs)
        captured["table"] = table
        return ([{"sys_id": "ci1", "name": "Visible CI"}], 1)

    with patch(
        "app.api.flake.catalog.list_records",
        new=AsyncMock(side_effect=fake_list_records),
    ):
        result = await catalog_api.get_variable_options(
            "item1", "ci", depends_on=None, auth=auth, db=db
        )

    assert captured["auth"] is auth
    assert captured["table"] == "cmdb_ci"
    assert result["result"]["total"] == 1
