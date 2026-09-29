import { Navigate, Route, Routes, useParams } from 'react-router-dom';
import { Layout } from './components/Layout';
import { getToken } from './api/client';
import { AdminTablesPage } from './pages/AdminTablesPage';
import { CatalogBrowsePage } from './pages/CatalogBrowsePage';
import { CatalogItemBuilderPage } from './pages/CatalogItemBuilderPage';
import { CatalogItemPage } from './pages/CatalogItemPage';
import { CatalogTaskDetailPage } from './pages/CatalogTaskDetailPage';
import { CatalogWebhooksPage } from './pages/CatalogWebhooksPage';
import { WebhookDetailPage } from './pages/WebhookDetailPage';
import { CatalogSecretsPage } from './pages/CatalogSecretsPage';
import { SecretDetailPage } from './pages/SecretDetailPage';
import { ChangeDetailPage } from './pages/ChangeDetailPage';
import { ChangeTaskDetailPage } from './pages/ChangeTaskDetailPage';
import { ConfigurationItemDetailPage } from './pages/ConfigurationItemDetailPage';
import { DashboardPage } from './pages/DashboardPage';
import { GroupDetailPage } from './pages/GroupDetailPage';
import { GroupsListPage } from './pages/GroupsListPage';
import { LoginPage } from './pages/LoginPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { RecordDetailPage } from './pages/RecordDetailPage';
import { RecordListPage, type ListColumn } from './pages/RecordListPage';
import { RequestDetailPage } from './pages/RequestDetailPage';
import { RequestedItemDetailPage } from './pages/RequestedItemDetailPage';
import { SettingsPage } from './pages/SettingsPage';
import { UserDetailPage } from './pages/UserDetailPage';
import { UsersPage } from './pages/UsersPage';

const INCIDENT_FIELDS = [
  { key: 'short_description', label: 'Short Description' },
  { key: 'description', label: 'Description', type: 'textarea' },
  { key: 'impact', label: 'Impact (1=High, 2=Medium, 3=Low)' },
  { key: 'urgency', label: 'Urgency (1=High, 2=Medium, 3=Low)' },
];

const INCIDENT_DETAIL_FIELDS = [
  { key: 'short_description', label: 'Short Description' },
  { key: 'description', label: 'Description', type: 'textarea' },
  { key: 'state', label: 'State', type: 'select-state' },
  { key: 'priority', label: 'Priority', readOnly: true },
];

const PROBLEM_DETAIL_FIELDS = [
  { key: 'short_description', label: 'Short Description' },
  { key: 'description', label: 'Description', type: 'textarea' },
  { key: 'state', label: 'State', type: 'select-state' },
  { key: 'priority', label: 'Priority', readOnly: true },
];

// Every column a user may choose to display for a resource's list view, offered through the
// column-config popover (see `ColumnConfigPopover` / `RecordListPage`'s `allColumns` prop). The
// first entry is the pinned link column and must match the resource's default `columns` (or
// `RecordListPage`'s built-in `DEFAULT_COLUMNS`) so the saved column list lines up with what's
// shown before any customization. Reference-field columns (assigned_to, cmdb_ci, etc.) are
// resolved to a name + link by `RecordListPage`'s `REFERENCE_COLUMN_TARGETS` map rather than
// showing a raw sys_id.
const ALL_INCIDENT_COLUMNS: ListColumn[] = [
  { key: 'number', label: 'Number', filterKeys: ['number', 'name'] },
  { key: 'short_description', label: 'Short Description' },
  { key: 'state', label: 'State' },
  { key: 'priority', label: 'Priority' },
  { key: 'impact', label: 'Impact' },
  { key: 'urgency', label: 'Urgency' },
  { key: 'category', label: 'Category' },
  { key: 'subcategory', label: 'Subcategory' },
  { key: 'assigned_to', label: 'Assigned To', sortable: false },
  { key: 'assignment_group', label: 'Assignment Group', sortable: false },
  { key: 'caller_id', label: 'Caller', sortable: false },
  { key: 'cmdb_ci', label: 'Configuration Item', sortable: false },
  { key: 'opened_at', label: 'Opened' },
  { key: 'resolved_at', label: 'Resolved' },
  { key: 'closed_at', label: 'Closed' },
  { key: 'active', label: 'Active' },
];

