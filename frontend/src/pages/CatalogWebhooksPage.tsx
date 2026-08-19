import { FormEvent, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { usePageHeader } from '../components/PageHeaderContext';
import { OFSelect } from '../components/OFSelect';
import './CatalogPages.css';

type CreateFormState = { name: string; url: string; method: string };
const EMPTY_FORM: CreateFormState = { name: '', url: '', method: 'POST' };

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

  const createMutation = useMutation({
    mutationFn: () =>
      api.adminCreateWebhook({
        name: form.name,
        url: form.url,
        method: form.method,
        active: true,
      }),
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
              <th>Headers</th>
              <th>Active</th>
            </tr>
          </thead>
          <tbody>
            {webhooks.length === 0 ? (
              <tr>
                <td colSpan={5} className="empty-state">
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
