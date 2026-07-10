"""Named secret storage and {{secret:name}} template resolution."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SysSecret

# Matches {{secret:my_token}} — name is alphanumeric, underscore, or hyphen.
SECRET_REF_PATTERN = re.compile(r"\{\{secret:([A-Za-z0-9_-]+)\}\}")
SECRET_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class SecretResolutionError(ValueError):
    """Raised when a header/template references a missing or inactive secret."""


def validate_secret_name(name: str) -> str:
    cleaned = (name or "").strip()
    if not cleaned:
        raise ValueError("Secret name is required")
    if not SECRET_NAME_PATTERN.fullmatch(cleaned):
        raise ValueError(
            "Secret name must contain only letters, numbers, underscores, and hyphens"
        )
    return cleaned


def extract_secret_names(text: str) -> list[str]:
    """Return unique secret names referenced in ``text`` (order preserved)."""
    seen: set[str] = set()
    names: list[str] = []
    for match in SECRET_REF_PATTERN.finditer(text or ""):
        name = match.group(1)
        if name not in seen:
            seen.add(name)
            names.append(name)
    return names


def substitute_secrets(text: str, secrets: dict[str, str]) -> str:
    """Replace ``{{secret:name}}`` placeholders using the provided map."""

    def _replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in secrets:
            raise SecretResolutionError(f"Unknown or inactive secret: {name}")
        return secrets[name]

    return SECRET_REF_PATTERN.sub(_replace, text or "")


async def load_secret_values(
    session: AsyncSession,
    names: list[str],
) -> dict[str, str]:
    """Load active secret values by name. Missing names are omitted."""
    if not names:
        return {}
    result = await session.execute(
        select(SysSecret).where(
            SysSecret.name.in_(names),
            SysSecret.active.is_(True),
        )
    )
    return {row.name: row.value for row in result.scalars().all()}


async def resolve_secret_refs(session: AsyncSession, text: str) -> str:
    """Resolve all ``{{secret:name}}`` references in ``text``."""
    names = extract_secret_names(text)
    if not names:
        return text or ""
    values = await load_secret_values(session, names)
    missing = [name for name in names if name not in values]
    if missing:
        raise SecretResolutionError(f"Unknown or inactive secret: {', '.join(missing)}")
    return substitute_secrets(text, values)


async def resolve_headers(
    session: AsyncSession,
    headers: dict[str, Any] | None,
) -> dict[str, str]:
    """Resolve secret refs in every header value; return a string map."""
    if not isinstance(headers, dict):
        return {}
    resolved: dict[str, str] = {}
    for key, value in headers.items():
        resolved[str(key)] = await resolve_secret_refs(session, str(value))
    return resolved