const ALL_PROBLEM_COLUMNS: ListColumn[] = [
  { key: 'number', label: 'Number', filterKeys: ['number', 'name'] },
  { key: 'short_description', label: 'Short Description' },
  { key: 'state', label: 'State' },
  { key: 'priority', label: 'Priority' },
  { key: 'impact', label: 'Impact' },
  { key: 'urgency', label: 'Urgency' },
  { key: 'category', label: 'Category' },
  { key: 'subcategory', label: 'Subcategory' },
  { key: 'assigned_to', label: 'Assigned To', sortable: false },
  { key: 'assignment_group', label: 'Assignment Group', sortable: false },
  { key: 'cmdb_ci', label: 'Configuration Item', sortable: false },
  { key: 'resolution_code', label: 'Resolution Code' },
  { key: 'opened_at', label: 'Opened' },
  { key: 'resolved_at', label: 'Resolved' },
  { key: 'closed_at', label: 'Closed' },
  { key: 'active', label: 'Active' },
];

const ALL_CHANGE_COLUMNS: ListColumn[] = [
  { key: 'number', label: 'Number', filterKeys: ['number', 'name'] },
  { key: 'short_description', label: 'Short Description' },
  { key: 'state', label: 'State' },
  { key: 'priority', label: 'Priority' },
  { key: 'type', label: 'Type' },
  { key: 'risk', label: 'Risk' },
  { key: 'impact', label: 'Impact' },
  { key: 'urgency', label: 'Urgency' },
  { key: 'category', label: 'Category' },
  { key: 'assigned_to', label: 'Assigned To', sortable: false },
  { key: 'assignment_group', label: 'Assignment Group', sortable: false },
  { key: 'requested_by', label: 'Requested By', sortable: false },
  { key: 'cmdb_ci', label: 'Configuration Item', sortable: false },
  { key: 'start_date', label: 'Start Date' },
  { key: 'end_date', label: 'End Date' },
  { key: 'approval', label: 'Approval' },
  { key: 'active', label: 'Active' },
];

const ALL_CHANGE_TASK_COLUMNS: ListColumn[] = [
  { key: 'number', label: 'Number', filterKeys: ['number', 'name'] },
  { key: 'short_description', label: 'Short Description' },
  { key: 'state', label: 'State' },
  { key: 'priority', label: 'Priority' },
  { key: 'change_task_type', label: 'Type' },
  { key: 'impact', label: 'Impact' },
  { key: 'urgency', label: 'Urgency' },
  { key: 'assigned_to', label: 'Assigned To', sortable: false },
  { key: 'assignment_group', label: 'Assignment Group', sortable: false },
  { key: 'cmdb_ci', label: 'Configuration Item', sortable: false },
  { key: 'planned_start_date', label: 'Planned Start' },
  { key: 'planned_end_date', label: 'Planned End' },
  { key: 'active', label: 'Active' },
];

const ALL_CI_COLUMNS: ListColumn[] = [
  { key: 'number', label: 'Name', filterKeys: ['number', 'name'], sortField: 'name' },
  { key: 'short_description', label: 'Short Description' },
  { key: 'sys_class_name', label: 'Class' },
  { key: 'install_status', label: 'Install Status' },
  { key: 'operational_status', label: 'Operational Status' },
  { key: 'category', label: 'Category' },
  { key: 'environment', label: 'Environment' },
  { key: 'classification', label: 'Classification' },
  { key: 'vendor', label: 'Vendor' },
  { key: 'os', label: 'Operating System' },
  { key: 'os_version', label: 'OS Version' },
  { key: 'ip_address', label: 'IP Address' },
  { key: 'asset_tag', label: 'Asset Tag' },
  { key: 'serial_number', label: 'Serial Number' },
  { key: 'assigned_to', label: 'Assigned To', sortable: false },
];

