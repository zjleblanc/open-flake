"""Catalog ordering: validate variables and create request / RITM / option records."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.table_service import create_record
from app.models import ItemOptionNew, ServiceCatalogItem


SUPPORTED_TYPES = {
    "string",
    "integer",
    "boolean",
    "reference",
    "select_box",
    "multi_select",
    "date",
    "text_area",
    "email",
    "url",
}


def _choice_values(variable: ItemOptionNew) -> set[str]:
    choices = variable.choice_list or []
    values: set[str] = set()
    for choice in choices:
        if isinstance(choice, dict) and "value" in choice:
            values.add(str(choice["value"]))
        elif isinstance(choice, str):
            values.add(choice)
    return values


def validate_variables(
    definitions: list[ItemOptionNew],
    submitted: dict[str, Any] | None,
) -> dict[str, str]:
    """Validate submitted variables against catalog item definitions.

    Returns a normalized name -> string value map.
    """
    submitted = submitted or {}
    by_name = {v.name: v for v in definitions if v.active}
    unknown = set(submitted.keys()) - set(by_name.keys())
    if unknown:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Unknown variables: {', '.join(sorted(unknown))}",
        )

    normalized: dict[str, str] = {}
    for name, variable in by_name.items():
        raw = submitted.get(name, variable.default_value)
        if raw is None or (isinstance(raw, str) and raw.strip() == ""):
            if variable.mandatory and not variable.hidden:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"Variable '{name}' is required",
                )
            continue

        if variable.type == "boolean":
            if isinstance(raw, bool):
                value = "true" if raw else "false"
            else:
                value = str(raw).strip().lower()
                if value not in {"true", "false", "1", "0", "yes", "no"}:
                    raise HTTPException(
                        status.HTTP_400_BAD_REQUEST,
                        f"Variable '{name}' must be a boolean",
                    )
                value = "true" if value in {"true", "1", "yes"} else "false"
        elif variable.type == "integer":
            try:
                value = str(int(str(raw).strip()))
            except (TypeError, ValueError) as exc:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"Variable '{name}' must be an integer",
                ) from exc
        elif variable.type == "multi_select":
            if isinstance(raw, list):
                parts = [str(part) for part in raw]
            else:
                parts = [part.strip() for part in str(raw).split(",") if part.strip()]
            allowed = _choice_values(variable)
            if allowed and any(part not in allowed for part in parts):
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"Variable '{name}' contains an invalid choice",
                )
            value = ",".join(parts)
        elif variable.type == "select_box":
            value = str(raw)
            allowed = _choice_values(variable)
            if allowed and value not in allowed:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"Variable '{name}' must be one of: {', '.join(sorted(allowed))}",
                )
        else:
            value = str(raw)

        if variable.type not in SUPPORTED_TYPES:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Variable '{name}' has unsupported type '{variable.type}'",
            )
        normalized[name] = value

    return normalized


async def load_active_variables(db: AsyncSession, cat_item_id: str) -> list[ItemOptionNew]:
    result = await db.execute(
        select(ItemOptionNew)
        .where(ItemOptionNew.cat_item == cat_item_id, ItemOptionNew.active.is_(True))
        .order_by(ItemOptionNew.order.asc(), ItemOptionNew.name.asc())
    )
    return list(result.scalars().all())


async def order_catalog_item(
    db: AsyncSession,
    item: ServiceCatalogItem,
    *,
    user_sys_id: str,
    variables: dict[str, Any] | None = None,
    quantity: int = 1,
    requested_for: str | None = None,
    cmdb_ci: str | None = None,
    short_description: str | None = None,
    create_fulfillment_task: bool = True,
) -> dict[str, Any]:
    """Create sc_request + sc_req_item + sc_item_option (+ optional sc_task)."""
    definitions = await load_active_variables(db, item.sys_id)
    normalized = validate_variables(definitions, variables)
    by_name = {v.name: v for v in definitions}

    request_short = short_description or f"Order: {item.name}"
    request = await create_record(
        db,
        "sc_request",
        {
            "short_description": request_short,
            "description": item.description or item.short_description or "",
            "requested_by": user_sys_id,
            "requested_for": requested_for or user_sys_id,
            "opened_by": user_sys_id,
            "assignment_group": item.fulfillment_group or "",
            "cmdb_ci": cmdb_ci or "",
            "category": item.category or "",
            "subcategory": item.subcategory or "",
            "state": "1",
            "request_state": "submitted",
            "stage": "request_approved",
            "approval": "not_requested",
        },
        user_sys_id,
    )

    ritm = await create_record(
        db,
        "sc_req_item",
        {
            "request": request["sys_id"],
            "cat_item": item.sys_id,
            "short_description": request_short,
            "description": item.description or item.short_description or "",
            "quantity": max(1, int(quantity or 1)),
            "price": item.price or "0",
            "state": "1",
            "stage": "fulfillment",
            "assignment_group": item.fulfillment_group or "",
            "cmdb_ci": cmdb_ci or "",
            "opened_by": user_sys_id,
            "approval": "not_requested",
        },
        user_sys_id,
    )

    option_records: list[dict[str, Any]] = []
    for name, value in normalized.items():
        variable = by_name[name]
        option = await create_record(
            db,
            "sc_item_option",
            {
                "item_option_new": variable.sys_id,
                "sc_req_item": ritm["sys_id"],
                "value": value,
            },
            user_sys_id,
        )
        option_records.append(option)

    task = None
    if create_fulfillment_task:
        task = await create_record(
            db,
            "sc_task",
            {
                "short_description": f"Fulfill: {item.name}",
                "description": item.description or item.short_description or "",
                "request": request["sys_id"],
                "request_item": ritm["sys_id"],
                "cat_item": item.sys_id,
                "assignment_group": item.fulfillment_group or "",
                "cmdb_ci": cmdb_ci or "",
                "state": "1",
                "stage": "fulfillment",
            },
            user_sys_id,
        )

    return {
        "request": request,
        "request_item": ritm,
        "variables": normalized,
        "options": option_records,
        "task": task,
        "request_id": request["sys_id"],
        "request_number": request.get("number", ""),
    }
