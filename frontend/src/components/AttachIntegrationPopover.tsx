import { FormEvent, useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api, type CatalogWebhook, type CatalogWebhookAttachment } from '../api/client';
import { FieldTooltip } from './FieldTooltip';
import { Portal } from './Portal';
import '../pages/CatalogPages.css';
import './Layout.css';

export type IntegrationKind = 'webhook';

const INTEGRATION_KINDS: { value: IntegrationKind; label: string; description: string }[] = [
  {
    value: 'webhook',
    label: 'Webhook',
    description: 'POST order/state events to a configured webhook destination.',
  },
];

type AttachForm = {
  kind: IntegrationKind;
  webhook: string;
  trigger_on: string;
  payload_template: string;
};

const emptyForm = (): AttachForm => ({
  kind: 'webhook',
  webhook: '',
  trigger_on: 'order',
  payload_template: '',
});

function formatPreview(preview: Record<string, unknown> | string | undefined): string {
  if (preview == null) return '';
  if (typeof preview === 'string') return preview;
  return JSON.stringify(preview, null, 2);
}

function PayloadTemplateLabel({
  htmlFor,
  variables,
}: {
  htmlFor: string;
  variables: { name: string; description: string }[];
}) {
  return (
    <span className="field-label-with-tooltip">
      <label htmlFor={htmlFor}>Payload Template</label>
      <FieldTooltip ariaLabel="Template variables">
        <strong>RITM template variables</strong>
        <p>
          Use <code>$name</code> placeholders. Leave blank for the default RITM payload.
        </p>
        <ul>
          {variables.map((variable) => (
            <li key={variable.name}>
              <code>{variable.name}</code> — {variable.description}
            </li>
          ))}
        </ul>
      </FieldTooltip>
    </span>
  );
}

interface AttachIntegrationPopoverProps {
  open: boolean;
  mode: 'attach' | 'edit';
  itemId: string;
  attachment?: CatalogWebhookAttachment | null;
  onClose: () => void;
  onSaved: (message: string) => void;
}

