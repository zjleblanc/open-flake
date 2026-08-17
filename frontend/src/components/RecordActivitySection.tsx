import { useQuery } from '@tanstack/react-query';
import { api, stateLabel, type ActivityChange, type ActivityEntry } from '../api/client';
import { useUserPreferences } from '../settings/UserPreferencesContext';
import { formatDateValue } from '../utils/formatDisplayValue';
import { ActivityIcon } from './DetailIcons';
import { ExpandableDetailSection } from './ExpandableDetailSection';
import { JournalFieldRenderer } from './JournalFieldRenderer';

interface RecordActivitySectionProps {
  resource: string;
  sysId: string;
  sectionId?: string;
  /** Known field key -> human label overrides; falls back to a humanized snake_case key. */
  fieldLabels?: Record<string, string>;
}

function humanizeFieldName(key: string): string {
  return key
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function fieldLabel(key: string, fieldLabels?: Record<string, string>): string {
  return fieldLabels?.[key] || humanizeFieldName(key);
}

function changeValueLabel(field: string, value: string, resource: string): string {
  if (!value) return '—';
  if (field === 'state') return stateLabel(value, resource);
  return value;
}

function ActivityChangeRow({
  change,
  resource,
  fieldLabels,
}: {
  change: ActivityChange;
  resource: string;
  fieldLabels?: Record<string, string>;
}) {
  return (
    <li className="activity-feed-change">
      <span className="activity-feed-change-field">{fieldLabel(change.field, fieldLabels)}</span>
      <span className="activity-feed-change-values">
        <span className="activity-feed-change-old">
          {changeValueLabel(change.field, change.old_value, resource)}
        </span>
        <span className="activity-feed-change-arrow" aria-hidden="true">
          →
        </span>
        <span className="activity-feed-change-new">
          {changeValueLabel(change.field, change.new_value, resource)}
        </span>
      </span>
    </li>
  );
}

function ActivityEntryItem({
  entry,
  resource,
  fieldLabels,
  dateDisplayFormat,
}: {
  entry: ActivityEntry;
  resource: string;
  fieldLabels?: Record<string, string>;
  dateDisplayFormat: Parameters<typeof formatDateValue>[1];
}) {
  return (
    <li className="activity-feed-item">
      <div className="activity-feed-item-header">
        <span className="activity-feed-item-user">{entry.user || 'System'}</span>
        <span className="activity-feed-item-time text-muted text-sm">
          {entry.timestamp ? formatDateValue(entry.timestamp, dateDisplayFormat) : ''}
        </span>
      </div>
      {entry.type === 'created' && <p className="activity-feed-item-body">Record created</p>}
      {entry.type === 'comment' && (
        <div className="activity-feed-item-body">
          <JournalFieldRenderer content={entry.comment ?? ''} />
        </div>
      )}
      {entry.type === 'update' && (
        <ul className="activity-feed-changes">
          {(entry.changes ?? []).map((change, idx) => (
            <ActivityChangeRow
              key={`${change.field}-${idx}`}
              change={change}
              resource={resource}
              fieldLabels={fieldLabels}
            />
          ))}
        </ul>
      )}
    </li>
  );
}

export function RecordActivitySection({
  resource,
  sysId,
  sectionId = 'record-section-activity',
  fieldLabels,
}: RecordActivitySectionProps) {
  const { dateDisplayFormat } = useUserPreferences();

  const { data, isLoading } = useQuery({
    queryKey: ['activity', resource, sysId],
    queryFn: () => api.listActivity(resource, sysId),
  });

  const activity = data?.activity ?? [];

  return (
    <ExpandableDetailSection
      id={sectionId}
      title="Activity"
      icon={<ActivityIcon size={14} />}
      accent="primary"
      count={isLoading ? '…' : activity.length}
    >
      {isLoading && <p className="empty-state">Loading activity…</p>}
      {!isLoading && activity.length === 0 && <p className="empty-state">No activity yet</p>}
      {!isLoading && activity.length > 0 && (
        <ul className="activity-feed-list">
          {activity.map((entry) => (
            <ActivityEntryItem
              key={entry.id}
              entry={entry}
              resource={resource}
              fieldLabels={fieldLabels}
              dateDisplayFormat={dateDisplayFormat}
            />
          ))}
        </ul>
      )}
    </ExpandableDetailSection>
  );
}
