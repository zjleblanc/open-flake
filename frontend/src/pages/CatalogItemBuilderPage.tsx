import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { api, type CatalogVariable, type CatalogWebhookAttachment } from '../api/client';
import { AttachIntegrationPopover } from '../components/AttachIntegrationPopover';
import { CatalogFilterConditionsPanel } from '../components/CatalogFilterConditionsPanel';
import { CatalogVariablePopover } from '../components/CatalogVariablePopover';
import { FieldsIcon, OverviewIcon, ShareIcon } from '../components/DetailIcons';
import { DetailSectionNav, type DetailSectionNavItem } from '../components/DetailSectionNav';
import { ExpandableDetailSection } from '../components/ExpandableDetailSection';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { MarkdownRenderer } from '../components/MarkdownRenderer';
import { usePageHeader } from '../components/PageHeaderContext';
import { ToastBanner } from '../components/ToastBanner';
import '../components/Layout.css';
import './CatalogPages.css';

const BUILDER_SECTION = {
  details: 'catalog-section-details',
  variables: 'catalog-section-variables',
  integrations: 'catalog-section-integrations',
} as const;

type PendingDelete =
  { kind: 'variable'; id: string; label: string } | { kind: 'process'; id: string; label: string };

type ItemSnapshot = {
  name: string;
  shortDescription: string;
  description: string;
  price: string;
  category: string;
};

