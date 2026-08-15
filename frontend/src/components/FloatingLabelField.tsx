import { useState, type ChangeEvent, type ReactNode } from 'react';
import { FieldTooltip } from './FieldTooltip';

interface FloatingLabelFieldProps {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  multiline?: boolean;
  rows?: number;
  disabled?: boolean;
  readOnly?: boolean;
  required?: boolean;
  tooltip?: ReactNode;
  tooltipAriaLabel?: string;
  autoComplete?: string;
  className?: string;
}

/**
 * Opt-in alternative to the standard `.form-group` + `<label>` pattern: the
 * label rests inside the control like a placeholder when empty/unfocused,
 * then floats up to sit centered on the top border, left-aligned, when the
 * field is focused or has a value. Not required app-wide -- use it per field
 * where the floating style is wanted.
 */
export function FloatingLabelField({
  id,
  label,
  value,
  onChange,
  type = 'text',
  multiline = false,
  rows = 3,
  disabled = false,
  readOnly = false,
  required = false,
  tooltip,
  tooltipAriaLabel,
  autoComplete,
  className,
}: FloatingLabelFieldProps) {
  const [isFocused, setIsFocused] = useState(false);
  const isActive = isFocused || value.length > 0;

  function handleChange(event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) {
    onChange(event.target.value);
  }

  const wrapperClassName = [
    'floating-field',
    isActive ? 'floating-field--active' : '',
    multiline ? 'floating-field--multiline' : '',
    disabled ? 'floating-field--disabled' : '',
    className || '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={wrapperClassName}>
      {multiline ? (
        <textarea
          id={id}
          rows={rows}
          value={value}
          disabled={disabled}
          readOnly={readOnly}
          onChange={handleChange}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
        />
      ) : (
        <input
          id={id}
          type={type}
          value={value}
          disabled={disabled}
          readOnly={readOnly}
          autoComplete={autoComplete}
          onChange={handleChange}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
        />
      )}
      <span className="floating-field-label">
        <label htmlFor={id}>
          {label}
          {required ? ' *' : ''}
        </label>
        {tooltip ? (
          <FieldTooltip ariaLabel={tooltipAriaLabel ?? `${label} info`}>{tooltip}</FieldTooltip>
        ) : null}
      </span>
    </div>
  );
}
