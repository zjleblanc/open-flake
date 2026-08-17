import { FormEvent, useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, IntegrationSecret } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { usePageHeader } from '../components/PageHeaderContext';
import { FieldTooltip } from '../components/FieldTooltip';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { EditIcon, DeleteIcon } from '../components/DetailIcons';
import './CatalogPages.css';

type SecretFormState = { name: string; value: string; description: string };
const EMPTY_FORM: SecretFormState = { name: '', value: '', description: '' };

function formFromSecret(secret: IntegrationSecret): SecretFormState {
  return { name: secret.name, value: '', description: secret.description || '' };
}

export function CatalogSecretsPage() {
  const queryClient = useQueryClient();
  const { hasPermission } = useAuth();
  const canRead = hasPermission('secrets.read');
  const canWrite = hasPermission('secrets.write');
  const canAdmin = hasPermission('secrets.admin');
  const [form, setForm] = useState<SecretFormState>(EMPTY_FORM);
  const [editing, setEditing] = useState<IntegrationSecret | null>(null);
  const [baseline, setBaseline] = useState<SecretFormState>(EMPTY_FORM);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [pendingDelete, setPendingDelete] = useState<{ id: string; label: string } | null>(null);

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
      setMessage('Secret created. Reference it in webhook headers as {{secret:name}}.');
      setError('');
      queryClient.invalidateQueries({ queryKey: ['integration-secrets'] });
    },
    onError: (err: Error) => {
      setError(err.message);
      setMessage('');
    },
  });

  const updateMutation = useMutation({
    mutationFn: () => {
      const patch: Record<string, unknown> = {};
      if (form.description !== baseline.description)
        patch.description = form.description || undefined;
      if (form.value) patch.value = form.value;
      return api.updateSecret(editing!.sys_id, patch);
    },
    onSuccess: () => {
      setEditing(null);
      setForm(EMPTY_FORM);
      setBaseline(EMPTY_FORM);
      setMessage('Secret updated.');
      setError('');
      queryClient.invalidateQueries({ queryKey: ['integration-secrets'] });
    },
    onError: (err: Error) => {
      setError(err.message);
      setMessage('');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteSecret(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['integration-secrets'] });
      setPendingDelete(null);
    },
  });

  usePageHeader({
    breadcrumbs: [{ label: 'Integrations' }, { label: 'Secrets' }],
  });

  function startEdit(secret: IntegrationSecret) {
    const initial = formFromSecret(secret);
    setEditing(secret);
    setForm(initial);
    setBaseline(initial);
    setError('');
    setMessage('');
  }

  function cancelEdit() {
    setEditing(null);
    setForm(EMPTY_FORM);
    setBaseline(EMPTY_FORM);
    setError('');
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (editing) {
      updateMutation.mutate();
    } else {
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
  }

  const isEditing = editing !== null;
  const isDirty = isEditing
    ? form.description !== baseline.description || form.value.length > 0
    : true;
  const isPending = isEditing ? updateMutation.isPending : createMutation.isPending;

  if (!canRead) {
    return <p className="error">You do not have permission to view secrets.</p>;
  }
  if (isLoading) return <p className="empty-state">Loading…</p>;
  if (loadError) return <p className="error">{(loadError as Error).message}</p>;

  const secrets = data?.result || [];

  return (
    <div className="catalog-admin-list">
      {message ? <p className="alert alert-success">{message}</p> : null}
      {error ? <p className="error">{error}</p> : null}

      <p className="catalog-browse-intro">
        Store credentials for outbound integrations. Reference them in webhook header values with{' '}
        <code className="code-inline">{'{{secret:name}}'}</code>. Values are write-only after
        create. Manage destinations under <Link to="/integrations/webhooks">Webhooks</Link>.
      </p>
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Description</th>
              <th>Active</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {secrets.map((secret) => (
              <tr
                key={secret.sys_id}
                className={editing?.sys_id === secret.sys_id ? 'catalog-row-active' : undefined}
              >
                <td>
                  <code className="code-inline">{`{{secret:${secret.name}}}`}</code>
                </td>
                <td>{secret.description || '—'}</td>
                <td>{secret.active ? 'Yes' : 'No'}</td>
                <td>
                  <div className="catalog-row-actions">
                    {canWrite ? (
                      <button
                        type="button"
                        className="btn-icon"
                        aria-label={`Edit ${secret.name}`}
                        onClick={() => startEdit(secret)}
                      >
                        <EditIcon size={14} />
                      </button>
                    ) : null}
                    {canAdmin ? (
                      <button
                        type="button"
                        className="btn-icon btn-icon-danger"
                        aria-label={`Delete ${secret.name}`}
                        onClick={() => setPendingDelete({ id: secret.sys_id, label: secret.name })}
                      >
                        <DeleteIcon size={14} />
                      </button>
                    ) : null}
                  </div>
                </td>
              </tr>
            ))}
            {!secrets.length ? (
              <tr>
                <td colSpan={4} className="empty-state">
                  No secrets yet
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      {canWrite ? (
        <div className="card">
          <form onSubmit={onSubmit} className="catalog-builder-form">
            <div className="section-header-row">
              <h2 className="section-title" style={{ marginBottom: 0 }}>
                {isEditing ? `Edit: ${editing.name}` : 'New Secret'}
              </h2>
              <div className="catalog-form-actions" style={{ margin: 0 }}>
                {isEditing ? (
                  <button type="button" className="btn btn-secondary" onClick={cancelEdit}>
                    Cancel
                  </button>
                ) : null}
                <button type="submit" className="btn btn-primary" disabled={!isDirty || isPending}>
                  {isEditing ? 'Save' : 'Create'}
                </button>
              </div>
            </div>
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
                  readOnly={isEditing}
                  className={isEditing ? 'readonly-input' : undefined}
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
                <label htmlFor="sec-value">
                  {isEditing ? 'New Value (leave blank to keep current)' : 'Value'}
                </label>
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

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        title="Delete secret"
        message={
          pendingDelete
            ? `Are you sure you want to permanently delete "${pendingDelete.label}"? This action cannot be undone.`
            : ''
        }
        onConfirm={() => {
          if (pendingDelete) deleteMutation.mutate(pendingDelete.id);
        }}
        onCancel={() => setPendingDelete(null)}
        isPending={deleteMutation.isPending}
      />
    </div>
  );
}
