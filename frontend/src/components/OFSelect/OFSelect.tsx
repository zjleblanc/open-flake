import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type MouseEvent as ReactMouseEvent,
} from 'react';
import { Portal } from '../Portal';
import { OFSelectDropdown, type OFSelectDropdownPosition } from './OFSelectDropdown';
import './OFSelect.css';

export interface OFSelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export type OFSelectSize = 'sm' | 'md' | 'lg';
export type OFSelectTheme = 'primary' | 'secondary';

export interface OFSelectProps {
  options: OFSelectOption[];
  value?: string | string[];
  defaultValue?: string | string[];
  onChange?: (value: string | string[]) => void;
  size?: OFSelectSize;
  theme?: OFSelectTheme;
  multiple?: boolean;
  disabled?: boolean;
  placeholder?: string;
  autocomplete?: boolean;
  id?: string;
  'aria-label'?: string;
  className?: string;
  /**
   * Opt-in floating label: rests inside the control like a placeholder when
   * closed/empty, then floats up onto the top border when open or when a
   * value is selected. When set, the `placeholder` prop is suppressed in the
   * idle state so the two don't overlap.
   */
  floatingLabel?: string;
}

function toArray(value: string | string[] | undefined): string[] {
  if (value === undefined) return [];
  if (Array.isArray(value)) return value;
  return value === '' ? [] : [value];
}

