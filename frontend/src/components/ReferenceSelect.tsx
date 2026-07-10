import { useQuery } from '@tanstack/react-query';
import { api, type CatalogChoice } from '../api/client';

interface ReferenceSelectProps {
  itemId: string;
  varName: string;
  value: string;
  dependsOn?: string;
  disabled?: boolean;
  id?: string;
  onChange: (value: string) => void;
}

export function ReferenceSelect({
  itemId,
  varName,
  value,
  dependsOn = '',
  disabled = false,
  id,
  onChange,
}: ReferenceSelectProps) {
  const optionsQuery = useQuery({
    queryKey: ['catalog-variable-options', itemId, varName, dependsOn],
    queryFn: () => api.getVariableOptions(itemId, varName, dependsOn || undefined),
    enabled: Boolean(itemId && varName),
  });

  const options: CatalogChoice[] = optionsQuery.data?.result?.options || [];
  const selectedStillValid = !value || options.some((opt) => opt.value === value);

  return (
    <div className="catalog-reference-select">
      <select
        id={id}
        value={selectedStillValid ? value : ''}
        disabled={disabled || optionsQuery.isLoading}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">{optionsQuery.isLoading ? 'Loading…' : 'Select…'}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label || option.value}
          </option>
        ))}
      </select>
      {optionsQuery.isLoading ? (
        <span className="catalog-reference-loading">Loading options…</span>
      ) : null}
      {optionsQuery.error ? <p className="error">{(optionsQuery.error as Error).message}</p> : null}
    </div>
  );
}