export function AttachIntegrationPopover({
  open,
  mode,
  itemId,
  attachment = null,
  onClose,
  onSaved,
}: AttachIntegrationPopoverProps) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<AttachForm>(emptyForm);
  const [error, setError] = useState('');

  const webhooksQuery = useQuery({
    queryKey: ['catalog-webhooks'],
    queryFn: () => api.adminListWebhooks(),
    enabled: open,
  });

  const previewQuery = useQuery({
    queryKey: ['catalog-payload-preview', form.payload_template],
    queryFn: () => api.adminPayloadPreview(form.payload_template || undefined),
    enabled: open && form.kind === 'webhook',
  });

  useEffect(() => {
    if (!open) return;
    if (mode === 'edit' && attachment) {
      setForm({
        kind: 'webhook',
        webhook: attachment.webhook,
        trigger_on: attachment.trigger_on || 'order',
        payload_template: attachment.payload_template || '',
      });
    } else {
      setForm(emptyForm());
    }
    setError('');
  }, [open, mode, attachment]);

  useEffect(() => {
    if (!open) return;
    function handleEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose();
    }
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [open, onClose]);

  const attachMutation = useMutation({
    mutationFn: () =>
      api.adminAttachItemWebhook(itemId, {
        webhook: form.webhook,
        trigger_on: form.trigger_on,
        payload_template: form.payload_template || undefined,
        active: true,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['catalog-admin-item-webhooks', itemId] });
      onSaved('Process attached.');
      onClose();
    },
    onError: (err: Error) => setError(err.message),
  });

  const updateMutation = useMutation({
    mutationFn: () =>
      api.adminUpdateItemWebhook(itemId, attachment!.sys_id, {
        webhook: form.webhook,
        trigger_on: form.trigger_on,
        payload_template: form.payload_template || null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['catalog-admin-item-webhooks', itemId] });
      onSaved('Process updated.');
      onClose();
    },
    onError: (err: Error) => setError(err.message),
  });

  if (!open) return null;

  const webhooks: CatalogWebhook[] = webhooksQuery.data?.result || [];
  const templateVariables = previewQuery.data?.result.variables || [];
  const pending = attachMutation.isPending || updateMutation.isPending;
  const title = mode === 'edit' ? 'Configure Process' : 'Attach Process';

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (form.kind !== 'webhook') {
      setError('Select a process type');
      return;
    }
    if (!form.webhook) {
      setError('Select a webhook destination');
      return;
    }
    if (mode === 'edit') {
      updateMutation.mutate();
    } else {
      attachMutation.mutate();
    }
  }

  return (
    <Portal>
      <div className="share-popover-overlay" role="presentation" onClick={onClose}>
        <div
          className="share-popover integration-popover catalog-form-popover"
          role="dialog"
          aria-modal="true"
          aria-label={title}
          onClick={(event) => event.stopPropagation()}
        >
          <div className="share-popover-header">
            <h2>{title}</h2>
            <button
              type="button"
              className="share-popover-close"
              aria-label="Close"
              onClick={onClose}
            >
              ×
            </button>
          </div>

          <form onSubmit={onSubmit} className="catalog-builder-form">
            <div className="form-group">
              <span className="field-label-with-tooltip">
                <label htmlFor="integration-kind">Process Type</label>
                <FieldTooltip ariaLabel="Process type info">
                  {INTEGRATION_KINDS.find((k) => k.value === form.kind)?.description}
                </FieldTooltip>
              </span>
              <select
                id="integration-kind"
                value={form.kind}
                disabled={mode === 'edit'}
                onChange={(e) =>
                  setForm((prev) => ({
                    ...prev,
                    kind: e.target.value as IntegrationKind,
                  }))
                }
              >
                {INTEGRATION_KINDS.map((kind) => (
                  <option key={kind.value} value={kind.value}>
                    {kind.label}
                  </option>
                ))}
              </select>
            </div>

            {form.kind === 'webhook' ? (
              <>
                <div className="catalog-form-grid">
                  <div className="form-group">
                    <label htmlFor="integration-webhook">Webhook</label>
                    <select
                      id="integration-webhook"
                      value={form.webhook}
                      onChange={(e) => setForm((prev) => ({ ...prev, webhook: e.target.value }))}
                    >
                      <option value="">Select configured webhook…</option>
                      {webhooks.map((webhook) => (
                        <option key={webhook.sys_id} value={webhook.sys_id}>
                          {webhook.name}
                          {webhook.active === false ? ' (inactive)' : ''}
                        </option>
                      ))}
                    </select>
                    {!webhooks.length ? (
                      <p className="catalog-help-text">
                        No webhooks yet. Create one under{' '}
                        <Link to="/integrations/webhooks" onClick={onClose}>
                          Integrations → Webhooks
                        </Link>
                        .
                      </p>
                    ) : null}
                  </div>
                  <div className="form-group">
                    <label htmlFor="integration-trigger">Trigger</label>
                    <select
                      id="integration-trigger"
                      value={form.trigger_on}
                      onChange={(e) => setForm((prev) => ({ ...prev, trigger_on: e.target.value }))}
                    >
                      <option value="order">On order</option>
                      <option value="state_change">On state change</option>
                      <option value="approval">On approval</option>
                    </select>
                  </div>
                </div>

                <div className="form-group">
                  <PayloadTemplateLabel
                    htmlFor="integration-payload"
                    variables={templateVariables}
                  />
                  <textarea
                    id="integration-payload"
                    className="code-block"
                    rows={6}
                    value={form.payload_template}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, payload_template: e.target.value }))
                    }
                    placeholder='{"number":"$number","variables":$variables_json}'
                  />
                </div>

                <div className="form-group">
                  <label>Preview</label>
                  <pre className="code-block payload-preview">
                    {formatPreview(previewQuery.data?.result.preview)}
                  </pre>
                </div>
              </>
            ) : null}

            {error ? <p className="error">{error}</p> : null}

            <div className="catalog-form-actions">
              <button type="button" className="btn btn-secondary" onClick={onClose}>
                Cancel
              </button>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={pending || (form.kind === 'webhook' && !webhooks.length)}
              >
                {pending ? 'Saving…' : mode === 'edit' ? 'Save' : 'Attach'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </Portal>
  );
}
