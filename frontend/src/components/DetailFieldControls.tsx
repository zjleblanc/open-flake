import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { useUserPreferences } from '../settings/UserPreferencesContext';
import type { ColorScheme, LayoutDensity } from '../settings/userPreferences';
import { formatDetailValue } from '../utils/formatDisplayValue';
import { LockIcon } from './DetailIcons';

interface SegmentedPreferenceSelectorProps<T extends string> {
  value: T;
  onChange: (value: T) => void;
  idPrefix: string;
  label: string;
  options: { value: T; label: string }[];
}

export function SegmentedPreferenceSelector<T extends string>({
  value,
  onChange,
  idPrefix,
  label,
  options,
}: SegmentedPreferenceSelectorProps<T>) {
  return (
    <div className="layout-density-control">
      <span className="layout-density-label" id={`${idPrefix}-label`}>
        {label}
      </span>
      <div
        className="layout-density-selector"
        role="radiogroup"
        aria-labelledby={`${idPrefix}-label`}
      >
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            id={`${idPrefix}-${option.value}`}
            role="radio"
            aria-checked={value === option.value}
            className={`layout-density-option${
              value === option.value ? ' layout-density-option--active' : ''
            }`}
            onClick={() => onChange(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}

const LAYOUT_DENSITY_OPTIONS: { value: LayoutDensity; label: string }[] = [
  { value: 'comfortable', label: 'Comfortable' },
  { value: 'compact', label: 'Compact' },
];

interface LayoutDensitySelectorProps {
  value: LayoutDensity;
  onChange: (density: LayoutDensity) => void;
  idPrefix: string;
  label?: string;
}

export function LayoutDensitySelector({
  value,
  onChange,
  idPrefix,
  label = 'Layout',
}: LayoutDensitySelectorProps) {
  return (
    <SegmentedPreferenceSelector
      value={value}
      onChange={onChange}
      idPrefix={idPrefix}
      label={label}
      options={LAYOUT_DENSITY_OPTIONS}
    />
  );
}

const COLOR_SCHEME_OPTIONS: { value: ColorScheme; label: string }[] = [
  { value: 'dark', label: 'Dark' },
  { value: 'light', label: 'Light' },
  { value: 'system', label: 'System' },
];

interface ColorSchemeSelectorProps {
  value: ColorScheme;
  onChange: (scheme: ColorScheme) => void;
  idPrefix: string;
  label?: string;
}

export function ColorSchemeSelector({
  value,
  onChange,
  idPrefix,
  label = 'Theme',
}: ColorSchemeSelectorProps) {
  return (
    <SegmentedPreferenceSelector
      value={value}
      onChange={onChange}
      idPrefix={idPrefix}
      label={label}
      options={COLOR_SCHEME_OPTIONS}
    />
  );
}

interface ToggleSwitchProps {
  id: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: ReactNode;
  icon?: ReactNode;
}

export function ToggleSwitch({ id, checked, onChange, label, icon }: ToggleSwitchProps) {
  return (
    <label className="toggle-switch" htmlFor={id}>
      {icon ? <span className="toggle-switch-icon">{icon}</span> : null}
      <span className="toggle-switch-label">{label}</span>
      <input
        id={id}
        type="checkbox"
        className="toggle-switch-input"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span className="toggle-switch-track" aria-hidden="true">
        <span className="toggle-switch-thumb" />
      </span>
    </label>
  );
}

interface ReadOnlyFieldInputProps {
  id: string;
  label: string;
  value: unknown;
  multiline?: boolean;
  gridColumn?: string;
  fieldKey?: string;
  /**
   * When set (and the field has a value), renders the value as a link to the
   * referenced object's display view instead of a plain readonly input.
   */
  href?: string;
  /**
   * When true, the reference target no longer exists -- render muted text
   * instead of a link that would 404, even if `href` is set.
   */
  deleted?: boolean;
}

export function ReadOnlyFieldInput({
  id,
  label,
  value,
  multiline = false,
  gridColumn,
  fieldKey,
  href,
  deleted = false,
}: ReadOnlyFieldInputProps) {
  const { dateDisplayFormat } = useUserPreferences();
  const display = formatDetailValue(value, { fieldKey, dateDisplayFormat });
  const isEmpty = display === '—';

  return (
    <div className="form-group form-group--readonly" style={{ marginBottom: 0, gridColumn }}>
      <label htmlFor={id}>{label}</label>
      <div className="readonly-input-wrap">
        {deleted && !isEmpty ? (
          <span
            id={id}
            className="readonly-input-link readonly-input-link--deleted"
            title="This record has been deleted"
          >
            {display}
          </span>
        ) : href && !isEmpty ? (
          <Link id={id} to={href} className="readonly-input-link">
            {display}
          </Link>
        ) : multiline ? (
          <textarea id={id} readOnly className="readonly-input" rows={3} value={display} />
        ) : (
          <input id={id} readOnly className="readonly-input" type="text" value={display} />
        )}
        <span className="readonly-input-lock" aria-hidden="true">
          <LockIcon size={14} />
        </span>
      </div>
    </div>
  );
}

interface DetailFieldGroupProps {
  title?: ReactNode;
  dividerTop?: boolean;
  children: ReactNode;
  style?: React.CSSProperties;
}

export function DetailFieldGroup({ title, dividerTop, children, style }: DetailFieldGroupProps) {
  return (
    <div
      className={`detail-field-group${dividerTop ? ' detail-field-group--divider-top' : ''}`}
      style={style}
    >
      {title ? <h3 className="detail-field-group-title">{title}</h3> : null}
      <div className="detail-grid">{children}</div>
    </div>
  );
}
