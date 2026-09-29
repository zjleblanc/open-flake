import { useCallback, useMemo, useState } from 'react';

export type SortDirection = 'asc' | 'desc';

/** Page-size choices offered across every paginated list view. */
export const PAGE_SIZE_OPTIONS = [10, 25, 50, 100] as const;
export const DEFAULT_PAGE_SIZE = 25;

/** Every list defaults to the most-recently-updated records first. */
export const DEFAULT_SORT_FIELD = 'sys_updated_on';
export const DEFAULT_SORT_DIRECTION: SortDirection = 'desc';

interface ServerPaginationOptions {
  defaultSortField?: string;
  defaultSortDirection?: SortDirection;
  defaultPageSize?: number;
}

interface ServerPaginationState {
  page: number;
  pageSize: number;
  sortField: string;
  sortDirection: SortDirection;
}

export interface ServerPagination extends ServerPaginationState {
  /** `limit`/`offset` derived from the current page + page size, ready to pass to `api.listRecords`. */
  limit: number;
  offset: number;
  setPage: (page: number) => void;
  setPageSize: (pageSize: number) => void;
  /** Click handler for a sortable column header: toggles asc/desc if it's already the active
   * sort column, otherwise switches to that column ascending. Always resets to page 0. */
  toggleSort: (field: string) => void;
}

/**
 * Shared pagination + sort state for server-driven list views (`RecordListPage`, `UsersPage`,
 * `GroupsListPage`). Consumers pass `limit`/`offset`/`sysparm_orderby(desc)` to `api.listRecords`
 * and key their query on the returned state so TanStack Query refetches on every change.
 */
export function useServerPagination(options?: ServerPaginationOptions): ServerPagination {
  const defaultPageSize = options?.defaultPageSize ?? DEFAULT_PAGE_SIZE;
  const defaultSortField = options?.defaultSortField ?? DEFAULT_SORT_FIELD;
  const defaultSortDirection = options?.defaultSortDirection ?? DEFAULT_SORT_DIRECTION;

  const [state, setState] = useState<ServerPaginationState>({
    page: 0,
    pageSize: defaultPageSize,
    sortField: defaultSortField,
    sortDirection: defaultSortDirection,
  });

  const setPage = useCallback((page: number) => {
    setState((current) => ({ ...current, page: Math.max(0, page) }));
  }, []);

  const setPageSize = useCallback((pageSize: number) => {
    setState((current) => ({ ...current, pageSize, page: 0 }));
  }, []);

  const toggleSort = useCallback((field: string) => {
    setState((current) => {
      if (current.sortField === field) {
        return {
          ...current,
          sortDirection: current.sortDirection === 'asc' ? 'desc' : 'asc',
          page: 0,
        };
      }
      return { ...current, sortField: field, sortDirection: 'asc', page: 0 };
    });
  }, []);

  const limit = state.pageSize;
  const offset = useMemo(() => state.page * state.pageSize, [state.page, state.pageSize]);

  return { ...state, limit, offset, setPage, setPageSize, toggleSort };
}
