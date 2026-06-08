import hashlib
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import AuthContext, authenticate_request
from app.auth.rbac import assert_record_action_by_id
from app.domain.registry import RBAC_RECORD_TABLES
from app.config import BACKEND_ROOT, get_settings
from app.db import get_db
from app.models import SysAttachment
from app.utils.ids import new_sys_id

router = APIRouter(prefix="/api/now/attachment", tags=["attachment-api"])
settings = get_settings()


def resolve_attachments_path() -> Path:
    path = Path(settings.attachments_path)
    if not path.is_absolute():
        path = (BACKEND_ROOT / path).resolve()
    return path


def _ensure_attach_dir() -> Path:
    path = resolve_attachments_path()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _attachment_hash(record: SysAttachment) -> str:
    stored = (record.other or {}).get("hash")
    if stored:
        return stored
    if record.storage_path and os.path.exists(record.storage_path):
        return _sha256_hex(Path(record.storage_path).read_bytes())
    return ""


def _attachment_to_dict(record: SysAttachment) -> dict:
    return {
        "sys_id": record.sys_id,
        "file_name": record.file_name,
        "table_name": record.table_name,
        "table_sys_id": record.table_sys_id,
        "size_bytes": str(record.size_bytes),
        "content_type": record.content_type,
        "hash": _attachment_hash(record),
        "download_link": f"{settings.base_url}/api/now/attachment/{record.sys_id}/file",
        "sys_created_on": record.sys_created_on.isoformat() if record.sys_created_on else "",
        "sys_updated_on": record.sys_updated_on.isoformat() if record.sys_updated_on else "",
        "sys_created_by": record.sys_created_by or "",
        "sys_updated_by": record.sys_updated_by or "",
    }


async def _parse_upload_request(
    request: Request,
) -> tuple[str, str, str, str, bytes]:
    content_type_header = request.headers.get("content-type", "")

    if content_type_header.startswith("multipart/form-data"):
        form = await request.form()
        table_name = form.get("table_name")
        table_sys_id = form.get("table_sys_id")
        upload = form.get("file")
        if not table_name or not table_sys_id or not upload:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "table_name, table_sys_id, and file are required",
            )
        content = await upload.read()
        file_name = upload.filename or "file"
        mime_type = upload.content_type or "application/octet-stream"
        return str(table_name), str(table_sys_id), file_name, mime_type, content

    params = request.query_params
    table_name = params.get("table_name")
    table_sys_id = params.get("table_sys_id")
    if not table_name or not table_sys_id:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "table_name and table_sys_id query parameters are required",
        )
    file_name = params.get("file_name") or "file"
    mime_type = (
        params.get("content_type")
        or content_type_header.split(";", 1)[0].strip()
        or "application/octet-stream"
    )
    content = await request.body()
    return str(table_name), str(table_sys_id), file_name, mime_type, content


async def _save_attachment(
    db: AsyncSession,
    auth: AuthContext,
    table_name: str,
    table_sys_id: str,
    file_name: str,
    mime_type: str,
    content: bytes,
) -> SysAttachment:
    attach_dir = _ensure_attach_dir()
    sys_id = new_sys_id()
    ext = Path(file_name).suffix
    storage_name = f"{sys_id}{ext}"
    storage_path = attach_dir / storage_name
    storage_path.write_bytes(content)

    record = SysAttachment(
        sys_id=sys_id,
        table_name=table_name,
        table_sys_id=table_sys_id,
        file_name=file_name,
        content_type=mime_type,
        size_bytes=len(content),
        storage_path=str(storage_path),
        sys_created_by=auth.user_sys_id,
        sys_updated_by=auth.user_sys_id,
        other={"hash": _sha256_hex(content)},
    )
    db.add(record)
    await db.flush()
    return record


async def _assert_attachment_parent_access(
    db: AsyncSession,
    auth: AuthContext,
    table_name: str,
    table_sys_id: str,
    action: str,
) -> None:
    if table_name in RBAC_RECORD_TABLES:
        await assert_record_action_by_id(db, auth, table_name, table_sys_id, action)  # type: ignore[arg-type]


def _remove_attachment_file(record: SysAttachment) -> None:
    if record.storage_path and os.path.exists(record.storage_path):
        os.remove(record.storage_path)


async def remove_attachment(db: AsyncSession, record: SysAttachment) -> None:
    _remove_attachment_file(record)
    await db.delete(record)
    await db.flush()


async def delete_attachments_for_parent(
    db: AsyncSession, table_name: str, table_sys_id: str
) -> int:
    result = await db.execute(
        select(SysAttachment).where(
            SysAttachment.table_name == table_name,
            SysAttachment.table_sys_id == table_sys_id,
        )
    )
    records = result.scalars().all()
    for record in records:
        await remove_attachment(db, record)
    return len(records)


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
    request: Request,
    auth: AuthContext = Depends(authenticate_request),
    db: AsyncSession = Depends(get_db),
):
    table_name, table_sys_id, file_name, mime_type, content = await _parse_upload_request(
        request
    )
    await _assert_attachment_parent_access(db, auth, table_name, table_sys_id, "write")

    record = await _save_attachment(
        db, auth, table_name, table_sys_id, file_name, mime_type, content
    )

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
    await remove_attachment(db, record)
    return None
