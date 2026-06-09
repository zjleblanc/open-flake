"""Split and merge CMDB CI API payloads."""

from __future__ import annotations

from typing import Any

from app.domain.cmdb.constants import PROMOTED_COLUMNS, SYSTEM_FIELDS
from app.domain.cmdb.registry import FieldMeta, get_merged_fields, is_registered
from app.domain.errors import InvalidFieldNameError, validate_other_field_keys
from app.models import CmdbCi


def _unwrap(value: Any) -> Any:
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value


def split_payload(class_name: str, payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split a flat API payload into promoted columns and attributes."""
    columns: dict[str, Any] = {}
    attributes: dict[str, Any] = {}
    merged = get_merged_fields(class_name) if is_registered(class_name) else {}
    strict = bool(merged)

    nested_attrs = payload.get("attributes")
    if isinstance(nested_attrs, dict):
        for key, value in nested_attrs.items():
            payload = {**payload, key: value}

    for key, raw_value in payload.items():
        if key in {"attributes", "other"}:
            continue
        value = _unwrap(raw_value)
        if key in SYSTEM_FIELDS:
            if key not in {"sys_class_path", "attributes"}:
                columns[key] = value
            continue
        if key in PROMOTED_COLUMNS:
            columns[key] = value
            continue
        if strict:
            if key not in merged:
                raise InvalidFieldNameError(
                    f"Field '{key}' is not defined for class '{class_name}'"
                )
            field = merged[key]
            if field.storage == "column":
                columns[key] = value
            else:
                attributes[key] = value
        else:
            validate_other_field_keys({key: value})
            attributes[key] = value

    if attributes:
        validate_other_field_keys(attributes)
    return columns, attributes


def merge_record(record: CmdbCi, *, exclude_links: bool = True) -> dict[str, Any]:
    """Serialize a CmdbCi row to a flat API dict."""
    from app.domain.table_service import _model_to_dict

    data = _model_to_dict(record, "cmdb_ci", exclude_links)
    attrs = record.attributes or {}
    if isinstance(attrs, dict):
        for key, value in attrs.items():
            if key not in data or data[key] == "":
                data[key] = "" if value is None else str(value)
    return data
