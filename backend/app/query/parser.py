from dataclasses import dataclass

from sqlalchemy import and_, or_


@dataclass
class QueryCondition:
    field: str
    operator: str
    value: str
    join: str = "AND"  # "AND" or "OR" — how this connects to the previous condition


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


def _parse_condition_part(part: str, join: str = "AND") -> QueryCondition | None:
    part = part.strip()
    if not part:
        return None
    if part.startswith("ORDERBYDESC") or part.startswith("ORDERBY"):
        return None

    for op in _OPERATORS:
        idx = part.find(op)
        if idx <= 0:
            continue
        field = part[:idx].strip()
        value = part[idx + len(op) :].strip()
        operator = "NOTIN" if op == "NOT IN" else op
        if operator in {"ISEMPTY", "ISNOTEMPTY"}:
            value = ""
        return QueryCondition(field=field, operator=operator, value=value, join=join)
    return None


def parse_sysparm_query(query: str | None) -> list[QueryCondition]:
    """Parse a ServiceNow-style sysparm_query into QueryCondition list.

    Supports:
    - AND via ``^``
    - OR via ``^OR``
    - Operators: ``=``, ``!=``, ``LIKE``, ``IN``, ``NOTIN``/``NOT IN``,
      ``ISEMPTY``, ``ISNOTEMPTY``
    """
    if not query:
        return []

    conditions: list[QueryCondition] = []
    or_groups = query.split("^OR")
    for group_index, group in enumerate(or_groups):
        parts = group.split("^")
        for part_index, part in enumerate(parts):
            join = "OR" if group_index > 0 and part_index == 0 else "AND"
            if group_index == 0 and part_index == 0:
                join = "AND"
            cond = _parse_condition_part(part, join=join)
            if cond is not None:
                conditions.append(cond)
    return conditions
