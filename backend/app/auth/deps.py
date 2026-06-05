from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import decode_access_token, hash_api_key, verify_password
from app.db import get_db
from app.models import ApiKey, OAuthToken, SysUser


@dataclass
class AuthContext:
    user_sys_id: str
    user_name: str
    auth_method: str


def _parse_basic_auth(request: Request) -> tuple[str, str] | None:
    auth = request.headers.get("Authorization", "")
    if not auth.lower().startswith("basic "):
        return None
    import base64

    try:
        decoded = base64.b64decode(auth[6:]).decode("utf-8")
        username, _, password = decoded.partition(":")
        return username, password
    except Exception:
        return None


async def authenticate_request(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AuthContext:
    token = request.cookies.get("openflake_token")
    auth_header = request.headers.get("Authorization", "")
    if not token and auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()

    api_key = request.headers.get("x-sn-apikey")

    if api_key:
        key_hash = hash_api_key(api_key)
        result = await db.execute(
            select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.active.is_(True))
        )
        api_key_row = result.scalar_one_or_none()
        if api_key_row:
            user = await db.get(SysUser, api_key_row.user_sys_id)
            if user and user.active == "true":
                return AuthContext(user.sys_id, user.user_name, "api_key")

    if token:
        oauth_result = await db.execute(
            select(OAuthToken).where(OAuthToken.access_token == token)
        )
        oauth_row = oauth_result.scalar_one_or_none()
        if oauth_row and oauth_row.expires_at > datetime.now(timezone.utc):
            if oauth_row.user_sys_id:
                user = await db.get(SysUser, oauth_row.user_sys_id)
                if user and user.active == "true":
                    return AuthContext(user.sys_id, user.user_name, "oauth")
        subject = decode_access_token(token)
        if subject:
            result = await db.execute(select(SysUser).where(SysUser.user_name == subject))
            user = result.scalar_one_or_none()
            if user and user.active == "true":
                return AuthContext(user.sys_id, user.user_name, "jwt")

    basic = _parse_basic_auth(request)
    if basic:
        username, password = basic
        result = await db.execute(select(SysUser).where(SysUser.user_name == username))
        user = result.scalar_one_or_none()
        if user and verify_password(password, user.user_password):
            return AuthContext(user.sys_id, user.user_name, "basic")

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
    )


async def optional_auth(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AuthContext | None:
    try:
        return await authenticate_request(request, db)
    except HTTPException:
        return None
