import { FormEvent, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, type TableRegistryEntry } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { usePageHeader } from '../components/PageHeaderContext';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { TableTreeSelect } from '../components/TableTreeSelect';
import { DeleteIcon, PlusCircleIcon } from '../components/DetailIcons';
import './AdminTablesPage.css';
import '../pages/CatalogPages.css';

const FIELD_TYPES = ['string', 'integer', 'decimal', 'boolean', 'date', 'reference'];

type TreeNode = { entry: TableRegistryEntry; children: TreeNode[] };

function buildTree(rows: TableRegistryEntry[]): TreeNode[] {
  const byName = new Map(rows.map((row) => [row.name, row]));
  const childrenOf = new Map<string, TableRegistryEntry[]>();
  const roots: TableRegistryEntry[] = [];

  for (const row of rows) {
    if (row.super_class && byName.has(row.super_class)) {
      const siblings = childrenOf.get(row.super_class) ?? [];
      siblings.push(row);
      childrenOf.set(row.super_class, siblings);
    } else {
      roots.push(row);
    }
  }

  const byLabel = (list: TableRegistryEntry[]) =>
    [...list].sort((a, b) => a.label.localeCompare(b.label));

  function toNode(entry: TableRegistryEntry): TreeNode {
    return { entry, children: byLabel(childrenOf.get(entry.name) ?? []).map(toNode) };
  }

  return byLabel(roots).map(toNode);
}

type NewClassForm = { name: string; label: string };
const EMPTY_NEW_CLASS: NewClassForm = { name: '', label: '' };

type NewFieldForm = {
  name: string;
  label: string;
  type: string;
  reference: string;
  mandatory: boolean;
};
const EMPTY_NEW_FIELD: NewFieldForm = {
  name: '',
  label: '',
  type: 'string',
  reference: '',
  mandatory: false,
};

