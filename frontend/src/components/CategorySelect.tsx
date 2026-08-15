import { useEffect, useRef, useState } from 'react';
import { OFSelect, type OFSelectOption } from './OFSelect';
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

  const selectOptions: OFSelectOption[] = mergedOptions.map((opt) => ({ value: opt, label: opt }));
  if (!disabled) {
    selectOptions.push({ value: NEW_OPTION_VALUE, label: `+ New ${newEntryLabel}` });
  }

  return (
    <div className="category-select" ref={wrapperRef}>
      <OFSelect
        id={id}
        options={selectOptions}
        value={value || ''}
        disabled={disabled}
        placeholder={disabled ? disabledPlaceholder || placeholder : placeholder}
        onChange={(next) => {
          const nextValue = next as string;
          if (nextValue === NEW_OPTION_VALUE) {
            setDraft('');
            setCreating(true);
          } else {
            onChange(nextValue);
          }
        }}
      />
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
