from dataclasses import dataclass


@dataclass
class QueryCondition:
    field: str
    operator: str
    value: str


def parse_sysparm_query(query: str | None) -> list[QueryCondition]:
    if not query:
        return []
    conditions: list[QueryCondition] = []
    for part in query.split("^"):
        part = part.strip()
        if not part:
            continue
        if part.startswith("ORDERBY"):
            continue
        if part.startswith("ORDERBYDESC"):
            continue
        if "=" in part:
            field, value = part.split("=", 1)
            conditions.append(QueryCondition(field=field.strip(), operator="=", value=value.strip()))
        elif "LIKE" in part:
            field, value = part.split("LIKE", 1)
            conditions.append(QueryCondition(field=field.strip(), operator="LIKE", value=value.strip()))
    return conditions