const ALL_CATALOG_REQUEST_COLUMNS: ListColumn[] = [
  { key: 'number', label: 'Number', filterKeys: ['number', 'name'] },
  { key: 'short_description', label: 'Short Description' },
  { key: 'state', label: 'State' },
  { key: 'priority', label: 'Priority' },
  { key: 'stage', label: 'Stage' },
  { key: 'urgency', label: 'Urgency' },
  { key: 'impact', label: 'Impact' },
  { key: 'requested_for', label: 'Requested For', sortable: false },
  { key: 'requested_by', label: 'Requested By', sortable: false },
  { key: 'assigned_to', label: 'Assigned To', sortable: false },
  { key: 'assignment_group', label: 'Assignment Group', sortable: false },
  { key: 'category', label: 'Category' },
  { key: 'approval', label: 'Approval' },
  { key: 'active', label: 'Active' },
];

const ALL_CATALOG_REQUEST_ITEM_COLUMNS: ListColumn[] = [
  { key: 'number', label: 'Number', filterKeys: ['number', 'name'] },
  { key: 'short_description', label: 'Short Description' },
  { key: 'state', label: 'State' },
  { key: 'priority', label: 'Priority' },
  { key: 'stage', label: 'Stage' },
  { key: 'urgency', label: 'Urgency' },
  { key: 'impact', label: 'Impact' },
  { key: 'quantity', label: 'Quantity' },
  { key: 'requested_for', label: 'Requested For', sortable: false },
  { key: 'assigned_to', label: 'Assigned To', sortable: false },
  { key: 'assignment_group', label: 'Assignment Group', sortable: false },
  { key: 'approval', label: 'Approval' },
];

const ALL_CATALOG_TASK_COLUMNS: ListColumn[] = [
  { key: 'number', label: 'Number', filterKeys: ['number', 'name'] },
  { key: 'short_description', label: 'Short Description' },
  { key: 'state', label: 'State' },
  { key: 'priority', label: 'Priority' },
  { key: 'stage', label: 'Stage' },
  { key: 'urgency', label: 'Urgency' },
  { key: 'impact', label: 'Impact' },
  { key: 'assigned_to', label: 'Assigned To', sortable: false },
  { key: 'assignment_group', label: 'Assignment Group', sortable: false },
  { key: 'approval', label: 'Approval' },
  { key: 'active', label: 'Active' },
];

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  if (!getToken()) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function LegacyUserRedirect() {
  const { sysId } = useParams<{ sysId: string }>();
  return <Navigate to={`/access/users/${sysId}`} replace />;
}

