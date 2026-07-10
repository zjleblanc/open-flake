export function refSysId(field: unknown): string {
  if (!field) return '';
  if (typeof field === 'object' && field !== null && 'value' in field) {
    return String((field as { value: string }).value);
  }
  return String(field);
}

export function resolveUserLabel(field: unknown, userLabels: Record<string, string>): string {
  const sysId = refSysId(field);
  if (!sysId) return '—';
  return userLabels[sysId] || sysId;
}
