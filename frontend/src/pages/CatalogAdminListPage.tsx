import { useMemo } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { usePageHeader } from '../components/PageHeaderContext';
import './CatalogPages.css';

export function CatalogAdminListPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const {
    data,
    isLoading,
    error: loadError,
  } = useQuery({
    queryKey: ['catalog-admin-items'],
    queryFn: () => api.adminListCatalogItems(),
  });

  const createMutation = useMutation({
    mutationFn: () => api.adminCreateCatalogItem({}),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['catalog-admin-items'] });
      queryClient.invalidateQueries({ queryKey: ['catalog-items'] });
      navigate(`/catalog/admin/${res.result.sys_id}`);
    },
  });

  const createItem = createMutation.mutate;
  const creating = createMutation.isPending;
  const createError = createMutation.error;

  const headerActions = useMemo(
    () => (
      <>
        <Link to="/catalog" className="btn btn-secondary">
          Browse
        </Link>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => createItem()}
          disabled={creating}
        >
          {creating ? 'Creating…' : 'Create'}
        </button>
      </>
    ),
    [createItem, creating],
  );

  usePageHeader({
    breadcrumbs: [{ label: 'Service Catalog', to: '/catalog' }, { label: 'Manage' }],
    actions: headerActions,
  });

  if (isLoading) return <p className="empty-state">Loading…</p>;
  if (loadError) return <p className="error">{(loadError as Error).message}</p>;

  const items = data?.result || [];

  return (
    <div className="catalog-admin-list">
      {createError ? <p className="error">{(createError as Error).message}</p> : null}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Category</th>
              <th>Active</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={4} className="empty-state">
                  No catalog items yet
                </td>
              </tr>
            ) : (
              items.map((item) => (
                <tr key={item.sys_id}>
                  <td>{item.name}</td>
                  <td>{item.category || '—'}</td>
                  <td>{item.active === false ? 'No' : 'Yes'}</td>
                  <td>
                    <Link to={`/catalog/admin/${item.sys_id}`} className="btn btn-secondary btn-sm">
                      Edit
                    </Link>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
