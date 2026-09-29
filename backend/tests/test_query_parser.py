from app.models import Incident
from app.query.parser import (
    DEFAULT_ORDER_BY,
    OrderByClause,
    apply_order_by,
    parse_sysparm_query,
    resolve_order_by,
)
from sqlalchemy import select


def test_parse_equality():
    conditions = parse_sysparm_query("user_name=admin").conditions
    assert len(conditions) == 1
    assert conditions[0].field == "user_name"
    assert conditions[0].operator == "="
    assert conditions[0].value == "admin"
    assert conditions[0].join == "AND"


def test_parse_and_chain():
    conditions = parse_sysparm_query("state=1^assignment_group=abc123").conditions
    assert len(conditions) == 2
    assert conditions[0].field == "state"
    assert conditions[0].join == "AND"
    assert conditions[1].field == "assignment_group"
    assert conditions[1].join == "AND"


def test_parse_empty():
    empty = parse_sysparm_query(None)
    assert empty.conditions == []
    assert empty.order_by == []
    assert parse_sysparm_query("").conditions == []


def test_parse_like():
    conditions = parse_sysparm_query("short_descriptionLIKEnetwork").conditions
    assert len(conditions) == 1
    assert conditions[0].operator == "LIKE"


def test_parse_sysparm_query_or_conditions():
    conditions = parse_sysparm_query("active=true^ORname=admin").conditions
    assert len(conditions) == 2
    assert conditions[0].field == "active"
    assert conditions[0].join == "AND"
    assert conditions[1].field == "name"
    assert conditions[1].join == "OR"
    assert conditions[1].value == "admin"


def test_parse_sysparm_query_operators():
    conditions = parse_sysparm_query(
        "state!=closed^roleINadmin,itil^deptNOTINhr^emailISEMPTY^phoneISNOTEMPTY"
    ).conditions
    assert [(c.field, c.operator, c.value) for c in conditions] == [
        ("state", "!=", "closed"),
        ("role", "IN", "admin,itil"),
        ("dept", "NOTIN", "hr"),
        ("email", "ISEMPTY", ""),
        ("phone", "ISNOTEMPTY", ""),
    ]


def test_parse_sysparm_query_mixed_and_or():
    conditions = parse_sysparm_query("active=true^ORname=admin^dept=IT").conditions
    assert len(conditions) == 3
    assert conditions[0].field == "active"
    assert conditions[0].join == "AND"
    assert conditions[1].field == "name"
    assert conditions[1].join == "OR"
    assert conditions[2].field == "dept"
    assert conditions[2].join == "AND"
    assert conditions[2].value == "IT"


def test_parse_not_in_with_space():
    conditions = parse_sysparm_query("stateNOT INclosed,canceled").conditions
    assert len(conditions) == 1
    assert conditions[0].operator == "NOTIN"
    assert conditions[0].value == "closed,canceled"


def test_parse_orderby_ascending():
    parsed = parse_sysparm_query("ORDERBYshort_description")
    assert parsed.conditions == []
    assert parsed.order_by == [OrderByClause(field="short_description", direction="asc")]


def test_parse_orderbydesc():
    parsed = parse_sysparm_query("ORDERBYDESCpriority")
    assert parsed.conditions == []
    assert parsed.order_by == [OrderByClause(field="priority", direction="desc")]


def test_parse_orderby_combined_with_conditions():
    parsed = parse_sysparm_query("active=true^ORDERBYDESCpriority")
    assert [(c.field, c.operator, c.value) for c in parsed.conditions] == [
        ("active", "=", "true"),
    ]
    assert parsed.order_by == [OrderByClause(field="priority", direction="desc")]


def test_parse_orderby_multiple_clauses():
    parsed = parse_sysparm_query("ORDERBYpriority^ORDERBYDESCsys_updated_on")
    assert parsed.order_by == [
        OrderByClause(field="priority", direction="asc"),
        OrderByClause(field="sys_updated_on", direction="desc"),
    ]


def test_parse_orderby_without_field_is_ignored():
    parsed = parse_sysparm_query("active=true^ORDERBY")
    assert len(parsed.conditions) == 1
    assert parsed.order_by == []


def test_resolve_order_by_defers_to_parsed_when_no_explicit_params():
    parsed_order_by = [OrderByClause(field="priority", direction="asc")]
    assert resolve_order_by(parsed_order_by) == parsed_order_by


def test_resolve_order_by_appends_explicit_orderby():
    result = resolve_order_by([], orderby="short_description")
    assert result == [OrderByClause(field="short_description", direction="asc")]


def test_resolve_order_by_appends_explicit_orderbydesc():
    result = resolve_order_by([], orderbydesc="priority")
    assert result == [OrderByClause(field="priority", direction="desc")]


def test_resolve_order_by_orderbydesc_takes_precedence_over_orderby():
    result = resolve_order_by([], orderby="priority", orderbydesc="sys_updated_on")
    assert result == [OrderByClause(field="sys_updated_on", direction="desc")]


def test_apply_order_by_defaults_to_sys_updated_on_desc():
    query = apply_order_by(select(Incident), Incident, None)
    compiled = str(query)
    assert "ORDER BY incident.sys_updated_on DESC" in compiled


def test_apply_order_by_empty_list_also_uses_default():
    query = apply_order_by(select(Incident), Incident, [])
    assert "ORDER BY incident.sys_updated_on DESC" in str(query)
    assert apply_order_by(select(Incident), Incident, None) is not None
    # DEFAULT_ORDER_BY itself sorts by sys_updated_on desc
    assert [OrderByClause(field="sys_updated_on", direction="desc")] == DEFAULT_ORDER_BY


def test_apply_order_by_explicit_field_and_direction():
    query = apply_order_by(
        select(Incident), Incident, [OrderByClause(field="priority", direction="asc")]
    )
    compiled = str(query)
    assert "ORDER BY incident.priority ASC" in compiled


def test_apply_order_by_multiple_fields_preserve_order():
    query = apply_order_by(
        select(Incident),
        Incident,
        [
            OrderByClause(field="priority", direction="asc"),
            OrderByClause(field="sys_updated_on", direction="desc"),
        ],
    )
    compiled = str(query)
    order_clause = compiled.split("ORDER BY", 1)[1]
    assert "incident.priority ASC" in order_clause
    assert order_clause.index("incident.priority") < order_clause.index("incident.sys_updated_on")


def test_apply_order_by_skips_unknown_field():
    query = apply_order_by(
        select(Incident), Incident, [OrderByClause(field="not_a_real_field", direction="asc")]
    )
    # Unknown field is dropped, leaving no ORDER BY clause at all (not the default).
    assert "ORDER BY" not in str(query)
