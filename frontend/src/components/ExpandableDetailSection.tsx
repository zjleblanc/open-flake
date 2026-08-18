import type { ReactNode } from 'react';
import type { DetailSectionAccent } from './DetailSection';
import { ChevronDownIcon, ChevronUpIcon } from './DetailIcons';

interface ExpandableDetailSectionProps {
  id?: string;
  title: string;
  icon: ReactNode;
  accent?: DetailSectionAccent;
  defaultOpen?: boolean;
  count?: ReactNode;
  headerActions?: ReactNode;
  children: ReactNode;
  className?: string;
}

export function ExpandableDetailSection({
  id,
  title,
  icon,
  accent = 'accent',
  defaultOpen = false,
  count,
  headerActions,
  children,
  className,
}: ExpandableDetailSectionProps) {
  return (
    <details
      id={id}
      className={`property-panel property-panel--${accent}${className ? ` ${className}` : ''}`}
      open={defaultOpen || undefined}
    >
      <summary>
        <span className="property-panel-summary-icon">{icon}</span>
        {title}
        {count !== undefined && count !== null ? (
          <span className="property-panel-count">{count}</span>
        ) : null}
        <span className="property-panel-summary-spacer" />
        {headerActions ? (
          // Clicking header actions must not toggle the <details> element; preventDefault on
          // the bubbled click stops the browser's native summary activation behavior.
          <span
            className="property-panel-header-actions"
            onClick={(event) => event.preventDefault()}
          >
            {headerActions}
          </span>
        ) : null}
        <span className="property-panel-toggle-icon property-panel-toggle-icon--collapsed">
          <ChevronDownIcon size={14} />
        </span>
        <span className="property-panel-toggle-icon property-panel-toggle-icon--expanded">
          <ChevronUpIcon size={14} />
        </span>
      </summary>
      <div className="property-panel-body">{children}</div>
    </details>
  );
}

interface NestedCollapsibleSectionProps {
  id?: string;
  title: string;
  defaultOpen?: boolean;
  count?: ReactNode;
  children: ReactNode;
}

/**
 * A lightweight collapsible block used *inside* an `ExpandableDetailSection`
 * (e.g. "Additional Properties" nested within "General"), separated from the
 * rest of the section body by an `<hr>`. Unlike `ExpandableDetailSection`,
 * this has no accent border/background — it's a subsection, not a page-level
 * panel.
 */
export function NestedCollapsibleSection({
  id,
  title,
  defaultOpen = false,
  count,
  children,
}: NestedCollapsibleSectionProps) {
  return (
    <>
      <hr className="detail-subsection-divider" />
      <details id={id} className="nested-collapsible" open={defaultOpen || undefined}>
        <summary>
          {title}
          {count !== undefined && count !== null ? (
            <span className="nested-collapsible-count">{count}</span>
          ) : null}
          <span className="nested-collapsible-spacer" />
          <span className="nested-collapsible-toggle-icon nested-collapsible-toggle-icon--collapsed">
            <ChevronDownIcon size={14} />
          </span>
          <span className="nested-collapsible-toggle-icon nested-collapsible-toggle-icon--expanded">
            <ChevronUpIcon size={14} />
          </span>
        </summary>
        <div className="nested-collapsible-body">{children}</div>
      </details>
    </>
  );
}
