import { useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, type CatalogWebhook } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { usePageHeader } from '../components/PageHeaderContext';
import { FieldTooltip } from '../components/FieldTooltip';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { TemplateAutocomplete } from '../components/TemplateAutocomplete';
import { OFSelect } from '../components/OFSelect';
import './CatalogPages.css';

const LIST_PATH = '/integrations/webhooks';

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

export function WebhookDetailPage() {
  const { sysId } = useParams<{ sysId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { hasPermission } = useAuth();
  const canReadSecrets = hasPermission('secrets.read');
  const [form, setForm] = useState<WebhookFormState | null>(null);
  const [baseline, setBaseline] = useState<WebhookFormState | null>(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ['catalog-webhook', sysId],
    queryFn: () => api.adminGetWebhook(sysId!),
    enabled: !!sysId,
  });

  const secretsQuery = useQuery({
    queryKey: ['integration-secrets'],
    queryFn: () => api.listSecrets(),
    enabled: canReadSecrets,
  });

  useEffect(() => {
    if (data?.result) {
      const initial = formFromWebhook(data.result);
      setForm(initial);
      setBaseline(initial);
    }
  }, [data]);

  const updateMutation = useMutation({
    mutationFn: (): Promise<unknown> => {
      const patch: Record<string, unknown> = {};
      if (!form || !baseline) return Promise.resolve();
      if (form.name !== baseline.name) patch.name = form.name;
      if (form.url !== baseline.url) patch.url = form.url;
      if (form.method !== baseline.method) patch.method = form.method;
      if (form.description !== baseline.description)
        patch.description = form.description || undefined;
      if (form.secret) patch.secret = form.secret;
      if (!headersEqual(form.headerRows, baseline.headerRows)) {
        patch.headers = headersFromRows(form.headerRows);
      }
      return api.adminUpdateWebhook(sysId!, patch);
    },
    onSuccess: () => {
      setMessage('Webhook updated.');
      setError('');
      queryClient.invalidateQueries({ queryKey: ['catalog-webhook', sysId] });
      queryClient.invalidateQueries({ queryKey: ['catalog-webhooks'] });
    },
    onError: (err: Error) => {
      setError(err.message);
      setMessage('');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.adminDeleteWebhook(sysId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['catalog-webhooks'] });
      navigate(LIST_PATH);
    },
    onError: (err: Error) => {
      setError(err.message);
      setConfirmDeleteOpen(false);
    },
  });

  const webhook = data?.result;
  const recordTitle = webhook?.name || 'Loading…';

  const headerBreadcrumbs = useMemo(
    () => [
      { label: 'Integrations' },
      { label: 'Webhooks', to: LIST_PATH },
      { label: isLoading || !webhook ? 'Loading…' : recordTitle },
    ],
    [isLoading, webhook, recordTitle],
  );
  const headerActions = useMemo(
    () =>
      !isLoading && webhook ? (
        <button
          type="button"
          className="btn btn-danger-solid"
          onClick={() => setConfirmDeleteOpen(true)}
          disabled={deleteMutation.isPending}
        >
          Delete
        </button>
      ) : undefined,
    [isLoading, webhook, deleteMutation.isPending],
  );

  usePageHeader({ breadcrumbs: headerBreadcrumbs, actions: headerActions });

  if (isLoading || !form) return <p className="empty-state">Loading…</p>;
  if (!webhook) return <p className="error">Webhook not found.</p>;

  const availableSecrets = secretsQuery.data?.result || [];
  const isDirty =
    form.name !== baseline!.name ||
    form.url !== baseline!.url ||
    form.method !== baseline!.method ||
    form.description !== baseline!.description ||
    form.secret.length > 0 ||
    !headersEqual(form.headerRows, baseline!.headerRows);

  function updateHeaderRow(index: number, field: keyof HeaderRow, value: string) {
    setForm((prev) =>
      prev
        ? {
            ...prev,
            headerRows: prev.headerRows.map((row, i) =>
              i === index ? { ...row, [field]: value } : row,
            ),
          }
        : prev,
    );
  }

  function addHeaderRow() {
    setForm((prev) =>
      prev ? { ...prev, headerRows: [...prev.headerRows, { key: '', value: '' }] } : prev,
    );
  }

  function removeHeaderRow(index: number) {
    setForm((prev) =>
      prev
        ? {
            ...prev,
            headerRows:
              prev.headerRows.length <= 1
                ? [{ key: '', value: '' }]
                : prev.headerRows.filter((_, i) => i !== index),
          }
        : prev,
    );
  }

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
              Webhook Details
            </h2>
            <div className="catalog-form-actions" style={{ margin: 0 }}>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={!isDirty || updateMutation.isPending}
              >
                {updateMutation.isPending ? 'Saving…' : 'Save'}
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
                placeholder="(leave blank to keep current)"
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
        open={confirmDeleteOpen}
        title="Delete webhook"
        message={`Are you sure you want to permanently delete "${webhook.name}"? This action cannot be undone.`}
        onConfirm={() => deleteMutation.mutate()}
        onCancel={() => setConfirmDeleteOpen(false)}
        isPending={deleteMutation.isPending}
      />
    </div>
  );
}
