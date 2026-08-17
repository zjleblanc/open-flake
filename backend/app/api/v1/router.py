from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.flake.attachment import (
    _assert_attachment_parent_access,
    _attachment_storage_candidates,
    _attachment_to_dict,
    _save_attachment,
    remove_attachment,
)
from app.auth.deps import AuthContext, authenticate_request
from app.auth.rbac import (
    assert_grant_management,
    assert_record_action_by_id,
    filter_record_list_query,
    get_user_group_ids,
    get_user_permissions,
)
from app.auth.security import create_access_token, hash_api_key, hash_password, verify_password
from app.config import get_settings
from app.db import get_db
from app.domain.table_service import (
    create_record,
    delete_record,
    get_record_by_sys_id,
    list_records,
    update_record,
)
from app.domain.user_preferences import merge_user_preferences_update, normalize_user_preferences
from app.models import (
    ApiKey,
    ChangeRequest,
    CmdbCi,
    Incident,
    ItemOptionNew,
    OAuthClient,
    Problem,
    RecordAccessGrant,
    ScItemOption,
    SysAttachment,
    SysAudit,
    SysComment,
    SysUser,
)
from app.query.parser import QueryCondition, parse_sysparm_query
from app.utils.ids import new_api_key, new_sys_id

router = APIRouter(prefix="/api/v1", tags=["ui-api"])
settings = get_settings()


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    user_name: str
    sys_id: str


class UserPreferencesResponse(BaseModel):
    date_display_format: str
    layout_density: str
    sidebar_expanded: bool
    color_scheme: str
    pinned_nav_items: list[str]


class UpdateUserPreferencesRequest(BaseModel):
    date_display_format: str | None = None
    layout_density: str | None = None
    sidebar_expanded: bool | None = None
    color_scheme: str | None = None
    pinned_nav_items: list[str] | None = None


