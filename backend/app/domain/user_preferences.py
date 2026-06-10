from typing import Any, Literal

DateDisplayFormat = Literal["raw", "local"]
LayoutDensity = Literal["comfortable", "compact"]
ColorScheme = Literal["dark", "light", "system"]

DEFAULT_USER_PREFERENCES: dict[str, Any] = {
    "date_display_format": "raw",
    "layout_density": "comfortable",
    "sidebar_expanded": True,
    "color_scheme": "dark",
}

_VALID_DATE_DISPLAY_FORMATS = {"raw", "local"}
_VALID_LAYOUT_DENSITIES = {"comfortable", "compact"}
_VALID_COLOR_SCHEMES = {"dark", "light", "system"}


def normalize_user_preferences(stored: dict[str, Any] | None) -> dict[str, Any]:
    """Merge stored preferences with defaults and coerce to supported values."""
    merged = {**DEFAULT_USER_PREFERENCES, **(stored or {})}

    date_display_format = merged.get("date_display_format")
    if date_display_format not in _VALID_DATE_DISPLAY_FORMATS:
        date_display_format = DEFAULT_USER_PREFERENCES["date_display_format"]

    layout_density = merged.get("layout_density")
    if layout_density not in _VALID_LAYOUT_DENSITIES:
        layout_density = DEFAULT_USER_PREFERENCES["layout_density"]

    sidebar_expanded = merged.get("sidebar_expanded")
    if isinstance(sidebar_expanded, str):
        lowered = sidebar_expanded.lower()
        if lowered == "true":
            sidebar_expanded = True
        elif lowered == "false":
            sidebar_expanded = False
        else:
            sidebar_expanded = DEFAULT_USER_PREFERENCES["sidebar_expanded"]
    elif sidebar_expanded is not True and sidebar_expanded is not False:
        sidebar_expanded = DEFAULT_USER_PREFERENCES["sidebar_expanded"]

    color_scheme = merged.get("color_scheme")
    if color_scheme not in _VALID_COLOR_SCHEMES:
        color_scheme = DEFAULT_USER_PREFERENCES["color_scheme"]

    return {
        "date_display_format": date_display_format,
        "layout_density": layout_density,
        "sidebar_expanded": sidebar_expanded,
        "color_scheme": color_scheme,
    }


def merge_user_preferences_update(
    current: dict[str, Any] | None,
    patch: dict[str, Any],
) -> dict[str, Any]:
    """Apply a partial preferences update and return the normalized result."""
    base = normalize_user_preferences(current)
    update: dict[str, Any] = {}

    if "date_display_format" in patch:
        value = patch["date_display_format"]
        if value in _VALID_DATE_DISPLAY_FORMATS:
            update["date_display_format"] = value

    if "layout_density" in patch:
        value = patch["layout_density"]
        if value in _VALID_LAYOUT_DENSITIES:
            update["layout_density"] = value

    if "sidebar_expanded" in patch:
        value = patch["sidebar_expanded"]
        if isinstance(value, str):
            value = value.lower() == "true"
        if isinstance(value, bool):
            update["sidebar_expanded"] = value

    if "color_scheme" in patch:
        value = patch["color_scheme"]
        if value in _VALID_COLOR_SCHEMES:
            update["color_scheme"] = value

    return normalize_user_preferences({**base, **update})