export function OFSelect({
  options,
  value,
  defaultValue,
  onChange,
  size = 'md',
  theme = 'primary',
  multiple = false,
  disabled = false,
  placeholder = 'Select…',
  autocomplete = false,
  id,
  className,
  floatingLabel,
  ...rest
}: OFSelectProps) {
  const generatedId = useId();
  const controlId = id || generatedId;
  const listboxId = `${controlId}-listbox`;
  const ariaLabel = rest['aria-label'];

  const isControlled = value !== undefined;
  const [internalValue, setInternalValue] = useState<string | string[]>(() =>
    defaultValue !== undefined ? defaultValue : multiple ? [] : '',
  );

  const currentValue = isControlled ? (value as string | string[]) : internalValue;
  const selectedValues = useMemo(() => toArray(currentValue), [currentValue]);

  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const [position, setPosition] = useState<OFSelectDropdownPosition | null>(null);

  const triggerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const filteredOptions = useMemo(() => {
    if (!autocomplete || !query.trim()) return options;
    const q = query.trim().toLowerCase();
    return options.filter((opt) => opt.label.toLowerCase().includes(q));
  }, [options, autocomplete, query]);

  const selectedOptions = useMemo(
    () => options.filter((opt) => selectedValues.includes(opt.value)),
    [options, selectedValues],
  );

  const updatePosition = useCallback(() => {
    const trigger = triggerRef.current;
    if (!trigger) return;
    const rect = trigger.getBoundingClientRect();
    setPosition({ top: rect.bottom + 4, left: rect.left, width: rect.width });
  }, []);

  const closeDropdown = useCallback(() => {
    setIsOpen(false);
    setQuery('');
  }, []);

  const openDropdown = useCallback(() => {
    if (disabled) return;
    updatePosition();
    setIsOpen(true);
  }, [disabled, updatePosition]);

  useEffect(() => {
    if (!isOpen) return;
    const firstEnabledIndex = filteredOptions.findIndex((opt) => !opt.disabled);
    setHighlightedIndex(firstEnabledIndex === -1 ? 0 : firstEnabledIndex);
    // Only re-run when the dropdown opens or the filtered set changes length,
    // not on every highlightedIndex change (that would fight keyboard nav).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, filteredOptions.length]);

  function emitChange(next: string | string[]) {
    if (!isControlled) setInternalValue(next);
    onChange?.(next);
  }

  function selectOption(option: OFSelectOption) {
    if (option.disabled) return;
    if (multiple) {
      const already = selectedValues.includes(option.value);
      const next = already
        ? selectedValues.filter((v) => v !== option.value)
        : [...selectedValues, option.value];
      emitChange(next);
      setQuery('');
      if (autocomplete) inputRef.current?.focus();
    } else {
      emitChange(option.value);
      closeDropdown();
    }
  }

  function removeTag(optValue: string, event: ReactMouseEvent) {
    event.stopPropagation();
    if (disabled) return;
    emitChange(selectedValues.filter((v) => v !== optValue));
  }

  useEffect(() => {
    if (!isOpen) return;
    function handlePointerDown(event: MouseEvent) {
      const target = event.target as Node;
      if (triggerRef.current?.contains(target)) return;
      if (dropdownRef.current?.contains(target)) return;
      closeDropdown();
    }
    document.addEventListener('mousedown', handlePointerDown);
    return () => document.removeEventListener('mousedown', handlePointerDown);
  }, [isOpen, closeDropdown]);

  useEffect(() => {
    if (!isOpen) return;
    function onScroll(event: Event) {
      const target = event.target;
      if (target instanceof Node && dropdownRef.current?.contains(target)) return;
      updatePosition();
    }
    function onResize() {
      updatePosition();
    }
    window.addEventListener('scroll', onScroll, true);
    window.addEventListener('resize', onResize);
    return () => {
      window.removeEventListener('scroll', onScroll, true);
      window.removeEventListener('resize', onResize);
    };
  }, [isOpen, updatePosition]);

  function moveHighlight(delta: number) {
    if (filteredOptions.length === 0) return;
    let next = highlightedIndex;
    for (let i = 0; i < filteredOptions.length; i++) {
      next = (next + delta + filteredOptions.length) % filteredOptions.length;
      if (!filteredOptions[next].disabled) break;
    }
    setHighlightedIndex(next);
  }

  function handleKeyDown(event: ReactKeyboardEvent) {
    if (disabled) return;
    if (!isOpen) {
      if (event.key === 'ArrowDown' || event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        openDropdown();
      }
      return;
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      moveHighlight(1);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      moveHighlight(-1);
    } else if (event.key === 'Enter') {
      event.preventDefault();
      const option = filteredOptions[highlightedIndex];
      if (option) selectOption(option);
    } else if (event.key === 'Escape') {
      event.preventDefault();
      closeDropdown();
    } else if (event.key === 'Tab') {
      closeDropdown();
    }
  }

  function handleTriggerClick() {
    if (disabled) return;
    if (isOpen) {
      closeDropdown();
    } else {
      openDropdown();
    }
  }

  function handleInputFocus() {
    openDropdown();
    setQuery('');
  }

  function handleInputChange(nextQuery: string) {
    setQuery(nextQuery);
    if (!isOpen) openDropdown();
    setHighlightedIndex(0);
  }

  const activeDescendant =
    isOpen && filteredOptions[highlightedIndex]
      ? `${listboxId}-option-${highlightedIndex}`
      : undefined;

  const singleLabel = !multiple ? (selectedOptions[0]?.label ?? '') : '';
  const labelActive = isOpen || selectedValues.length > 0;
  const idlePlaceholder = floatingLabel ? '' : placeholder;

  function renderTags() {
    if (selectedOptions.length === 0) return null;
    return (
      <span className="of-select-tags">
        {selectedOptions.map((opt) => (
          <span key={opt.value} className="of-select-tag">
            {opt.label}
            {!disabled ? (
              <button
                type="button"
                className="of-select-tag-remove"
                aria-label={`Remove ${opt.label}`}
                onClick={(event) => removeTag(opt.value, event)}
              >
                ×
              </button>
            ) : null}
          </span>
        ))}
      </span>
    );
  }

  const rootClassName = [
    'of-select',
    `of-select--${size}`,
    `of-select--${theme}`,
    disabled ? 'of-select--disabled' : '',
    isOpen ? 'of-select--open' : '',
    className || '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={rootClassName}>
      <div
        ref={triggerRef}
        id={autocomplete ? undefined : controlId}
        className={`of-select-trigger${multiple ? ' of-select-trigger--multiple' : ''}${
          autocomplete ? ' of-select-trigger--autocomplete' : ''
        }`}
        role={autocomplete ? undefined : 'combobox'}
        aria-haspopup={autocomplete ? undefined : 'listbox'}
        aria-expanded={autocomplete ? undefined : isOpen}
        aria-controls={autocomplete ? undefined : listboxId}
        aria-disabled={disabled || undefined}
        aria-activedescendant={autocomplete ? undefined : activeDescendant}
        aria-label={autocomplete ? undefined : ariaLabel}
        tabIndex={autocomplete || disabled ? undefined : 0}
        onClick={autocomplete ? undefined : handleTriggerClick}
        onKeyDown={autocomplete ? undefined : handleKeyDown}
      >
        {multiple ? renderTags() : null}

        {autocomplete ? (
          <input
            ref={inputRef}
            id={controlId}
            role="combobox"
            aria-autocomplete="list"
            aria-expanded={isOpen}
            aria-controls={listboxId}
            aria-activedescendant={activeDescendant}
            aria-label={ariaLabel}
            className="of-select-input"
            disabled={disabled}
            placeholder={multiple && selectedOptions.length > 0 ? '' : idlePlaceholder}
            value={isOpen ? query : multiple ? '' : singleLabel}
            onFocus={handleInputFocus}
            onClick={openDropdown}
            onChange={(event) => handleInputChange(event.target.value)}
            onKeyDown={handleKeyDown}
          />
        ) : !multiple || selectedOptions.length === 0 ? (
          <span className={`of-select-value${singleLabel ? '' : ' of-select-placeholder'}`}>
            {singleLabel || idlePlaceholder}
          </span>
        ) : null}

        {!autocomplete ? <span className="of-select-chevron" aria-hidden="true" /> : null}
      </div>

      {floatingLabel ? (
        <span
          className={`of-select-floating-label${labelActive ? ' of-select-floating-label--active' : ''}`}
        >
          {floatingLabel}
        </span>
      ) : null}

      {isOpen && position ? (
        <Portal>
          <OFSelectDropdown
            ref={dropdownRef}
            listboxId={listboxId}
            options={filteredOptions}
            selectedValues={selectedValues}
            highlightedIndex={highlightedIndex}
            multiple={multiple}
            theme={theme}
            position={position}
            emptyMessage={autocomplete && query.trim() ? 'No matches' : 'No options'}
            onOptionClick={selectOption}
            onOptionHover={setHighlightedIndex}
          />
        </Portal>
      ) : null}
    </div>
  );
}
