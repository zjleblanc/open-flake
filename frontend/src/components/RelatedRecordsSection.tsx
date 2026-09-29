import { useState } from 'react';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { stateBadge, stateLabel } from '../api/client';
import type { DetailSectionAccent } from './DetailSection';
import { EmptyValue } from './EmptyValue';
import { ExpandableDetailSection } from './ExpandableDetailSection';
import { isEmptyDisplayValue } from '../utils/emptyDisplay';

export interface ReferenceTab {
  /** Unique key for the tab, e.g. `requested-items`. */
  key: string;
  /** Tab label, e.g. `Requested Items`. */
  label: string;
  /** Link prefix for records in this tab, e.g. `/requested-items`. */
  basePath: string;
  /** Resource slug of the related records (e.g. `change-tasks`), used to resolve state labels/badges correctly. */
  resource?: string;
  /** Human-readable type shown in the "Type" column (e.g. "Change Task", "Requested Item"). */
  typeLabel: string;
  records: Record<string, string>[];
  isLoading?: boolean;
  /** Message shown in place of the table when this tab has no records. */
  emptyMessage: string;
}

interface RelatedRecordsSectionProps {
  id: string;
  title?: string;
  icon: ReactNode;
  accent?: DetailSectionAccent;
  /** One tab per reference type. All tabs are always rendered, even when empty. */
  tabs: ReferenceTab[];
}

function recordLabel(record: Record<string, string>): string {
  return record.number || record.name || record.sys_id;
}

export function RelatedRecordsSection({
  id,
  title = 'References',
  icon,
  accent = 'accent',
  tabs,
}: RelatedRecordsSectionProps) {
  const [activeTabKey, setActiveTabKey] = useState(tabs[0]?.key);
  const activeTab = tabs.find((tab) => tab.key === activeTabKey) ?? tabs[0];

  const anyLoading = tabs.some((tab) => tab.isLoading);
  const totalCount = tabs.reduce((sum, tab) => sum + tab.records.length, 0);
  const isDisabled = !anyLoading && totalCount === 0;

  return (
    <ExpandableDetailSection
      id={id}
      title={title}
      icon={icon}
      accent={accent}
      count={anyLoading ? '…' : totalCount}
      className={isDisabled ? 'property-panel--disabled' : undefined}
      headerActions={
        isDisabled ? <span className="property-panel-disabled-note">No references</span> : undefined
      }
    >
      <div className="references-tabs" role="tablist" aria-label={`${title} type`}>
        {tabs.map((tab) => {
          const isActive = tab.key === activeTab?.key;
          const count = tab.isLoading ? undefined : tab.records.length;
          return (
            <button
              key={tab.key}
              type="button"
              role="tab"
              aria-selected={isActive}
              aria-controls={`${id}-tabpanel`}
              tabIndex={isActive ? 0 : -1}
              className={`references-tab${isActive ? ' references-tab--active' : ''}`}
              onClick={() => setActiveTabKey(tab.key)}
            >
              {tab.label}
              {count !== undefined && count > 0 ? (
                <span className="references-tab-count">{count}</span>
              ) : null}
            </button>
          );
        })}
      </div>

      {activeTab && (
        <div id={`${id}-tabpanel`} className="references-tab-panel" role="tabpanel">
          {activeTab.isLoading && <p className="empty-state">Loading…</p>}
          {!activeTab.isLoading && activeTab.records.length === 0 && (
            <p className="empty-state">{activeTab.emptyMessage}</p>
          )}
          {!activeTab.isLoading && activeTab.records.length > 0 && (
            <table>
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Name</th>
                  <th>State</th>
                </tr>
              </thead>
              <tbody>
                {activeTab.records.map((record) => (
                  <tr key={record.sys_id}>
                    <td>{activeTab.typeLabel}</td>
                    <td>
                      <Link to={`${activeTab.basePath}/${record.sys_id}`}>
                        {recordLabel(record)}
                      </Link>
                    </td>
                    <td>
                      {isEmptyDisplayValue(record.state) ? (
                        <EmptyValue />
                      ) : (
                        <span className={`badge ${stateBadge(record.state, activeTab.resource)}`}>
                          {stateLabel(record.state, activeTab.resource)}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </ExpandableDetailSection>
  );
}
