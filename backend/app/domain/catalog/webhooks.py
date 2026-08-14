"""Outbound webhook delivery for catalog item orders."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from string import Template
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import db as db_module
from app.domain.secrets import SecretResolutionError, resolve_headers
from app.events.bus import RecordEvent, subscribe
from app.models import ItemOptionNew, ScCatItemWebhook, ScItemOption, ScWebhook, ScWebhookLog
from app.utils.ids import new_sys_id

logger = logging.getLogger("openflake.catalog.webhooks")

WEBHOOK_TIMEOUT_SECONDS = 15.0

# Sample RITM used for admin payload previews (matches default delivery shape).
DEFAULT_RITM_PREVIEW: dict[str, Any] = {
    "event": "catalog_order",
    "request_item": {
        "sys_id": "sample_ritm_sys_id",
        "number": "RITM0000001",
        "short_description": "Order: Sample Catalog Item",
        "description": "Sample description",
        "state": "1",
        "stage": "fulfillment",
        "quantity": "1",
        "price": "0",
        "request": "sample_req_sys_id",
        "cat_item": "sample_cat_item_sys_id",
        "cmdb_ci": "",
        "assignment_group": "",
        "assigned_to": "",
        "approval": "not_requested",
        "opened_by": "admin",
    },
    "variables": {
        "example_field": "example_value",
    },
}

# Documented $placeholders available in custom payload templates (string.Template).
TEMPLATE_VARIABLES: list[dict[str, str]] = [
    {"name": "$event", "description": "Trigger event (catalog_order, state_change, …)"},
    {"name": "$sys_id", "description": "RITM sys_id"},
    {"name": "$number", "description": "RITM number (e.g. RITM0000001)"},
    {"name": "$short_description", "description": "RITM short description"},
    {"name": "$description", "description": "RITM description"},
    {"name": "$state", "description": "RITM state"},
    {"name": "$stage", "description": "RITM stage"},
    {"name": "$quantity", "description": "Order quantity"},
    {"name": "$price", "description": "Item price"},
    {"name": "$request", "description": "Parent sc_request sys_id"},
    {"name": "$cat_item", "description": "Catalog item sys_id"},
    {"name": "$cmdb_ci", "description": "Linked CI sys_id"},
    {"name": "$assignment_group", "description": "Assignment group sys_id"},
    {"name": "$assigned_to", "description": "Assignee sys_id"},
    {"name": "$approval", "description": "Approval state"},
    {"name": "$opened_by", "description": "Opened-by user sys_id"},
    {"name": "$request_item_json", "description": "Full request_item object as JSON"},
    {"name": "$variables_json", "description": "All variable answers as a JSON object"},
    {
        "name": "$var_<name>",
        "description": "Value of a catalog variable (e.g. $var_sn_vm_name)",
    },
]


def default_payload(ritm: dict[str, Any], variables: dict[str, str]) -> dict[str, Any]:
    """Canonical payload sent when no per-item template is configured."""
    return {
        "event": "catalog_order",
        "request_item": {
            "sys_id": ritm.get("sys_id", ""),
            "number": ritm.get("number", ""),
            "short_description": ritm.get("short_description", ""),
            "description": ritm.get("description", ""),
            "state": ritm.get("state", ""),
            "stage": ritm.get("stage", ""),
            "quantity": ritm.get("quantity", ""),
            "price": ritm.get("price", ""),
            "request": _ref_value(ritm.get("request")),
            "cat_item": _ref_value(ritm.get("cat_item")),
            "cmdb_ci": _ref_value(ritm.get("cmdb_ci")),
            "assignment_group": _ref_value(ritm.get("assignment_group")),
            "assigned_to": _ref_value(ritm.get("assigned_to")),
            "approval": ritm.get("approval", ""),
            "opened_by": _ref_value(ritm.get("opened_by")),
        },
        "variables": variables,
    }


def preview_payload(payload_template: str | None = None) -> dict[str, Any] | str:
    """Return the payload preview for the admin UI (default RITM or rendered template)."""
    if not payload_template:
        return DEFAULT_RITM_PREVIEW
    return _render_template(
        payload_template,
        ritm=DEFAULT_RITM_PREVIEW["request_item"],
        variables=DEFAULT_RITM_PREVIEW["variables"],
        event=str(DEFAULT_RITM_PREVIEW.get("event") or "catalog_order"),
    )


def _render_payload(
    attachment: ScCatItemWebhook,
    *,
    ritm: dict[str, Any],
    variables: dict[str, str],
    event: str = "catalog_order",
) -> dict[str, Any] | str:
    if not attachment.payload_template:
        return default_payload(ritm, variables)
    return _render_template(
        attachment.payload_template,
        ritm=ritm,
        variables=variables,
        event=event,
    )


def template_context(
    *,
    ritm: dict[str, Any],
    variables: dict[str, str],
    event: str = "catalog_order",
) -> dict[str, str]:
    """Build string.Template substitution map from a RITM and its variables."""
    request_item = {
        "sys_id": ritm.get("sys_id", ""),
        "number": ritm.get("number", ""),
        "short_description": ritm.get("short_description", ""),
        "description": ritm.get("description", ""),
        "state": ritm.get("state", ""),
        "stage": ritm.get("stage", ""),
        "quantity": str(ritm.get("quantity", "")),
        "price": ritm.get("price", ""),
        "request": _ref_value(ritm.get("request")),
        "cat_item": _ref_value(ritm.get("cat_item")),
        "cmdb_ci": _ref_value(ritm.get("cmdb_ci")),
        "assignment_group": _ref_value(ritm.get("assignment_group")),
        "assigned_to": _ref_value(ritm.get("assigned_to")),
        "approval": str(ritm.get("approval", "")),
        "opened_by": _ref_value(ritm.get("opened_by")),
    }
    return {
        "event": event,
        **{key: str(value) for key, value in request_item.items()},
        "request_item_json": json.dumps(request_item),
        "variables_json": json.dumps(variables),
        **{f"var_{key}": str(value) for key, value in variables.items()},
    }


def _render_template(
    payload_template: str,
    *,
    ritm: dict[str, Any],
    variables: dict[str, str],
    event: str = "catalog_order",
) -> dict[str, Any] | str:
    context = template_context(ritm=ritm, variables=variables, event=event)
    rendered = Template(payload_template).safe_substitute(context)
    try:
        parsed: dict[str, Any] = json.loads(rendered)
        return parsed
    except json.JSONDecodeError:
        return rendered


def _ref_value(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("value") or "")
    return str(value or "")


def _sign_body(secret: str | None, body: bytes) -> str | None:
    if not secret:
        return None
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


async def _load_variables_for_ritm(session: AsyncSession, ritm_sys_id: str) -> dict[str, str]:
    result = await session.execute(
        select(ScItemOption, ItemOptionNew)
        .join(ItemOptionNew, ItemOptionNew.sys_id == ScItemOption.item_option_new)
        .where(ScItemOption.sc_req_item == ritm_sys_id)
    )
    return {variable.name: (option.value or "") for option, variable in result.all()}


async def deliver_webhooks_for_ritm(
    session: AsyncSession,
    ritm: dict[str, Any],
    *,
    trigger_on: str = "order",
) -> list[dict[str, Any]]:
    cat_item_id = _ref_value(ritm.get("cat_item"))
    if not cat_item_id:
        return []

    result = await session.execute(
        select(ScCatItemWebhook, ScWebhook)
        .join(ScWebhook, ScWebhook.sys_id == ScCatItemWebhook.webhook)
        .where(
            ScCatItemWebhook.cat_item == cat_item_id,
            ScCatItemWebhook.active.is_(True),
            ScCatItemWebhook.trigger_on == trigger_on,
            ScWebhook.active.is_(True),
        )
    )
    rows = list(result.all())
    if not rows:
        return []

    variables = await _load_variables_for_ritm(session, ritm["sys_id"])
    deliveries: list[dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=WEBHOOK_TIMEOUT_SECONDS) as client:
        for attachment, webhook in rows:
            payload = _render_payload(
                attachment,
                ritm=ritm,
                variables=variables,
                event=f"catalog_{trigger_on}",
            )
            if isinstance(payload, str):
                body = payload.encode("utf-8")
                content_type = "text/plain"
            else:
                body = json.dumps(payload).encode("utf-8")
                content_type = "application/json"

            status_code: int | None = None
            response_body: str | None = None
            success = False
            error_message: str | None = None
            try:
                headers = {"Content-Type": content_type}
                headers.update(await resolve_headers(session, webhook.headers))
                signature = _sign_body(webhook.secret, body)
                if signature:
                    headers["X-OpenFlake-Signature"] = signature

                response = await client.request(
                    webhook.method.upper(),
                    webhook.url,
                    content=body,
                    headers=headers,
                )
                status_code = response.status_code
                response_body = response.text[:4000]
                success = 200 <= response.status_code < 300
                if not success:
                    error_message = f"HTTP {response.status_code}"
            except SecretResolutionError as exc:
                error_message = str(exc)
                logger.warning(
                    "Webhook %s skipped: secret resolution failed: %s",
                    webhook.sys_id,
                    exc,
                )
            except Exception as exc:
                error_message = str(exc)
                logger.exception("Webhook delivery failed for %s", webhook.sys_id)

            log = ScWebhookLog(
                sys_id=new_sys_id(),
                webhook_id=webhook.sys_id,
                attachment_id=attachment.sys_id,
                sc_req_item=ritm.get("sys_id"),
                status_code=status_code,
                response_body=response_body,
                success=success,
                error_message=error_message,
            )
            session.add(log)
            deliveries.append(
                {
                    "webhook_id": webhook.sys_id,
                    "attachment_id": attachment.sys_id,
                    "success": success,
                    "status_code": status_code,
                    "error_message": error_message,
                }
            )

    await session.flush()
    return deliveries


async def _on_record_event(event: RecordEvent) -> None:
    if event.table != "sc_req_item":
        return
    # "create" (order) delivery is handled explicitly by order_catalog_item, using
    # the same session that has the sc_item_option rows flushed, so variables are
    # visible. Delivering here instead would race the option inserts and always
    # see an empty variables map.
    if event.action != "update":
        return

    async with db_module.async_session_factory() as session:
        try:
            await deliver_webhooks_for_ritm(session, event.record, trigger_on="state_change")
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("Failed processing catalog webhook event")


def register_webhook_subscriber() -> None:
    """Subscribe the catalog webhook handler to the record event bus."""
    subscribe(_on_record_event)
