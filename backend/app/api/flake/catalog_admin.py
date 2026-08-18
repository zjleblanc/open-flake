"""Admin CRUD for service catalog items, variables, conditions, and webhooks."""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import AuthContext, authenticate_request
from app.auth.rbac import can_read_table, get_user_permissions
from app.db import get_db
from app.domain.catalog.webhooks import TEMPLATE_VARIABLES, preview_payload
from app.domain.cmdb.registry import _require_snapshot
from app.domain.registry import TABLE_MODELS
from app.domain.table_service import create_record, delete_record, update_record
from app.models import (
    ItemOptionNew,
    ItemOptionNewCondition,
    ScCatItemWebhook,
    ScWebhook,
    ServiceCatalog,
    ServiceCatalogItem,
)
from app.utils.ids import new_sys_id

router = APIRouter(prefix="/api/flake/catalog/admin", tags=["catalog-admin-api"])

_HIDDEN_TABLE_FIELDS = {"user_password", "key_hash", "storage_path"}


async def _require_catalog_admin(db: AsyncSession, auth: AuthContext) -> None:
    perms = await get_user_permissions(db, auth.user_sys_id)
    if "records.*.write" not in perms and "records.*.read" not in perms:
        # platform_admin has records.*.write; allow any user with broad write
        if not any(p.startswith("records.") and p.endswith(".write") for p in perms):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Catalog admin access required")


def _item_dict(item: ServiceCatalogItem) -> dict[str, Any]:
    return {
        "sys_id": item.sys_id,
        "catalog_sys_id": item.catalog_sys_id,
        "name": item.name,
        "short_description": item.short_description or "",
        "description": item.description or "",
        "active": item.active,
        "price": item.price,
        "category": item.category or "",
        "subcategory": item.subcategory or "",
        "fulfillment_group": item.fulfillment_group or "",
        "order": item.order,
        "icon": item.icon or "",
    }


def _variable_dict(variable: ItemOptionNew) -> dict[str, Any]:
    return {
        "sys_id": variable.sys_id,
        "cat_item": variable.cat_item,
        "name": variable.name,
        "question_text": variable.question_text,
        "type": variable.type,
        "mandatory": bool(variable.mandatory),
        "default_value": variable.default_value or "",
        "order": variable.order,
        "reference_table": variable.reference_table or "",
        "reference_filter": variable.reference_filter or "",
        "reference_display_field": variable.reference_display_field or "",
        "choice_list": variable.choice_list or [],
        "help_text": variable.help_text or "",
        "read_only": bool(variable.read_only),
        "hidden": bool(variable.hidden),
        "active": bool(variable.active),
    }


def _condition_dict(condition: ItemOptionNewCondition) -> dict[str, Any]:
    return {
        "sys_id": condition.sys_id,
        "variable": condition.variable,
        "condition_type": condition.condition_type,
        "depends_on": condition.depends_on,
        "operator": condition.operator,
        "value": condition.value or "",
        "filter_override": condition.filter_override or "",
        "active": bool(condition.active),
    }


def _webhook_dict(webhook: ScWebhook, *, include_secret: bool = False) -> dict[str, Any]:
    data = {
        "sys_id": webhook.sys_id,
        "name": webhook.name,
        "url": webhook.url,
        "method": webhook.method,
        "headers": webhook.headers or {},
        "description": webhook.description or "",
        "active": bool(webhook.active),
        "has_secret": bool(webhook.secret),
    }
    if include_secret:
        data["secret"] = webhook.secret or ""
    return data


def _attachment_dict(
    attachment: ScCatItemWebhook,
    webhook: ScWebhook | None = None,
) -> dict[str, Any]:
    data = {
        "sys_id": attachment.sys_id,
        "cat_item": attachment.cat_item,
        "webhook": attachment.webhook,
        "payload_template": attachment.payload_template or "",
        "trigger_on": attachment.trigger_on,
        "active": bool(attachment.active),
        "payload_preview": preview_payload(attachment.payload_template),
    }
    if webhook is not None:
        data["webhook_name"] = webhook.name
        data["webhook_url"] = webhook.url
        data["webhook_method"] = webhook.method
        data["webhook_active"] = bool(webhook.active)
    return data


async def _get_item(db: AsyncSession, item_id: str) -> ServiceCatalogItem:
    item = await db.get(ServiceCatalogItem, item_id)
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Catalog item not found")
    return cast(ServiceCatalogItem, item)