function LegacyGroupRedirect() {
  const { sysId } = useParams<{ sysId: string }>();
  return <Navigate to={`/access/groups/${sysId}`} replace />;
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route
          path="incidents"
          element={
            <RecordListPage
              resource="incidents"
              title="Incidents"
              basePath="/incidents"
              createFields={INCIDENT_FIELDS}
              allColumns={ALL_INCIDENT_COLUMNS}
            />
          }
        />
        <Route
          path="incidents/:sysId"
          element={
            <RecordDetailPage
              resource="incidents"
              title="Incidents"
              listPath="/incidents"
              fields={INCIDENT_DETAIL_FIELDS}
            />
          }
        />
        <Route
          path="problems"
          element={
            <RecordListPage
              resource="problems"
              title="Problems"
              basePath="/problems"
              createFields={[{ key: 'short_description', label: 'Short Description' }]}
              allColumns={ALL_PROBLEM_COLUMNS}
            />
          }
        />
        <Route
          path="problems/:sysId"
          element={
            <RecordDetailPage
              resource="problems"
              title="Problems"
              listPath="/problems"
              fields={PROBLEM_DETAIL_FIELDS}
            />
          }
        />
        <Route
          path="changes"
          element={
            <RecordListPage
              resource="change-requests"
              title="Change Requests"
              basePath="/changes"
              createFields={[{ key: 'short_description', label: 'Short Description' }]}
              allColumns={ALL_CHANGE_COLUMNS}
            />
          }
        />
        <Route path="changes/:sysId" element={<ChangeDetailPage />} />
        <Route
          path="change-tasks"
          element={
            <RecordListPage
              resource="change-tasks"
              title="Change Tasks"
              basePath="/change-tasks"
              allColumns={ALL_CHANGE_TASK_COLUMNS}
            />
          }
        />
        <Route path="change-tasks/:sysId" element={<ChangeTaskDetailPage />} />
        <Route
          path="configuration-items"
          element={
            <RecordListPage
              resource="configuration-items"
              title="Configuration Items"
              basePath="/configuration-items"
              columns={[
                {
                  key: 'number',
                  label: 'Name',
                  filterKeys: ['number', 'name'],
                  sortField: 'name',
                },
                { key: 'short_description', label: 'Short Description' },
                { key: 'state', label: 'State' },
                { key: 'priority', label: 'Priority' },
              ]}
              createFields={[
                { key: 'name', label: 'Name' },
                { key: 'short_description', label: 'Short Description' },
                { key: 'sys_class_name', label: 'Class (e.g. cmdb_ci_server)' },
              ]}
              allColumns={ALL_CI_COLUMNS}
            />
          }
        />
        <Route path="configuration-items/:sysId" element={<ConfigurationItemDetailPage />} />
        <Route
          path="requests"
          element={
            <RecordListPage
              resource="catalog-requests"
              title="Requests"
              basePath="/requests"
              allColumns={ALL_CATALOG_REQUEST_COLUMNS}
            />
          }
        />
        <Route path="requests/:sysId" element={<RequestDetailPage />} />
        <Route
          path="requested-items"
          element={
            <RecordListPage
              resource="catalog-request-items"
              title="Requested Items"
              basePath="/requested-items"
              allColumns={ALL_CATALOG_REQUEST_ITEM_COLUMNS}
            />
          }
        />
        <Route path="requested-items/:sysId" element={<RequestedItemDetailPage />} />
        <Route
          path="catalog-tasks"
          element={
            <RecordListPage
              resource="catalog-tasks"
              title="Catalog Tasks"
              basePath="/catalog-tasks"
              allColumns={ALL_CATALOG_TASK_COLUMNS}
            />
          }
        />
        <Route path="catalog-tasks/:sysId" element={<CatalogTaskDetailPage />} />
        <Route path="catalog" element={<CatalogBrowsePage />} />
        <Route path="catalog/admin" element={<Navigate to="/catalog" replace />} />
        <Route path="catalog/admin/:itemId" element={<CatalogItemBuilderPage />} />
        <Route path="catalog/webhooks" element={<Navigate to="/integrations/webhooks" replace />} />
        <Route path="catalog/:itemId" element={<CatalogItemPage />} />
        <Route path="integrations/webhooks" element={<CatalogWebhooksPage />} />
        <Route path="integrations/webhooks/:sysId" element={<WebhookDetailPage />} />
        <Route path="integrations/secrets" element={<CatalogSecretsPage />} />
        <Route path="integrations/secrets/:sysId" element={<SecretDetailPage />} />
        <Route path="access/users" element={<UsersPage />} />
        <Route path="access/users/:sysId" element={<UserDetailPage />} />
        <Route path="access/groups" element={<GroupsListPage />} />
        <Route path="access/groups/:sysId" element={<GroupDetailPage />} />
        <Route path="users" element={<Navigate to="/access/users" replace />} />
        <Route path="users/:sysId" element={<LegacyUserRedirect />} />
        <Route path="groups" element={<Navigate to="/access/groups" replace />} />
        <Route path="groups/:sysId" element={<LegacyGroupRedirect />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="admin/tables" element={<AdminTablesPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
