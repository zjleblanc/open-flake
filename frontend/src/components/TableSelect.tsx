import { useMemo } from 'react';
import { OFSelect } from './OFSelect';
import type { TableInfo } from '../api/client';
import { buildTableSelectOptions } from '../utils/tableOptions';

interface TableSelectProps {
  id?: string;
  tables: TableInfo[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
}

/** Plain, searchable table picker covering physical tables and CMDB
 * subclasses alike. Each option shows the technical class name (e.g.
 * `cmdb_ci_server`) as subtext under its label, so a subclass is still
 * identifiable without grouping options into a hierarchy. */
export function TableSelect({
  id,
  tables,
  value,
  onChange,
  placeholder = 'Select a table…',
  disabled = false,
}: TableSelectProps) {
  const options = useMemo(() => buildTableSelectOptions(tables), [tables]);
  return (
    <OFSelect
      id={id}
      autocomplete
      placeholder={placeholder}
      disabled={disabled}
      value={value}
      onChange={(next) => onChange(next as string)}
      options={options}
    />
  );
}
