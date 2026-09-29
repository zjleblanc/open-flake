from dataclasses import dataclass, field

from sqlalchemy import and_, or_


@dataclass
class QueryCondition:
    field: str
    operator: str
    value: str
    join: str = "AND"  # "AND" or "OR" — how this connects to the previous condition


@dataclass
class OrderByClause:
    field: str
    direction: str = "asc"  # "asc" or "desc"


@dataclass
class ParsedQuery:
    """Result of parsing a `sysparm_query` string: filter conditions plus any
    `ORDERBY`/`ORDERBYDESC` clauses found in the string, in the order they
    appeared."""

    conditions: list[QueryCondition] = field(default_factory=list)
    order_by: list[OrderByClause] = field(default_factory=list)


# The default sort applied to list queries when no explicit sort is requested.
DEFAULT_ORDER_BY = [OrderByClause(field="sys_updated_on", direction="desc")]

_OPERATORS = (
    "ISNOTEMPTY",
    "ISEMPTY",
    "NOTIN",
    "NOT IN",
    "LIKE",
    "!=",
    "IN",
    "=",
)


def condition_clause(col, cond: QueryCondition):
    """Build a SQLAlchemy clause for a single QueryCondition."""
    if cond.operator == "=":
        return col == cond.value
    if cond.operator == "!=":
        return col != cond.value
    if cond.operator == "IN":
        values = [part.strip() for part in cond.value.split(",") if part.strip()]
        return col.in_(values) if values else None
    if cond.operator == "NOTIN":
        values = [part.strip() for part in cond.value.split(",") if part.strip()]
        return ~col.in_(values) if values else None
    if cond.operator == "LIKE":
        return col.ilike(f"%{cond.value}%")
    if cond.operator == "ISEMPTY":
        return or_(col.is_(None), col == "")
    if cond.operator == "ISNOTEMPTY":
        return and_(col.isnot(None), col != "")
    return None


def apply_condition_groups(query, model, conditions: list[QueryCondition]):
    """Apply QueryConditions with AND/OR join semantics.

    Conditions are grouped into OR-separated groups of AND-clauses:
    ``a=1^b=2^ORc=3`` becomes ``(a=1 AND b=2) OR (c=3)``.
    """
    if not conditions:
        return query

    groups: list[list] = [[]]
    for cond in conditions:
        col = getattr(model, cond.field, None)
        if col is None:
            continue
        clause = condition_clause(col, cond)
        if clause is None:
            continue
        if cond.join == "OR" and groups[-1]:
            groups.append([clause])
        else:
            groups[-1].append(clause)

    group_clauses = []
    for group in groups:
        if not group:
            continue
        group_clauses.append(and_(*group) if len(group) > 1 else group[0])

    if not group_clauses:
        return query
    if len(group_clauses) == 1:
        return query.where(group_clauses[0])
    return query.where(or_(*group_clauses))


def apply_order_by(query, model, order_by: list[OrderByClause] | None):
    """Apply an ordered list of OrderByClause to a query.

    Falls back to `DEFAULT_ORDER_BY` (`sys_updated_on` desc) when `order_by`
    is `None` or empty. Fields that don't exist on `model` are silently
    skipped, matching `apply_condition_groups`'s tolerance for unknown
    field names.
    """
    clauses = order_by if order_by else DEFAULT_ORDER_BY
    order_clauses = []
    for clause in clauses:
        col = getattr(model, clause.field, None)
        if col is None:
            continue
        order_clauses.append(col.desc() if clause.direction == "desc" else col.asc())
    if not order_clauses:
        return query
    return query.order_by(*order_clauses)


def resolve_order_by(
    parsed_order_by: list[OrderByClause],
    orderby: str | None = None,
    orderbydesc: str | None = None,
) -> list[OrderByClause]:
    """Merge `ORDERBY`/`ORDERBYDESC` clauses parsed from a `sysparm_query`
    string with explicit `sysparm_orderby`/`sysparm_orderbydesc` query
    params, matching ServiceNow's Table API where either mechanism can
    specify sort. Explicit params are appended after any parsed clauses so
    they act as a final tiebreaker/override when both are supplied."""
    order_by = list(parsed_order_by)
    if orderbydesc:
        order_by.append(OrderByClause(field=orderbydesc, direction="desc"))
    elif orderby:
        order_by.append(OrderByClause(field=orderby, direction="asc"))
    return order_by


def _parse_condition_part(part: str, join: str = "AND") -> QueryCondition | None:
    part = part.strip()
    if not part:
        return None

    for op in _OPERATORS:
        idx = part.find(op)
        if idx <= 0:
            continue
        field_name = part[:idx].strip()
        value = part[idx + len(op) :].strip()
        operator = "NOTIN" if op == "NOT IN" else op
        if operator in {"ISEMPTY", "ISNOTEMPTY"}:
            value = ""
        return QueryCondition(field=field_name, operator=operator, value=value, join=join)
    return None


def _parse_order_by_part(part: str) -> OrderByClause | None:
    part = part.strip()
    if part.startswith("ORDERBYDESC"):
        field_name = part[len("ORDERBYDESC") :].strip()
        return OrderByClause(field=field_name, direction="desc") if field_name else None
    if part.startswith("ORDERBY"):
        field_name = part[len("ORDERBY") :].strip()
        return OrderByClause(field=field_name, direction="asc") if field_name else None
    return None


def parse_sysparm_query(query: str | None) -> ParsedQuery:
    """Parse a ServiceNow-style sysparm_query into filter conditions plus sort.

    Supports:
    - AND via ``^``
    - OR via ``^OR``
    - Operators: ``=``, ``!=``, ``LIKE``, ``IN``, ``NOTIN``/``NOT IN``,
      ``ISEMPTY``, ``ISNOTEMPTY``
    - Sort via ``ORDERBY<field>`` / ``ORDERBYDESC<field>`` (returned in
      ``ParsedQuery.order_by``, in the order they appear in the string)

    Segments are split on a single ``^`` (not ``^OR``) because ``ORDERBY``/
    ``ORDERBYDESC`` themselves start with ``OR`` -- splitting on ``^OR``
    first would also chop off the front of ``^ORDERBY...`` segments. Each
    non-leading segment that starts with a literal ``OR`` (but not
    ``ORDERBY``) is instead treated as an OR-joined condition and has that
    prefix stripped before further parsing.
    """
    if not query:
        return ParsedQuery()

    conditions: list[QueryCondition] = []
    order_by: list[OrderByClause] = []
    for index, raw_part in enumerate(query.split("^")):
        part = raw_part
        join = "AND"
        if index > 0 and part.startswith("OR") and not part.startswith("ORDERBY"):
            join = "OR"
            part = part[2:]

        order_clause = _parse_order_by_part(part)
        if order_clause is not None:
            order_by.append(order_clause)
            continue
        cond = _parse_condition_part(part, join=join)
        if cond is not None:
            conditions.append(cond)
    return ParsedQuery(conditions=conditions, order_by=order_by)
