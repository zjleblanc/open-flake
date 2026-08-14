import { FormEvent, useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, CatalogWebhook } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { usePageHeader } from '../components/PageHeaderContext';
import { FieldTooltip } from '../components/FieldTooltip';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { TemplateAutocomplete } from '../components/TemplateAutocomplete';
import './CatalogPages.css';

type HeaderRow = { key: string; value: string };

function headersFromRows(rows: HeaderRow[]): Record<string, string> {
  const headers: Record<string, string> = {};
  for (const row of rows) {
    const key = row.key.trim();
    if (!key) continue;
    headers[key] = row.value;
  }
  return headers;
}

function rowsFromHeaders(headers: Record<string, string>): HeaderRow[] {
  const entries = Object.entries(headers);
  return entries.length
    ? entries.map(([key, value]) => ({ key, value }))
    : [{ key: '', value: '' }];
}

type WebhookFormState = {
  name: string;
  url: string;
  method: string;
  secret: string;
  description: string;
  headerRows: HeaderRow[];
};

const EMPTY_FORM: WebhookFormState = {
  name: '',
  url: '',
  method: 'POST',
  secret: '',
  description: '',
  headerRows: [{ key: '', value: '' }],
};

function formFromWebhook(webhook: CatalogWebhook): WebhookFormState {
  return {
    name: webhook.name,
    url: webhook.url,
    method: webhook.method,
    secret: '',
    description: webhook.description || '',
    headerRows: rowsFromHeaders(webhook.headers || {}),
  };
}

function headersEqual(a: HeaderRow[], b: HeaderRow[]): boolean {
  const mapA = headersFromRows(a);
  const mapB = headersFromRows(b);
  const keysA = Object.keys(mapA).sort();
  const keysB = Object.keys(mapB).sort();
  if (keysA.length !== keysB.length) return false;
  return keysA.every((key, i) => key === keysB[i] && mapA[key] === mapB[key]);
}

