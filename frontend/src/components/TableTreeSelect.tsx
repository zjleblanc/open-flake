import { useMemo } from 'react';
import { OFSelect } from './OFSelect';
import type { TableInfo } from '../api/client';
import { buildTableTreeOptions } from '../utils/tableTree';

interface TableTreeSelectProps {
  id?: string;
  tables: TableInfo[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
}

/** Tree-aware table picker: shows physical tables and the full CMDB class
 * hierarchy (subclasses indented under their parent) in one searchable
 * dropdown, so users can reference `cmdb_ci_server` directly instead of
 * only the top-level `cmdb_ci` table. */
export function TableTreeSelect({
  id,
  tables,
  value,
  onChange,
  placeholder = 'Select a table…',
  disabled = false,
}: TableTreeSelectProps) {
  const options = useMemo(() => buildTableTreeOptions(tables), [tables]);
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
