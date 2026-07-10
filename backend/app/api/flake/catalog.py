"""ServiceNow-compatible service catalog API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import AuthContext, authenticate_request
from app.db import get_db
from app.domain.catalog.ordering import load_active_variables, order_catalog_item
from app.domain.table_service import list_records
from app.models import (
    ItemOptionNew,
    ItemOptionNewCondition,
    ServiceCatalog,
    ServiceCatalogItem,
)
from app.query.parser import parse_sysparm_query

router = APIRouter(prefix="/api/sn_sc/servicecatalog", tags=["catalog-api"])

_cart: dict[str, list[dict]] = {}


def _item_summary(item: ServiceCatalogItem) -> dict[str, Any]:
    return {
        "sys_id": item.sys_id,
        "name": item.name,
        "short_description": item.short_description or "",
        "description": item.description or "",
        "price": item.price,
        "category": item.category or "",
        "subcategory": item.subcategory or "",
        "icon": item.icon or "",
        "order": item.order,
        "catalog_sys_id": item.catalog_sys_id,
        "fulfillment_group": item.fulfillment_group or "",
    }


def _variable_dict(variable: ItemOptionNew) -> dict[str, Any]:
    return {
        "sys_id": variable.sys_id,
        "cat_item": variable.cat_item,
        "name": variable.name,
        "question_text": variable.question_text,
        "type": variable.type,
        "mandatory": variable.mandatory,
        "default_value": variable.default_value or "",
        "order": variable.order,
        "reference_table": variable.reference_table or "",
        "reference_filter": variable.reference_filter or "",
        "choice_list": variable.choice_list or [],
        "help_text": variable.help_text or "",
        "read_only": variable.read_only,
        "hidden": variable.hidden,
        "active": variable.active,
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
        "active": condition.active,
    }


@router.get("/catalogs")
async def list_catalogs(
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ServiceCatalog).where(ServiceCatalog.active.is_(True)))
    catalogs = result.scalars().all()
    return {
        "result": [
            {"sys_id": c.sys_id, "title": c.title, "description": c.description or ""}
            for c in catalogs
        ]
    }


@router.get("/catalogs/{catalog_id}")
async def get_catalog(
    catalog_id: str,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    catalog = await db.get(ServiceCatalog, catalog_id)
    if not catalog:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Catalog not found")
    return {
        "result": {
            "sys_id": catalog.sys_id,
            "title": catalog.title,
            "description": catalog.description or "",
        }
    }


@router.get("/items")
async def list_items(
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ServiceCatalogItem)
        .where(ServiceCatalogItem.active.is_(True))
        .order_by(ServiceCatalogItem.order.asc(), ServiceCatalogItem.name.asc())
    )
    items = result.scalars().all()
    return {"result": [_item_summary(i) for i in items]}


@router.get("/items/{item_id}")
async def get_item(
    item_id: str,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    item = await db.get(ServiceCatalogItem, item_id)
    if not item or not item.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    variables = await load_active_variables(db, item.sys_id)
    var_ids = [v.sys_id for v in variables]
    conditions: list[ItemOptionNewCondition] = []
    if var_ids:
        cond_result = await db.execute(
            select(ItemOptionNewCondition).where(
                ItemOptionNewCondition.variable.in_(var_ids),
                ItemOptionNewCondition.active.is_(True),
            )
        )
        conditions = list(cond_result.scalars().all())
    payload = _item_summary(item)
    payload["variables"] = [_variable_dict(v) for v in variables]
    payload["conditions"] = [_condition_dict(c) for c in conditions]
    return {"result": payload}


@router.get("/items/{item_id}/variables/{var_name}/options")
async def get_variable_options(
    item_id: str,
    var_name: str,
    depends_on: str | None = None,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    """Return filtered reference options for a dynamic catalog variable."""
    item = await db.get(ServiceCatalogItem, item_id)
    if not item or not item.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")

    result = await db.execute(
        select(ItemOptionNew).where(
            ItemOptionNew.cat_item == item_id,
            ItemOptionNew.name == var_name,
            ItemOptionNew.active.is_(True),
        )
    )
    variable = result.scalar_one_or_none()
    if not variable:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Variable not found")
    if variable.type != "reference":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Variable is not a reference type")
    if not variable.reference_table:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Variable has no reference_table")

    query_filter = variable.reference_filter or ""
    if depends_on:
        # depends_on format: "field_name=value" pairs joined by &
        depends_map: dict[str, str] = {}
        for part in depends_on.split("&"):
            if "=" in part:
                key, value = part.split("=", 1)
                depends_map[key.strip()] = value.strip()

        cond_result = await db.execute(
            select(ItemOptionNewCondition).where(
                ItemOptionNewCondition.variable == variable.sys_id,
                ItemOptionNewCondition.condition_type == "filter",
                ItemOptionNewCondition.active.is_(True),
            )
        )
        for condition in cond_result.scalars().all():
            dep_var = await db.get(ItemOptionNew, condition.depends_on)
            if not dep_var:
                continue
            current = depends_map.get(dep_var.name)
            if current is None:
                continue
            matched = False
            if condition.operator == "=":
                matched = current == (condition.value or "")
            elif condition.operator == "!=":
                matched = current != (condition.value or "")
            elif condition.operator == "IN":
                allowed = {p.strip() for p in (condition.value or "").split(",") if p.strip()}
                matched = current in allowed
            elif condition.operator == "NOT_IN":
                allowed = {p.strip() for p in (condition.value or "").split(",") if p.strip()}
                matched = current not in allowed
            elif condition.operator == "EMPTY":
                matched = current == ""
            elif condition.operator == "NOT_EMPTY":
                matched = current != ""
            if matched and condition.filter_override:
                query_filter = condition.filter_override
                break

    conditions = parse_sysparm_query(query_filter) if query_filter else []
    records, total = await list_records(
        db,
        variable.reference_table,
        conditions,
        limit=100,
        offset=0,
        exclude_links=False,
        auth=auth,
    )
    options = []
    for record in records:
        label = (
            record.get("name")
            or record.get("user_name")
            or record.get("number")
            or record.get("short_description")
            or record.get("sys_id")
            or ""
        )
        options.append(
            {
                "value": record.get("sys_id", ""),
                "label": label,
                "record": record,
            }
        )
    return {"result": {"options": options, "total": total}}


@router.get("/cart")
async def get_cart(auth: AuthContext = Depends(authenticate_request)):
    return {"result": _cart.get(auth.user_sys_id, [])}


@router.post("/items/{item_id}/add_to_cart")
async def add_to_cart(
    item_id: str,
    payload: dict[str, Any] | None = None,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    item = await db.get(ServiceCatalogItem, item_id)
    if not item or not item.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    body = payload or {}
    cart = _cart.setdefault(auth.user_sys_id, [])
    cart.append(
        {
            "item_id": item_id,
            "name": item.name,
            "quantity": int(body.get("quantity") or body.get("sysparm_quantity") or 1),
            "variables": body.get("variables") or {},
            "cmdb_ci": body.get("cmdb_ci") or "",
            "requested_for": body.get("requested_for") or auth.user_sys_id,
        }
    )
    return {"result": cart}


@router.post("/cart/checkout")
async def checkout(auth: AuthContext = Depends(authenticate_request)):
    cart = _cart.get(auth.user_sys_id, [])
    return {"result": {"cart": cart, "status": "ready"}}


@router.post("/cart/submit_order", status_code=status.HTTP_201_CREATED)
async def submit_order(
    payload: dict[str, Any] | None = None,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    cart = _cart.pop(auth.user_sys_id, [])
    if not cart:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cart is empty")

    results = []
    for entry in cart:
        item = await db.get(ServiceCatalogItem, entry["item_id"])
        if not item or not item.active:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Catalog item not found: {entry['item_id']}",
            )
        ordered = await order_catalog_item(
            db,
            item,
            user_sys_id=auth.user_sys_id,
            variables=entry.get("variables") or {},
            quantity=int(entry.get("quantity") or 1),
            requested_for=entry.get("requested_for") or auth.user_sys_id,
            cmdb_ci=entry.get("cmdb_ci") or None,
        )
        results.append(ordered)

    return {
        "result": {
            "orders": results,
            "request_ids": [r["request_id"] for r in results],
            "request_numbers": [r["request_number"] for r in results],
        }
    }


@router.post("/items/{item_id}/order_now", status_code=status.HTTP_201_CREATED)
async def order_now(
    item_id: str,
    payload: dict[str, Any] | None = None,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    item = await db.get(ServiceCatalogItem, item_id)
    if not item or not item.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")

    body = payload or {}
    variables = body.get("variables") or {}
    quantity = int(body.get("quantity") or body.get("sysparm_quantity") or 1)
    ordered = await order_catalog_item(
        db,
        item,
        user_sys_id=auth.user_sys_id,
        variables=variables,
        quantity=quantity,
        requested_for=body.get("requested_for") or auth.user_sys_id,
        cmdb_ci=body.get("cmdb_ci") or None,
        short_description=body.get("short_description"),
    )
    return {
        "result": {
            "request_id": ordered["request_id"],
            "request_number": ordered["request_number"],
            "request": ordered["request"],
            "request_item": ordered["request_item"],
            "variables": ordered["variables"],
            "task": ordered["task"],
        }
    }
