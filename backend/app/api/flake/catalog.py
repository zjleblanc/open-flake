from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import AuthContext, authenticate_request
from app.db import get_db
from app.domain.table_service import create_record
from app.models import ServiceCatalog, ServiceCatalogItem
from app.utils.ids import new_sys_id

router = APIRouter(prefix="/api/sn_sc/servicecatalog", tags=["catalog-api"])

_cart: dict[str, list[dict]] = {}


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
        select(ServiceCatalogItem).where(ServiceCatalogItem.active.is_(True))
    )
    items = result.scalars().all()
    return {
        "result": [
            {
                "sys_id": i.sys_id,
                "name": i.name,
                "short_description": i.short_description or "",
                "price": i.price,
            }
            for i in items
        ]
    }


@router.get("/items/{item_id}")
async def get_item(
    item_id: str,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    item = await db.get(ServiceCatalogItem, item_id)
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    return {
        "result": {
            "sys_id": item.sys_id,
            "name": item.name,
            "short_description": item.short_description or "",
            "price": item.price,
        }
    }


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
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    cart = _cart.setdefault(auth.user_sys_id, [])
    cart.append({"item_id": item_id, "name": item.name, "quantity": 1})
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
    items_desc = ", ".join(i["name"] for i in cart)
    request = await create_record(
        db,
        "sc_request",
        {
            "short_description": f"Catalog order: {items_desc}",
            "requested_by": auth.user_sys_id,
            "requested_for": auth.user_sys_id,
            "state": "1",
        },
        auth.user_sys_id,
    )
    for item in cart:
        await create_record(
            db,
            "sc_task",
            {
                "short_description": f"Fulfill: {item['name']}",
                "request": request["sys_id"],
                "state": "1",
            },
            auth.user_sys_id,
        )
    return {"result": request}


@router.post("/items/{item_id}/order_now", status_code=status.HTTP_201_CREATED)
async def order_now(
    item_id: str,
    payload: dict[str, Any] | None = None,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    item = await db.get(ServiceCatalogItem, item_id)
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    request = await create_record(
        db,
        "sc_request",
        {
            "short_description": f"Order: {item.name}",
            "requested_by": auth.user_sys_id,
            "requested_for": auth.user_sys_id,
            "state": "1",
        },
        auth.user_sys_id,
    )
    await create_record(
        db,
        "sc_task",
        {
            "short_description": f"Fulfill: {item.name}",
            "request": request["sys_id"],
            "state": "1",
        },
        auth.user_sys_id,
    )
    return {"result": request}
