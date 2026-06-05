import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import AuthContext, authenticate_request
from app.config import get_settings
from app.db import get_db
from app.domain.table_service import create_record, delete_record, get_record_by_sys_id
from app.models import SysAttachment
from app.utils.ids import new_sys_id

router = APIRouter(prefix="/api/now/attachment", tags=["attachment-api"])
settings = get_settings()


def _ensure_attach_dir() -> Path:
    path = Path(settings.attachments_path)
    path.mkdir(parents=True, exist_ok=True)
    return path


@router.post("/file", status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    table_name: str = Form(...),
    table_sys_id: str = Form(...),
    file: UploadFile = File(...),
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
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
        "result": {
            "sys_id": sys_id,
            "file_name": record.file_name,
            "table_name": table_name,
            "table_sys_id": table_sys_id,
            "size_bytes": str(record.size_bytes),
            "content_type": record.content_type,
        }
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
    return {
        "result": {
            "sys_id": record.sys_id,
            "file_name": record.file_name,
            "table_name": record.table_name,
            "table_sys_id": record.table_sys_id,
            "size_bytes": str(record.size_bytes),
            "content_type": record.content_type,
        }
    }


@router.get("/{sys_id}/file")
async def download_attachment(
    sys_id: str,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    record = await db.get(SysAttachment, sys_id)
    if not record or not os.path.exists(record.storage_path):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attachment not found")
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
    if os.path.exists(record.storage_path):
        os.remove(record.storage_path)
    await db.delete(record)
    await db.flush()
    return None
