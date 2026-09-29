import { OFSelect } from './OFSelect';
import { PAGE_SIZE_OPTIONS } from '../hooks/useServerPagination';
import './PaginationBar.css';

interface PaginationBarProps {
  /** 0-indexed current page. */
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  idPrefix: string;
}

/** Shared "Showing X-Y of Z" + page-size selector + prev/next controls for server-paginated
 * list tables. See `useServerPagination` for the state this renders. */
export function PaginationBar({
  page,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
  idPrefix,
}: PaginationBarProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const currentPage = Math.min(page, totalPages - 1);
  const startItem = total === 0 ? 0 : currentPage * pageSize + 1;
  const endItem = total === 0 ? 0 : Math.min(total, (currentPage + 1) * pageSize);

  return (
    <div className="pagination-bar">
      <div className="pagination-bar-size">
        <label htmlFor={`${idPrefix}-page-size`}>Rows per page</label>
        <OFSelect
          id={`${idPrefix}-page-size`}
          size="sm"
          className="pagination-bar-size-select"
          value={String(pageSize)}
          onChange={(value) => onPageSizeChange(Number(value))}
          options={PAGE_SIZE_OPTIONS.map((size) => ({ value: String(size), label: String(size) }))}
        />
      </div>
      <span className="pagination-bar-info">
        {total === 0 ? 'No records' : `Showing ${startItem}-${endItem} of ${total}`}
      </span>
      <div className="pagination-bar-controls">
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage <= 0}
        >
          Previous
        </button>
        <span className="pagination-bar-page">
          Page {currentPage + 1} of {totalPages}
        </span>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage >= totalPages - 1}
        >
          Next
        </button>
      </div>
    </div>
  );
}
