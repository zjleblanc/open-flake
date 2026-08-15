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

function CatalogSearchBar({
  searchText,
  onSearchTextChange,
  category,
  onCategoryChange,
  categoryOptions,
  subcategory,
  onSubcategoryChange,
  subcategoryOptions,
  onClear,
  isFiltered,
}: {
  searchText: string;
  onSearchTextChange: (value: string) => void;
  category: string;
  onCategoryChange: (value: string) => void;
  categoryOptions: string[];
  subcategory: string;
  onSubcategoryChange: (value: string) => void;
  subcategoryOptions: string[];
  onClear: () => void;
  isFiltered: boolean;
}) {
  return (
    <div className="catalog-search-bar">
      <input
        type="search"
        value={searchText}
        onChange={(event) => onSearchTextChange(event.target.value)}
        placeholder="Search services by name…"
        aria-label="Search services by name"
        className="catalog-search-input"
      />
      <select
        value={category}
        onChange={(event) => onCategoryChange(event.target.value)}
        aria-label="Filter by category"
      >
        <option value="">All categories</option>
        {categoryOptions.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
      <select
        value={subcategory}
        onChange={(event) => onSubcategoryChange(event.target.value)}
        aria-label="Filter by subcategory"
        disabled={subcategoryOptions.length === 0}
      >
        <option value="">All subcategories</option>
        {subcategoryOptions.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
      {isFiltered ? (
        <button type="button" className="btn btn-secondary btn-sm" onClick={onClear}>
          Clear
        </button>
      ) : null}
    </div>
  );
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

function CatalogCompactItemList({ items }: { items: CatalogItemSummary[] }) {
  return (
    <ul className="catalog-compact-item-list">
      {items.map((item) => (
        <li key={item.sys_id} className="catalog-compact-item">
          <Link to={`/catalog/${item.sys_id}`} className="catalog-compact-item-link">
            <span className="catalog-compact-item-title">{item.name}</span>
            {item.short_description ? (
              <span className="catalog-compact-item-desc">{item.short_description}</span>
            ) : null}
          </Link>
        </li>
      ))}
    </ul>
  );
}

function CatalogCategoryCard({ node }: { node: CatalogCategoryNode }) {
  return (
    <div className="card catalog-compact-category">
      <h2 className="catalog-compact-category-title">{node.label}</h2>
      {node.items.length > 0 ? <CatalogCompactItemList items={node.items} /> : null}
      {node.children.map((sub) => (
        <div key={sub.id} className="catalog-compact-subcategory">
          <h3 className="catalog-compact-subcategory-title">{sub.label}</h3>
          <CatalogCompactItemList items={sub.items} />
        </div>
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
  nested = false,
}: {
  node: CatalogCategoryNode;
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
              <CatalogItemTable items={node.items} />
            </div>
          ) : null}
          {hasChildren ? (
            <div className="catalog-category-children">
              {node.children.map((child) => (
                <CatalogCategorySection key={child.id} node={child} nested />
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
      <CatalogCompactItemList items={nodes[0].items} />
    ) : (
      <CatalogItemTable items={nodes[0].items} />
    );
  }

  if (view === 'card') {
    return (
      <div className="catalog-compact-grid">
        {nodes.map((node) => (
          <CatalogCategoryCard key={node.id} node={node} />
        ))}
      </div>
    );
  }

  return (
    <div className="catalog-category-tree">
      {nodes.map((node) => (
        <CatalogCategorySection key={node.id} node={node} />
      ))}
    </div>
  );
}

function sortedUnique(values: (string | undefined)[]): string[] {
  const set = new Set<string>();
  for (const value of values) {
    const trimmed = value?.trim();
    if (trimmed) set.add(trimmed);
  }
  return [...set].sort((a, b) => a.localeCompare(b));
}

export function CatalogBrowsePage() {
  const { hasPermission } = useAuth();
  const canAdmin = hasPermission('records.*.write');
  const [view, setView] = useState<CatalogBrowseView>(readStoredView);
  const [searchText, setSearchText] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [subcategoryFilter, setSubcategoryFilter] = useState('');

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

  const categoryOptions = useMemo(
    () => sortedUnique((items || []).map((i) => i.category)),
    [items],
  );

  const subcategoryOptions = useMemo(
    () =>
      sortedUnique(
        (items || [])
          .filter((i) => !categoryFilter || i.category?.trim() === categoryFilter)
          .map((i) => i.subcategory),
      ),
    [items, categoryFilter],
  );

  const handleCategoryChange = useCallback(
    (next: string) => {
      setCategoryFilter(next);
      if (subcategoryFilter) {
        const stillValid = (items || []).some(
          (i) =>
            i.subcategory?.trim() === subcategoryFilter && (!next || i.category?.trim() === next),
        );
        if (!stillValid) setSubcategoryFilter('');
      }
    },
    [items, subcategoryFilter],
  );

  const handleSubcategoryChange = useCallback(
    (next: string) => {
      setSubcategoryFilter(next);
      // If no category is selected yet, infer it from the chosen subcategory
      // when it unambiguously belongs to a single category.
      if (next && !categoryFilter) {
        const owningCategories = sortedUnique(
          (items || []).filter((i) => i.subcategory?.trim() === next).map((i) => i.category),
        );
        if (owningCategories.length === 1) {
          setCategoryFilter(owningCategories[0]);
        }
      }
    },
    [items, categoryFilter],
  );

  const isFiltered = Boolean(searchText.trim() || categoryFilter || subcategoryFilter);

  const clearFilters = useCallback(() => {
    setSearchText('');
    setCategoryFilter('');
    setSubcategoryFilter('');
  }, []);

  const filteredItems = useMemo(() => {
    const query = searchText.trim().toLowerCase();
    return (items || []).filter((item) => {
      if (query && !item.name.toLowerCase().includes(query)) return false;
      if (categoryFilter && item.category?.trim() !== categoryFilter) return false;
      if (subcategoryFilter && item.subcategory?.trim() !== subcategoryFilter) return false;
      return true;
    });
  }, [items, searchText, categoryFilter, subcategoryFilter]);

  const tree = useMemo(() => buildCatalogCategoryTree(filteredItems), [filteredItems]);

  return (
    <div className="catalog-browse">
      <div className="section-header-row">
        <CatalogSearchBar
          searchText={searchText}
          onSearchTextChange={setSearchText}
          category={categoryFilter}
          onCategoryChange={handleCategoryChange}
          categoryOptions={categoryOptions}
          subcategory={subcategoryFilter}
          onSubcategoryChange={handleSubcategoryChange}
          subcategoryOptions={subcategoryOptions}
          onClear={clearFilters}
          isFiltered={isFiltered}
        />
        <CatalogViewToggle view={view} onChange={onViewChange} />
      </div>
      {isLoading ? (
        <p className="empty-state">Loading catalog…</p>
      ) : error ? (
        <p className="error">{(error as Error).message}</p>
      ) : !items?.length ? (
        <p className="empty-state">No catalog items yet</p>
      ) : !filteredItems.length ? (
        <p className="empty-state">No services match your search</p>
      ) : (
        <CatalogBrowseResults nodes={tree} view={view} />
      )}
    </div>
  );
}