@router.get("/tables")
async def list_reference_tables(
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    """Return every table -- physical tables and CMDB subclasses alike --
    the current user may reference, filtered by RBAC read access.

    Sourced from the `sys_db_object` registry (rather than the static
    `TABLE_MODELS` map) so CMDB classes like `cmdb_ci_server` are directly
    selectable, not just the top-level `cmdb_ci` table.
    """
    await _require_catalog_admin(db, auth)
    snap = _require_snapshot()
    tables = []
    for name, obj in sorted(snap.classes.items()):
        if obj.is_logical:
            continue
        if not await can_read_table(db, auth, name):
            continue
        tables.append(
            {
                "name": name,
                "label": obj.label,
                "super_class": obj.super_class,
                "is_extendable": obj.is_extendable,
            }
        )
    return {"result": tables}


@router.get("/tables/{table}/fields")
async def list_table_fields(
    table: str,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    """Return column metadata for a table the user can read."""
    await _require_catalog_admin(db, auth)
    model = TABLE_MODELS.get(table)
    if not model:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Table not found")
    if not await can_read_table(db, auth, table):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No read access to this table")
    fields = []
    for col in model.__table__.columns:
        if col.name in _HIDDEN_TABLE_FIELDS:
            continue
        fields.append({"name": col.name, "type": str(col.type)})
    return {"result": fields}


@router.get("/items")
async def admin_list_items(
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    await _require_catalog_admin(db, auth)
    result = await db.execute(
        select(ServiceCatalogItem).order_by(
            ServiceCatalogItem.order.asc(), ServiceCatalogItem.name.asc()
        )
    )
    return {"result": [_item_dict(i) for i in result.scalars().all()]}


@router.post("/items", status_code=status.HTTP_201_CREATED)
async def admin_create_item(
    payload: dict[str, Any],
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    await _require_catalog_admin(db, auth)
    catalog_id = payload.get("catalog_sys_id")
    if not catalog_id:
        existing = await db.execute(select(ServiceCatalog).limit(1))
        catalog = existing.scalar_one_or_none()
        if not catalog:
            catalog = ServiceCatalog(
                sys_id=new_sys_id(),
                title="IT Services",
                description="Standard IT service catalog",
            )
            db.add(catalog)
            await db.flush()
        catalog_id = catalog.sys_id

    item = ServiceCatalogItem(
        sys_id=new_sys_id(),
        catalog_sys_id=catalog_id,
        name=payload.get("name") or "Untitled Item",
        short_description=payload.get("short_description") or "",
        description=payload.get("description") or "",
        active=bool(payload.get("active", True)),
        price=str(payload.get("price") or "0"),
        category=payload.get("category") or None,
        subcategory=payload.get("subcategory") or None,
        fulfillment_group=payload.get("fulfillment_group") or None,
        order=int(payload.get("order") or 100),
        icon=payload.get("icon") or None,
    )
    db.add(item)
    await db.flush()

    for var_payload in payload.get("variables") or []:
        await create_record(
            db,
            "item_option_new",
            {**var_payload, "cat_item": item.sys_id},
            auth.user_sys_id,
        )

    return {"result": _item_dict(item)}


@router.get("/items/{item_id}")
async def admin_get_item(
    item_id: str,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    await _require_catalog_admin(db, auth)
    item = await _get_item(db, item_id)
    return {"result": _item_dict(item)}


@router.patch("/items/{item_id}")
async def admin_update_item(
    item_id: str,
    payload: dict[str, Any],
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    await _require_catalog_admin(db, auth)
    item = await _get_item(db, item_id)
    for field in (
        "name",
        "short_description",
        "description",
        "price",
        "category",
        "subcategory",
        "fulfillment_group",
        "icon",
        "catalog_sys_id",
    ):
        if field in payload:
            setattr(item, field, payload[field])
    if "active" in payload:
        item.active = bool(payload["active"])
    if "order" in payload:
        item.order = int(payload["order"])
    await db.flush()
    return {"result": _item_dict(item)}


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_item(
    item_id: str,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    await _require_catalog_admin(db, auth)
    item = await _get_item(db, item_id)
    item.active = False
    await db.flush()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/items/{item_id}/variables")
async def list_variables(
    item_id: str,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    await _require_catalog_admin(db, auth)
    await _get_item(db, item_id)
    result = await db.execute(
        select(ItemOptionNew)
        .where(ItemOptionNew.cat_item == item_id)
        .order_by(ItemOptionNew.order.asc(), ItemOptionNew.name.asc())
    )
    return {"result": [_variable_dict(v) for v in result.scalars().all()]}


@router.post("/items/{item_id}/variables", status_code=status.HTTP_201_CREATED)
async def create_variable(
    item_id: str,
    payload: dict[str, Any],
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    await _require_catalog_admin(db, auth)
    await _get_item(db, item_id)
    record = await create_record(
        db,
        "item_option_new",
        {
            "cat_item": item_id,
            "name": payload.get("name") or "variable",
            "question_text": payload.get("question_text") or "",
            "type": payload.get("type") or "string",
            "mandatory": bool(payload.get("mandatory", False)),
            "default_value": payload.get("default_value") or None,
            "order": int(payload.get("order") or 100),
            "reference_table": payload.get("reference_table") or None,
            "reference_filter": payload.get("reference_filter") or None,
            "reference_display_field": payload.get("reference_display_field") or None,
            "choice_list": payload.get("choice_list") or [],
            "help_text": payload.get("help_text") or None,
            "read_only": bool(payload.get("read_only", False)),
            "hidden": bool(payload.get("hidden", False)),
            "active": bool(payload.get("active", True)),
        },
        auth.user_sys_id,
    )
    variable = await db.get(ItemOptionNew, record["sys_id"])
    if not variable:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Variable not found")
    return {"result": _variable_dict(variable)}


@router.patch("/items/{item_id}/variables/{var_id}")
async def update_variable(
    item_id: str,
    var_id: str,
    payload: dict[str, Any],
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    await _require_catalog_admin(db, auth)
    await _get_item(db, item_id)
    variable = await db.get(ItemOptionNew, var_id)
    if not variable or variable.cat_item != item_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Variable not found")
    await update_record(db, "item_option_new", var_id, payload, auth.user_sys_id)
    await db.refresh(variable)
    return {"result": _variable_dict(variable)}


@router.delete("/items/{item_id}/variables/{var_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_variable(
    item_id: str,
    var_id: str,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    await _require_catalog_admin(db, auth)
    await _get_item(db, item_id)
    variable = await db.get(ItemOptionNew, var_id)
    if not variable or variable.cat_item != item_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Variable not found")
    # Remove conditions first
    conds = await db.execute(
        select(ItemOptionNewCondition).where(ItemOptionNewCondition.variable == var_id)
    )
    for condition in conds.scalars().all():
        await db.delete(condition)
    await delete_record(db, "item_option_new", var_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/items/{item_id}/variables/{var_id}/conditions")
async def list_conditions(
    item_id: str,
    var_id: str,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    await _require_catalog_admin(db, auth)
    await _get_item(db, item_id)
    variable = await db.get(ItemOptionNew, var_id)
    if not variable or variable.cat_item != item_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Variable not found")
    result = await db.execute(
        select(ItemOptionNewCondition).where(ItemOptionNewCondition.variable == var_id)
    )
    return {"result": [_condition_dict(c) for c in result.scalars().all()]}


@router.post(
    "/items/{item_id}/variables/{var_id}/conditions",
    status_code=status.HTTP_201_CREATED,
)
async def create_condition(
    item_id: str,
    var_id: str,
    payload: dict[str, Any],
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    await _require_catalog_admin(db, auth)
    await _get_item(db, item_id)
    variable = await db.get(ItemOptionNew, var_id)
    if not variable or variable.cat_item != item_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Variable not found")
    record = await create_record(
        db,
        "item_option_new_condition",
        {
            "variable": var_id,
            "condition_type": payload.get("condition_type") or "visibility",
            "depends_on": payload.get("depends_on") or "",
            "operator": payload.get("operator") or "=",
            "value": payload.get("value") or None,
            "filter_override": payload.get("filter_override") or None,
            "active": bool(payload.get("active", True)),
        },
        auth.user_sys_id,
    )
    condition = await db.get(ItemOptionNewCondition, record["sys_id"])
    if not condition:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Condition not found")
    return {"result": _condition_dict(condition)}


@router.patch("/items/{item_id}/variables/{var_id}/conditions/{cond_id}")
async def update_condition(
    item_id: str,
    var_id: str,
    cond_id: str,
    payload: dict[str, Any],
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    await _require_catalog_admin(db, auth)
    await _get_item(db, item_id)
    condition = await db.get(ItemOptionNewCondition, cond_id)
    if not condition or condition.variable != var_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Condition not found")
    await update_record(db, "item_option_new_condition", cond_id, payload, auth.user_sys_id)
    await db.refresh(condition)
    return {"result": _condition_dict(condition)}


@router.delete(
    "/items/{item_id}/variables/{var_id}/conditions/{cond_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_condition(
    item_id: str,
    var_id: str,
    cond_id: str,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    await _require_catalog_admin(db, auth)
    await _get_item(db, item_id)
    condition = await db.get(ItemOptionNewCondition, cond_id)
    if not condition or condition.variable != var_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Condition not found")
    await delete_record(db, "item_option_new_condition", cond_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/webhooks")
async def list_global_webhooks(
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    await _require_catalog_admin(db, auth)
    result = await db.execute(select(ScWebhook).order_by(ScWebhook.name.asc()))
    return {"result": [_webhook_dict(w) for w in result.scalars().all()]}


@router.post("/webhooks", status_code=status.HTTP_201_CREATED)
async def create_global_webhook(
    payload: dict[str, Any],
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    await _require_catalog_admin(db, auth)
    if not payload.get("url"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "url is required")
    record = await create_record(
        db,
        "sc_webhook",
        {
            "name": payload.get("name") or "Webhook",
            "url": payload.get("url") or "",
            "method": (payload.get("method") or "POST").upper(),
            "headers": payload.get("headers") or {},
            "secret": payload.get("secret") or None,
            "description": payload.get("description") or None,
            "active": bool(payload.get("active", True)),
        },
        auth.user_sys_id,
    )
    webhook = await db.get(ScWebhook, record["sys_id"])
    if not webhook:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found")
    return {"result": _webhook_dict(webhook)}


@router.get("/webhooks/{webhook_id}")
async def get_global_webhook(
    webhook_id: str,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    await _require_catalog_admin(db, auth)
    webhook = await db.get(ScWebhook, webhook_id)
    if not webhook:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found")
    return {"result": _webhook_dict(webhook)}


@router.patch("/webhooks/{webhook_id}")
async def update_global_webhook(
    webhook_id: str,
    payload: dict[str, Any],
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    await _require_catalog_admin(db, auth)
    webhook = await db.get(ScWebhook, webhook_id)
    if not webhook:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found")
    await update_record(db, "sc_webhook", webhook_id, payload, auth.user_sys_id)
    await db.refresh(webhook)
    return {"result": _webhook_dict(webhook)}


@router.delete("/webhooks/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_global_webhook(
    webhook_id: str,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    await _require_catalog_admin(db, auth)
    webhook = await db.get(ScWebhook, webhook_id)
    if not webhook:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found")
    attachments = await db.execute(
        select(ScCatItemWebhook).where(ScCatItemWebhook.webhook == webhook_id)
    )
    for attachment in attachments.scalars().all():
        await db.delete(attachment)
    await delete_record(db, "sc_webhook", webhook_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/payload-preview")
async def get_payload_preview(
    template: str | None = None,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    await _require_catalog_admin(db, auth)
    return {
        "result": {
            "preview": preview_payload(template or None),
            "variables": TEMPLATE_VARIABLES,
        }
    }


@router.get("/items/{item_id}/webhooks")
async def list_item_webhook_attachments(
    item_id: str,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    await _require_catalog_admin(db, auth)
    await _get_item(db, item_id)
    result = await db.execute(
        select(ScCatItemWebhook, ScWebhook)
        .join(ScWebhook, ScWebhook.sys_id == ScCatItemWebhook.webhook)
        .where(ScCatItemWebhook.cat_item == item_id)
    )
    return {
        "result": [_attachment_dict(attachment, webhook) for attachment, webhook in result.all()]
    }


@router.post("/items/{item_id}/webhooks", status_code=status.HTTP_201_CREATED)
async def attach_webhook_to_item(
    item_id: str,
    payload: dict[str, Any],
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    await _require_catalog_admin(db, auth)
    await _get_item(db, item_id)
    webhook_id = payload.get("webhook") or payload.get("webhook_id")
    if not webhook_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "webhook is required")
    webhook = await db.get(ScWebhook, webhook_id)
    if not webhook:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found")
    record = await create_record(
        db,
        "sc_cat_item_webhook",
        {
            "cat_item": item_id,
            "webhook": webhook_id,
            "payload_template": payload.get("payload_template") or None,
            "trigger_on": payload.get("trigger_on") or "order",
            "active": bool(payload.get("active", True)),
        },
        auth.user_sys_id,
    )
    attachment = await db.get(ScCatItemWebhook, record["sys_id"])
    if not attachment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook attachment not found")
    return {"result": _attachment_dict(attachment, webhook)}


@router.patch("/items/{item_id}/webhooks/{attachment_id}")
async def update_item_webhook_attachment(
    item_id: str,
    attachment_id: str,
    payload: dict[str, Any],
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    await _require_catalog_admin(db, auth)
    await _get_item(db, item_id)
    attachment = await db.get(ScCatItemWebhook, attachment_id)
    if not attachment or attachment.cat_item != item_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook attachment not found")
    allowed = {
        k: v
        for k, v in payload.items()
        if k in {"webhook", "payload_template", "trigger_on", "active"}
    }
    await update_record(db, "sc_cat_item_webhook", attachment_id, allowed, auth.user_sys_id)
    await db.refresh(attachment)
    webhook = await db.get(ScWebhook, attachment.webhook)
    return {"result": _attachment_dict(attachment, webhook)}


@router.delete(
    "/items/{item_id}/webhooks/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def detach_webhook_from_item(
    item_id: str,
    attachment_id: str,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    await _require_catalog_admin(db, auth)
    await _get_item(db, item_id)
    attachment = await db.get(ScCatItemWebhook, attachment_id)
    if not attachment or attachment.cat_item != item_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook attachment not found")
    await delete_record(db, "sc_cat_item_webhook", attachment_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
