import type { TableInfo } from '../api/client';
import type { OFSelectOption } from '../components/OFSelect';

/**
 * Flattens a `TableInfo[]` list into a plain, alphabetically-sorted list of
 * `OFSelectOption`s for a normal (non-hierarchical) dropdown. Each option's
 * `subLabel` carries the technical class name (e.g. `cmdb_ci_server`) so
 * CMDB subclasses remain identifiable even though they're no longer grouped
 * under their parent class.
 */
export function buildTableSelectOptions(tables: TableInfo[]): OFSelectOption[] {
  return [...tables]
    .sort((a, b) => (a.label || a.name).localeCompare(b.label || b.name))
    .map((table) => ({
      value: table.name,
      label: table.label || table.name,
      subLabel: table.name,
    }));
}
