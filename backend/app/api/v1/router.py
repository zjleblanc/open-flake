from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import AuthContext, authenticate_request
from app.auth.security import create_access_token, hash_api_key, hash_password, verify_password
from app.config import get_settings
from app.db import get_db
from app.domain.registry import TABLE_MODELS
from app.domain.table_service import (
    create_record,
    delete_record,
    get_record_by_sys_id,
    list_records,
    update_record,
)
from app.models import (
    ApiKey,
    ChangeRequest,
    CmdbCi,
    Incident,
    OAuthClient,
    Problem,
    SysUser,
    SysUserGroup,
)
from app.utils.ids import new_api_key, new_sys_id

router = APIRouter(prefix="/api/v1", tags=["ui-api"])
settings = get_settings()


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    user_name: str


@router.post("/auth/login", response_model=LoginResponse)
async def ui_login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SysUser).where(SysUser.user_name == body.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.user_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    token = create_access_token(user.user_name)
    response = LoginResponse(access_token=token, user_name=user.user_name)
    return response


@router.get("/dashboard")
async def dashboard(
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    async def count(model, open_states: list[str] | None = None):
        q = select(func.count()).select_from(model)
        if open_states:
            q = q.where(model.state.in_(open_states))
        return (await db.execute(q)).scalar() or 0

    return {
        "incidents_open": await count(Incident, ["1", "2", "3"]),
        "problems_open": await count(Problem, ["1", "2", "3"]),
        "changes_open": await count(ChangeRequest, ["-5", "-4", "-3", "-2", "-1", "0", "1", "2"]),
        "cis_total": await count(CmdbCi),
    }


TABLE_ENDPOINTS = {
    "incidents": "incident",
    "problems": "problem",
    "change-requests": "change_request",
    "change-tasks": "change_task",
    "problem-tasks": "problem_task",
    "configuration-items": "cmdb_ci",
    "users": "sys_user",
    "groups": "sys_user_group",
    "catalog-requests": "sc_request",
    "catalog-tasks": "sc_task",
}


def _table_router_name(name: str) -> str:
    return TABLE_ENDPOINTS[name]


@router.get("/records/{resource}")
async def list_resource(
    resource: str,
    state: str | None = None,
    limit: int = 50,
    offset: int = 0,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    if resource not in TABLE_ENDPOINTS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown resource")
    table = TABLE_ENDPOINTS[resource]
    from app.query.parser import QueryCondition

    conditions = []
    if state:
        conditions.append(QueryCondition(field="state", operator="=", value=state))
    records, total = await list_records(db, table, conditions, limit, offset, False)
    return {"records": records, "total": total}


@router.get("/records/{resource}/{sys_id}")
async def get_resource(
    resource: str,
    sys_id: str,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    if resource not in TABLE_ENDPOINTS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown resource")
    table = TABLE_ENDPOINTS[resource]
    record = await get_record_by_sys_id(db, table, sys_id, False)
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return record


@router.post("/records/{resource}", status_code=status.HTTP_201_CREATED)
async def create_resource(
    resource: str,
    payload: dict[str, Any],
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    if resource not in TABLE_ENDPOINTS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown resource")
    table = TABLE_ENDPOINTS[resource]
    return await create_record(db, table, payload, auth.user_sys_id, False)


@router.patch("/records/{resource}/{sys_id}")
async def update_resource(
    resource: str,
    sys_id: str,
    payload: dict[str, Any],
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    if resource not in TABLE_ENDPOINTS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown resource")
    table = TABLE_ENDPOINTS[resource]
    record = await update_record(db, table, sys_id, payload, auth.user_sys_id, False)
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return record


@router.delete("/records/{resource}/{sys_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resource(
    resource: str,
    sys_id: str,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    if resource not in TABLE_ENDPOINTS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown resource")
    table = TABLE_ENDPOINTS[resource]
    if not await delete_record(db, table, sys_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class CreateUserRequest(BaseModel):
    user_name: str
    password: str
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(
    body: CreateUserRequest,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    return await create_record(
        db,
        "sys_user",
        {
            "user_name": body.user_name,
            "user_password": hash_password(body.password),
            "first_name": body.first_name or "",
            "last_name": body.last_name or "",
            "email": body.email or "",
            "active": "true",
        },
        auth.user_sys_id,
        False,
    )


class CreateApiKeyRequest(BaseModel):
    name: str


@router.post("/settings/api-keys", status_code=status.HTTP_201_CREATED)
async def create_api_key(
    body: CreateApiKeyRequest,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    raw_key = new_api_key()
    row = ApiKey(
        sys_id=new_sys_id(),
        key_hash=hash_api_key(raw_key),
        name=body.name,
        user_sys_id=auth.user_sys_id,
    )
    db.add(row)
    await db.flush()
    return {"sys_id": row.sys_id, "name": row.name, "api_key": raw_key}


@router.get("/settings/api-keys")
async def list_api_keys(
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ApiKey).where(ApiKey.user_sys_id == auth.user_sys_id))
    keys = result.scalars().all()
    return [{"sys_id": k.sys_id, "name": k.name, "active": k.active} for k in keys]


class CreateOAuthClientRequest(BaseModel):
    name: str
    client_id: str
    client_secret: str


@router.post("/settings/oauth-clients", status_code=status.HTTP_201_CREATED)
async def create_oauth_client(
    body: CreateOAuthClientRequest,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    client = OAuthClient(
        sys_id=new_sys_id(),
        client_id=body.client_id,
        client_secret=body.client_secret,
        name=body.name,
    )
    db.add(client)
    await db.flush()
    return {"sys_id": client.sys_id, "client_id": client.client_id, "name": client.name}


@router.get("/settings/oauth-clients")
async def list_oauth_clients(
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(OAuthClient))
    clients = result.scalars().all()
    return [
        {"sys_id": c.sys_id, "client_id": c.client_id, "name": c.name, "active": c.active}
        for c in clients
    ]
