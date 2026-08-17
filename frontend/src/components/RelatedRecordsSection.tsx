import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { stateBadge, stateLabel } from '../api/client';
import type { DetailSectionAccent } from './DetailSection';
import { EmptyValue } from './EmptyValue';
import { ExpandableDetailSection } from './ExpandableDetailSection';
import { isEmptyDisplayValue } from '../utils/emptyDisplay';

interface RelatedRecordsSectionProps {
  id: string;
  title: string;
  icon: ReactNode;
  accent?: DetailSectionAccent;
  basePath: string;
  /** Resource slug of the related records (e.g. `change-tasks`), used to resolve state labels/badges correctly. */
  resource?: string;
  records: Record<string, string>[];
  isLoading?: boolean;
  emptyMessage: string;
}

function recordLabel(record: Record<string, string>): string {
  return record.number || record.name || record.sys_id;
}

export function RelatedRecordsSection({
  id,
  title,
  icon,
  accent = 'accent',
  basePath,
  resource,
  records,
  isLoading,
  emptyMessage,
}: RelatedRecordsSectionProps) {
  return (
    <ExpandableDetailSection
      id={id}
      title={title}
      icon={icon}
      accent={accent}
      count={isLoading ? '…' : records.length}
    >
      {isLoading && <p className="empty-state">Loading…</p>}
      {!isLoading && records.length === 0 && <p className="empty-state">{emptyMessage}</p>}
      {!isLoading && records.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Number</th>
              <th>Short Description</th>
              <th>State</th>
            </tr>
          </thead>
          <tbody>
            {records.map((record) => (
              <tr key={record.sys_id}>
                <td>
                  <Link to={`${basePath}/${record.sys_id}`}>{recordLabel(record)}</Link>
                </td>
                <td>{record.short_description ? record.short_description : <EmptyValue />}</td>
                <td>
                  {isEmptyDisplayValue(record.state) ? (
                    <EmptyValue />
                  ) : (
                    <span className={`badge ${stateBadge(record.state, resource)}`}>
                      {stateLabel(record.state, resource)}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </ExpandableDetailSection>
  );
}
