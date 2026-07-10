import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api, getRecordPermissions, STATE_LABELS, stateBadge } from '../api/client';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { EmptyValue } from '../components/EmptyValue';
import { displayValue, isEmptyDisplayValue } from '../utils/emptyDisplay';
import { usePageHeader } from '../components/PageHeaderContext';
import { ToastBanner } from '../components/ToastBanner';
import '../components/Layout.css';

interface RecordListProps {
  resource: string;
  title: string;
  basePath: string;
  createFields?: { key: string; label: string; type?: string }[];
  columns?: ListColumn[];
}

interface ListColumn {
  key: string;
  label: string;
  filterKeys?: string[];
}

const DEFAULT_COLUMNS: ListColumn[] = [
  { key: 'number', label: 'Number', filterKeys: ['number', 'name'] },
  { key: 'short_description', label: 'Short Description' },
  { key: 'state', label: 'State' },
  { key: 'priority', label: 'Priority' },
];

type ListBanner = { type: 'success' | 'error'; text: string };

function recordLabel(record: Record<string, string>): string {
  return record.number || record.name || record.sys_id;
}

function getColumnFilterValue(record: Record<string, string>, column: ListColumn): string {
  const keys = column.filterKeys ?? [column.key];
  const values = keys.map((key) => record[key] || '').filter(Boolean);
  if (column.key === 'state') {
    const raw = record.state || '';
    const label = STATE_LABELS[raw] || '';
    if (label && !values.includes(label)) values.push(label);
  }
  return values.join(' ');
}

