import type { DateDisplayFormat } from "../settings/userPreferences";

const DATE_FIELD_KEY_PATTERN = /_(on|at|date|time)$/;

export function isDateFieldKey(fieldKey?: string): boolean {
  if (!fieldKey) return false;
  return DATE_FIELD_KEY_PATTERN.test(fieldKey);
}

export function formatDateValue(value: unknown, format: DateDisplayFormat): string {
  if (value === null || value === undefined || value === "") return "—";
  const raw = String(value);
  if (format === "raw") return raw;

  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return raw;
  return date.toLocaleString();
}

export function formatDetailValue(
  value: unknown,
  options?: { fieldKey?: string; dateDisplayFormat?: DateDisplayFormat }
): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "object") {
    const ref = value as { value?: string; link?: string };
    if (ref.value) return ref.value;
    return JSON.stringify(value, null, 2);
  }

  const raw = String(value);
  const dateDisplayFormat = options?.dateDisplayFormat ?? "raw";
  if (isDateFieldKey(options?.fieldKey) && dateDisplayFormat === "local") {
    return formatDateValue(raw, "local");
  }
  return raw;
}
