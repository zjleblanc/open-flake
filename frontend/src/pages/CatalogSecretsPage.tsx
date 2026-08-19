import { FormEvent, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { usePageHeader } from '../components/PageHeaderContext';
import { FieldTooltip } from '../components/FieldTooltip';
import './CatalogPages.css';

type CreateFormState = { name: string; value: string; description: string };
const EMPTY_FORM: CreateFormState = { name: '', value: '', description: '' };

export function CatalogSecretsPage() {
  const queryClient = useQueryClient();
  const { hasPermission } = useAuth();
  const canRead = hasPermission('secrets.read');
  const canWrite = hasPermission('secrets.write');
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState<CreateFormState>(EMPTY_FORM);
  const [error, setError] = useState('');

  const {
    data,
    isLoading,
    error: loadError,
  } = useQuery({
    queryKey: ['integration-secrets'],
    queryFn: () => api.listSecrets(),
    enabled: canRead,
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api.createSecret({
        name: form.name.trim(),
        value: form.value,
        description: form.description || undefined,
        active: true,
      }),
    onSuccess: () => {
      setForm(EMPTY_FORM);
      setShowCreate(false);
      setError('');
      queryClient.invalidateQueries({ queryKey: ['integration-secrets'] });
    },
    onError: (err: Error) => setError(err.message),
  });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!form.name.trim()) {
      setError('Name is required');
      return;
    }
    if (!form.value) {
      setError('Value is required');
      return;
    }
    createMutation.mutate();
  }

  const headerBreadcrumbs = useMemo(() => [{ label: 'Integrations' }, { label: 'Secrets' }], []);
  const headerActions = useMemo(
    () =>
      canWrite ? (
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
      ) : null,
    [canWrite, showCreate],
  );

  usePageHeader({ breadcrumbs: headerBreadcrumbs, actions: headerActions });

  if (!canRead) {
    return <p className="error">You do not have permission to view secrets.</p>;
  }
  if (isLoading) return <p className="empty-state">Loading…</p>;
  if (loadError) return <p className="error">{(loadError as Error).message}</p>;

  const secrets = data?.result || [];

  return (
    <div className="catalog-admin-list">
      <p className="catalog-browse-intro">
        Store credentials for outbound integrations. Reference them in webhook header values with{' '}
        <code className="code-inline">{'{{secret:name}}'}</code>. Values are write-only after
        create. Manage destinations under <Link to="/integrations/webhooks">Webhooks</Link>.
      </p>

      {showCreate && canWrite ? (
        <div className="card">
          <form onSubmit={onSubmit} className="catalog-builder-form">
            <div className="section-header-row">
              <h2 className="section-title" style={{ marginBottom: 0 }}>
                New Secret
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
                <span className="field-label-with-tooltip">
                  <label htmlFor="sec-name">Name</label>
                  <FieldTooltip ariaLabel="Name format">
                    Letters, numbers, underscores, and hyphens only.
                  </FieldTooltip>
                </span>
                <input
                  id="sec-name"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="aap_token"
                  autoComplete="off"
                />
              </div>
              <div className="form-group">
                <label htmlFor="sec-desc">Description</label>
                <input
                  id="sec-desc"
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  placeholder="AAP API token"
                />
              </div>
              <div className="form-group catalog-form-span">
                <label htmlFor="sec-value">Value</label>
                <input
                  id="sec-value"
                  type="password"
                  value={form.value}
                  onChange={(e) => setForm({ ...form, value: e.target.value })}
                  autoComplete="new-password"
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
              <th>Description</th>
              <th>Active</th>
            </tr>
          </thead>
          <tbody>
            {secrets.map((secret) => (
              <tr key={secret.sys_id}>
                <td>
                  <Link to={`/integrations/secrets/${secret.sys_id}`} className="reference-link">
                    <code className="code-inline">{`{{secret:${secret.name}}}`}</code>
                  </Link>
                </td>
                <td>{secret.description || '—'}</td>
                <td>{secret.active ? 'Yes' : 'No'}</td>
              </tr>
            ))}
            {!secrets.length ? (
              <tr>
                <td colSpan={3} className="empty-state">
                  No secrets yet
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}