export function CatalogWebhooksPage() {
  const queryClient = useQueryClient();
  const { hasPermission } = useAuth();
  const canReadSecrets = hasPermission('secrets.read');
  const [form, setForm] = useState<WebhookFormState>(EMPTY_FORM);
  const [editing, setEditing] = useState<CatalogWebhook | null>(null);
  const [baseline, setBaseline] = useState<WebhookFormState>(EMPTY_FORM);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [pendingDelete, setPendingDelete] = useState<{ id: string; label: string } | null>(null);

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
    enabled: canReadSecrets,
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api.adminCreateWebhook({
        name: form.name,
        url: form.url,
        method: form.method,
        secret: form.secret || undefined,
        description: form.description || undefined,
        headers: headersFromRows(form.headerRows),
        active: true,
      }),
    onSuccess: () => {
      setForm(EMPTY_FORM);
      setMessage('Webhook created.');
      setError('');
      queryClient.invalidateQueries({ queryKey: ['catalog-webhooks'] });
    },
    onError: (err: Error) => {
      setError(err.message);
      setMessage('');
    },
  });

  const updateMutation = useMutation({
    mutationFn: () => {
      const patch: Record<string, unknown> = {};
      if (form.name !== baseline.name) patch.name = form.name;
      if (form.url !== baseline.url) patch.url = form.url;
      if (form.method !== baseline.method) patch.method = form.method;
      if (form.description !== baseline.description)
        patch.description = form.description || undefined;
      if (form.secret) patch.secret = form.secret;
      if (!headersEqual(form.headerRows, baseline.headerRows)) {
        patch.headers = headersFromRows(form.headerRows);
      }
      return api.adminUpdateWebhook(editing!.sys_id, patch);
    },
    onSuccess: () => {
      setEditing(null);
      setForm(EMPTY_FORM);
      setBaseline(EMPTY_FORM);
      setMessage('Webhook updated.');
      setError('');
      queryClient.invalidateQueries({ queryKey: ['catalog-webhooks'] });
    },
    onError: (err: Error) => {
      setError(err.message);
      setMessage('');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.adminDeleteWebhook(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['catalog-webhooks'] });
      setPendingDelete(null);
    },
  });

  usePageHeader({
    breadcrumbs: [{ label: 'Integrations' }, { label: 'Webhooks' }],
  });

  function startEdit(webhook: CatalogWebhook) {
    const initial = formFromWebhook(webhook);
    setEditing(webhook);
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
      if (!form.url.trim()) {
        setError('URL is required');
        return;
      }
      createMutation.mutate();
    }
  }

  function updateHeaderRow(index: number, field: keyof HeaderRow, value: string) {
    setForm((prev) => ({
      ...prev,
      headerRows: prev.headerRows.map((row, i) => (i === index ? { ...row, [field]: value } : row)),
    }));
  }

  function addHeaderRow() {
    setForm((prev) => ({ ...prev, headerRows: [...prev.headerRows, { key: '', value: '' }] }));
  }

  function removeHeaderRow(index: number) {
    setForm((prev) => ({
      ...prev,
      headerRows:
        prev.headerRows.length <= 1
          ? [{ key: '', value: '' }]
          : prev.headerRows.filter((_, i) => i !== index),
    }));
  }

  const isEditing = editing !== null;
  const isDirty = isEditing
    ? form.name !== baseline.name ||
      form.url !== baseline.url ||
      form.method !== baseline.method ||
      form.description !== baseline.description ||
      form.secret.length > 0 ||
      !headersEqual(form.headerRows, baseline.headerRows)
    : true;
  const isPending = isEditing ? updateMutation.isPending : createMutation.isPending;

  if (isLoading) return <p className="empty-state">Loading…</p>;
  if (loadError) return <p className="error">{(loadError as Error).message}</p>;

  const webhooks = data?.result || [];
  const availableSecrets = secretsQuery.data?.result || [];

  return (
    <div className="catalog-admin-list">
      {message ? <p className="alert alert-success">{message}</p> : null}
      {error ? <p className="error">{error}</p> : null}

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
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>URL</th>
              <th>Method</th>
              <th>Headers</th>
              <th>Active</th>
              <th />
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
                  <tr
                    key={webhook.sys_id}
                    className={
                      editing?.sys_id === webhook.sys_id ? 'catalog-row-active' : undefined
                    }
                  >
                    <td>{webhook.name}</td>
                    <td>
                      <code className="code-inline">{webhook.url}</code>
                    </td>
                    <td>{webhook.method}</td>
                    <td>{headerCount ? `${headerCount}` : '—'}</td>
                    <td>{webhook.active ? 'Yes' : 'No'}</td>
                    <td>
                      <div className="catalog-row-actions">
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => startEdit(webhook)}
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          className="btn btn-danger btn-sm"
                          onClick={() =>
                            setPendingDelete({ id: webhook.sys_id, label: webhook.name })
                          }
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      <div className="card">
        <form onSubmit={onSubmit} className="catalog-builder-form">
          <div className="section-header-row">
            <h2 className="section-title" style={{ marginBottom: 0 }}>
              {isEditing ? `Edit: ${editing.name}` : 'New Webhook'}
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
              <label htmlFor="wh-name">Name</label>
              <input
                id="wh-name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label htmlFor="wh-method">Method</label>
              <select
                id="wh-method"
                value={form.method}
                onChange={(e) => setForm({ ...form, method: e.target.value })}
              >
                <option value="POST">POST</option>
                <option value="PUT">PUT</option>
                <option value="PATCH">PATCH</option>
              </select>
            </div>
            <div className="form-group catalog-form-span">
              <label htmlFor="wh-url">URL</label>
              <input
                id="wh-url"
                value={form.url}
                onChange={(e) => setForm({ ...form, url: e.target.value })}
              />
            </div>
            <div className="form-group">
              <span className="field-label-with-tooltip">
                <label htmlFor="wh-secret">Secret (HMAC)</label>
                <FieldTooltip ariaLabel="HMAC secret info">
                  Optional signing key for the X-OpenFlake-Signature header.
                </FieldTooltip>
              </span>
              <input
                id="wh-secret"
                value={form.secret}
                onChange={(e) => setForm({ ...form, secret: e.target.value })}
                placeholder={isEditing ? '(leave blank to keep current)' : ''}
              />
            </div>
            <div className="form-group">
              <label htmlFor="wh-desc">Description</label>
              <input
                id="wh-desc"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />
            </div>
          </div>

          <div className="form-group">
            <span className="field-label-with-tooltip">
              <label>Custom headers</label>
              <FieldTooltip ariaLabel="Header value secrets">
                <p>
                  Use <code>{'{{secret:name}}'}</code> in a value to inject a stored secret at
                  delivery time.
                </p>
                {canReadSecrets && availableSecrets.length ? (
                  <p>Available: {availableSecrets.map((s) => s.name).join(', ')}</p>
                ) : null}
              </FieldTooltip>
            </span>
            <div className="webhook-header-rows">
              {form.headerRows.map((row, index) => (
                <div key={index} className="webhook-header-row">
                  <input
                    aria-label={`Header name ${index + 1}`}
                    placeholder="Authorization"
                    value={row.key}
                    onChange={(e) => updateHeaderRow(index, 'key', e.target.value)}
                  />
                  <TemplateAutocomplete
                    ariaLabel={`Header value ${index + 1}`}
                    placeholder="Bearer {{secret:aap_token}}"
                    value={row.value}
                    onChange={(value) => updateHeaderRow(index, 'value', value)}
                  />
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => removeHeaderRow(index)}
                    aria-label={`Remove header ${index + 1}`}
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
            <button type="button" className="btn btn-secondary" onClick={addHeaderRow}>
              Add header
            </button>
          </div>
        </form>
      </div>

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        title="Delete webhook"
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
