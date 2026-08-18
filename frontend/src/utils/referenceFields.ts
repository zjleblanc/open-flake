export function refSysId(field: unknown): string {
  if (!field) return '';
  if (typeof field === 'object' && field !== null && 'value' in field) {
    return String((field as { value: string }).value);
  }
  return String(field);
}

/**
 * The kinds of records a reference field can point to, each backed by its own
 * detail/display view. Used to build a link for a resolved reference value.
 */
export type RefTarget =
  | 'user'
  | 'group'
  | 'cmdb_ci'
  | 'incident'
  | 'problem'
  | 'change_request'
  | 'sc_request'
  | 'sc_req_item'
  | 'sc_cat_item'
  | 'sc_task';

const REF_TARGET_BASE_PATH: Record<RefTarget, string> = {
  user: '/access/users',
  group: '/access/groups',
  cmdb_ci: '/configuration-items',
  incident: '/incidents',
  problem: '/problems',
  change_request: '/changes',
  sc_request: '/requests',
  sc_req_item: '/requested-items',
  sc_cat_item: '/catalog',
  sc_task: '/catalog-tasks',
};

/** Build the frontend route to a reference target's display view. */
export function referenceHref(target: RefTarget, sysId: string): string {
  return `${REF_TARGET_BASE_PATH[target]}/${sysId}`;
}

/**
 * Resolve the human-readable label for a reference field on a record.
 *
 * The API attaches a `<field>_display_value` sibling key (see
 * `attach_reference_display_values` on the backend) alongside the raw sys_id
 * field. Falls back to the sys_id itself if no label was resolved.
 */
export function referenceDisplayValue(
  record: Record<string, unknown> | undefined | null,
  field: string,
): string {
  if (!record) return '';
  const displayValue = record[`${field}_display_value`];
  if (typeof displayValue === 'string' && displayValue) return displayValue;
  return refSysId(record[field]);
}

/**
 * True when a reference field's target row no longer exists (see the
 * `<field>_deleted` flag set by `attach_reference_display_values` on the
 * backend). Used to render a dangling reference as muted text instead of a
 * link to a page that would 404.
 */
export function isReferenceDeleted(
  record: Record<string, unknown> | undefined | null,
  field: string,
): boolean {
  if (!record) return false;
  return record[`${field}_deleted`] === true;
}
