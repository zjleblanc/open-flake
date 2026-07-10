from app.query.parser import parse_sysparm_query


def test_parse_equality():
    conditions = parse_sysparm_query("user_name=admin")
    assert len(conditions) == 1
    assert conditions[0].field == "user_name"
    assert conditions[0].operator == "="
    assert conditions[0].value == "admin"
    assert conditions[0].join == "AND"


def test_parse_and_chain():
    conditions = parse_sysparm_query("state=1^assignment_group=abc123")
    assert len(conditions) == 2
    assert conditions[0].field == "state"
    assert conditions[0].join == "AND"
    assert conditions[1].field == "assignment_group"
    assert conditions[1].join == "AND"


def test_parse_empty():
    assert parse_sysparm_query(None) == []
    assert parse_sysparm_query("") == []


def test_parse_like():
    conditions = parse_sysparm_query("short_descriptionLIKEnetwork")
    assert len(conditions) == 1
    assert conditions[0].operator == "LIKE"


def test_parse_sysparm_query_or_conditions():
    conditions = parse_sysparm_query("active=true^ORname=admin")
    assert len(conditions) == 2
    assert conditions[0].field == "active"
    assert conditions[0].join == "AND"
    assert conditions[1].field == "name"
    assert conditions[1].join == "OR"
    assert conditions[1].value == "admin"


def test_parse_sysparm_query_operators():
    conditions = parse_sysparm_query(
        "state!=closed^roleINadmin,itil^deptNOTINhr^emailISEMPTY^phoneISNOTEMPTY"
    )
    assert [(c.field, c.operator, c.value) for c in conditions] == [
        ("state", "!=", "closed"),
        ("role", "IN", "admin,itil"),
        ("dept", "NOTIN", "hr"),
        ("email", "ISEMPTY", ""),
        ("phone", "ISNOTEMPTY", ""),
    ]


def test_parse_sysparm_query_mixed_and_or():
    conditions = parse_sysparm_query("active=true^ORname=admin^dept=IT")
    assert len(conditions) == 3
    assert conditions[0].field == "active"
    assert conditions[0].join == "AND"
    assert conditions[1].field == "name"
    assert conditions[1].join == "OR"
    assert conditions[2].field == "dept"
    assert conditions[2].join == "AND"
    assert conditions[2].value == "IT"


def test_parse_not_in_with_space():
    conditions = parse_sysparm_query("stateNOT INclosed,canceled")
    assert len(conditions) == 1
    assert conditions[0].operator == "NOTIN"
    assert conditions[0].value == "closed,canceled"
