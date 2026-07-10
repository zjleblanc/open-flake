from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import (
    new_oauth_token,
    new_refresh_token,
    verify_password,
)
from app.config import get_settings
from app.db import get_db
from app.models import OAuthClient, OAuthToken, SysUser
from app.utils.ids import new_sys_id

router = APIRouter(tags=["oauth"])
settings = get_settings()


@router.post("/oauth_token.do")
async def oauth_token(
    grant_type: str = Form(default="password"),
    username: str | None = Form(default=None),
    password: str | None = Form(default=None),
    client_id: str | None = Form(default=None),
    client_secret: str | None = Form(default=None),
    refresh_token: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
):
    expires_in = settings.oauth_token_expire_seconds
    expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

    if grant_type == "password":
        if not username or not password:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "username and password required")
        result = await db.execute(select(SysUser).where(SysUser.user_name == username))
        user = result.scalar_one_or_none()
        if not user or not verify_password(password, user.user_password):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
        if client_id and client_secret:
            client_result = await db.execute(
                select(OAuthClient).where(
                    OAuthClient.client_id == client_id,
                    OAuthClient.client_secret == client_secret,
                    OAuthClient.active.is_(True),
                )
            )
            if not client_result.scalar_one_or_none():
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid client")
        access = new_oauth_token()
        refresh = new_refresh_token()
        token_row = OAuthToken(
            sys_id=new_sys_id(),
            access_token=access,
            refresh_token=refresh,
            client_id=client_id,
            user_sys_id=user.sys_id,
            expires_at=expires_at,
        )
        db.add(token_row)
        await db.flush()
        return {
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "Bearer",
            "expires_in": expires_in,
        }

    if grant_type == "client_credentials":
        if not client_id or not client_secret:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "client_id and client_secret required"
            )
        client_result = await db.execute(
            select(OAuthClient).where(
                OAuthClient.client_id == client_id,
                OAuthClient.client_secret == client_secret,
                OAuthClient.active.is_(True),
            )
        )
        client = client_result.scalar_one_or_none()
        if not client:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid client")
        access = new_oauth_token()
        token_row = OAuthToken(
            sys_id=new_sys_id(),
            access_token=access,
            refresh_token=None,
            client_id=client_id,
            user_sys_id=None,
            expires_at=expires_at,
        )
        db.add(token_row)
        await db.flush()
        return {
            "access_token": access,
            "token_type": "Bearer",
            "expires_in": expires_in,
        }

    if grant_type == "refresh_token":
        if not refresh_token:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "refresh_token required")
        token_result = await db.execute(
            select(OAuthToken).where(OAuthToken.refresh_token == refresh_token)
        )
        old = token_result.scalar_one_or_none()
        if not old:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
        access = new_oauth_token()
        refresh = new_refresh_token()
        old.access_token = access
        old.refresh_token = refresh
        old.expires_at = expires_at
        await db.flush()
        return {
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "Bearer",
            "expires_in": expires_in,
        }

    raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unsupported grant_type: {grant_type}")
