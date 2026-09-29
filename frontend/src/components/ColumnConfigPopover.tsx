import { useEffect, useMemo, useState } from 'react';
import type { ListColumn } from '../pages/RecordListPage';
import {
  ChevronDownIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ChevronUpIcon,
  SettingsIcon,
} from './DetailIcons';
import { Portal } from './Portal';
import './ColumnConfigPopover.css';

interface ColumnConfigPopoverProps {
  /** Human-readable resource label used in the trigger's aria-label, e.g. "Incidents". */
  title: string;
  /** Every column that can be shown for this resource, in catalog order. The first entry is
   * treated as the pinned link column (e.g. Number) and is always shown, first, non-removable. */
  allColumns: ListColumn[];
  /** The columns currently being displayed (saved preference, or defaults if unset). */
  currentColumns: ListColumn[];
  /** Persists an ordered list of column keys (including the pinned column) as the resource's
   * saved column configuration. */
  onSave: (keys: string[]) => void;
  /** Clears any saved column override for this resource, reverting it to the page's defaults. */
  onReset: () => void;
}

/** Icon-triggered popover letting a user choose and reorder which columns a resource's list
 * table displays, persisted per-user via `UserPreferencesContext`. */
export function ColumnConfigPopover({
  title,
  allColumns,
  currentColumns,
  onSave,
  onReset,
}: ColumnConfigPopoverProps) {
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const [leftChecked, setLeftChecked] = useState<Set<string>>(new Set());
  const [rightChecked, setRightChecked] = useState<Set<string>>(new Set());

  const pinned = allColumns[0];
  const movableColumns = useMemo(
    () => allColumns.filter((column) => column.key !== pinned?.key),
    [allColumns, pinned],
  );
  const columnLabels = useMemo(() => {
    const map = new Map<string, string>();
    for (const column of allColumns) map.set(column.key, column.label);
    return map;
  }, [allColumns]);

  // Re-stage the working selection from the currently displayed columns every time the popover
  // opens, so edits made and cancelled in a prior session don't leak into the next one.
  useEffect(() => {
    if (!open) return;
    setSelected(
      currentColumns.filter((column) => column.key !== pinned?.key).map((column) => column.key),
    );
    setLeftChecked(new Set());
    setRightChecked(new Set());
  }, [open, currentColumns, pinned]);

  useEffect(() => {
    if (!open) return;

    function handleEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false);
    }

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [open]);

  const selectedSet = useMemo(() => new Set(selected), [selected]);
  const leftItems = movableColumns.filter((column) => !selectedSet.has(column.key));
  const rightItems = useMemo(
    () => selected.map((key) => ({ key, label: columnLabels.get(key) ?? key })),
    [selected, columnLabels],
  );

  function toggleChecked(setChecked: (updater: (current: Set<string>) => Set<string>) => void) {
    return (key: string) => {
      setChecked((current) => {
        const next = new Set(current);
        if (next.has(key)) next.delete(key);
        else next.add(key);
        return next;
      });
    };
  }

  const toggleLeft = toggleChecked(setLeftChecked);
  const toggleRight = toggleChecked(setRightChecked);

  function pushRight() {
    if (leftChecked.size === 0) return;
    const toAdd = leftItems
      .filter((column) => leftChecked.has(column.key))
      .map((column) => column.key);
    setSelected((current) => [...current, ...toAdd]);
    setLeftChecked(new Set());
  }

  function pushLeft() {
    if (rightChecked.size === 0) return;
    setSelected((current) => current.filter((key) => !rightChecked.has(key)));
    setRightChecked(new Set());
  }

  function moveSelected(offset: -1 | 1) {
    if (rightChecked.size !== 1) return;
    const [key] = rightChecked;
    setSelected((current) => {
      const index = current.indexOf(key);
      const target = index + offset;
      if (index < 0 || target < 0 || target >= current.length) return current;
      const next = [...current];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  }

  function handleSave() {
    onSave(pinned ? [pinned.key, ...selected] : selected);
    setOpen(false);
  }

  function handleReset() {
    onReset();
    setOpen(false);
  }

  return (
    <div className="column-config-popover-root">
      <button
        type="button"
        className={`column-config-popover-trigger${open ? ' active' : ''}`}
        aria-label={`Configure ${title} columns`}
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => setOpen((prev) => !prev)}
      >
        <SettingsIcon size={18} />
      </button>

      {open && (
        <Portal>
          <div
            className="column-config-popover-overlay"
            role="presentation"
            onClick={() => setOpen(false)}
          >
            <div
              className="column-config-popover"
              role="dialog"
              aria-label={`Configure ${title} columns`}
              onClick={(event) => event.stopPropagation()}
            >
              <div className="column-config-popover-header">
                <h2>Configure Columns</h2>
                <button
                  type="button"
                  className="column-config-popover-close"
                  aria-label="Close"
                  onClick={() => setOpen(false)}
                >
                  ×
                </button>
              </div>

              <div className="column-config-lists">
                <div className="column-config-list-panel">
                  <h3>Available Columns</h3>
                  <ul className="column-config-list" aria-label="Available columns">
                    {leftItems.map((column) => (
                      <li key={column.key}>
                        <label className="column-config-list-item">
                          <input
                            type="checkbox"
                            checked={leftChecked.has(column.key)}
                            onChange={() => toggleLeft(column.key)}
                          />
                          <span>{column.label}</span>
                        </label>
                      </li>
                    ))}
                    {leftItems.length === 0 && (
                      <li className="column-config-list-empty">All columns selected</li>
                    )}
                  </ul>
                </div>

                <div className="column-config-move-controls">
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    aria-label="Add selected columns"
                    onClick={pushRight}
                    disabled={leftChecked.size === 0}
                  >
                    <ChevronRightIcon size={16} />
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    aria-label="Remove selected columns"
                    onClick={pushLeft}
                    disabled={rightChecked.size === 0}
                  >
                    <ChevronLeftIcon size={16} />
                  </button>
                </div>

                <div className="column-config-list-panel">
                  <h3>Selected Columns</h3>
                  <ul className="column-config-list" aria-label="Selected columns">
                    {pinned && (
                      <li className="column-config-list-item column-config-list-item--pinned">
                        <span>{pinned.label}</span>
                        <span className="column-config-pinned-badge">Always shown</span>
                      </li>
                    )}
                    {rightItems.map((column) => (
                      <li key={column.key}>
                        <label className="column-config-list-item">
                          <input
                            type="checkbox"
                            checked={rightChecked.has(column.key)}
                            onChange={() => toggleRight(column.key)}
                          />
                          <span>{column.label}</span>
                        </label>
                      </li>
                    ))}
                    {rightItems.length === 0 && (
                      <li className="column-config-list-empty">No columns selected</li>
                    )}
                  </ul>
                </div>

                <div className="column-config-reorder-controls">
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    aria-label="Move column up"
                    onClick={() => moveSelected(-1)}
                    disabled={rightChecked.size !== 1}
                  >
                    <ChevronUpIcon size={16} />
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    aria-label="Move column down"
                    onClick={() => moveSelected(1)}
                    disabled={rightChecked.size !== 1}
                  >
                    <ChevronDownIcon size={16} />
                  </button>
                </div>
              </div>

              <div className="column-config-popover-actions">
                <button type="button" className="btn btn-secondary" onClick={handleReset}>
                  Reset to Default
                </button>
                <div className="column-config-popover-actions-right">
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => setOpen(false)}
                  >
                    Cancel
                  </button>
                  <button type="button" className="btn btn-primary" onClick={handleSave}>
                    Save
                  </button>
                </div>
              </div>
            </div>
          </div>
        </Portal>
      )}
    </div>
  );
}
