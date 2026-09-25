import { FormEvent, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { usePageHeader } from '../components/PageHeaderContext';
import { FieldTooltip } from '../components/FieldTooltip';
import { OFSelect } from '../components/OFSelect';
import './CatalogPages.css';

type CreateFormState = {
  name: string;
  url: string;
  method: string;
  auth_type: string;
  oauth_token_url: string;
  oauth_client_id: string;
  oauth_client_secret: string;
  oauth_scope: string;
};
const EMPTY_FORM: CreateFormState = {
  name: '',
  url: '',
  method: 'POST',
  auth_type: 'none',
  oauth_token_url: '',
  oauth_client_id: '',
  oauth_client_secret: '',
  oauth_scope: '',
};

export function CatalogWebhooksPage() {
  const queryClient = useQueryClient();
  const { hasPermission } = useAuth();
  const canReadSecrets = hasPermission('secrets.read');
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState<CreateFormState>(EMPTY_FORM);
  const [error, setError] = useState('');

  const {
    data,
    isLoading,
    error: loadError,
  } = useQuery({
    queryKey: ['catalog-webhooks'],
    queryFn: () => api.adminListWebhooks(),
  });

  const secretsQuery = useQuery({
    queryKey: ['integration-secrets'],
    queryFn: () => api.listSecrets(),
    enabled: canReadSecrets && showCreate && form.auth_type === 'oauth2_client_credentials',
  });

  const createMutation = useMutation({
    mutationFn: () => {
      const payload: Record<string, unknown> = {
        name: form.name,
        url: form.url,
        method: form.method,
        active: true,
        auth_type: form.auth_type,
      };
      if (form.auth_type === 'oauth2_client_credentials') {
        payload.oauth_token_url = form.oauth_token_url || undefined;
        payload.oauth_client_id = form.oauth_client_id || undefined;
        payload.oauth_client_secret = form.oauth_client_secret || undefined;
        payload.oauth_scope = form.oauth_scope || undefined;
      }
      return api.adminCreateWebhook(payload);
    },
    onSuccess: () => {
      setForm(EMPTY_FORM);
      setShowCreate(false);
      setError('');
      queryClient.invalidateQueries({ queryKey: ['catalog-webhooks'] });
    },
    onError: (err: Error) => setError(err.message),
  });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!form.url.trim()) {
      setError('URL is required');
      return;
    }
    createMutation.mutate();
  }

  const headerBreadcrumbs = useMemo(() => [{ label: 'Integrations' }, { label: 'Webhooks' }], []);
  const headerActions = useMemo(
    () => (
      <button
        type="button"
        className="btn btn-primary"
        onClick={() => {
          setShowCreate((prev) => !prev);
          setError('');
        }}
      >
        {showCreate ? 'Cancel' : 'Create'}
      </button>
    ),
    [showCreate],
  );

  usePageHeader({ breadcrumbs: headerBreadcrumbs, actions: headerActions });

  if (isLoading) return <p className="empty-state">Loading…</p>;
  if (loadError) return <p className="error">{(loadError as Error).message}</p>;

  const webhooks = data?.result || [];

  return (
    <div className="catalog-admin-list">
      <p className="catalog-browse-intro">
        Configure reusable webhook destinations, then attach them to catalog items. Header values
        can reference stored secrets as <code className="code-inline">{'{{secret:name}}'}</code>
        {canReadSecrets ? (
          <>
            . Manage secrets under <Link to="/integrations/secrets">Integrations → Secrets</Link>
          </>
        ) : null}
        .
      </p>

      {showCreate ? (
        <div className="card">
          <form onSubmit={onSubmit} className="catalog-builder-form">
            <div className="section-header-row">
              <h2 className="section-title" style={{ marginBottom: 0 }}>
                New Webhook
              </h2>
              <div className="catalog-form-actions" style={{ margin: 0 }}>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={createMutation.isPending}
                >
                  {createMutation.isPending ? 'Creating…' : 'Create'}
                </button>
              </div>
            </div>
            {error ? <p className="error">{error}</p> : null}
            <div className="catalog-form-grid">
              <div className="form-group">
                <label htmlFor="wh-name">Name</label>
                <input
                  id="wh-name"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                />
              </div>
              <div className="form-group">
                <OFSelect
                  id="wh-method"
                  floatingLabel="Method"
                  value={form.method}
                  onChange={(value) => setForm({ ...form, method: value as string })}
                  options={[
                    { value: 'POST', label: 'POST' },
                    { value: 'PUT', label: 'PUT' },
                    { value: 'PATCH', label: 'PATCH' },
                  ]}
                />
              </div>
              <div className="form-group catalog-form-span">
                <label htmlFor="wh-url">URL</label>
                <input
                  id="wh-url"
                  value={form.url}
                  onChange={(e) => setForm({ ...form, url: e.target.value })}
                />
              </div>
            </div>
            <div className="catalog-form-grid">
              <div className="form-group">
                <OFSelect
                  id="wh-auth-type"
                  floatingLabel="Authentication"
                  value={form.auth_type}
                  onChange={(value) => setForm({ ...form, auth_type: value as string })}
                  options={[
                    { value: 'none', label: 'None' },
                    { value: 'oauth2_client_credentials', label: 'OAuth 2.0 Client Credentials' },
                  ]}
                />
              </div>
            </div>
            {form.auth_type === 'oauth2_client_credentials' && (
              <div className="catalog-form-grid">
                <div className="form-group catalog-form-span">
                  <span className="field-label-with-tooltip">
                    <label htmlFor="wh-c-oauth-token-url">Token URL</label>
                    <FieldTooltip ariaLabel="OAuth token URL info">
                      The external OAuth token endpoint (e.g. https://aap.example.com/api/o/token/).
                    </FieldTooltip>
                  </span>
                  <input
                    id="wh-c-oauth-token-url"
                    value={form.oauth_token_url}
                    onChange={(e) => setForm({ ...form, oauth_token_url: e.target.value })}
                    placeholder="https://example.com/oauth/token"
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="wh-c-oauth-client-id">Client ID</label>
                  <input
                    id="wh-c-oauth-client-id"
                    value={form.oauth_client_id}
                    onChange={(e) => setForm({ ...form, oauth_client_id: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <span className="field-label-with-tooltip">
                    <label htmlFor="wh-c-oauth-client-secret">Client Secret</label>
                    <FieldTooltip ariaLabel="OAuth client secret info">
                      Select the secret that holds the OAuth client secret value.
                    </FieldTooltip>
                  </span>
                  {canReadSecrets && (secretsQuery.data?.result || []).length ? (
                    <OFSelect
                      id="wh-c-oauth-client-secret"
                      value={form.oauth_client_secret}
                      onChange={(value) =>
                        setForm({ ...form, oauth_client_secret: value as string })
                      }
                      options={[
                        { value: '', label: '(select a secret)' },
                        ...(secretsQuery.data?.result || []).map((s) => ({
                          value: s.name,
                          label: s.name,
                        })),
                      ]}
                    />
                  ) : (
                    <input
                      id="wh-c-oauth-client-secret"
                      value={form.oauth_client_secret}
                      onChange={(e) => setForm({ ...form, oauth_client_secret: e.target.value })}
                      placeholder="Secret name"
                    />
                  )}
                </div>
                <div className="form-group">
                  <span className="field-label-with-tooltip">
                    <label htmlFor="wh-c-oauth-scope">Scope</label>
                    <FieldTooltip ariaLabel="OAuth scope info">
                      Optional OAuth scope string. Leave blank if not required.
                    </FieldTooltip>
                  </span>
                  <input
                    id="wh-c-oauth-scope"
                    value={form.oauth_scope}
                    onChange={(e) => setForm({ ...form, oauth_scope: e.target.value })}
                  />
                </div>
              </div>
            )}
          </form>
        </div>
      ) : null}

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>URL</th>
              <th>Method</th>
              <th>Auth</th>
              <th>Headers</th>
              <th>Active</th>
            </tr>
          </thead>
          <tbody>
            {webhooks.length === 0 ? (
              <tr>
                <td colSpan={6} className="empty-state">
                  No webhooks yet
                </td>
              </tr>
            ) : (
              webhooks.map((webhook) => {
                const headerCount = Object.keys(webhook.headers || {}).length;
                return (
                  <tr key={webhook.sys_id}>
                    <td>
                      <Link
                        to={`/integrations/webhooks/${webhook.sys_id}`}
                        className="reference-link"
                      >
                        {webhook.name}
                      </Link>
                    </td>
                    <td>
                      <code className="code-inline">{webhook.url}</code>
                    </td>
                    <td>{webhook.method}</td>
                    <td>{webhook.auth_type === 'oauth2_client_credentials' ? 'OAuth 2.0' : '—'}</td>
                    <td>{headerCount ? `${headerCount}` : '—'}</td>
                    <td>{webhook.active ? 'Yes' : 'No'}</td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
