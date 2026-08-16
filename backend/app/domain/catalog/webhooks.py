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
DEFAULT_RITM_PREVIEW_EVENT = "catalog_order"
DEFAULT_RITM_PREVIEW_RITM: dict[str, Any] = {
    "sys_id": "sample_ritm_sys_id",
    "number": "RITM0000001",
    "sys_class_name": "sc_req_item",
    "task_effective_number": "RITM0000001",
    "short_description": "Order: Sample Catalog Item",
    "description": "Sample description",
    "active": "true",
    "state": "1",
    "stage": "fulfillment",
    "quantity": "1",
    "price": "0",
    "recurring_price": "0",
    "request": "sample_req_sys_id",
    "cat_item": "sample_cat_item_sys_id",
    "cmdb_ci": "",
    "assignment_group": "",
    "assigned_to": "",
    "requested_for": "admin",
    "opened_by": "admin",
    "opened_at": "2026-01-01 00:00:00",
    "due_date": "2026-01-03 00:00:00",
    "approval": "not_requested",
    "approval_set": "",
    "upon_approval": "proceed",
    "upon_reject": "cancel",
    "priority": "4",
    "urgency": "3",
    "impact": "3",
    "escalation": "0",
    "made_sla": "true",
    "backordered": "false",
    "billable": "false",
    "knowledge": "false",
    "reassignment_count": "0",
    "delivery_plan": "",
    "sys_domain": "global",
    "sys_domain_path": "/",
    "sys_created_by": "admin",
    "sys_created_on": "2026-01-01 00:00:00",
    "sys_updated_by": "admin",
    "sys_updated_on": "2026-01-01 00:00:00",
}
DEFAULT_RITM_PREVIEW_VARIABLES: dict[str, str] = {
    "example_field": "example_value",
}

# Documented $placeholders available in custom payload templates (string.Template).
TEMPLATE_VARIABLES: list[dict[str, str]] = [
    {"name": "$event", "description": "Trigger event (catalog_order, state_change, …)"},
    {"name": "$sys_id", "description": "RITM sys_id"},
    {"name": "$number", "description": "RITM number (e.g. RITM0000001)"},
    {"name": "$task_effective_number", "description": "Effective number (mirrors number)"},
    {"name": "$sys_class_name", "description": "Table class name (sc_req_item)"},
    {"name": "$short_description", "description": "RITM short description"},
    {"name": "$description", "description": "RITM description"},
    {"name": "$active", "description": "Whether the RITM is active"},
    {"name": "$state", "description": "RITM state"},
    {"name": "$stage", "description": "RITM stage"},
    {"name": "$quantity", "description": "Order quantity"},
    {"name": "$price", "description": "Item price"},
    {"name": "$recurring_price", "description": "Recurring price"},
    {"name": "$request", "description": "Parent sc_request sys_id"},
    {"name": "$cat_item", "description": "Catalog item sys_id"},
    {"name": "$cmdb_ci", "description": "Linked CI sys_id"},
    {"name": "$assignment_group", "description": "Assignment group sys_id"},
    {"name": "$assigned_to", "description": "Assignee sys_id"},
    {"name": "$requested_for", "description": "User the item was requested for"},
    {"name": "$opened_by", "description": "Opened-by user sys_id"},
    {"name": "$opened_at", "description": "Timestamp the RITM was opened"},
    {"name": "$due_date", "description": "Due date"},
    {"name": "$approval", "description": "Approval state"},
    {"name": "$approval_set", "description": "Timestamp the approval state was set"},
    {"name": "$upon_approval", "description": "Action to take on approval (e.g. proceed)"},
    {"name": "$upon_reject", "description": "Action to take on rejection (e.g. cancel)"},
    {"name": "$priority", "description": "Priority"},
    {"name": "$urgency", "description": "Urgency"},
    {"name": "$impact", "description": "Impact"},
    {"name": "$escalation", "description": "Escalation level"},
    {"name": "$made_sla", "description": "Whether the SLA was met"},
    {"name": "$backordered", "description": "Whether the item is backordered"},
    {"name": "$billable", "description": "Whether the item is billable"},
    {"name": "$knowledge", "description": "Whether a knowledge article exists"},
    {"name": "$reassignment_count", "description": "Number of reassignments"},
    {"name": "$delivery_plan", "description": "Linked delivery plan sys_id"},
    {"name": "$sys_domain", "description": "Domain (e.g. global)"},
    {"name": "$sys_domain_path", "description": "Domain path"},
    {"name": "$sys_created_by", "description": "User who created the RITM"},
    {"name": "$sys_created_on", "description": "Timestamp the RITM was created"},
    {"name": "$sys_updated_by", "description": "User who last updated the RITM"},
    {"name": "$sys_updated_on", "description": "Timestamp the RITM was last updated"},
    {"name": "$request_item_json", "description": "Full request_item object as JSON"},
    {"name": "$variables_json", "description": "All variable answers as a JSON object"},
    {
        "name": "$var_<name>",
        "description": "Value of a catalog variable (e.g. $var_sn_vm_name)",
    },
]


def _flatten_refs(record: dict[str, Any]) -> dict[str, Any]:
    """Collapse ServiceNow-style {"link": ..., "value": sys_id} refs to plain sys_ids."""
    return {
        key: _ref_value(value) if isinstance(value, dict) and "value" in value else value
        for key, value in record.items()
    }


def default_payload(ritm: dict[str, Any], variables: dict[str, str]) -> dict[str, Any]:
    """Canonical payload sent when no per-item template is configured.

    Mirrors ServiceNow's ITSM webhook shape: the full sc_req_item record
    flattened at the top level (reference fields collapsed to their sys_id),
    with catalog variable answers nested under ``variables``.
    """
    payload = _flatten_refs(ritm)
    payload["variables"] = variables
    return payload


def preview_payload(payload_template: str | None = None) -> dict[str, Any] | str:
    """Return the payload preview for the admin UI (default RITM or rendered template)."""
    if not payload_template:
        return default_payload(DEFAULT_RITM_PREVIEW_RITM, DEFAULT_RITM_PREVIEW_VARIABLES)
    return _render_template(
        payload_template,
        ritm=DEFAULT_RITM_PREVIEW_RITM,
        variables=DEFAULT_RITM_PREVIEW_VARIABLES,
        event=DEFAULT_RITM_PREVIEW_EVENT,
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
    """Build string.Template substitution map from a RITM and its variables.

    Every scalar field on the flattened RITM record is exposed as a
    top-level ``$<field>`` placeholder, mirroring the flat default payload.
    """
    request_item = _flatten_refs(ritm)
    scalar_fields = {
        key: value for key, value in request_item.items() if not isinstance(value, dict | list)
    }
    return {
        "event": event,
        **{key: str(value) for key, value in scalar_fields.items()},
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
