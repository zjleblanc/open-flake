from app.domain.field_coercion import coerce_scalar_for_column
from app.models import Incident, ScTask, ServiceCatalogItem


def _col(model, name):
    return model.__table__.columns[name]


def test_int_coerced_to_string_for_string_column():
    assert coerce_scalar_for_column(2, _col(ScTask, "state")) == "2"


def test_bool_coerced_to_lowercase_string_for_string_column():
    assert coerce_scalar_for_column(True, _col(Incident, "active")) == "true"
    assert coerce_scalar_for_column(False, _col(Incident, "active")) == "false"


def test_string_value_passes_through_unchanged_for_string_column():
    assert coerce_scalar_for_column("2", _col(ScTask, "state")) == "2"


def test_none_passes_through_unchanged():
    assert coerce_scalar_for_column(None, _col(ScTask, "state")) is None


def test_dict_and_list_pass_through_unchanged():
    ref = {"value": "abc123"}
    assert coerce_scalar_for_column(ref, _col(ScTask, "assigned_to")) == ref
    values = ["a", "b"]
    assert coerce_scalar_for_column(values, _col(ScTask, "state")) == values


def test_real_boolean_column_accepts_truthy_string():
    col = _col(ServiceCatalogItem, "active")
    assert coerce_scalar_for_column("true", col) is True
    assert coerce_scalar_for_column("yes", col) is True
    assert coerce_scalar_for_column("false", col) is False
    assert coerce_scalar_for_column("no", col) is False


def test_real_boolean_column_coerces_non_string_via_bool():
    col = _col(ServiceCatalogItem, "active")
    assert coerce_scalar_for_column(1, col) is True
    assert coerce_scalar_for_column(0, col) is False
    assert coerce_scalar_for_column(True, col) is True


def test_float_left_untouched_for_string_column():
    # Deliberately out of scope: only int/bool are coerced, not float.
    assert coerce_scalar_for_column(2.5, _col(ScTask, "state")) == 2.5
