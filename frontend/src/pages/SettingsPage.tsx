import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import {
  ColorSchemeSelector,
  LayoutDensitySelector,
  ToggleSwitch,
} from '../components/DetailFieldControls';
import { usePageHeader } from '../components/PageHeaderContext';
import { useUserPreferences } from '../settings/UserPreferencesContext';
import { formatDateValue } from '../utils/formatDisplayValue';
import '../components/Layout.css';

const SETTINGS_BREADCRUMBS = [{ label: 'Settings' }];

export function SettingsPage() {
  usePageHeader({ breadcrumbs: SETTINGS_BREADCRUMBS });
  const {
    dateDisplayFormat,
    setDateDisplayFormat,
    layoutDensity,
    setLayoutDensity,
    colorScheme,
    setColorScheme,
  } = useUserPreferences();
  const [apiKeyName, setApiKeyName] = useState('');
  const [newKey, setNewKey] = useState<string | null>(null);
  const [oauthForm, setOauthForm] = useState({ name: '', client_id: '', client_secret: '' });
  const queryClient = useQueryClient();

  const apiKeys = useQuery({ queryKey: ['api-keys'], queryFn: api.listApiKeys });
  const oauthClients = useQuery({ queryKey: ['oauth-clients'], queryFn: api.listOAuthClients });

  const createKeyMutation = useMutation({
    mutationFn: () => api.createApiKey(apiKeyName),
    onSuccess: (data) => {
      setNewKey(data.api_key);
      setApiKeyName('');
      queryClient.invalidateQueries({ queryKey: ['api-keys'] });
    },
  });

  const createOAuthMutation = useMutation({
    mutationFn: () => api.createOAuthClient(oauthForm),
    onSuccess: () => {
      setOauthForm({ name: '', client_id: '', client_secret: '' });
      queryClient.invalidateQueries({ queryKey: ['oauth-clients'] });
    },
  });

  const sampleDate = useMemo(() => new Date().toISOString(), []);
  const datePreview = formatDateValue(sampleDate, dateDisplayFormat);

  return (
    <div>
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <h2 className="section-title">Preferences</h2>
        <p className="text-body" style={{ marginBottom: '1rem' }}>
          Display preferences are saved to your account.
        </p>
        <div className="preferences-layout-row">
          <div className="preferences-layout-control">
            <ColorSchemeSelector
              idPrefix="settings-theme"
              value={colorScheme}
              onChange={setColorScheme}
            />
          </div>
          <div className="preferences-layout-control">
            <LayoutDensitySelector
              idPrefix="settings-layout"
              value={layoutDensity}
              onChange={setLayoutDensity}
            />
          </div>
        </div>
        <div className="preferences-date-row">
          <div className="preferences-toggle-row">
            <ToggleSwitch
              id="date-display-local"
              checked={dateDisplayFormat === 'local'}
              onChange={(checked) => setDateDisplayFormat(checked ? 'local' : 'raw')}
              label="Local Dates"
            />
          </div>
          <div className="preferences-date-preview">
            <span className="preferences-date-preview-label">Preview</span>
            <code className="preferences-date-preview-value">{datePreview}</code>
          </div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <h2 className="section-title">API Keys</h2>
        <p className="text-body" style={{ marginBottom: '1rem' }}>
          API keys are sent via the <code className="code-inline">x-sn-apikey</code> header for
          Ansible automation.
        </p>
        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
          <input
            placeholder="Key name"
            value={apiKeyName}
            onChange={(e) => setApiKeyName(e.target.value)}
            style={{ flex: 1 }}
          />
          <button
            className="btn btn-primary"
            onClick={() => createKeyMutation.mutate()}
            disabled={!apiKeyName || createKeyMutation.isPending}
          >
            Generate
          </button>
        </div>
        {newKey && (
          <div className="code-block" style={{ marginBottom: '1rem' }}>
            <p className="text-xs text-muted" style={{ marginBottom: '0.5rem' }}>
              Copy this key now — it won't be shown again:
            </p>
            {newKey}
          </div>
        )}
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {(apiKeys.data || []).length === 0 ? (
              <tr>
                <td colSpan={2} className="empty-state">
                  No API keys yet
                </td>
              </tr>
            ) : (
              (apiKeys.data || []).map((k) => (
                <tr key={k.sys_id}>
                  <td>{k.name}</td>
                  <td>{k.active ? 'Active' : 'Inactive'}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2 className="section-title">OAuth Clients</h2>
        <div className="detail-grid" style={{ marginBottom: '1rem' }}>
          {(['name', 'client_id', 'client_secret'] as const).map((key) => (
            <div className="form-group" key={key}>
              <label>{key.replace('_', ' ')}</label>
              <input
                value={oauthForm[key]}
                onChange={(e) => setOauthForm({ ...oauthForm, [key]: e.target.value })}
              />
            </div>
          ))}
        </div>
        <button
          className="btn btn-primary"
          onClick={() => createOAuthMutation.mutate()}
          disabled={createOAuthMutation.isPending}
        >
          Add Client
        </button>
        <table style={{ marginTop: '1rem' }}>
          <thead>
            <tr>
              <th>Name</th>
              <th>Client ID</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {(oauthClients.data || []).length === 0 ? (
              <tr>
                <td colSpan={3} className="empty-state">
                  No OAuth clients yet
                </td>
              </tr>
            ) : (
              (oauthClients.data || []).map((c) => (
                <tr key={c.sys_id}>
                  <td>{c.name}</td>
                  <td>{c.client_id}</td>
                  <td>{c.active ? 'Active' : 'Inactive'}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
