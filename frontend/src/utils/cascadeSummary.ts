/** Shared helpers for turning a cascade-preview response into a plain-language
 * delete confirmation summary, used by both single-record and bulk deletes. */

export const PERIPHERAL_LABELS: Record<string, { singular: string; plural: string }> = {
  comments: { singular: 'comment', plural: 'comments' },
  audit_entries: { singular: 'audit entry', plural: 'audit entries' },
  access_grants: { singular: 'access grant', plural: 'access grants' },
  attachments: { singular: 'attachment', plural: 'attachments' },
};

export function joinWithAnd(parts: string[]): string {
  if (parts.length === 0) return '';
  if (parts.length === 1) return parts[0];
  if (parts.length === 2) return `${parts[0]} and ${parts[1]}`;
  return `${parts.slice(0, -1).join(', ')}, and ${parts[parts.length - 1]}`;
}

export function peripheralParts(peripheral: Record<string, number>): string[] {
  const parts: string[] = [];
  for (const [key, count] of Object.entries(peripheral)) {
    const labels = PERIPHERAL_LABELS[key];
    if (!labels || !count) continue;
    parts.push(`${count} ${count === 1 ? labels.singular : labels.plural}`);
  }
  return parts;
}

export function buildCascadeSummary(
  subject: string,
  cascadeParts: string[],
  peripheral: Record<string, number>,
  fallback: string,
): string {
  const parts = [...cascadeParts, ...peripheralParts(peripheral)];
  if (parts.length === 0) return fallback;
  return `${subject} will permanently delete ${joinWithAnd(parts)}. This action cannot be undone.`;
}
