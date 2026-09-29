import { useMemo, useState } from 'react';
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { usePageHeader } from '../components/PageHeaderContext';
import { OFSelect } from '../components/OFSelect';
import { PaginationBar } from '../components/PaginationBar';
import { SortableColumnHeader } from '../components/SortableColumnHeader';
import { useServerPagination } from '../hooks/useServerPagination';
import '../components/Layout.css';

type UserFormState = {
  user_name: string;
  password: string;
  first_name: string;
  last_name: string;
  email: string;
};

const EMPTY_USER_FORM: UserFormState = {
  user_name: '',
  password: '',
  first_name: '',
  last_name: '',
  email: '',
};

interface ListColumn {
  key: string;
  label: string;
  /** Set false for columns that don't map to a single sortable server field. Defaults to true. */
  sortable?: boolean;
}

const COLUMNS: ListColumn[] = [
  { key: 'user_name', label: 'Username' },
  // "name" is a virtual first_name + last_name combination, not a real sortable column.
  { key: 'name', label: 'Name', sortable: false },
  { key: 'email', label: 'Email' },
];

function userLabel(record: Record<string, string>): string {
  return record.user_name || record.sys_id;
}

function getColumnFilterValue(record: Record<string, string>, columnKey: string): string {
  if (columnKey === 'name') {
    return `${record.first_name || ''} ${record.last_name || ''}`.trim();
  }
  return record[columnKey] || '';
}

export function UsersPage() {
  const { hasPermission } = useAuth();
  const canWriteUsers = hasPermission('users.write');
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState<UserFormState>(EMPTY_USER_FORM);
  const [filterField, setFilterField] = useState(COLUMNS[0].key);
  const [filterText, setFilterText] = useState('');
  const queryClient = useQueryClient();
  const pagination = useServerPagination();

  const { data, isLoading } = useQuery({
    queryKey: [
      'records',
      'users',
      pagination.offset,
      pagination.limit,
      pagination.sortField,
      pagination.sortDirection,
    ],
    queryFn: () =>
      api.listRecords('users', {
        limit: pagination.limit,
        offset: pagination.offset,
        ...(pagination.sortDirection === 'desc'
          ? { orderbydesc: pagination.sortField }
          : { orderby: pagination.sortField }),
      }),
    placeholderData: keepPreviousData,
  });

  const records = useMemo(() => data?.records ?? [], [data?.records]);
  const total = data?.total ?? 0;

  const filteredRecords = useMemo(() => {
    const query = filterText.trim().toLowerCase();
    if (!query) return records;
    return records.filter((record) =>
      getColumnFilterValue(record, filterField).toLowerCase().includes(query),
    );
  }, [records, filterText, filterField]);
  const isFiltered = filterText.trim().length > 0;

  const createMutation = useMutation({
    mutationFn: () => api.createUser(form),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['records', 'users'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      setShowCreate(false);
      setForm(EMPTY_USER_FORM);
    },
  });

  const headerBreadcrumbs = useMemo(() => [{ label: 'Users' }], []);
  const headerActions = useMemo(
    () =>
      canWriteUsers ? (
        <button className="btn btn-primary" onClick={() => setShowCreate((prev) => !prev)}>
          {showCreate ? 'Cancel' : 'Create'}
        </button>
      ) : null,
    [canWriteUsers, showCreate],
  );

  usePageHeader({ breadcrumbs: headerBreadcrumbs, actions: headerActions });

  if (!hasPermission('users.read')) {
    return (
      <div>
        <p className="text-muted">You do not have permission to view users.</p>
      </div>
    );
  }

  if (isLoading) return <p className="empty-state">Loading…</p>;

  return (
    <div>
      {showCreate && canWriteUsers && (
        <div className="card" style={{ marginBottom: '1.5rem' }}>
          <h2 className="section-title">New User</h2>
          {(['user_name', 'password', 'first_name', 'last_name', 'email'] as const).map((key) => (
            <div className="form-group" key={key}>
              <label>{key.replace('_', ' ')}</label>
              <input
                type={key === 'password' ? 'password' : 'text'}
                value={form[key]}
                onChange={(e) => setForm({ ...form, [key]: e.target.value })}
              />
            </div>
          ))}
          <button
            className="btn btn-primary"
            onClick={() => createMutation.mutate()}
            disabled={createMutation.isPending}
          >
            Save
          </button>
        </div>
      )}

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div className="record-list-filter">
          <label htmlFor="filter-field-users">Filter by</label>
          <OFSelect
            id="filter-field-users"
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
            placeholder={`Search ${COLUMNS.find((c) => c.key === filterField)?.label.toLowerCase() ?? 'users'}…`}
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
              {filteredRecords.length} of {records.length} on this page
            </span>
          )}
        </div>
        <table>
          <thead>
            <tr>
              {COLUMNS.map((column) => (
                <SortableColumnHeader
                  key={column.key}
                  field={column.key}
                  label={column.label}
                  sortField={pagination.sortField}
                  sortDirection={pagination.sortDirection}
                  onSort={pagination.toggleSort}
                  sortable={column.sortable}
                />
              ))}
            </tr>
          </thead>
          <tbody>
            {filteredRecords.map((record) => (
              <tr key={record.sys_id}>
                <td>
                  <Link to={`/access/users/${record.sys_id}`} className="reference-link">
                    {userLabel(record)}
                  </Link>
                </td>
                <td>
                  {record.first_name} {record.last_name}
                </td>
                <td>{record.email}</td>
              </tr>
            ))}
            {filteredRecords.length === 0 && (
              <tr>
                <td colSpan={COLUMNS.length} className="empty-state">
                  {isFiltered ? 'No records match this filter' : 'No users found'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
        <PaginationBar
          idPrefix="users-list"
          page={pagination.page}
          pageSize={pagination.pageSize}
          total={total}
          onPageChange={pagination.setPage}
          onPageSizeChange={pagination.setPageSize}
        />
      </div>
    </div>
  );
}
