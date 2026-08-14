import { useCallback, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api, type CatalogItemSummary } from '../api/client';
import { usePageHeader } from '../components/PageHeaderContext';
import { useAuth } from '../auth/AuthContext';
import { CardViewIcon, ListViewIcon } from '../components/NavIcons';
import {
  buildCatalogCategoryTree,
  countCatalogItems,
  UNCATEGORIZED_ID,
  type CatalogCategoryNode,
} from './catalogBrowseTree';
import './CatalogPages.css';

export type CatalogBrowseView = 'card' | 'list';

const VIEW_STORAGE_KEY = 'openflake.catalog.browseView';

function readStoredView(): CatalogBrowseView {
  try {
    const stored = localStorage.getItem(VIEW_STORAGE_KEY);
    if (stored === 'card' || stored === 'list') return stored;
  } catch {
    // Ignore unavailable storage.
  }
  return 'card';
}

function CatalogViewToggle({
  view,
  onChange,
}: {
  view: CatalogBrowseView;
  onChange: (view: CatalogBrowseView) => void;
}) {
  return (
    <div className="catalog-view-toggle" role="radiogroup" aria-label="Catalog layout">
      <button
        type="button"
        role="radio"
        aria-checked={view === 'card'}
        aria-label="Card view"
        className={`catalog-view-toggle-option${view === 'card' ? ' catalog-view-toggle-option--active' : ''}`}
        onClick={() => onChange('card')}
      >
        <CardViewIcon size={16} />
      </button>
      <button
        type="button"
        role="radio"
        aria-checked={view === 'list'}
        aria-label="List view"
        className={`catalog-view-toggle-option${view === 'list' ? ' catalog-view-toggle-option--active' : ''}`}
        onClick={() => onChange('list')}
      >
        <ListViewIcon size={16} />
      </button>
    </div>
  );
}

function CatalogItemCopy({ item }: { item: CatalogItemSummary }) {
  return (
    <>
      <h3 className="catalog-item-title">{item.name}</h3>
      {item.short_description ? (
        <p className="catalog-item-description">{item.short_description}</p>
      ) : null}
    </>
  );
}

function CatalogCardGrid({ items }: { items: CatalogItemSummary[] }) {
  return (
    <div className="catalog-card-grid">
      {items.map((item) => (
        <Link key={item.sys_id} to={`/catalog/${item.sys_id}`} className="catalog-card">
          <CatalogItemCopy item={item} />
        </Link>
      ))}
    </div>
  );
}

function CatalogItemTable({ items }: { items: CatalogItemSummary[] }) {
  return (
    <div className="card catalog-item-table-card">
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Short description</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.sys_id}>
              <td>
                <Link to={`/catalog/${item.sys_id}`} className="catalog-item-title-link">
                  <span className="catalog-item-title catalog-item-title--compact">
                    {item.name}
                  </span>
                </Link>
              </td>
              <td>
                {item.short_description ? (
                  <p className="catalog-item-description">{item.short_description}</p>
                ) : (
                  <span className="empty-value">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CategoryToggleIcon() {
  return (
    <svg width={14} height={14} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M6 9l6 6 6-6"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function CatalogCategorySection({
  node,
  view,
  nested = false,
}: {
  node: CatalogCategoryNode;
  view: CatalogBrowseView;
  nested?: boolean;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const total = countCatalogItems(node);
  const hasChildren = node.children.length > 0;

  return (
    <section className={`catalog-category${nested ? ' catalog-category--nested' : ''}`}>
      <button
        type="button"
        className="catalog-category-header"
        aria-expanded={!collapsed}
        onClick={() => setCollapsed((prev) => !prev)}
      >
        <h2 className="catalog-category-title">{node.label}</h2>
        <span className="catalog-category-header-trailing">
          {collapsed ? <span className="catalog-category-count">{total}</span> : null}
          <span
            className={`catalog-category-toggle${collapsed ? ' catalog-category-toggle--collapsed' : ''}`}
          >
            <CategoryToggleIcon />
          </span>
        </span>
      </button>
      {!collapsed ? (
        <>
          {node.items.length > 0 ? (
            <div
              className={`catalog-category-items${hasChildren ? ' catalog-category-items--indented' : ''}`}
            >
              {view === 'card' ? (
                <CatalogCardGrid items={node.items} />
              ) : (
                <CatalogItemTable items={node.items} />
              )}
            </div>
          ) : null}
          {hasChildren ? (
            <div className="catalog-category-children">
              {node.children.map((child) => (
                <CatalogCategorySection key={child.id} node={child} view={view} nested />
              ))}
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}

function CatalogBrowseResults({
  nodes,
  view,
}: {
  nodes: CatalogCategoryNode[];
  view: CatalogBrowseView;
}) {
  const flattenUncategorized =
    nodes.length === 1 && nodes[0].id === UNCATEGORIZED_ID && nodes[0].children.length === 0;

  if (flattenUncategorized) {
    return view === 'card' ? (
      <CatalogCardGrid items={nodes[0].items} />
    ) : (
      <CatalogItemTable items={nodes[0].items} />
    );
  }

  return (
    <div className="catalog-category-tree">
      {nodes.map((node) => (
        <CatalogCategorySection key={node.id} node={node} view={view} />
      ))}
    </div>
  );
}

export function CatalogBrowsePage() {
  const { hasPermission } = useAuth();
  const canAdmin = hasPermission('records.*.write');
  const [view, setView] = useState<CatalogBrowseView>(readStoredView);

  const onViewChange = useCallback((next: CatalogBrowseView) => {
    setView(next);
    try {
      localStorage.setItem(VIEW_STORAGE_KEY, next);
    } catch {
      // Ignore unavailable storage.
    }
  }, []);

  const headerActions = useMemo(
    () =>
      canAdmin ? (
        <Link to="/catalog/admin" className="btn btn-primary">
          Manage
        </Link>
      ) : null,
    [canAdmin],
  );

  usePageHeader({
    breadcrumbs: [{ label: 'Service Catalog' }],
    actions: headerActions,
  });

  const { data, isLoading, error } = useQuery({
    queryKey: ['catalog-items'],
    queryFn: () => api.listCatalogItems(),
  });

  const items = data?.result;
  const tree = useMemo(() => buildCatalogCategoryTree(items || []), [items]);

  return (
    <div className="catalog-browse">
      <div className="section-header-row">
        <p className="catalog-browse-intro">Browse available services and submit requests.</p>
        <CatalogViewToggle view={view} onChange={onViewChange} />
      </div>
      {isLoading ? (
        <p className="empty-state">Loading catalog…</p>
      ) : error ? (
        <p className="error">{(error as Error).message}</p>
      ) : !items?.length ? (
        <p className="empty-state">No catalog items yet</p>
      ) : (
        <CatalogBrowseResults nodes={tree} view={view} />
      )}
    </div>
  );
}
