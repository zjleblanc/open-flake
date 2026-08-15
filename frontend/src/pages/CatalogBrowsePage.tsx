import { useCallback, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { api, type CatalogItemSummary } from '../api/client';
import { usePageHeader } from '../components/PageHeaderContext';
import { useAuth } from '../auth/AuthContext';
import { CardViewIcon, FilterIcon, ListViewIcon } from '../components/NavIcons';
import { DeleteIcon, EditIcon } from '../components/DetailIcons';
import { ToggleSwitch } from '../components/DetailFieldControls';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { OFSelect } from '../components/OFSelect';
import { FloatingLabelField } from '../components/FloatingLabelField';
import {
  buildCatalogCategoryTree,
  UNCATEGORIZED_ID,
  type CatalogCategoryNode,
} from './catalogBrowseTree';
import './CatalogPages.css';

const ADMIN_ITEMS_QUERY_KEY = ['catalog-admin-items'];
const PUBLIC_ITEMS_QUERY_KEY = ['catalog-items'];

type CatalogManageHandlers = {
  onToggleActive: (item: CatalogItemSummary, active: boolean) => void;
  onRequestDelete: (item: CatalogItemSummary) => void;
};

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
  category: string[];
  onCategoryChange: (value: string[]) => void;
  categoryOptions: string[];
  subcategory: string[];
  onSubcategoryChange: (value: string[]) => void;
  subcategoryOptions: string[];
  onClear: () => void;
  isFiltered: boolean;
}) {
  return (
    <div className="catalog-search-bar">
      <span className="catalog-search-filter-icon" aria-hidden="true">
        <FilterIcon size={18} />
      </span>
      <FloatingLabelField
        id="catalog-search"
        label="Search by name"
        type="search"
        value={searchText}
        onChange={onSearchTextChange}
        className="catalog-search-input"
      />
      <OFSelect
        multiple
        className="catalog-filter-select"
        floatingLabel="Category"
        aria-label="Filter by category"
        value={category}
        onChange={(value) => onCategoryChange(value as string[])}
        options={categoryOptions.map((option) => ({ value: option, label: option }))}
      />
      <OFSelect
        multiple
        className="catalog-filter-select"
        floatingLabel="Subcategory"
        aria-label="Filter by subcategory"
        value={subcategory}
        onChange={(value) => onSubcategoryChange(value as string[])}
        disabled={subcategoryOptions.length === 0}
        options={subcategoryOptions.map((option) => ({ value: option, label: option }))}
      />
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

function CatalogManageActions({
  item,
  manage,
  stacked = false,
}: {
  item: CatalogItemSummary;
  manage: CatalogManageHandlers;
  stacked?: boolean;
}) {
  const active = item.active !== false;
  return (
    <span className={`catalog-manage-actions${stacked ? ' catalog-manage-actions--stacked' : ''}`}>
      <ToggleSwitch
        id={`catalog-manage-active-${item.sys_id}`}
        checked={active}
        onChange={(checked) => manage.onToggleActive(item, checked)}
        label="Active"
      />
      <span className="catalog-manage-actions-icons">
        <Link
          to={`/catalog/admin/${item.sys_id}`}
          className="btn-icon catalog-manage-edit"
          aria-label={`Edit ${item.name}`}
        >
          <EditIcon size={14} />
        </Link>
        <button
          type="button"
          className="btn-icon btn-icon-danger catalog-manage-delete"
          aria-label={`Delete ${item.name}`}
          onClick={() => manage.onRequestDelete(item)}
        >
          <DeleteIcon size={14} />
        </button>
      </span>
    </span>
  );
}

function CatalogCompactItemList({
  items,
  manage,
}: {
  items: CatalogItemSummary[];
  manage?: CatalogManageHandlers;
}) {
  return (
    <ul className="catalog-compact-item-list">
      {items.map((item) => {
        const inactive = Boolean(manage) && item.active === false;
        return (
          <li
            key={item.sys_id}
            className={`catalog-compact-item${inactive ? ' catalog-item--inactive' : ''}`}
          >
            <Link to={`/catalog/${item.sys_id}`} className="catalog-compact-item-link">
              <span className="catalog-compact-item-title">{item.name}</span>
              {item.short_description ? (
                <span className="catalog-compact-item-desc">{item.short_description}</span>
              ) : null}
            </Link>
            {manage ? <CatalogManageActions item={item} manage={manage} stacked /> : null}
          </li>
        );
      })}
    </ul>
  );
}

function CatalogCategoryCard({
  node,
  manage,
}: {
  node: CatalogCategoryNode;
  manage?: CatalogManageHandlers;
}) {
  return (
    <div className="card catalog-compact-category">
      <h2 className="catalog-compact-category-title">{node.label}</h2>
      {node.items.length > 0 ? <CatalogCompactItemList items={node.items} manage={manage} /> : null}
      {node.children.map((sub) => (
        <div key={sub.id} className="catalog-compact-subcategory">
          <h3 className="catalog-compact-subcategory-title">{sub.label}</h3>
          <CatalogCompactItemList items={sub.items} manage={manage} />
        </div>
      ))}
    </div>
  );
}

function CatalogItemCell({ item }: { item: CatalogItemSummary }) {
  return (
    <td className="catalog-item-table-item-cell">
      <Link to={`/catalog/${item.sys_id}`} className="catalog-item-table-item-link">
        <span className="catalog-item-title catalog-item-title--compact">{item.name}</span>
        {item.short_description ? (
          <span className="catalog-item-table-item-desc">{item.short_description}</span>
        ) : null}
      </Link>
    </td>
  );
}

function CatalogItemTableRows({
  items,
  manage,
}: {
  items: CatalogItemSummary[];
  manage?: CatalogManageHandlers;
}) {
  return (
    <table className="catalog-item-table catalog-item-table--compact">
      <tbody>
        {items.map((item) => {
          const inactive = Boolean(manage) && item.active === false;
          return (
            <tr key={item.sys_id} className={inactive ? 'catalog-item--inactive' : undefined}>
              <CatalogItemCell item={item} />
              {manage ? (
                <td className="catalog-item-table-manage-cell">
                  <CatalogManageActions item={item} manage={manage} />
                </td>
              ) : null}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function CatalogItemTable({
  items,
  manage,
}: {
  items: CatalogItemSummary[];
  manage?: CatalogManageHandlers;
}) {
  return (
    <div className="card catalog-item-table-card">
      <CatalogItemTableRows items={items} manage={manage} />
    </div>
  );
}

function GeneralItemsIcon({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="3" y="5" width="18" height="14" rx="2" stroke="currentColor" strokeWidth="2.5" />
      <circle cx="12" cy="12" r="2" fill="currentColor" />
    </svg>
  );
}

type CategoryTableRow = {
  item: CatalogItemSummary;
  subcategoryLabel: string;
  isGroupStart: boolean;
  groupSize: number;
};

function buildCategoryTableRows(node: CatalogCategoryNode): CategoryTableRow[] {
  const rows: CategoryTableRow[] = [];
  const appendGroup = (label: string, items: CatalogItemSummary[]) => {
    items.forEach((item, index) => {
      rows.push({
        item,
        subcategoryLabel: label,
        isGroupStart: index === 0,
        groupSize: items.length,
      });
    });
  };
  // Items filed directly under the category (no subcategory) form their own
  // unlabelled group, rendered before the labelled subcategory groups.
  if (node.items.length > 0) appendGroup('', node.items);
  for (const sub of node.children) {
    appendGroup(sub.label, sub.items);
  }
  return rows;
}

function CatalogCategoryGroupedTable({
  node,
  manage,
}: {
  node: CatalogCategoryNode;
  manage?: CatalogManageHandlers;
}) {
  const rows = buildCategoryTableRows(node);
  return (
    <div className="catalog-item-table-wrap">
      <table className="catalog-item-table catalog-item-table--compact catalog-item-table--grouped">
        <tbody>
          {rows.map(({ item, subcategoryLabel, isGroupStart, groupSize }) => {
            const inactive = Boolean(manage) && item.active === false;
            return (
              <tr key={item.sys_id} className={inactive ? 'catalog-item--inactive' : undefined}>
                {isGroupStart ? (
                  <td rowSpan={groupSize} className="catalog-item-table-subcategory-cell">
                    {subcategoryLabel ? (
                      <span className="catalog-item-table-subcategory-label">
                        {subcategoryLabel}
                      </span>
                    ) : (
                      <span
                        className="catalog-item-table-subcategory-general"
                        title="General (no subcategory)"
                        aria-label="General, no subcategory"
                      >
                        <GeneralItemsIcon />
                      </span>
                    )}
                  </td>
                ) : null}
                <CatalogItemCell item={item} />
                {manage ? (
                  <td className="catalog-item-table-manage-cell">
                    <CatalogManageActions item={item} manage={manage} />
                  </td>
                ) : null}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function CatalogCategoryListCard({
  node,
  manage,
}: {
  node: CatalogCategoryNode;
  manage?: CatalogManageHandlers;
}) {
  return (
    <div className="card catalog-compact-category">
      <h2 className="catalog-compact-category-title">{node.label}</h2>
      <CatalogCategoryGroupedTable node={node} manage={manage} />
    </div>
  );
}

function CatalogBrowseResults({
  nodes,
  view,
  manage,
}: {
  nodes: CatalogCategoryNode[];
  view: CatalogBrowseView;
  manage?: CatalogManageHandlers;
}) {
  const flattenUncategorized =
    nodes.length === 1 && nodes[0].id === UNCATEGORIZED_ID && nodes[0].children.length === 0;

  if (flattenUncategorized) {
    return view === 'card' ? (
      <CatalogCompactItemList items={nodes[0].items} manage={manage} />
    ) : (
      <CatalogItemTable items={nodes[0].items} manage={manage} />
    );
  }

  if (view === 'card') {
    return (
      <div className="catalog-compact-grid">
        {nodes.map((node) => (
          <CatalogCategoryCard key={node.id} node={node} manage={manage} />
        ))}
      </div>
    );
  }

  return (
    <div className="catalog-compact-list-stack">
      {nodes.map((node) => (
        <CatalogCategoryListCard key={node.id} node={node} manage={manage} />
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
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [view, setView] = useState<CatalogBrowseView>(readStoredView);
  const [searchText, setSearchText] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string[]>([]);
  const [subcategoryFilter, setSubcategoryFilter] = useState<string[]>([]);
  const [managing, setManaging] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<CatalogItemSummary | null>(null);

  const onViewChange = useCallback((next: CatalogBrowseView) => {
    setView(next);
    try {
      localStorage.setItem(VIEW_STORAGE_KEY, next);
    } catch {
      // Ignore unavailable storage.
    }
  }, []);

  const createMutation = useMutation({
    mutationFn: () => api.adminCreateCatalogItem({}),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ADMIN_ITEMS_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: PUBLIC_ITEMS_QUERY_KEY });
      navigate(`/catalog/admin/${res.result.sys_id}`);
    },
  });

  const toggleActiveMutation = useMutation({
    mutationFn: ({ sys_id, active }: { sys_id: string; active: boolean }) =>
      api.adminUpdateCatalogItem(sys_id, { active }),
    onMutate: async ({ sys_id, active }) => {
      await queryClient.cancelQueries({ queryKey: ADMIN_ITEMS_QUERY_KEY });
      const previous = queryClient.getQueryData<{ result: CatalogItemSummary[] }>(
        ADMIN_ITEMS_QUERY_KEY,
      );
      if (previous) {
        queryClient.setQueryData(ADMIN_ITEMS_QUERY_KEY, {
          result: previous.result.map((entry) =>
            entry.sys_id === sys_id ? { ...entry, active } : entry,
          ),
        });
      }
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) queryClient.setQueryData(ADMIN_ITEMS_QUERY_KEY, context.previous);
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ADMIN_ITEMS_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: PUBLIC_ITEMS_QUERY_KEY });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (sys_id: string) => api.adminDeleteCatalogItem(sys_id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ADMIN_ITEMS_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: PUBLIC_ITEMS_QUERY_KEY });
      setPendingDelete(null);
    },
  });

  const createItem = createMutation.mutate;
  const creatingItem = createMutation.isPending;

  const headerActions = useMemo(() => {
    if (!canAdmin) return null;
    return (
      <>
        {managing ? (
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => createItem()}
            disabled={creatingItem}
          >
            {creatingItem ? 'Creating…' : 'Create'}
          </button>
        ) : null}
        <button
          type="button"
          className={managing ? 'btn btn-secondary' : 'btn btn-primary'}
          onClick={() => setManaging((prev) => !prev)}
        >
          {managing ? 'Done' : 'Manage'}
        </button>
      </>
    );
  }, [canAdmin, managing, createItem, creatingItem]);

  usePageHeader({
    breadcrumbs: [{ label: 'Service Catalog' }],
    actions: headerActions,
  });

  const { data, isLoading, error } = useQuery({
    queryKey: managing ? ADMIN_ITEMS_QUERY_KEY : PUBLIC_ITEMS_QUERY_KEY,
    queryFn: () => (managing ? api.adminListCatalogItems() : api.listCatalogItems()),
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
          .filter(
            (i) => categoryFilter.length === 0 || categoryFilter.includes(i.category?.trim() || ''),
          )
          .map((i) => i.subcategory),
      ),
    [items, categoryFilter],
  );

  const handleCategoryChange = useCallback(
    (next: string[]) => {
      setCategoryFilter(next);
      if (subcategoryFilter.length > 0) {
        const stillValid = subcategoryFilter.filter((sub) =>
          (items || []).some(
            (i) =>
              i.subcategory?.trim() === sub &&
              (next.length === 0 || next.includes(i.category?.trim() || '')),
          ),
        );
        if (stillValid.length !== subcategoryFilter.length) setSubcategoryFilter(stillValid);
      }
    },
    [items, subcategoryFilter],
  );

  const handleSubcategoryChange = useCallback(
    (next: string[]) => {
      setSubcategoryFilter(next);
      // If no category is selected yet, infer it from the chosen subcategories
      // when they unambiguously belong to a single category.
      if (next.length > 0 && categoryFilter.length === 0) {
        const owningCategories = sortedUnique(
          (items || [])
            .filter((i) => next.includes(i.subcategory?.trim() || ''))
            .map((i) => i.category),
        );
        if (owningCategories.length === 1) {
          setCategoryFilter(owningCategories);
        }
      }
    },
    [items, categoryFilter],
  );

  const isFiltered = Boolean(
    searchText.trim() || categoryFilter.length > 0 || subcategoryFilter.length > 0,
  );

  const clearFilters = useCallback(() => {
    setSearchText('');
    setCategoryFilter([]);
    setSubcategoryFilter([]);
  }, []);

  const filteredItems = useMemo(() => {
    const query = searchText.trim().toLowerCase();
    return (items || []).filter((item) => {
      if (query && !item.name.toLowerCase().includes(query)) return false;
      if (categoryFilter.length > 0 && !categoryFilter.includes(item.category?.trim() || ''))
        return false;
      if (
        subcategoryFilter.length > 0 &&
        !subcategoryFilter.includes(item.subcategory?.trim() || '')
      )
        return false;
      return true;
    });
  }, [items, searchText, categoryFilter, subcategoryFilter]);

  const tree = useMemo(() => buildCatalogCategoryTree(filteredItems), [filteredItems]);

  const manageHandlers: CatalogManageHandlers | undefined = managing
    ? {
        onToggleActive: (item, active) =>
          toggleActiveMutation.mutate({ sys_id: item.sys_id, active }),
        onRequestDelete: (item) => setPendingDelete(item),
      }
    : undefined;

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
        <CatalogBrowseResults nodes={tree} view={view} manage={manageHandlers} />
      )}
      <ConfirmDialog
        open={Boolean(pendingDelete)}
        title="Delete catalog item"
        message={
          pendingDelete
            ? `Are you sure you want to delete "${pendingDelete.name}"? This action cannot be undone.`
            : ''
        }
        error={deleteMutation.error ? (deleteMutation.error as Error).message : null}
        isPending={deleteMutation.isPending}
        onConfirm={() => {
          if (pendingDelete) deleteMutation.mutate(pendingDelete.sys_id);
        }}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );
}
