import type { ReactNode } from 'react';
import type { DetailSectionAccent } from './DetailSection';

interface ExpandableDetailSectionProps {
  id?: string;
  title: string;
  icon: ReactNode;
  accent?: DetailSectionAccent;
  defaultOpen?: boolean;
  count?: ReactNode;
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
      </summary>
      <div className="property-panel-body">{children}</div>
    </details>
  );
}
