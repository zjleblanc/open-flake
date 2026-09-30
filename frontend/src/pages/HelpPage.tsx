import { useMemo } from 'react';
import { STATE_LABELS, TABLE_STATE_LABELS } from '../api/client';
import { DetailSectionNav, type DetailSectionNavItem } from '../components/DetailSectionNav';
import { ExpandableDetailSection } from '../components/ExpandableDetailSection';
import { FieldsIcon, OverviewIcon, SystemIcon } from '../components/DetailIcons';
import { CatalogIcon, IntegrationsIcon, SettingsIcon } from '../components/NavIcons';
import { MarkdownRenderer } from '../components/MarkdownRenderer';
import { usePageHeader } from '../components/PageHeaderContext';
import '../components/Layout.css';
import './CatalogPages.css';
import {
  BUILDING_PROCESSES_CONTENT,
  CONFIGURING_CONTENT,
  DEVELOPER_REFERENCE_CONTENT,
  INTEGRATING_CONTENT,
  OVERVIEW_CONTENT,
} from './helpContent';

const HELP_BREADCRUMBS = [{ label: 'Help' }];

const SECTION = {
  overview: 'help-section-overview',
  configuring: 'help-section-configuring',
  integrating: 'help-section-integrating',
  building: 'help-section-building',
  fields: 'help-section-fields',
  developer: 'help-section-developer',
} as const;

const SECTION_NAV_ITEMS: DetailSectionNavItem[] = [
  {
    id: SECTION.overview,
    title: 'Overview',
    icon: <OverviewIcon size={14} />,
    accent: 'primary',
  },
  {
    id: SECTION.configuring,
    title: 'Configuring',
    icon: <SettingsIcon size={14} />,
    accent: 'accent',
  },
  {
    id: SECTION.integrating,
    title: 'Integrating',
    icon: <IntegrationsIcon size={14} />,
    accent: 'info',
  },
  {
    id: SECTION.building,
    title: 'Building Processes',
    icon: <CatalogIcon size={14} />,
    accent: 'success',
  },
  {
    id: SECTION.fields,
    title: 'Field Reference',
    icon: <FieldsIcon size={14} />,
    accent: 'primary',
  },
  {
    id: SECTION.developer,
    title: 'Developer Reference',
    icon: <SystemIcon size={14} />,
    accent: 'accent',
  },
];

/** Human-friendly labels for the resource slugs that key `TABLE_STATE_LABELS`. */
const STATE_TABLE_RESOURCE_LABELS: Record<string, string> = {
  'change-requests': 'Changes',
  'change-tasks': 'Change Tasks',
  'problem-tasks': 'Problem Tasks',
};

function StateCodeTable({ title, labels }: { title: string; labels: Record<string, string> }) {
  const rows = useMemo(
    () => Object.entries(labels).sort(([a], [b]) => Number(a) - Number(b)),
    [labels],
  );
  return (
    <div className="markdown-body">
      <h4>{title}</h4>
      <table>
        <thead>
          <tr>
            <th>Code</th>
            <th>Label</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([code, label]) => (
            <tr key={code}>
              <td>
                <code>{code}</code>
              </td>
              <td>{label}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * Static help/reference page — the in-app "interactive readme" for configuring,
 * integrating with, and building processes on OpenFlake. Uses the same detail-page
 * chrome (`detail-page-layout` + `ExpandableDetailSection` + `DetailSectionNav`) as
 * record detail pages so navigation feels consistent, even though there's no record
 * being fetched here. See `helpContent.ts` for the prose and `frontend/AGENTS.md` for
 * the detail-page layout convention this mirrors.
 */
export function HelpPage() {
  usePageHeader({ breadcrumbs: HELP_BREADCRUMBS });

  return (
    <div className="detail-page-layout">
      <div className="detail-page-main">
        <div className="detail-sections-stack">
          <ExpandableDetailSection
            id={SECTION.overview}
            title="Overview"
            icon={<OverviewIcon size={14} />}
            accent="primary"
            defaultOpen
          >
            <MarkdownRenderer content={OVERVIEW_CONTENT} />
          </ExpandableDetailSection>

          <ExpandableDetailSection
            id={SECTION.configuring}
            title="Configuring OpenFlake"
            icon={<SettingsIcon size={14} />}
            accent="accent"
          >
            <MarkdownRenderer content={CONFIGURING_CONTENT} />
          </ExpandableDetailSection>

          <ExpandableDetailSection
            id={SECTION.integrating}
            title="Integrating with OpenFlake"
            icon={<IntegrationsIcon size={14} />}
            accent="info"
          >
            <MarkdownRenderer content={INTEGRATING_CONTENT} />
          </ExpandableDetailSection>

          <ExpandableDetailSection
            id={SECTION.building}
            title="Building Processes"
            icon={<CatalogIcon size={14} />}
            accent="success"
          >
            <MarkdownRenderer content={BUILDING_PROCESSES_CONTENT} />
          </ExpandableDetailSection>

          <ExpandableDetailSection
            id={SECTION.fields}
            title="Field Reference: State Codes"
            icon={<FieldsIcon size={14} />}
            accent="primary"
          >
            <p>
              The <code>state</code> field stores an integer whose meaning depends on the table —
              the same code can mean different things on different tables, so always resolve it
              through the mapping for that specific resource rather than assuming it matches another
              table. In the app, this is exactly what <code>stateLabel()</code> /{' '}
              <code>stateOptionsFor()</code> / <code>stateBadge()</code> (in{' '}
              <code>src/api/client.ts</code>) do — the tables below are generated directly from
              those same mappings.
            </p>
            <StateCodeTable
              title="Generic (default) — Incidents, Problems, and any table without an override"
              labels={STATE_LABELS}
            />
            {Object.entries(TABLE_STATE_LABELS).map(([resource, labels]) => (
              <StateCodeTable
                key={resource}
                title={STATE_TABLE_RESOURCE_LABELS[resource] ?? resource}
                labels={labels}
              />
            ))}
          </ExpandableDetailSection>

          <ExpandableDetailSection
            id={SECTION.developer}
            title="Developer Reference"
            icon={<SystemIcon size={14} />}
            accent="accent"
          >
            <MarkdownRenderer content={DEVELOPER_REFERENCE_CONTENT} />
          </ExpandableDetailSection>
        </div>
      </div>
      <DetailSectionNav sections={SECTION_NAV_ITEMS} />
    </div>
  );
}
