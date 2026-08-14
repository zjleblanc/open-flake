"""CRUD for named secrets used in template resolution (e.g. {{secret:name}}).

Available to any user with the appropriate secrets.* permission -- not
restricted to catalog admins.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import AuthContext, authenticate_request
from app.auth.rbac import get_user_permissions, has_permission
from app.db import get_db
from app.domain.secrets import validate_secret_name
from app.domain.table_service import create_record, delete_record, update_record
from app.models import SysSecret

router = APIRouter(prefix="/api/flake/secrets", tags=["secrets-api"])


async def _require_secrets_permission(
    db: AsyncSession,
    auth: AuthContext,
    required: str,
) -> None:
    perms = await get_user_permissions(db, auth.user_sys_id)
    if not has_permission(perms, required):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")


def _secret_dict(secret: SysSecret) -> dict[str, Any]:
    return {
        "sys_id": secret.sys_id,
        "name": secret.name,
        "description": secret.description or "",
        "active": bool(secret.active),
        "has_value": bool(secret.value),
    }


@router.get("")
async def list_secrets(
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    await _require_secrets_permission(db, auth, "secrets.read")
    result = await db.execute(select(SysSecret).order_by(SysSecret.name.asc()))
    return {"result": [_secret_dict(s) for s in result.scalars().all()]}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_secret(
    payload: dict[str, Any],
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    await _require_secrets_permission(db, auth, "secrets.write")
    try:
        name = validate_secret_name(str(payload.get("name") or ""))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    value = payload.get("value")
    if value is None or str(value) == "":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "value is required")
    existing = await db.execute(select(SysSecret).where(SysSecret.name == name))
    if existing.scalar_one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, f"Secret '{name}' already exists")
    record = await create_record(
        db,
        "sys_secret",
        {
            "name": name,
            "value": str(value),
            "description": payload.get("description") or None,
            "active": bool(payload.get("active", True)),
        },
        auth.user_sys_id,
        auth=auth,
    )
    secret = await db.get(SysSecret, record["sys_id"])
    if not secret:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Secret not found")
    return {"result": _secret_dict(secret)}


@router.get("/{secret_id}")
async def get_secret(
    secret_id: str,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    await _require_secrets_permission(db, auth, "secrets.read")
    secret = await db.get(SysSecret, secret_id)
    if not secret:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Secret not found")
    return {"result": _secret_dict(secret)}


@router.patch("/{secret_id}")
async def update_secret(
    secret_id: str,
    payload: dict[str, Any],
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    await _require_secrets_permission(db, auth, "secrets.write")
    secret = await db.get(SysSecret, secret_id)
    if not secret:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Secret not found")
    allowed: dict[str, Any] = {}
    if "name" in payload:
        try:
            new_name = validate_secret_name(str(payload["name"]))
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
        if new_name != secret.name:
            clash = await db.execute(select(SysSecret).where(SysSecret.name == new_name))
            if clash.scalar_one_or_none():
                raise HTTPException(
                    status.HTTP_409_CONFLICT, f"Secret '{new_name}' already exists"
                )
            allowed["name"] = new_name
    if "value" in payload and payload["value"] is not None and str(payload["value"]) != "":
        allowed["value"] = str(payload["value"])
    if "description" in payload:
        allowed["description"] = payload["description"] or None
    if "active" in payload:
        allowed["active"] = bool(payload["active"])
    if allowed:
        await update_record(db, "sys_secret", secret_id, allowed, auth.user_sys_id, auth=auth)
        await db.refresh(secret)
    return {"result": _secret_dict(secret)}


@router.delete("/{secret_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_secret(
    secret_id: str,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    await _require_secrets_permission(db, auth, "secrets.admin")
    secret = await db.get(SysSecret, secret_id)
    if not secret:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Secret not found")
    await delete_record(db, "sys_secret", secret_id, auth=auth)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
