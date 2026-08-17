import { Navigate, Route, Routes, useParams } from 'react-router-dom';
import { Layout } from './components/Layout';
import { getToken } from './api/client';
import { CatalogBrowsePage } from './pages/CatalogBrowsePage';
import { CatalogItemBuilderPage } from './pages/CatalogItemBuilderPage';
import { CatalogItemPage } from './pages/CatalogItemPage';
import { CatalogWebhooksPage } from './pages/CatalogWebhooksPage';
import { CatalogSecretsPage } from './pages/CatalogSecretsPage';
import { ConfigurationItemDetailPage } from './pages/ConfigurationItemDetailPage';
import { DashboardPage } from './pages/DashboardPage';
import { GroupDetailPage } from './pages/GroupDetailPage';
import { GroupsListPage } from './pages/GroupsListPage';
import { LoginPage } from './pages/LoginPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { RecordDetailPage } from './pages/RecordDetailPage';
import { RecordListPage } from './pages/RecordListPage';
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

const CHANGE_DETAIL_FIELDS = [
  { key: 'short_description', label: 'Short Description' },
  { key: 'state', label: 'State', type: 'select-state' },
  { key: 'priority', label: 'Priority', readOnly: true },
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
            />
          }
        />
        <Route
          path="changes/:sysId"
          element={
            <RecordDetailPage
              resource="change-requests"
              title="Change Requests"
              listPath="/changes"
              fields={CHANGE_DETAIL_FIELDS}
            />
          }
        />
        <Route
          path="configuration-items"
          element={
            <RecordListPage
              resource="configuration-items"
              title="Configuration Items"
              basePath="/configuration-items"
              columns={[
                { key: 'number', label: 'Name', filterKeys: ['number', 'name'] },
                { key: 'short_description', label: 'Short Description' },
                { key: 'state', label: 'State' },
                { key: 'priority', label: 'Priority' },
              ]}
              createFields={[
                { key: 'name', label: 'Name' },
                { key: 'short_description', label: 'Short Description' },
                { key: 'sys_class_name', label: 'Class (e.g. cmdb_ci_server)' },
              ]}
            />
          }
        />
        <Route path="configuration-items/:sysId" element={<ConfigurationItemDetailPage />} />
        <Route
          path="requests"
          element={
            <RecordListPage resource="catalog-requests" title="Requests" basePath="/requests" />
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
            />
          }
        />
        <Route path="requested-items/:sysId" element={<RequestedItemDetailPage />} />
        <Route path="catalog" element={<CatalogBrowsePage />} />
        <Route path="catalog/admin" element={<Navigate to="/catalog" replace />} />
        <Route path="catalog/admin/:itemId" element={<CatalogItemBuilderPage />} />
        <Route path="catalog/webhooks" element={<Navigate to="/integrations/webhooks" replace />} />
        <Route path="catalog/:itemId" element={<CatalogItemPage />} />
        <Route path="integrations/webhooks" element={<CatalogWebhooksPage />} />
        <Route path="integrations/secrets" element={<CatalogSecretsPage />} />
        <Route path="access/users" element={<UsersPage />} />
        <Route path="access/users/:sysId" element={<UserDetailPage />} />
        <Route path="access/groups" element={<GroupsListPage />} />
        <Route path="access/groups/:sysId" element={<GroupDetailPage />} />
        <Route path="users" element={<Navigate to="/access/users" replace />} />
        <Route path="users/:sysId" element={<LegacyUserRedirect />} />
        <Route path="groups" element={<Navigate to="/access/groups" replace />} />
        <Route path="groups/:sysId" element={<LegacyGroupRedirect />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
