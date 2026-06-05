import type { ReactNode } from "react";
import { LockIcon } from "./DetailIcons";

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

export function formatDetailValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "object") {
    const ref = value as { value?: string; link?: string };
    if (ref.value) return ref.value;
    return JSON.stringify(value, null, 2);
  }
  return String(value);
}

interface ReadOnlyFieldInputProps {
  id: string;
  label: string;
  value: unknown;
  multiline?: boolean;
  gridColumn?: string;
}

export function ReadOnlyFieldInput({
  id,
  label,
  value,
  multiline = false,
  gridColumn,
}: ReadOnlyFieldInputProps) {
  const display = formatDetailValue(value);

  return (
    <div
      className="form-group form-group--readonly"
      style={{ marginBottom: 0, gridColumn }}
    >
      <label htmlFor={id}>{label}</label>
      <div className="readonly-input-wrap">
        {multiline ? (
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
      className={`detail-field-group${dividerTop ? " detail-field-group--divider-top" : ""}`}
      style={style}
    >
      {title ? <h3 className="detail-field-group-title">{title}</h3> : null}
      <div className="detail-grid">{children}</div>
    </div>
  );
}

export function refSysId(field: unknown): string {
  if (!field) return "";
  if (typeof field === "object" && field !== null && "value" in field) {
    return String((field as { value: string }).value);
  }
  return String(field);
}

export function resolveUserLabel(field: unknown, userLabels: Record<string, string>): string {
  const sysId = refSysId(field);
  if (!sysId) return "—";
  return userLabels[sysId] || sysId;
}
