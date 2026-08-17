import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { usePageHeader } from '../components/PageHeaderContext';
import { OFSelect } from '../components/OFSelect';
import { ReferenceLink } from '../components/ReferenceLink';
import '../components/Layout.css';

type GroupFormState = { name: string; description: string };
const EMPTY_GROUP_FORM: GroupFormState = { name: '', description: '' };

interface ListColumn {
  key: string;
  label: string;
}

const COLUMNS: ListColumn[] = [
  { key: 'name', label: 'Name' },
  { key: 'description', label: 'Description' },
];

function groupLabel(record: Record<string, string>): string {
  return record.name || record.sys_id;
}

export function GroupsListPage() {
  const { hasPermission } = useAuth();
  const canWriteGroups = hasPermission('groups.write');
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState<GroupFormState>(EMPTY_GROUP_FORM);
  const [filterField, setFilterField] = useState(COLUMNS[0].key);
  const [filterText, setFilterText] = useState('');
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ['records', 'groups'],
    queryFn: () => api.listRecords('groups'),
  });

  const records = useMemo(() => data?.records ?? [], [data?.records]);

  const filteredRecords = useMemo(() => {
    const query = filterText.trim().toLowerCase();
    if (!query) return records;
    return records.filter((record) => (record[filterField] || '').toLowerCase().includes(query));
  }, [records, filterText, filterField]);
  const isFiltered = filterText.trim().length > 0;

  const createMutation = useMutation({
    mutationFn: () => api.createRecord('groups', form),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['records', 'groups'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      setShowCreate(false);
      setForm(EMPTY_GROUP_FORM);
    },
  });

  const headerBreadcrumbs = useMemo(() => [{ label: 'Groups' }], []);
  const headerActions = useMemo(
    () =>
      canWriteGroups ? (
        <button className="btn btn-primary" onClick={() => setShowCreate((prev) => !prev)}>
          {showCreate ? 'Cancel' : 'Create'}
        </button>
      ) : null,
    [canWriteGroups, showCreate],
  );

  usePageHeader({ breadcrumbs: headerBreadcrumbs, actions: headerActions });

  if (!hasPermission('groups.read')) {
    return (
      <div>
        <p className="text-muted">You do not have permission to view groups.</p>
      </div>
    );
  }

  if (isLoading) return <p className="empty-state">Loading…</p>;

  return (
    <div>
      {showCreate && canWriteGroups && (
        <div className="card" style={{ marginBottom: '1.5rem' }}>
          <h2 className="section-title">New Group</h2>
          <div className="form-group">
            <label>Name</label>
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div className="form-group">
            <label>Description</label>
            <input
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </div>
          <button
            className="btn btn-primary"
            onClick={() => createMutation.mutate()}
            disabled={createMutation.isPending || !form.name.trim()}
          >
            Save
          </button>
        </div>
      )}

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div className="record-list-filter">
          <label htmlFor="filter-field-groups">Filter by</label>
          <OFSelect
            id="filter-field-groups"
            size="sm"
            className="record-list-filter-select"
            value={filterField}
            onChange={(value) => setFilterField(value as string)}
            options={COLUMNS.map((column) => ({ value: column.key, label: column.label }))}
          />
          <input
            type="search"
            value={filterText}
            onChange={(event) => setFilterText(event.target.value)}
            placeholder={`Search ${COLUMNS.find((c) => c.key === filterField)?.label.toLowerCase() ?? 'groups'}…`}
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
              {COLUMNS.map((column) => (
                <th key={column.key}>{column.label}</th>
              ))}
              <th>Owner</th>
            </tr>
          </thead>
          <tbody>
            {filteredRecords.map((record) => (
              <tr key={record.sys_id}>
                <td>
                  <Link to={`/access/groups/${record.sys_id}`} className="reference-link">
                    {groupLabel(record)}
                  </Link>
                </td>
                <td>{record.description}</td>
                <td>
                  <ReferenceLink value={record.owner} record={record} field="owner" target="user" />
                </td>
              </tr>
            ))}
            {filteredRecords.length === 0 && (
              <tr>
                <td colSpan={COLUMNS.length + 1} className="empty-state">
                  {isFiltered ? 'No records match this filter' : 'No groups found'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
