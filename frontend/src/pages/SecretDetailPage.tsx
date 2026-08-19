import { useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, type IntegrationSecret } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { usePageHeader } from '../components/PageHeaderContext';
import { ConfirmDialog } from '../components/ConfirmDialog';
import './CatalogPages.css';

const LIST_PATH = '/integrations/secrets';

type SecretFormState = { name: string; value: string; description: string };

function formFromSecret(secret: IntegrationSecret): SecretFormState {
  return { name: secret.name, value: '', description: secret.description || '' };
}

export function SecretDetailPage() {
  const { sysId } = useParams<{ sysId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { hasPermission } = useAuth();
  const canRead = hasPermission('secrets.read');
  const canWrite = hasPermission('secrets.write');
  const canAdmin = hasPermission('secrets.admin');
  const [form, setForm] = useState<SecretFormState | null>(null);
  const [baseline, setBaseline] = useState<SecretFormState | null>(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ['integration-secret', sysId],
    queryFn: () => api.getSecret(sysId!),
    enabled: !!sysId && canRead,
  });

  useEffect(() => {
    if (data?.result) {
      const initial = formFromSecret(data.result);
      setForm(initial);
      setBaseline(initial);
    }
  }, [data]);

  const updateMutation = useMutation({
    mutationFn: (): Promise<unknown> => {
      if (!form || !baseline) return Promise.resolve();
      const patch: Record<string, unknown> = {};
      if (form.description !== baseline.description)
        patch.description = form.description || undefined;
      if (form.value) patch.value = form.value;
      return api.updateSecret(sysId!, patch);
    },
    onSuccess: () => {
      setMessage('Secret updated.');
      setError('');
      queryClient.invalidateQueries({ queryKey: ['integration-secret', sysId] });
      queryClient.invalidateQueries({ queryKey: ['integration-secrets'] });
    },
    onError: (err: Error) => {
      setError(err.message);
      setMessage('');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteSecret(sysId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['integration-secrets'] });
      navigate(LIST_PATH);
    },
    onError: (err: Error) => {
      setError(err.message);
      setConfirmDeleteOpen(false);
    },
  });

  const secret = data?.result;
  const recordTitle = secret?.name || 'Loading…';

  const headerBreadcrumbs = useMemo(
    () => [
      { label: 'Integrations' },
      { label: 'Secrets', to: LIST_PATH },
      { label: isLoading || !secret ? 'Loading…' : recordTitle },
    ],
    [isLoading, secret, recordTitle],
  );
  const headerActions = useMemo(
    () =>
      !isLoading && secret && canAdmin ? (
        <button
          type="button"
          className="btn btn-danger-solid"
          onClick={() => setConfirmDeleteOpen(true)}
          disabled={deleteMutation.isPending}
        >
          Delete
        </button>
      ) : undefined,
    [isLoading, secret, canAdmin, deleteMutation.isPending],
  );

  usePageHeader({ breadcrumbs: headerBreadcrumbs, actions: headerActions });

  if (!canRead) {
    return <p className="error">You do not have permission to view secrets.</p>;
  }
  if (isLoading || !form) return <p className="empty-state">Loading…</p>;
  if (!secret) return <p className="error">Secret not found.</p>;

  const isDirty = form.description !== baseline!.description || form.value.length > 0;

  return (
    <div className="catalog-admin-list">
      {message ? <p className="alert alert-success">{message}</p> : null}
      {error ? <p className="error">{error}</p> : null}

      <div className="card">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            updateMutation.mutate();
          }}
          className="catalog-builder-form"
        >
          <div className="section-header-row">
            <h2 className="section-title" style={{ marginBottom: 0 }}>
              Secret Details
            </h2>
            {canWrite ? (
              <div className="catalog-form-actions" style={{ margin: 0 }}>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={!isDirty || updateMutation.isPending}
                >
                  {updateMutation.isPending ? 'Saving…' : 'Save'}
                </button>
              </div>
            ) : null}
          </div>
          <div className="catalog-form-grid">
            <div className="form-group">
              <label htmlFor="sec-name">Name</label>
              <input id="sec-name" value={form.name} readOnly className="readonly-input" />
            </div>
            <div className="form-group">
              <label htmlFor="sec-desc">Description</label>
              <input
                id="sec-desc"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                disabled={!canWrite}
              />
            </div>
            <div className="form-group catalog-form-span">
              <label htmlFor="sec-value">New Value (leave blank to keep current)</label>
              <input
                id="sec-value"
                type="password"
                value={form.value}
                onChange={(e) => setForm({ ...form, value: e.target.value })}
                autoComplete="new-password"
                disabled={!canWrite}
              />
            </div>
          </div>
        </form>
      </div>

      <ConfirmDialog
        open={confirmDeleteOpen}
        title="Delete secret"
        message={`Are you sure you want to permanently delete "${secret.name}"? This action cannot be undone.`}
        onConfirm={() => deleteMutation.mutate()}
        onCancel={() => setConfirmDeleteOpen(false)}
        isPending={deleteMutation.isPending}
      />
    </div>
  );
}
