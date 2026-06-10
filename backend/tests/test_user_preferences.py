from app.domain.user_preferences import (
    DEFAULT_USER_PREFERENCES,
    merge_user_preferences_update,
    normalize_user_preferences,
)


def test_normalize_user_preferences_applies_defaults():
    assert normalize_user_preferences(None) == DEFAULT_USER_PREFERENCES


def test_normalize_user_preferences_coerces_invalid_values():
    result = normalize_user_preferences(
        {
            "date_display_format": "invalid",
            "layout_density": "spacious",
            "sidebar_expanded": "maybe",
        }
    )
    assert result == DEFAULT_USER_PREFERENCES


def test_normalize_user_preferences_accepts_valid_values():
    result = normalize_user_preferences(
        {
            "date_display_format": "local",
            "layout_density": "compact",
            "sidebar_expanded": "false",
        }
    )
    assert result == {
        "date_display_format": "local",
        "layout_density": "compact",
        "sidebar_expanded": False,
        "color_scheme": "dark",
    }


def test_merge_user_preferences_update_partial_patch():
    current = {
        "date_display_format": "local",
        "layout_density": "comfortable",
        "sidebar_expanded": True,
    }
    result = merge_user_preferences_update(current, {"layout_density": "compact"})
    assert result == {
        "date_display_format": "local",
        "layout_density": "compact",
        "sidebar_expanded": True,
        "color_scheme": "dark",
    }


def test_merge_user_preferences_update_ignores_invalid_patch_values():
    current = DEFAULT_USER_PREFERENCES.copy()
    result = merge_user_preferences_update(
        current,
        {"date_display_format": "utc", "sidebar_expanded": False},
    )
    assert result == {
        "date_display_format": "raw",
        "layout_density": "comfortable",
        "sidebar_expanded": False,
        "color_scheme": "dark",
    }


def test_normalize_user_preferences_accepts_color_scheme():
    result = normalize_user_preferences({"color_scheme": "system"})
    assert result["color_scheme"] == "system"
