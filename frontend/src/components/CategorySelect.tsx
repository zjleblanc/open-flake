import { useEffect, useRef, useState } from 'react';
import '../pages/CatalogPages.css';

const NEW_OPTION_VALUE = '__new__';

interface CategorySelectProps {
  id: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
  placeholder: string;
  newEntryLabel: string;
  disabled?: boolean;
  disabledPlaceholder?: string;
}

export function CategorySelect({
  id,
  value,
  options,
  onChange,
  placeholder,
  newEntryLabel,
  disabled = false,
  disabledPlaceholder,
}: CategorySelectProps) {
  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState('');
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (disabled) setCreating(false);
  }, [disabled]);

  useEffect(() => {
    if (!creating) return;
    function handleClickOutside(event: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setCreating(false);
      }
    }
    function handleEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') setCreating(false);
    }
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [creating]);

  function confirmCreate() {
    const next = draft.trim();
    if (!next) return;
    onChange(next);
    setCreating(false);
    setDraft('');
  }

  function cancelCreate() {
    setCreating(false);
    setDraft('');
  }

  const mergedOptions = value && !options.includes(value) ? [value, ...options] : options;

  return (
    <div className="category-select" ref={wrapperRef}>
      <select
        id={id}
        value={value || ''}
        disabled={disabled}
        onChange={(e) => {
          if (e.target.value === NEW_OPTION_VALUE) {
            setDraft('');
            setCreating(true);
          } else {
            onChange(e.target.value);
          }
        }}
      >
        <option value="">{disabled ? disabledPlaceholder || placeholder : placeholder}</option>
        {mergedOptions.map((opt) => (
          <option key={opt} value={opt}>
            {opt}
          </option>
        ))}
        {!disabled ? <option value={NEW_OPTION_VALUE}>+ New {newEntryLabel}</option> : null}
      </select>
      {creating ? (
        <div className="category-select-popover" role="dialog" aria-label={`New ${newEntryLabel}`}>
          <input
            autoFocus
            value={draft}
            placeholder={`New ${newEntryLabel} name`}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                confirmCreate();
              }
            }}
          />
          <div className="category-select-popover-actions">
            <button type="button" className="btn btn-secondary btn-sm" onClick={cancelCreate}>
              Cancel
            </button>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={confirmCreate}
              disabled={!draft.trim()}
            >
              Create
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