async def _load_user_preferences(
    db: AsyncSession,
    user_sys_id: str,
) -> dict[str, Any]:
    user = await db.get(SysUser, user_sys_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return normalize_user_preferences(user.preferences)


@router.post("/auth/login", response_model=LoginResponse)
async def ui_login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SysUser).where(SysUser.user_name == body.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.user_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    token = create_access_token(user.user_name)
    return LoginResponse(access_token=token, user_name=user.user_name, sys_id=user.sys_id)


@router.get("/auth/me")
async def auth_me(
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    perms = await get_user_permissions(db, auth.user_sys_id)
    group_ids = list(await get_user_group_ids(db, auth.user_sys_id))
    preferences = await _load_user_preferences(db, auth.user_sys_id)
    return {
        "sys_id": auth.user_sys_id,
        "user_name": auth.user_name,
        "permissions": sorted(perms),
        "group_ids": group_ids,
        "preferences": preferences,
    }


@router.get("/dashboard")
async def dashboard(
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    async def count(model, table: str, open_states: list[str] | None = None):
        q = select(func.count()).select_from(model)
        if open_states:
            q = q.where(model.state.in_(open_states))
        q = await filter_record_list_query(db, auth, table, q, model)
        return (await db.execute(q)).scalar() or 0

    return {
        "incidents_open": await count(Incident, "incident", ["1", "2", "3"]),
        "problems_open": await count(Problem, "problem", ["1", "2", "3"]),
        "changes_open": await count(
            ChangeRequest, "change_request", ["-5", "-4", "-3", "-2", "-1", "0", "1", "2"]
        ),
        "cis_total": await count(CmdbCi, "cmdb_ci"),
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
    "catalog-request-items": "sc_req_item",
    "catalog-tasks": "sc_task",
    "catalog-items": "sc_cat_item",
}


def _table_router_name(name: str) -> str:
    return TABLE_ENDPOINTS[name]


@router.get("/records/{resource}")
async def list_resource(
    resource: str,
    state: str | None = None,
    query: str | None = None,
    limit: int = 50,
    offset: int = 0,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    if resource not in TABLE_ENDPOINTS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown resource")
    table = TABLE_ENDPOINTS[resource]

    conditions = parse_sysparm_query(query)
    if state:
        conditions.append(QueryCondition(field="state", operator="=", value=state))
    records, total = await list_records(
        db, table, conditions, limit, offset, False, auth=auth, include_permissions=True
    )
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
    record = await get_record_by_sys_id(
        db, table, sys_id, False, auth=auth, include_permissions=True
    )
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return record


@router.get("/records/{resource}/{sys_id}/variables")
async def list_record_variables(
    resource: str,
    sys_id: str,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    """Return submitted catalog variable values for a requested item (RITM).

    In ServiceNow, variable values (``sc_item_option``) are always attached to
    the requested item, never the parent request, so this is only meaningful
    for the ``catalog-request-items`` resource.
    """
    if resource not in TABLE_ENDPOINTS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown resource")
    table = TABLE_ENDPOINTS[resource]
    if table != "sc_req_item":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Variables are only available for requested items"
        )
    await assert_record_action_by_id(db, auth, table, sys_id, "read")
    result = await db.execute(
        select(ScItemOption, ItemOptionNew)
        .join(ItemOptionNew, ItemOptionNew.sys_id == ScItemOption.item_option_new)
        .where(ScItemOption.sc_req_item == sys_id)
        .order_by(ItemOptionNew.order, ItemOptionNew.name)
    )
    return [
        {
            "sys_id": option.sys_id,
            "name": variable.name,
            "question_text": variable.question_text or variable.name,
            "type": variable.type,
            "value": option.value or "",
        }
        for option, variable in result.all()
    ]


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
    return await create_record(db, table, payload, auth.user_sys_id, False, auth=auth)


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
    record = await update_record(db, table, sys_id, payload, auth.user_sys_id, False, auth=auth)
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
    if not await delete_record(db, table, sys_id, auth=auth):
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
        auth=auth,
    )


class CreateGrantRequest(BaseModel):
    access_level: str
    user_sys_id: str | None = None
    group_sys_id: str | None = None


@router.get("/records/{resource}/{sys_id}/grants")
async def list_grants(
    resource: str,
    sys_id: str,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    if resource not in TABLE_ENDPOINTS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown resource")
    table = TABLE_ENDPOINTS[resource]
    await assert_grant_management(db, auth, table, sys_id)
    result = await db.execute(
        select(RecordAccessGrant).where(
            RecordAccessGrant.table_name == table,
            RecordAccessGrant.record_sys_id == sys_id,
        )
    )
    grants = result.scalars().all()
    return [
        {
            "sys_id": g.sys_id,
            "access_level": g.access_level,
            "user_sys_id": g.user_sys_id or "",
            "group_sys_id": g.group_sys_id or "",
            "source": g.source,
            "granted_by": g.granted_by or "",
        }
        for g in grants
    ]


@router.post("/records/{resource}/{sys_id}/grants", status_code=status.HTTP_201_CREATED)
async def create_grant(
    resource: str,
    sys_id: str,
    body: CreateGrantRequest,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    if resource not in TABLE_ENDPOINTS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown resource")
    table = TABLE_ENDPOINTS[resource]
    if body.access_level not in ("view", "comment"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "access_level must be view or comment")
    if bool(body.user_sys_id) == bool(body.group_sys_id):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Specify exactly one of user_sys_id or group_sys_id"
        )
    await assert_grant_management(db, auth, table, sys_id)
    payload: dict[str, Any] = {
        "table_name": table,
        "record_sys_id": sys_id,
        "access_level": body.access_level,
        "granted_by": auth.user_sys_id,
        "source": "manual",
    }
    if body.user_sys_id:
        payload["user_sys_id"] = body.user_sys_id
    if body.group_sys_id:
        payload["group_sys_id"] = body.group_sys_id
    return await create_record(
        db,
        "record_access_grant",
        payload,
        auth.user_sys_id,
        False,
        auth=auth,
    )


@router.delete(
    "/records/{resource}/{sys_id}/grants/{grant_sys_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_grant(
    resource: str,
    sys_id: str,
    grant_sys_id: str,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    if resource not in TABLE_ENDPOINTS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown resource")
    table = TABLE_ENDPOINTS[resource]
    await assert_grant_management(db, auth, table, sys_id)
    grant = await db.get(RecordAccessGrant, grant_sys_id)
    if not grant or grant.table_name != table or grant.record_sys_id != sys_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Grant not found")
    if not await delete_record(db, "record_access_grant", grant_sys_id, auth=auth):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Grant not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class CreateCommentRequest(BaseModel):
    comment: str


@router.get("/records/{resource}/{sys_id}/comments")
async def list_comments(
    resource: str,
    sys_id: str,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    if resource not in TABLE_ENDPOINTS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown resource")
    table = TABLE_ENDPOINTS[resource]
    await assert_record_action_by_id(db, auth, table, sys_id, "read")
    result = await db.execute(
        select(SysComment)
        .where(SysComment.table_name == table, SysComment.record_sys_id == sys_id)
        .order_by(SysComment.sys_created_on.desc())
    )
    comments = result.scalars().all()
    return [
        {
            "sys_id": c.sys_id,
            "comment": c.comment,
            "sys_created_by": c.sys_created_by or "",
            "sys_created_on": c.sys_created_on.isoformat() if c.sys_created_on else "",
        }
        for c in comments
    ]


@router.post("/records/{resource}/{sys_id}/comments", status_code=status.HTTP_201_CREATED)
async def create_comment(
    resource: str,
    sys_id: str,
    body: CreateCommentRequest,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    if resource not in TABLE_ENDPOINTS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown resource")
    table = TABLE_ENDPOINTS[resource]
    return await create_record(
        db,
        "sys_comment",
        {
            "table_name": table,
            "record_sys_id": sys_id,
            "comment": body.comment,
        },
        auth.user_sys_id,
        False,
        auth=auth,
    )


@router.get("/records/{resource}/{sys_id}/activity")
async def list_record_activity(
    resource: str,
    sys_id: str,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    """Return a merged, time-descending activity timeline for a record: a
    synthetic "created" entry, field-change batches from `sys_audit`, and
    threaded `sys_comment` entries."""
    if resource not in TABLE_ENDPOINTS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown resource")
    table = TABLE_ENDPOINTS[resource]
    record = await get_record_by_sys_id(db, table, sys_id, exclude_links=True, auth=auth)
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")

    activity: list[dict[str, Any]] = []

    audit_result = await db.execute(
        select(SysAudit)
        .where(SysAudit.table_name == table, SysAudit.record_sys_id == sys_id)
        .order_by(SysAudit.sys_created_on.asc())
    )
    batches: dict[str, dict[str, Any]] = {}
    for row in audit_result.scalars().all():
        batch = batches.get(row.batch_id)
        if batch is None:
            batch = {
                "id": row.batch_id,
                "type": "update",
                "user": row.user or "",
                "timestamp": row.sys_created_on.isoformat() if row.sys_created_on else "",
                "changes": [],
            }
            batches[row.batch_id] = batch
            activity.append(batch)
        batch["changes"].append(
            {
                "field": row.field_name,
                "old_value": row.old_value or "",
                "new_value": row.new_value or "",
            }
        )

    comments_result = await db.execute(
        select(SysComment)
        .where(SysComment.table_name == table, SysComment.record_sys_id == sys_id)
        .order_by(SysComment.sys_created_on.asc())
    )
    for comment in comments_result.scalars().all():
        activity.append(
            {
                "id": comment.sys_id,
                "type": "comment",
                "user": comment.sys_created_by or "",
                "timestamp": comment.sys_created_on.isoformat() if comment.sys_created_on else "",
                "comment": comment.comment,
            }
        )

    created_on = record.get("sys_created_on")
    if created_on:
        activity.append(
            {
                "id": f"{sys_id}-created",
                "type": "created",
                "user": record.get("sys_created_by") or "",
                "timestamp": created_on,
            }
        )

    activity.sort(key=lambda entry: entry.get("timestamp") or "", reverse=True)
    return {"activity": activity}


@router.get("/records/{resource}/{sys_id}/attachments")
async def list_record_attachments(
    resource: str,
    sys_id: str,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    if resource not in TABLE_ENDPOINTS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown resource")
    table = TABLE_ENDPOINTS[resource]
    await assert_record_action_by_id(db, auth, table, sys_id, "read")
    result = await db.execute(
        select(SysAttachment)
        .where(SysAttachment.table_name == table, SysAttachment.table_sys_id == sys_id)
        .order_by(SysAttachment.sys_created_on.desc())
    )
    return [_attachment_to_dict(record) for record in result.scalars().all()]


@router.post("/records/{resource}/{sys_id}/attachments", status_code=status.HTTP_201_CREATED)
async def upload_record_attachment(
    resource: str,
    sys_id: str,
    file: UploadFile = File(...),
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    if resource not in TABLE_ENDPOINTS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown resource")
    table = TABLE_ENDPOINTS[resource]
    await _assert_attachment_parent_access(db, auth, table, sys_id, "write")
    content = await file.read()
    record = await _save_attachment(
        db,
        auth,
        table,
        sys_id,
        file.filename or "file",
        file.content_type or "application/octet-stream",
        content,
    )
    return _attachment_to_dict(record)


@router.get("/records/{resource}/{sys_id}/attachments/{attachment_sys_id}/file")
async def download_record_attachment(
    resource: str,
    sys_id: str,
    attachment_sys_id: str,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    if resource not in TABLE_ENDPOINTS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown resource")
    table = TABLE_ENDPOINTS[resource]
    record = await db.get(SysAttachment, attachment_sys_id)
    if (
        not record
        or record.table_name != table
        or record.table_sys_id != sys_id
        or not any(path.is_file() for path in _attachment_storage_candidates(record))
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attachment not found")
    await _assert_attachment_parent_access(db, auth, table, sys_id, "read")
    file_path = next(path for path in _attachment_storage_candidates(record) if path.is_file())
    return FileResponse(
        file_path,
        filename=record.file_name,
        media_type=record.content_type,
    )


@router.delete(
    "/records/{resource}/{sys_id}/attachments/{attachment_sys_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_record_attachment(
    resource: str,
    sys_id: str,
    attachment_sys_id: str,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    if resource not in TABLE_ENDPOINTS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown resource")
    table = TABLE_ENDPOINTS[resource]
    record = await db.get(SysAttachment, attachment_sys_id)
    if not record or record.table_name != table or record.table_sys_id != sys_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attachment not found")
    await _assert_attachment_parent_access(db, auth, table, sys_id, "write")
    await remove_attachment(db, record)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/settings/preferences", response_model=UserPreferencesResponse)
async def get_user_preferences(
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    return await _load_user_preferences(db, auth.user_sys_id)


@router.patch("/settings/preferences", response_model=UserPreferencesResponse)
async def update_user_preferences(
    body: UpdateUserPreferencesRequest,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(SysUser, auth.user_sys_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    patch = body.model_dump(exclude_unset=True)
    if not patch:
        return normalize_user_preferences(user.preferences)

    user.preferences = merge_user_preferences_update(user.preferences, patch)
    await db.flush()
    return normalize_user_preferences(user.preferences)


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
