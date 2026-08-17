/** Shared helpers for turning a cascade-preview response into the
 * structured "Permanently deleted" / "Referenced by" sections shown in the
 * delete confirmation dialog, used by both single-record and bulk deletes. */
import type { CascadeChildPreview, CascadePreview, LooseReferenceRecord } from '../api/client';

export const PERIPHERAL_LABELS: Record<string, { singular: string; plural: string }> = {
  comments: { singular: 'comment', plural: 'comments' },
  audit_entries: { singular: 'audit entry', plural: 'audit entries' },
  access_grants: { singular: 'access grant', plural: 'access grants' },
  attachments: { singular: 'attachment', plural: 'attachments' },
};

/** One row in the "Permanently deleted" section: a group of cascaded child
 * records (with a sample to display), or a plain peripheral-data count. */
export type PermanentItem = {
  key: string;
  table: string;
  label: string;
  count: number;
  records: LooseReferenceRecord[];
};

function peripheralItems(peripheral: Record<string, number>): PermanentItem[] {
  const items: PermanentItem[] = [];
  for (const [key, count] of Object.entries(peripheral)) {
    const labels = PERIPHERAL_LABELS[key];
    if (!labels || !count) continue;
    items.push({
      key: `peripheral-${key}`,
      table: 'peripheral',
      label: count === 1 ? labels.singular : labels.plural,
      count,
      records: [],
    });
  }
  return items;
}

export function buildPermanentItems(
  cascadeChildren: CascadeChildPreview[],
  peripheral: Record<string, number>,
): PermanentItem[] {
  return [
    ...cascadeChildren.map((child) => ({
      key: child.table,
      table: child.table,
      label: child.label,
      count: child.count,
      records: child.records,
    })),
    ...peripheralItems(peripheral),
  ];
}

/** Aggregate permanent-deletion counts across several previews (bulk delete),
 * without per-record samples since they'd span multiple base records. */
export function aggregatePermanentItems(previews: CascadePreview[]): PermanentItem[] {
  const cascadeTotals = new Map<string, { label: string; count: number }>();
  const peripheralTotals: Record<string, number> = {};
  for (const preview of previews) {
    for (const child of preview.cascade_children) {
      const current = cascadeTotals.get(child.table) ?? { label: child.label, count: 0 };
      current.count += child.count;
      cascadeTotals.set(child.table, current);
    }
    for (const [key, count] of Object.entries(preview.peripheral)) {
      peripheralTotals[key] = (peripheralTotals[key] ?? 0) + count;
    }
  }
  return [
    ...[...cascadeTotals.entries()].map(([table, entry]) => ({
      key: table,
      table,
      label: entry.label,
      count: entry.count,
      records: [],
    })),
    ...peripheralItems(peripheralTotals),
  ];
}

export function permanentTotal(items: PermanentItem[]): number {
  return items.reduce((sum, item) => sum + item.count, 0);
}
