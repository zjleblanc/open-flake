import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { FILTER_OPERATORS, emptyFilterRow, type FilterRow } from './filterBuilderUtils';

interface ReferenceFilterBuilderProps {
  table: string;
  rows: FilterRow[];
  onChange: (rows: FilterRow[]) => void;
  disabled?: boolean;
}

export function ReferenceFilterBuilder({
  table,
  rows,
  onChange,
  disabled = false,
}: ReferenceFilterBuilderProps) {
  const fieldsQuery = useQuery({
    queryKey: ['catalog-admin-table-fields', table],
    queryFn: () => api.adminListTableFields(table),
    enabled: Boolean(table),
  });

  const fields = fieldsQuery.data?.result || [];

  function updateRow(index: number, patch: Partial<FilterRow>) {
    onChange(rows.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  }

  function removeRow(index: number) {
    onChange(rows.filter((_, i) => i !== index));
  }

  function addRow() {
    onChange([...rows, emptyFilterRow(rows.length ? 'AND' : 'AND')]);
  }

  if (!table) {
    return <p className="catalog-help-text">Select a reference table to configure filters.</p>;
  }

  return (
    <div className="catalog-filter-builder">
      {fieldsQuery.isLoading ? (
        <p className="catalog-help-text">Loading fields…</p>
      ) : fieldsQuery.error ? (
        <p className="error">{(fieldsQuery.error as Error).message}</p>
      ) : null}

      {rows.map((row, index) => (
        <div key={index} className="catalog-filter-row-wrap">
          {index > 0 ? (
            <button
              type="button"
              className={`catalog-filter-join ${row.join === 'OR' ? 'is-or' : 'is-and'}`}
              disabled={disabled}
              onClick={() => updateRow(index, { join: row.join === 'OR' ? 'AND' : 'OR' })}
              title="Toggle AND/OR"
            >
              {row.join}
            </button>
          ) : null}
          <div className="catalog-filter-row">
            <select
              aria-label={`Filter field ${index + 1}`}
              value={row.field}
              disabled={disabled}
              onChange={(e) => updateRow(index, { field: e.target.value })}
            >
              <option value="">Field…</option>
              {fields.map((field) => (
                <option key={field.name} value={field.name}>
                  {field.name}
                </option>
              ))}
            </select>
            <select
              aria-label={`Filter operator ${index + 1}`}
              value={row.operator}
              disabled={disabled}
              onChange={(e) => updateRow(index, { operator: e.target.value })}
            >
              {FILTER_OPERATORS.map((op) => (
                <option key={op} value={op}>
                  {op}
                </option>
              ))}
            </select>
            {row.operator === 'ISEMPTY' || row.operator === 'ISNOTEMPTY' ? (
              <span className="catalog-filter-value-placeholder" />
            ) : (
              <input
                aria-label={`Filter value ${index + 1}`}
                value={row.value}
                disabled={disabled}
                placeholder={row.operator === 'IN' || row.operator === 'NOT IN' ? 'a,b,c' : 'value'}
                onChange={(e) => updateRow(index, { value: e.target.value })}
              />
            )}
            <button
              type="button"
              className="btn btn-secondary catalog-filter-remove"
              disabled={disabled}
              aria-label={`Remove filter ${index + 1}`}
              onClick={() => removeRow(index)}
            >
              ×
            </button>
          </div>
        </div>
      ))}

      <button
        type="button"
        className="btn btn-secondary"
        disabled={disabled || !fields.length}
        onClick={addRow}
      >
        + Add Filter
      </button>
    </div>
  );
}
