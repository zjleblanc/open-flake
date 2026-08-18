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
        "reference_display_field": variable.reference_display_field or "",
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


def _parse_depends_on(depends_on: str) -> dict[str, str]:
    """Parse a "field_name=value&field2=value2" string into a dict."""
    depends_map: dict[str, str] = {}
    for part in depends_on.split("&"):
        if "=" in part:
            key, value = part.split("=", 1)
            depends_map[key.strip()] = value.strip()
    return depends_map


async def _resolve_effective_filter(
    db: AsyncSession,
    variable: ItemOptionNew,
    depends_on: str | None,
) -> str:
    """Resolve the reference_filter for a variable, applying any matching filter_override."""
    query_filter = variable.reference_filter or ""
    if not depends_on:
        return query_filter

    depends_map = _parse_depends_on(depends_on)
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
    return query_filter


def _record_label(record: dict[str, Any], display_field: str) -> str:
    """Resolve a reference record's display label, preferring the configured field."""
    return record.get(display_field) or record.get("name") or record.get("sys_id") or ""


async def _load_reference_options(
    db: AsyncSession,
    *,
    table: str,
    query_filter: str,
    display_field: str,
    auth: AuthContext,
) -> tuple[list[dict[str, Any]], int]:
    """Fetch options for a single (table, filter, display_field) combination."""
    conditions = parse_sysparm_query(query_filter) if query_filter else []
    records, total = await list_records(
        db,
        table,
        conditions,
        limit=100,
        offset=0,
        exclude_links=False,
        auth=auth,
    )
    options = [
        {
            "value": record.get("sys_id", ""),
            "label": _record_label(record, display_field),
            "record": record,
        }
        for record in records
    ]
    return options, total


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

    query_filter = await _resolve_effective_filter(db, variable, depends_on)
    options, total = await _load_reference_options(
        db,
        table=variable.reference_table,
        query_filter=query_filter,
        display_field=variable.reference_display_field or "name",
        auth=auth,
    )
    return {"result": {"options": options, "total": total}}


@router.post("/items/{item_id}/variables/options")
async def get_batch_variable_options(
    item_id: str,
    payload: dict[str, Any] | None = None,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    """Return reference options for several variables in one call.

    Body: {"variables": {"<var_name>": "<depends_on_string>", ...}}

    Variables that share the same (reference_table, effective_filter,
    reference_display_field) are resolved with a single underlying query,
    which avoids redundant round-trips when a form references the same
    table multiple times (e.g. two "assignment group" style fields).
    """
    item = await db.get(ServiceCatalogItem, item_id)
    if not item or not item.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")

    var_depends_on: dict[str, str] = (payload or {}).get("variables") or {}
    if not var_depends_on:
        return {"result": {}}

    result = await db.execute(
        select(ItemOptionNew).where(
            ItemOptionNew.cat_item == item_id,
            ItemOptionNew.name.in_(var_depends_on.keys()),
            ItemOptionNew.active.is_(True),
            ItemOptionNew.type == "reference",
        )
    )
    variables = result.scalars().all()

    # Group variable names by (table, effective_filter, display_field) so that
    # identical combinations share a single list_records() call.
    groups: dict[tuple[str, str, str], list[str]] = {}
    group_key_by_var: dict[str, tuple[str, str, str]] = {}
    for variable in variables:
        if not variable.reference_table:
            continue
        depends_on = var_depends_on.get(variable.name)
        query_filter = await _resolve_effective_filter(db, variable, depends_on)
        display_field = variable.reference_display_field or "name"
        key = (variable.reference_table, query_filter, display_field)
        groups.setdefault(key, []).append(variable.name)
        group_key_by_var[variable.name] = key

    resolved: dict[tuple[str, str, str], tuple[list[dict[str, Any]], int]] = {}
    for table, query_filter, display_field in groups:
        resolved[(table, query_filter, display_field)] = await _load_reference_options(
            db,
            table=table,
            query_filter=query_filter,
            display_field=display_field,
            auth=auth,
        )

    out: dict[str, Any] = {}
    for var_name, key in group_key_by_var.items():
        options, total = resolved[key]
        out[var_name] = {"options": options, "total": total}
    return {"result": out}


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
