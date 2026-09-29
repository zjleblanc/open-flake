import { ChevronDownIcon, ChevronUpIcon } from './DetailIcons';
import type { SortDirection } from '../hooks/useServerPagination';
import './SortableColumnHeader.css';

interface SortableColumnHeaderProps {
  /** Field name sent to the API as `sysparm_orderby`/`sysparm_orderbydesc`. */
  field: string;
  label: string;
  sortField: string;
  sortDirection: SortDirection;
  onSort: (field: string) => void;
  /** Set false for columns that don't map to a sortable server field (default true). */
  sortable?: boolean;
}

/** A `<th>` that toggles server-side sort on click, with a chevron indicating the active
 * sort column's direction. Use inside a `<thead><tr>` alongside plain `<th>` cells. */
export function SortableColumnHeader({
  field,
  label,
  sortField,
  sortDirection,
  onSort,
  sortable = true,
}: SortableColumnHeaderProps) {
  if (!sortable) {
    return <th>{label}</th>;
  }

  const isActive = sortField === field;

  return (
    <th
      className="sortable-column-header"
      aria-sort={isActive ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}
    >
      <button type="button" className="sortable-column-header-btn" onClick={() => onSort(field)}>
        <span>{label}</span>
        {isActive ? (
          sortDirection === 'asc' ? (
            <ChevronUpIcon size={12} />
          ) : (
            <ChevronDownIcon size={12} />
          )
        ) : (
          <span className="sortable-column-header-spacer" aria-hidden="true" />
        )}
      </button>
    </th>
  );
}
