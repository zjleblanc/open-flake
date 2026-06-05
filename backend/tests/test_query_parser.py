from app.query.parser import parse_sysparm_query


def test_parse_equality():
    conditions = parse_sysparm_query("user_name=admin")
    assert len(conditions) == 1
    assert conditions[0].field == "user_name"
    assert conditions[0].operator == "="
    assert conditions[0].value == "admin"


def test_parse_and_chain():
    conditions = parse_sysparm_query("state=1^assignment_group=abc123")
    assert len(conditions) == 2
    assert conditions[0].field == "state"
    assert conditions[1].field == "assignment_group"


def test_parse_empty():
    assert parse_sysparm_query(None) == []
    assert parse_sysparm_query("") == []


def test_parse_like():
    conditions = parse_sysparm_query("short_descriptionLIKEnetwork")
    assert len(conditions) == 1
    assert conditions[0].operator == "LIKE"
