"""Shared scalar coercion helpers for inbound API payloads.

ServiceNow-compatible clients (Ansible's `servicenow.itsm` modules, custom
scripts) commonly send choice-list fields like `state`/`priority`/`active`
as native JSON integers or booleans even though OpenFlake stores them as
strings. Real ServiceNow tolerates this; OpenFlake should too rather than
letting the database driver reject the mismatched type at flush time with
an opaque 500.
"""

from typing import Any

from sqlalchemy import Boolean, String, Text
from sqlalchemy.sql.elements import ColumnElement


def coerce_scalar_for_column(value: Any, column: ColumnElement[Any]) -> Any:
    """Coerce a raw JSON scalar to match a column's expected Python type.

    - `Boolean` columns accept a string ("true"/"1"/"yes" -> True, anything
      else -> False) or coerce any other non-string value via `bool()`.
    - `String`/`Text` columns accept a JSON `int` or `bool` and stringify it
      (`bool` becomes the lowercase `"true"`/`"false"` ServiceNow convention,
      matching how OpenFlake itself stores boolean-like string fields such as
      `active`).

    `None`, `dict`, and `list` values always pass through unchanged.
    """
    if value is None or isinstance(value, dict | list):
        return value
    if isinstance(column.type, Boolean):
        if isinstance(value, str):
            return value.strip().lower() in {"true", "1", "yes"}
        return bool(value)
    if isinstance(column.type, String | Text) and isinstance(value, bool | int):
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)
    return value
