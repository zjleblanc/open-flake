import { type CatalogChoice } from '../api/client';
import { OFSelect, type OFSelectOption } from './OFSelect';

interface ReferenceSelectProps {
  value: string;
  options: CatalogChoice[];
  loading?: boolean;
  error?: string;
  disabled?: boolean;
  id?: string;
  onChange: (value: string) => void;
}

export function ReferenceSelect({
  value,
  options,
  loading = false,
  error,
  disabled = false,
  id,
  onChange,
}: ReferenceSelectProps) {
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
        disabled={disabled || loading}
        placeholder={loading ? 'Loading…' : 'Select…'}
        onChange={(next) => onChange(next as string)}
      />
      {loading ? <span className="catalog-reference-loading">Loading options…</span> : null}
      {error ? <p className="error">{error}</p> : null}
    </div>
  );
}
