import secrets
import uuid


def new_sys_id() -> str:
    return uuid.uuid4().hex


def new_api_key() -> str:
    return secrets.token_urlsafe(32)
