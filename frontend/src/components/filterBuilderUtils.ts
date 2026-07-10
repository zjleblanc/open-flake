export type FilterRow = {
  field: string;
  operator: string;
  value: string;
  join: "AND" | "OR";
};

export const FILTER_OPERATORS = [
  "=",
  "!=",
  "LIKE",
  "IN",
  "NOT IN",
  "ISEMPTY",
  "ISNOTEMPTY",
] as const;

export function emptyFilterRow(join: "AND" | "OR" = "AND"): FilterRow {
  return { field: "", operator: "=", value: "", join };
}

export function serializeFilterRows(rows: FilterRow[]): string {
  return rows
    .filter((row) => row.field)
    .map((row, i) => {
      const prefix = i === 0 ? "" : row.join === "OR" ? "^OR" : "^";
      if (row.operator === "ISEMPTY") return `${prefix}${row.field}ISEMPTY`;
      if (row.operator === "ISNOTEMPTY") return `${prefix}${row.field}ISNOTEMPTY`;
      const op = row.operator === "NOT IN" ? "NOTIN" : row.operator;
      return `${prefix}${row.field}${op}${row.value}`;
    })
    .join("");
}

const PARSE_OPERATORS = [
  "ISNOTEMPTY",
  "ISEMPTY",
  "NOTIN",
  "NOT IN",
  "LIKE",
  "!=",
  "IN",
  "=",
] as const;

function parseConditionPart(part: string, join: "AND" | "OR"): FilterRow | null {
  const trimmed = part.trim();
  if (!trimmed) return null;
  for (const op of PARSE_OPERATORS) {
    const idx = trimmed.indexOf(op);
    if (idx <= 0) continue;
    const field = trimmed.slice(0, idx).trim();
    const value = trimmed.slice(idx + op.length).trim();
    const operator = op === "NOTIN" ? "NOT IN" : op;
    return {
      field,
      operator,
      value: operator === "ISEMPTY" || operator === "ISNOTEMPTY" ? "" : value,
      join,
    };
  }
  return null;
}

export function parseFilterRows(query: string | undefined | null): FilterRow[] {
  if (!query?.trim()) return [];
  const rows: FilterRow[] = [];
  const orGroups = query.split("^OR");
  orGroups.forEach((group, groupIndex) => {
    const parts = group.split("^");
    parts.forEach((part, partIndex) => {
      let join: "AND" | "OR" = "AND";
      if (groupIndex > 0 && partIndex === 0) join = "OR";
      const row = parseConditionPart(part, join);
      if (row) rows.push(row);
    });
  });
  return rows;
}