export function RecordListPage({
  resource,
  title,
  basePath,
  createFields,
  columns = DEFAULT_COLUMNS,
}: RecordListProps) {
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState<Record<string, string>>({});
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [banner, setBanner] = useState<ListBanner | null>(null);
  const [filterField, setFilterField] = useState(columns[0]?.key ?? 'number');
  const [filterText, setFilterText] = useState('');
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ['records', resource],
    queryFn: () => api.listRecords(resource),
  });

  const records = useMemo(() => data?.records ?? [], [data?.records]);
  const activeFilterColumn = columns.find((column) => column.key === filterField) ?? columns[0];
  const filteredRecords = useMemo(() => {
    const query = filterText.trim().toLowerCase();
    if (!query || !activeFilterColumn) return records;
    return records.filter((record) =>
      getColumnFilterValue(record, activeFilterColumn).toLowerCase().includes(query),
    );
  }, [records, filterText, activeFilterColumn]);
  const isFiltered = filterText.trim().length > 0;
  const deletableRecords = useMemo(
    () => filteredRecords.filter((record) => getRecordPermissions(record).delete),
    [filteredRecords],
  );
  const hasDeletable = deletableRecords.length > 0;
  const allDeletableSelected =
    hasDeletable && deletableRecords.every((record) => selected.has(record.sys_id));
  const someDeletableSelected = selected.size > 0 && !allDeletableSelected;
  const selectAllCheckboxRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (selectAllCheckboxRef.current) {
      selectAllCheckboxRef.current.indeterminate = someDeletableSelected;
    }
  }, [someDeletableSelected]);

  const createMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) => api.createRecord(resource, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['records', resource] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      setShowCreate(false);
      setForm({});
    },
  });

  const bulkDeleteMutation = useMutation({
    mutationFn: async (sysIds: string[]) => {
      const results = await Promise.allSettled(
        sysIds.map((sysId) => api.deleteRecord(resource, sysId)),
      );
      const succeeded = results.filter((result) => result.status === 'fulfilled').length;
      const failed = results.length - succeeded;
      return { succeeded, failed };
    },
    onSuccess: ({ succeeded, failed }) => {
      queryClient.invalidateQueries({ queryKey: ['records', resource] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      setSelected(new Set());
      setConfirmOpen(false);
      if (failed > 0) {
        setBanner({
          type: 'error',
          text:
            succeeded > 0
              ? `Deleted ${succeeded} record(s). ${failed} could not be deleted.`
              : `Failed to delete ${failed} record(s).`,
        });
      } else {
        setBanner({ type: 'success', text: `Deleted ${succeeded} record(s).` });
      }
    },
    onError: (error: Error) => {
      setConfirmOpen(false);
      setBanner({ type: 'error', text: error.message || 'Failed to delete records.' });
    },
  });

  const toggleSelect = (sysId: string) => {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(sysId)) next.delete(sysId);
      else next.add(sysId);
      return next;
    });
  };

  const selectAll = () => {
    setSelected(new Set(deletableRecords.map((record) => record.sys_id)));
  };

  const clearSelection = () => {
    setSelected(new Set());
  };

  const toggleSelectAll = () => {
    if (allDeletableSelected) {
      clearSelection();
      return;
    }
    selectAll();
  };

  const selectedLabels = records.filter((record) => selected.has(record.sys_id)).map(recordLabel);

  const headerBreadcrumbs = useMemo(() => [{ label: title }], [title]);
  const headerActions = useMemo(
    () => (
      <>
        {selected.size > 0 && (
          <button
            type="button"
            className="btn btn-danger-solid"
            onClick={() => setConfirmOpen(true)}
            disabled={bulkDeleteMutation.isPending}
          >
            Delete ({selected.size})
          </button>
        )}
        {createFields ? (
          <button className="btn btn-primary" onClick={() => setShowCreate(!showCreate)}>
            {showCreate ? 'Cancel' : 'Create'}
          </button>
        ) : null}
      </>
    ),
    [selected.size, createFields, showCreate, bulkDeleteMutation.isPending],
  );

  usePageHeader({ breadcrumbs: headerBreadcrumbs, actions: headerActions });

  if (isLoading) return <p className="empty-state">Loading…</p>;

  const columnCount = columns.length + (hasDeletable ? 1 : 0);

  function renderCell(column: ListColumn, record: Record<string, string>) {
    if (column.key === 'number') {
      return <Link to={`${basePath}/${record.sys_id}`}>{recordLabel(record)}</Link>;
    }
    if (column.key === 'state') {
      if (isEmptyDisplayValue(record.state)) {
        return <EmptyValue />;
      }
      return (
        <span className={`badge ${stateBadge(record.state)}`}>
          {STATE_LABELS[record.state] || record.state}
        </span>
      );
    }
    return displayValue(record[column.key]);
  }

  return (
    <div>
      {banner && (
        <ToastBanner
          message={banner.text}
          type={banner.type}
          onDismiss={() => setBanner(null)}
          durationMs={banner.type === 'success' ? 2500 : 5000}
        />
      )}

      {showCreate && createFields && (
        <div className="card" style={{ marginBottom: '1.5rem' }}>
          <h2 className="section-title">New {title.slice(0, -1)}</h2>
          {createFields.map((f) => (
            <div className="form-group" key={f.key}>
              <label>{f.label}</label>
              {f.type === 'textarea' ? (
                <textarea
                  rows={3}
                  value={form[f.key] || ''}
                  onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
                />
              ) : (
                <input
                  type={f.type || 'text'}
                  value={form[f.key] || ''}
                  onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
                />
              )}
            </div>
          ))}
          <button
            className="btn btn-primary"
            onClick={() => createMutation.mutate(form)}
            disabled={createMutation.isPending}
          >
            Save
          </button>
        </div>
      )}

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div className="record-list-filter">
          <label htmlFor={`filter-field-${resource}`}>Filter by</label>
          <select
            id={`filter-field-${resource}`}
            value={filterField}
            onChange={(event) => setFilterField(event.target.value)}
          >
            {columns.map((column) => (
              <option key={column.key} value={column.key}>
                {column.label}
              </option>
            ))}
          </select>
          <input
            type="search"
            value={filterText}
            onChange={(event) => setFilterText(event.target.value)}
            placeholder={`Search ${activeFilterColumn?.label.toLowerCase() ?? 'records'}…`}
            aria-label="Filter value"
          />
          {isFiltered && (
            <button
              type="button"
              className="btn btn-secondary btn-sm record-list-filter-clear"
              onClick={() => setFilterText('')}
            >
              Clear
            </button>
          )}
          {isFiltered && (
            <span className="record-list-filter-count">
              {filteredRecords.length} of {records.length}
            </span>
          )}
        </div>
        <table>
          <thead>
            <tr>
              {hasDeletable && (
                <th className="record-select-column">
                  <input
                    ref={selectAllCheckboxRef}
                    type="checkbox"
                    checked={allDeletableSelected}
                    onChange={toggleSelectAll}
                    aria-label="Select all deletable records"
                  />
                </th>
              )}
              {columns.map((column) => (
                <th key={column.key}>{column.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filteredRecords.map((record) => {
              const canDelete = getRecordPermissions(record).delete;
              return (
                <tr key={record.sys_id}>
                  {hasDeletable && (
                    <td className="record-select-column">
                      {canDelete ? (
                        <input
                          type="checkbox"
                          checked={selected.has(record.sys_id)}
                          onChange={() => toggleSelect(record.sys_id)}
                          aria-label={`Select ${recordLabel(record)}`}
                        />
                      ) : null}
                    </td>
                  )}
                  {columns.map((column) => (
                    <td key={column.key}>{renderCell(column, record)}</td>
                  ))}
                </tr>
              );
            })}
            {filteredRecords.length === 0 && (
              <tr>
                <td colSpan={columnCount} className="empty-state">
                  {isFiltered ? 'No records match this filter' : 'No records found'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <ConfirmDialog
        open={confirmOpen}
        title={`Delete ${selected.size} record${selected.size === 1 ? '' : 's'}`}
        message={
          selected.size === 1
            ? `Are you sure you want to permanently delete "${selectedLabels[0]}"? This action cannot be undone.`
            : `Are you sure you want to permanently delete ${selected.size} records? This action cannot be undone.${
                selectedLabels.length > 0
                  ? ` (${selectedLabels.slice(0, 3).join(', ')}${
                      selectedLabels.length > 3 ? ', …' : ''
                    })`
                  : ''
              }`
        }
        onConfirm={() => bulkDeleteMutation.mutate([...selected])}
        onCancel={() => setConfirmOpen(false)}
        isPending={bulkDeleteMutation.isPending}
      />
    </div>
  );
}
