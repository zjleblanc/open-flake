import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import AuthContext, authenticate_request
from app.auth.rbac import assert_record_action_by_id
from app.domain.registry import RBAC_RECORD_TABLES
from app.config import get_settings
from app.db import get_db
from app.models import SysAttachment
from app.utils.ids import new_sys_id

router = APIRouter(prefix="/api/now/attachment", tags=["attachment-api"])
settings = get_settings()


def _ensure_attach_dir() -> Path:
    path = Path(settings.attachments_path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _attachment_to_dict(record: SysAttachment) -> dict:
    return {
        "sys_id": record.sys_id,
        "file_name": record.file_name,
        "table_name": record.table_name,
        "table_sys_id": record.table_sys_id,
        "size_bytes": str(record.size_bytes),
        "content_type": record.content_type,
        "download_link": f"{settings.base_url}/api/now/attachment/{record.sys_id}/file",
        "sys_created_on": record.sys_created_on.isoformat() if record.sys_created_on else "",
        "sys_updated_on": record.sys_updated_on.isoformat() if record.sys_updated_on else "",
        "sys_created_by": record.sys_created_by or "",
        "sys_updated_by": record.sys_updated_by or "",
    }


async def _assert_attachment_parent_access(
    db: AsyncSession,
    auth: AuthContext,
    table_name: str,
    table_sys_id: str,
    action: str,
) -> None:
    if table_name in RBAC_RECORD_TABLES:
        await assert_record_action_by_id(db, auth, table_name, table_sys_id, action)  # type: ignore[arg-type]


@router.get("")
async def list_attachments(
    response: Response,
    table_name: str | None = Query(default=None),
    table_sys_id: str | None = Query(default=None),
    sysparm_limit: int = Query(default=10000),
    sysparm_offset: int = Query(default=0),
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    if table_name and table_sys_id:
        await _assert_attachment_parent_access(db, auth, table_name, table_sys_id, "read")

    filters: list = []
    if table_name:
        filters.append(SysAttachment.table_name == table_name)
    if table_sys_id:
        filters.append(SysAttachment.table_sys_id == table_sys_id)

    query = select(SysAttachment)
    count_query = select(func.count()).select_from(SysAttachment)
    for condition in filters:
        query = query.where(condition)
        count_query = count_query.where(condition)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(query.limit(sysparm_limit).offset(sysparm_offset))
    records = result.scalars().all()
    response.headers["x-total-count"] = str(total)
    return {"result": [_attachment_to_dict(record) for record in records]}


@router.post("/file", status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    table_name: str = Form(...),
    table_sys_id: str = Form(...),
    file: UploadFile = File(...),
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    await _assert_attachment_parent_access(db, auth, table_name, table_sys_id, "write")

    attach_dir = _ensure_attach_dir()
    sys_id = new_sys_id()
    ext = Path(file.filename or "file").suffix
    storage_name = f"{sys_id}{ext}"
    storage_path = attach_dir / storage_name

    content = await file.read()
    storage_path.write_bytes(content)

    record = SysAttachment(
        sys_id=sys_id,
        table_name=table_name,
        table_sys_id=table_sys_id,
        file_name=file.filename or storage_name,
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(content),
        storage_path=str(storage_path),
        sys_created_by=auth.user_sys_id,
        sys_updated_by=auth.user_sys_id,
    )
    db.add(record)
    await db.flush()

    return {
        "result": _attachment_to_dict(record)
    }


@router.get("/{sys_id}")
async def get_attachment_meta(
    sys_id: str,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    record = await db.get(SysAttachment, sys_id)
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attachment not found")
    await _assert_attachment_parent_access(
        db, auth, record.table_name, record.table_sys_id, "read"
    )
    return {"result": _attachment_to_dict(record)}


@router.get("/{sys_id}/file")
async def download_attachment(
    sys_id: str,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    record = await db.get(SysAttachment, sys_id)
    if not record or not os.path.exists(record.storage_path):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attachment not found")
    await _assert_attachment_parent_access(
        db, auth, record.table_name, record.table_sys_id, "read"
    )
    return FileResponse(
        record.storage_path,
        filename=record.file_name,
        media_type=record.content_type,
    )


@router.delete("/{sys_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attachment(
    sys_id: str,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    record = await db.get(SysAttachment, sys_id)
    if not record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attachment not found")
    await _assert_attachment_parent_access(
        db, auth, record.table_name, record.table_sys_id, "write"
    )
    if os.path.exists(record.storage_path):
        os.remove(record.storage_path)
    await db.delete(record)
    await db.flush()
    return None