export function CatalogItemBuilderPage() {
  const { itemId = '' } = useParams();
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<'edit' | 'preview'>('edit');
  const [name, setName] = useState('');
  const [shortDescription, setShortDescription] = useState('');
  const [description, setDescription] = useState('');
  const [price, setPrice] = useState('0');
  const [category, setCategory] = useState('');
  const [savedItem, setSavedItem] = useState<ItemSnapshot | null>(null);
  const [toast, setToast] = useState<{ text: string; type: 'success' | 'error' } | null>(null);
  const [variablePopover, setVariablePopover] = useState<{
    mode: 'add' | 'edit';
    variable: CatalogVariable | null;
  } | null>(null);
  const [integrationPopover, setIntegrationPopover] = useState<{
    mode: 'attach' | 'edit';
    attachment: CatalogWebhookAttachment | null;
  } | null>(null);
  const [pendingDelete, setPendingDelete] = useState<PendingDelete | null>(null);
  const [initialized, setInitialized] = useState(false);
  const [saving, setSaving] = useState(false);

  const itemQuery = useQuery({
    queryKey: ['catalog-admin-item', itemId],
    queryFn: () => api.adminGetCatalogItem(itemId),
    enabled: Boolean(itemId),
  });

  const variablesQuery = useQuery({
    queryKey: ['catalog-admin-variables', itemId],
    queryFn: () => api.adminListVariables(itemId),
    enabled: Boolean(itemId),
  });

  const attachmentsQuery = useQuery({
    queryKey: ['catalog-admin-item-webhooks', itemId],
    queryFn: () => api.adminListItemWebhooks(itemId),
    enabled: Boolean(itemId),
  });

  useEffect(() => {
    setInitialized(false);
  }, [itemId]);

  useEffect(() => {
    if (!itemQuery.data || initialized) return;
    const item = itemQuery.data.result;
    const snapshot: ItemSnapshot = {
      name: item.name || '',
      shortDescription: item.short_description || '',
      description: item.description || '',
      price: item.price || '0',
      category: item.category || '',
    };
    setName(snapshot.name);
    setShortDescription(snapshot.shortDescription);
    setDescription(snapshot.description);
    setPrice(snapshot.price);
    setCategory(snapshot.category);
    setSavedItem(snapshot);
    setInitialized(true);
  }, [itemQuery.data, initialized]);

  const headerBreadcrumbs = useMemo(
    () => [
      { label: 'Service Catalog', to: '/catalog' },
      { label: 'Manage', to: '/catalog/admin' },
      { label: name || 'Edit' },
    ],
    [name],
  );

  const headerActions = useMemo(
    () => (
      <Link to={`/catalog/${itemId}`} className="btn btn-primary">
        View
      </Link>
    ),
    [itemId],
  );

  usePageHeader({
    breadcrumbs: headerBreadcrumbs,
    actions: headerActions,
  });

  const isDirty = useMemo(() => {
    if (!savedItem) return false;
    return (
      name !== savedItem.name ||
      shortDescription !== savedItem.shortDescription ||
      description !== savedItem.description ||
      price !== savedItem.price ||
      category !== savedItem.category
    );
  }, [savedItem, name, shortDescription, description, price, category]);

  const deleteVariable = useMutation({
    mutationFn: (varId: string) => api.adminDeleteVariable(itemId, varId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['catalog-admin-variables', itemId] });
      setPendingDelete(null);
    },
  });

  const detachIntegration = useMutation({
    mutationFn: (attachmentId: string) => api.adminDetachItemWebhook(itemId, attachmentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['catalog-admin-item-webhooks', itemId] });
      setPendingDelete(null);
    },
  });

  const variables: CatalogVariable[] = variablesQuery.data?.result || [];
  const attachments: CatalogWebhookAttachment[] = attachmentsQuery.data?.result || [];

  const sectionNavItems = useMemo((): DetailSectionNavItem[] => {
    return [
      {
        id: BUILDER_SECTION.details,
        title: 'Details',
        icon: <OverviewIcon size={14} />,
        accent: 'accent',
      },
      {
        id: BUILDER_SECTION.variables,
        title: 'Variables',
        icon: <FieldsIcon size={14} />,
        accent: 'info',
        count: variables.length,
      },
      {
        id: BUILDER_SECTION.integrations,
        title: 'Processes',
        icon: <ShareIcon size={14} />,
        accent: 'success',
        count: attachments.length,
      },
    ];
  }, [variables.length, attachments.length]);

  async function saveChanges() {
    if (!isDirty || saving) return;
    setSaving(true);
    try {
      await api.adminUpdateCatalogItem(itemId, {
        name,
        short_description: shortDescription,
        description,
        price,
        category,
      });
      setSavedItem({ name, shortDescription, description, price, category });
      queryClient.invalidateQueries({ queryKey: ['catalog-admin-item', itemId] });
      queryClient.invalidateQueries({ queryKey: ['catalog-items'] });
      setToast({ text: 'Changes saved.', type: 'success' });
    } catch (err) {
      setToast({ text: (err as Error).message, type: 'error' });
    } finally {
      setSaving(false);
    }
  }

  if (itemQuery.isLoading) return <p className="empty-state">Loading builder…</p>;
  if (itemQuery.error) return <p className="error">{(itemQuery.error as Error).message}</p>;

  return (
    <>
      {toast ? (
        <ToastBanner
          message={toast.text}
          type={toast.type}
          onDismiss={() => setToast(null)}
          durationMs={toast.type === 'success' ? 2500 : 4000}
        />
      ) : null}

      <div className="detail-page-layout">
        <div className="detail-page-main">
          <div className="detail-sections-stack">
            <ExpandableDetailSection
              id={BUILDER_SECTION.details}
              title="Details"
              icon={<OverviewIcon size={14} />}
              accent="accent"
              defaultOpen
            >
              <div className="catalog-builder-form">
                <div className="catalog-form-grid">
                  <div className="form-group">
                    <label htmlFor="item-name">Name</label>
                    <input id="item-name" value={name} onChange={(e) => setName(e.target.value)} />
                  </div>
                  <div className="form-group">
                    <label htmlFor="item-short">Short Description</label>
                    <input
                      id="item-short"
                      value={shortDescription}
                      onChange={(e) => setShortDescription(e.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="item-category">Category</label>
                    <input
                      id="item-category"
                      value={category}
                      onChange={(e) => setCategory(e.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="item-price">Price</label>
                    <input
                      id="item-price"
                      value={price}
                      onChange={(e) => setPrice(e.target.value)}
                    />
                  </div>
                </div>

                <div className="markdown-editor">
                  <div className="markdown-editor-toolbar">
                    <span>Description (Markdown)</span>
                    <div
                      className="markdown-editor-tabs"
                      role="tablist"
                      aria-label="Description editor mode"
                    >
                      <button
                        type="button"
                        role="tab"
                        id="description-tab-edit"
                        aria-selected={mode === 'edit'}
                        aria-controls="description-panel-edit"
                        tabIndex={mode === 'edit' ? 0 : -1}
                        className={`markdown-editor-tab${mode === 'edit' ? ' markdown-editor-tab--active' : ''}`}
                        onClick={() => setMode('edit')}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        role="tab"
                        id="description-tab-preview"
                        aria-selected={mode === 'preview'}
                        aria-controls="description-panel-preview"
                        tabIndex={mode === 'preview' ? 0 : -1}
                        className={`markdown-editor-tab${mode === 'preview' ? ' markdown-editor-tab--active' : ''}`}
                        onClick={() => setMode('preview')}
                      >
                        Preview
                      </button>
                    </div>
                  </div>
                  {mode === 'edit' ? (
                    <textarea
                      id="description-panel-edit"
                      role="tabpanel"
                      aria-labelledby="description-tab-edit"
                      className="code-block markdown-editor-textarea"
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      rows={12}
                      placeholder="Write markdown description…"
                    />
                  ) : (
                    <div
                      id="description-panel-preview"
                      role="tabpanel"
                      aria-labelledby="description-tab-preview"
                      className="markdown-editor-preview panel"
                    >
                      <MarkdownRenderer content={description} />
                    </div>
                  )}
                </div>
              </div>
            </ExpandableDetailSection>

            <ExpandableDetailSection
              id={BUILDER_SECTION.variables}
              title="Variables"
              icon={<FieldsIcon size={14} />}
              accent="info"
              count={variables.length}
              defaultOpen
            >
              <div className="section-header-row">
                <p className="catalog-browse-intro">Form fields shown when ordering this item.</p>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => setVariablePopover({ mode: 'add', variable: null })}
                >
                  Add
                </button>
              </div>

              <table className="data-table">
                <thead>
                  <tr>
                    <th>Order</th>
                    <th>Name</th>
                    <th>Label</th>
                    <th>Type</th>
                    <th>Required</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {variables.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="empty-state">
                        No variables yet
                      </td>
                    </tr>
                  ) : (
                    variables.map((variable) => (
                      <tr key={variable.sys_id}>
                        <td>{variable.order}</td>
                        <td>
                          <code className="code-inline">{variable.name}</code>
                        </td>
                        <td>{variable.question_text}</td>
                        <td>{variable.type}</td>
                        <td>{variable.mandatory ? 'Yes' : 'No'}</td>
                        <td className="catalog-row-actions">
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => setVariablePopover({ mode: 'edit', variable })}
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            className="btn btn-danger btn-sm"
                            onClick={() =>
                              setPendingDelete({
                                kind: 'variable',
                                id: variable.sys_id,
                                label: variable.question_text || variable.name,
                              })
                            }
                          >
                            Delete
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>

              <CatalogFilterConditionsPanel
                itemId={itemId}
                variables={variables}
                onToast={(message, type = 'success') => setToast({ text: message, type })}
              />
            </ExpandableDetailSection>

            <ExpandableDetailSection
              id={BUILDER_SECTION.integrations}
              title="Processes"
              icon={<ShareIcon size={14} />}
              accent="success"
              count={attachments.length}
              defaultOpen
            >
              <div className="section-header-row">
                <p className="catalog-browse-intro">Attach processes to this catalog item.</p>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => setIntegrationPopover({ mode: 'attach', attachment: null })}
                >
                  Attach
                </button>
              </div>

              <table className="data-table">
                <thead>
                  <tr>
                    <th>Type</th>
                    <th>Name</th>
                    <th>Trigger</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {attachments.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="empty-state">
                        No processes yet
                      </td>
                    </tr>
                  ) : (
                    attachments.map((attachment) => (
                      <tr key={attachment.sys_id}>
                        <td>Webhook</td>
                        <td>{attachment.webhook_name || attachment.webhook}</td>
                        <td>{attachment.trigger_on}</td>
                        <td className="catalog-row-actions">
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() =>
                              setIntegrationPopover({
                                mode: 'edit',
                                attachment,
                              })
                            }
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            className="btn btn-danger btn-sm"
                            onClick={() =>
                              setPendingDelete({
                                kind: 'process',
                                id: attachment.sys_id,
                                label: attachment.webhook_name || attachment.webhook,
                              })
                            }
                          >
                            Delete
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </ExpandableDetailSection>
          </div>
        </div>

        <DetailSectionNav sections={sectionNavItems} />
      </div>

      <CatalogVariablePopover
        open={Boolean(variablePopover)}
        mode={variablePopover?.mode || 'add'}
        itemId={itemId}
        variable={variablePopover?.variable}
        onClose={() => setVariablePopover(null)}
        onSaved={(message) => setToast({ text: message, type: 'success' })}
      />

      <AttachIntegrationPopover
        open={Boolean(integrationPopover)}
        mode={integrationPopover?.mode || 'attach'}
        itemId={itemId}
        attachment={integrationPopover?.attachment}
        onClose={() => setIntegrationPopover(null)}
        onSaved={(message) => setToast({ text: message, type: 'success' })}
      />

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        title={pendingDelete?.kind === 'process' ? 'Detach process' : 'Delete variable'}
        message={
          pendingDelete
            ? pendingDelete.kind === 'process'
              ? `Are you sure you want to detach "${pendingDelete.label}" from this catalog item?`
              : `Are you sure you want to permanently delete "${pendingDelete.label}"? This action cannot be undone.`
            : ''
        }
        confirmLabel={pendingDelete?.kind === 'process' ? 'Detach' : 'Delete'}
        pendingLabel={pendingDelete?.kind === 'process' ? 'Detaching…' : 'Deleting…'}
        onConfirm={() => {
          if (!pendingDelete) return;
          if (pendingDelete.kind === 'process') {
            detachIntegration.mutate(pendingDelete.id);
          } else {
            deleteVariable.mutate(pendingDelete.id);
          }
        }}
        onCancel={() => setPendingDelete(null)}
        isPending={deleteVariable.isPending || detachIntegration.isPending}
      />

      {isDirty ? (
        <div className="floating-save-bar">
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => void saveChanges()}
            disabled={saving}
          >
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      ) : null}
    </>
  );
}
