import pytest

from app.domain.errors import InvalidFieldNameError, validate_other_field_keys, validate_snake_case_field_name


@pytest.mark.parametrize(
    "name",
    ["model_number", "u_custom_field", "a", "field2", "cpu_count"],
)
def test_valid_snake_case_names(name):
    validate_snake_case_field_name(name)


@pytest.mark.parametrize(
    "name",
    ["ModelNumber", "model-number", "_model", "model_", "model__number", "123", ""],
)
def test_invalid_snake_case_names(name):
    with pytest.raises(InvalidFieldNameError):
        validate_snake_case_field_name(name)


def test_validate_other_field_keys():
    validate_other_field_keys({"model_number": "x", "rack_unit": "1"})


def test_validate_other_field_keys_rejects_invalid():
    with pytest.raises(InvalidFieldNameError):
        validate_other_field_keys({"model_number": "x", "BadKey": "y"})