export function AdminTablesPage() {
  const queryClient = useQueryClient();
  const { hasPermission } = useAuth();
  const canWrite = hasPermission('records.*.write');

  const [selected, setSelected] = useState<string | null>(null);
  const [extendParent, setExtendParent] = useState<string | null>(null);
  const [newClassForm, setNewClassForm] = useState<NewClassForm>(EMPTY_NEW_CLASS);
  const [newFieldForm, setNewFieldForm] = useState<NewFieldForm>(EMPTY_NEW_FIELD);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [pendingDelete, setPendingDelete] = useState<TableRegistryEntry | null>(null);

  usePageHeader({ breadcrumbs: [{ label: 'Settings' }, { label: 'Tables' }] });

  const tablesQuery = useQuery({
    queryKey: ['admin-table-registry'],
    queryFn: () => api.listTableRegistry(),
  });

  const rows = useMemo(() => tablesQuery.data?.result || [], [tablesQuery.data]);
  const tree = useMemo(() => buildTree(rows), [rows]);
  const selectedEntry = rows.find((row) => row.name === selected) || null;

  const schemaQuery = useQuery({
    queryKey: ['admin-table-schema', selected],
    queryFn: () => api.getTableSchema(selected!),
    enabled: Boolean(selected),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api.createTableClass({
        name: newClassForm.name.trim(),
        label: newClassForm.label.trim() || newClassForm.name.trim(),
        super_class: extendParent,
      }),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['admin-table-registry'] });
      setMessage(`Created "${result.result.class_name}".`);
      setError('');
      setExtendParent(null);
      setNewClassForm(EMPTY_NEW_CLASS);
      setSelected(result.result.class_name);
    },
    onError: (err: Error) => {
      setError(err.message);
      setMessage('');
    },
  });

  const addFieldMutation = useMutation({
    mutationFn: () =>
      api.addTableClassField(selected!, {
        name: newFieldForm.name.trim(),
        label: newFieldForm.label.trim() || newFieldForm.name.trim(),
        type: newFieldForm.type,
        reference: newFieldForm.type === 'reference' ? newFieldForm.reference || null : null,
        mandatory: newFieldForm.mandatory,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-table-schema', selected] });
      setMessage(`Added field "${newFieldForm.name.trim()}".`);
      setError('');
      setNewFieldForm(EMPTY_NEW_FIELD);
    },
    onError: (err: Error) => {
      setError(err.message);
      setMessage('');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (name: string) => api.deleteTableClass(name),
    onSuccess: (_data, name) => {
      queryClient.invalidateQueries({ queryKey: ['admin-table-registry'] });
      setPendingDelete(null);
      setMessage(`Deleted "${name}".`);
      setError('');
      if (selected === name) setSelected(null);
    },
    onError: (err: Error) => {
      setError(err.message);
      setPendingDelete(null);
    },
  });

  function startExtend(parent: string) {
    setExtendParent(parent);
    setNewClassForm(EMPTY_NEW_CLASS);
    setError('');
  }

  function onCreateSubmit(event: FormEvent) {
    event.preventDefault();
    if (!newClassForm.name.trim()) {
      setError('Table name is required');
      return;
    }
    createMutation.mutate();
  }

  function onAddFieldSubmit(event: FormEvent) {
    event.preventDefault();
    if (!newFieldForm.name.trim()) {
      setError('Field name is required');
      return;
    }
    addFieldMutation.mutate();
  }

  function selectEntry(name: string) {
    setSelected(name);
    setExtendParent(null);
    setError('');
    setMessage('');
  }

  function renderNode(node: TreeNode, depth: number) {
    const { entry } = node;
    return (
      <li key={entry.name}>
        <div
          className={`admin-tables-row${selected === entry.name ? ' admin-tables-row--selected' : ''}`}
          style={{ paddingLeft: `${depth * 1.25 + 0.5}rem` }}
        >
          <button
            type="button"
            className="admin-tables-row-label"
            onClick={() => selectEntry(entry.name)}
          >
            <span className="admin-tables-row-name">{entry.label}</span>
            <code className="code-inline admin-tables-row-code">{entry.name}</code>
          </button>
          <div className="admin-tables-row-tags">
            {entry.is_logical ? <span className="badge badge-closed">logical</span> : null}
            {entry.user_defined ? <span className="badge badge-accent">custom</span> : null}
          </div>
          <div className="catalog-row-actions">
            {canWrite && entry.is_extendable ? (
              <button
                type="button"
                className="btn-icon"
                aria-label={`Extend ${entry.label}`}
                title="Extend this table"
                onClick={() => startExtend(entry.name)}
              >
                <PlusCircleIcon size={14} />
              </button>
            ) : null}
            {canWrite && entry.user_defined ? (
              <button
                type="button"
                className="btn-icon btn-icon-danger"
                aria-label={`Delete ${entry.label}`}
                title="Delete this table"
                onClick={() => setPendingDelete(entry)}
              >
                <DeleteIcon size={14} />
              </button>
            ) : null}
          </div>
        </div>
        {node.children.length ? (
          <ul className="admin-tables-tree-children">
            {node.children.map((child) => renderNode(child, depth + 1))}
          </ul>
        ) : null}
      </li>
    );
  }

  const schema = schemaQuery.data?.result || null;

  return (
    <div className="catalog-admin-list admin-tables-page">
      {message ? <p className="alert alert-success">{message}</p> : null}
      {error ? <p className="error">{error}</p> : null}

      <p className="catalog-browse-intro">
        Every table and CMDB class — physical tables and their subclasses alike — lives in one
        hierarchy. Extend an extendable table to create a new class, or add fields to any registered
        table below.
      </p>

      <div className="admin-tables-layout">
        <div className="card admin-tables-tree-card">
          <div className="section-header-row">
            <h2 className="section-title">Tables</h2>
          </div>
          {tablesQuery.isLoading ? <p className="empty-state">Loading…</p> : null}
          {tablesQuery.error ? (
            <p className="error">{(tablesQuery.error as Error).message}</p>
          ) : null}
          {!tablesQuery.isLoading && tree.length ? (
            <ul className="admin-tables-tree">{tree.map((node) => renderNode(node, 0))}</ul>
          ) : null}
        </div>

        <div className="card admin-tables-detail-card">
          {extendParent ? (
            <form onSubmit={onCreateSubmit} className="catalog-builder-form">
              <div className="section-header-row">
                <h2 className="section-title" style={{ marginBottom: 0 }}>
                  Extend <code className="code-inline">{extendParent}</code>
                </h2>
                <div className="catalog-form-actions" style={{ margin: 0 }}>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => setExtendParent(null)}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={createMutation.isPending}
                  >
                    {createMutation.isPending ? 'Creating…' : 'Create'}
                  </button>
                </div>
              </div>
              <div className="catalog-form-grid">
                <div className="form-group">
                  <label htmlFor="new-class-name">Table Name</label>
                  <input
                    id="new-class-name"
                    value={newClassForm.name}
                    onChange={(e) =>
                      setNewClassForm((p) => ({
                        ...p,
                        name: e.target.value.trim().toLowerCase().replace(/\s+/g, '_'),
                      }))
                    }
                    placeholder="cmdb_ci_gpu_server"
                    autoComplete="off"
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="new-class-label">Label</label>
                  <input
                    id="new-class-label"
                    value={newClassForm.label}
                    onChange={(e) => setNewClassForm((p) => ({ ...p, label: e.target.value }))}
                    placeholder="GPU Server"
                  />
                </div>
              </div>
            </form>
          ) : selectedEntry ? (
            <>
              <div className="section-header-row">
                <h2 className="section-title" style={{ marginBottom: 0 }}>
                  {selectedEntry.label} <code className="code-inline">{selectedEntry.name}</code>
                </h2>
              </div>
              {schema ? (
                <p className="catalog-help-text">
                  Inheritance: {schema.inheritance_path.filter((n) => n !== 'cmdb').join(' → ')}
                </p>
              ) : null}

              <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
                <table>
                  <thead>
                    <tr>
                      <th>Field</th>
                      <th>Label</th>
                      <th>Type</th>
                      <th>Origin</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(schema?.fields || []).map((field) => (
                      <tr key={field.name}>
                        <td>
                          <code className="code-inline">{field.name}</code>
                        </td>
                        <td>{field.label || '—'}</td>
                        <td>{field.type || '—'}</td>
                        <td>
                          <span
                            className={`badge ${field.origin === 'Native' ? 'badge-accent' : 'badge-closed'}`}
                          >
                            {field.origin}
                          </span>
                          {field.origin !== 'Native' ? (
                            <span className="catalog-help-text"> ({field.defined_on})</span>
                          ) : null}
                        </td>
                      </tr>
                    ))}
                    {!schema?.fields.length ? (
                      <tr>
                        <td colSpan={4} className="empty-state">
                          No fields yet
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>

              {canWrite ? (
                <form onSubmit={onAddFieldSubmit} className="catalog-builder-form nested-form">
                  <div className="section-header-row">
                    <h2 className="section-title" style={{ marginBottom: 0 }}>
                      Add Field
                    </h2>
                    <div className="catalog-form-actions" style={{ margin: 0 }}>
                      <button
                        type="submit"
                        className="btn btn-primary"
                        disabled={addFieldMutation.isPending}
                      >
                        {addFieldMutation.isPending ? 'Adding…' : 'Add Field'}
                      </button>
                    </div>
                  </div>
                  <div className="catalog-form-grid">
                    <div className="form-group">
                      <label htmlFor="new-field-name">Field Name</label>
                      <input
                        id="new-field-name"
                        value={newFieldForm.name}
                        onChange={(e) =>
                          setNewFieldForm((p) => ({
                            ...p,
                            name: e.target.value.trim().toLowerCase().replace(/\s+/g, '_'),
                          }))
                        }
                        placeholder="gpu_count"
                        autoComplete="off"
                      />
                    </div>
                    <div className="form-group">
                      <label htmlFor="new-field-label">Label</label>
                      <input
                        id="new-field-label"
                        value={newFieldForm.label}
                        onChange={(e) => setNewFieldForm((p) => ({ ...p, label: e.target.value }))}
                        placeholder="GPU Count"
                      />
                    </div>
                    <div className="form-group">
                      <label htmlFor="new-field-type">Type</label>
                      <select
                        id="new-field-type"
                        value={newFieldForm.type}
                        onChange={(e) => setNewFieldForm((p) => ({ ...p, type: e.target.value }))}
                      >
                        {FIELD_TYPES.map((type) => (
                          <option key={type} value={type}>
                            {type}
                          </option>
                        ))}
                      </select>
                    </div>
                    {newFieldForm.type === 'reference' ? (
                      <div className="form-group">
                        <label htmlFor="new-field-reference">Reference Table</label>
                        <TableTreeSelect
                          id="new-field-reference"
                          tables={rows}
                          value={newFieldForm.reference}
                          onChange={(value) => setNewFieldForm((p) => ({ ...p, reference: value }))}
                        />
                      </div>
                    ) : null}
                    <div className="form-group">
                      <div className="form-check">
                        <input
                          id="new-field-mandatory"
                          type="checkbox"
                          checked={newFieldForm.mandatory}
                          onChange={(e) =>
                            setNewFieldForm((p) => ({ ...p, mandatory: e.target.checked }))
                          }
                        />
                        <label htmlFor="new-field-mandatory">Mandatory</label>
                      </div>
                    </div>
                  </div>
                </form>
              ) : null}
            </>
          ) : (
            <p className="empty-state">Select a table on the left to view its schema.</p>
          )}
        </div>
      </div>

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        title="Delete table"
        message={
          pendingDelete
            ? `Are you sure you want to permanently delete "${pendingDelete.label}" (${pendingDelete.name})? This is only possible when it has no subclasses and no existing records.`
            : ''
        }
        onConfirm={() => {
          if (pendingDelete) deleteMutation.mutate(pendingDelete.name);
        }}
        onCancel={() => setPendingDelete(null)}
        isPending={deleteMutation.isPending}
        error={deleteMutation.isError ? (deleteMutation.error as Error).message : null}
      />
    </div>
  );
}
