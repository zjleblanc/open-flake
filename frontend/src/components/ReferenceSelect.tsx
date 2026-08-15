import { useQuery } from '@tanstack/react-query';
import { api, type CatalogChoice } from '../api/client';
import { OFSelect, type OFSelectOption } from './OFSelect';

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

  const selectOptions: OFSelectOption[] = options.map((option) => ({
    value: option.value,
    label: option.label || option.value,
  }));

  return (
    <div className="catalog-reference-select">
      <OFSelect
        id={id}
        options={selectOptions}
        value={selectedStillValid ? value : ''}
        disabled={disabled || optionsQuery.isLoading}
        placeholder={optionsQuery.isLoading ? 'Loading…' : 'Select…'}
        onChange={(next) => onChange(next as string)}
      />
      {optionsQuery.isLoading ? (
        <span className="catalog-reference-loading">Loading options…</span>
      ) : null}
      {optionsQuery.error ? <p className="error">{(optionsQuery.error as Error).message}</p> : null}
    </div>
  );
}
