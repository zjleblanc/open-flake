import type { CatalogItemSummary } from '../api/client';

export const UNCATEGORIZED_ID = 'uncategorized';
export const UNCATEGORIZED_LABEL = 'Uncategorized';

/**
 * A browse node in the catalog category tree.
 *
 * Today this is built from item `category` / `subcategory` strings (two levels).
 * The same shape can represent a deeper hierarchy later — swap
 * `buildCatalogCategoryTree` to walk first-class category records with parent ids
 * without changing the landing-page renderer.
 */
export type CatalogCategoryNode = {
  id: string;
  label: string;
  items: CatalogItemSummary[];
  children: CatalogCategoryNode[];
};

function compareItems(a: CatalogItemSummary, b: CatalogItemSummary): number {
  const order = (a.order ?? 100) - (b.order ?? 100);
  if (order !== 0) return order;
  return a.name.localeCompare(b.name);
}

function compareLabels(a: string, b: string): number {
  return a.localeCompare(b);
}

export function countCatalogItems(node: CatalogCategoryNode): number {
  return (
    node.items.length + node.children.reduce((sum, child) => sum + countCatalogItems(child), 0)
  );
}

export function buildCatalogCategoryTree(items: CatalogItemSummary[]): CatalogCategoryNode[] {
  type Bucket = { items: CatalogItemSummary[]; subs: Map<string, CatalogItemSummary[]> };
  const buckets = new Map<string, Bucket>();

  for (const item of items) {
    const category = item.category?.trim() || '';
    const subcategory = item.subcategory?.trim() || '';
    const key = category || UNCATEGORIZED_LABEL;
    let bucket = buckets.get(key);
    if (!bucket) {
      bucket = { items: [], subs: new Map() };
      buckets.set(key, bucket);
    }
    if (category && subcategory) {
      const existing = bucket.subs.get(subcategory);
      if (existing) {
        existing.push(item);
      } else {
        bucket.subs.set(subcategory, [item]);
      }
    } else {
      bucket.items.push(item);
    }
  }

  function toNode(label: string, bucket: Bucket): CatalogCategoryNode {
    const isUncategorized = label === UNCATEGORIZED_LABEL;
    return {
      id: isUncategorized ? UNCATEGORIZED_ID : `category:${label}`,
      label,
      items: [...bucket.items].sort(compareItems),
      children: [...bucket.subs.entries()]
        .sort(([a], [b]) => compareLabels(a, b))
        .map(([subLabel, subItems]) => ({
          id: `category:${label}/${subLabel}`,
          label: subLabel,
          items: [...subItems].sort(compareItems),
          children: [],
        })),
    };
  }

  const categorized = [...buckets.entries()]
    .filter(([label]) => label !== UNCATEGORIZED_LABEL)
    .sort(([a], [b]) => compareLabels(a, b))
    .map(([label, bucket]) => toNode(label, bucket));

  const uncategorized = buckets.get(UNCATEGORIZED_LABEL);
  if (uncategorized) {
    categorized.push(toNode(UNCATEGORIZED_LABEL, uncategorized));
  }

  return categorized;
}
