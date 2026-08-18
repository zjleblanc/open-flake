import type { TableInfo } from '../api/client';
import type { OFSelectOption } from '../components/OFSelect';

const INDENT = '\u00A0\u00A0'; // two non-breaking spaces per depth level, so option labels align in the dropdown

/**
 * Flattens a `TableInfo[]` list (which carries `super_class` pointers) into
 * depth-ordered, indented `OFSelectOption`s so parent/child relationships
 * (e.g. `cmdb_ci` -> `cmdb_ci_server` -> `cmdb_ci_linux_server`) read as a
 * tree inside a single searchable dropdown. Each subclass remains directly
 * selectable -- picking `cmdb_ci_server` filters to that class specifically.
 */
export function buildTableTreeOptions(tables: TableInfo[]): OFSelectOption[] {
  const byName = new Map(tables.map((table) => [table.name, table]));
  const childrenOf = new Map<string, TableInfo[]>();
  const roots: TableInfo[] = [];

  for (const table of tables) {
    const parent = table.super_class;
    if (parent && byName.has(parent)) {
      const siblings = childrenOf.get(parent) ?? [];
      siblings.push(table);
      childrenOf.set(parent, siblings);
    } else {
      roots.push(table);
    }
  }

  const byLabel = (list: TableInfo[]) =>
    [...list].sort((a, b) => (a.label || a.name).localeCompare(b.label || b.name));

  const options: OFSelectOption[] = [];
  function visit(table: TableInfo, depth: number) {
    const displayLabel = table.label || table.name;
    const prefix = depth > 0 ? `${INDENT.repeat(depth)}\u21B3 ` : '';
    options.push({ value: table.name, label: `${prefix}${displayLabel}` });
    for (const child of byLabel(childrenOf.get(table.name) ?? [])) {
      visit(child, depth + 1);
    }
  }

  for (const root of byLabel(roots)) visit(root, 0);
  return options;
}
