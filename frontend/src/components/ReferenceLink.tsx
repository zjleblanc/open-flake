import { Link } from 'react-router-dom';
import { EmptyValue } from './EmptyValue';
import {
  isReferenceDeleted,
  referenceDisplayValue,
  referenceHref,
  refSysId,
  type RefTarget,
} from '../utils/referenceFields';

interface ReferenceLinkProps {
  /** Raw field value: a sys_id string, or a `{ value }` reference object. */
  value: unknown;
  /** The record the field lives on, used to look up `<field>_display_value`. */
  record?: Record<string, unknown> | null;
  /** The field key on `record` (required when `record` is provided). */
  field?: string;
  /** What kind of record this reference points to, to build the link target. */
  target: RefTarget;
  className?: string;
}

/**
 * Renders a resolved reference field (e.g. a group's owner) as a link to that
 * object's display view, using the label the API resolved via
 * `<field>_display_value` rather than the raw sys_id.
 */
export function ReferenceLink({ value, record, field, target, className }: ReferenceLinkProps) {
  const sysId = refSysId(value);
  if (!sysId) return <EmptyValue />;
  const label = record && field ? referenceDisplayValue(record, field) : sysId;
  if (record && field && isReferenceDeleted(record, field)) {
    return (
      <span className="reference-link reference-link--deleted" title="This record has been deleted">
        {label}
      </span>
    );
  }
  return (
    <Link to={referenceHref(target, sysId)} className={className ?? 'reference-link'}>
      {label}
    </Link>
  );
}
