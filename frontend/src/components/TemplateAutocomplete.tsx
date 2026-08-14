import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type KeyboardEvent,
  type SyntheticEvent,
} from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { Portal } from './Portal';
import './TemplateAutocomplete.css';

type AutocompleteOption = {
  id: string;
  label: string;
  description?: string;
  insertText: string;
  /** When true, selecting the option closes the `}}` and ends the trigger. */
  closeBraces?: boolean;
};

type ActiveTrigger = {
  /** Index of the opening `{{` within the field value. */
  start: number;
  /** Text typed between `{{` and the cursor. */
  query: string;
};

type DropdownPosition = {
  top: number;
  left: number;
  width: number;
};

const NAMESPACE_OPTIONS: AutocompleteOption[] = [
  {
    id: 'secret',
    label: 'secret:',
    description: 'Reference a stored secret value',
    insertText: 'secret:',
  },
];

/**
 * Find the nearest unterminated `{{` before the cursor, if any, and return
 * the text typed since that `{{`. Returns null when the cursor is not
 * inside an open `{{ ... }}` template reference.
 */
function findActiveTrigger(text: string, cursor: number): ActiveTrigger | null {
  const before = text.slice(0, cursor);
  const openIdx = before.lastIndexOf('{{');
  if (openIdx === -1) return null;
  const between = before.slice(openIdx + 2);
  if (between.includes('}}') || between.includes('{{')) return null;
  return { start: openIdx, query: between };
}

type FieldElement = HTMLInputElement | HTMLTextAreaElement;

interface TemplateAutocompleteProps {
  id?: string;
  value: string;
  onChange: (value: string) => void;
  multiline?: boolean;
  rows?: number;
  placeholder?: string;
  className?: string;
  disabled?: boolean;
  readOnly?: boolean;
  ariaLabel?: string;
}

/**
 * A text input/textarea that offers autocomplete for `{{ }}` template
 * references. Currently supports `{{secret:name}}`, suggesting only secret
 * names the current user has permission to read (`secrets.read`).
 */
export function TemplateAutocomplete({
  id,
  value,
  onChange,
  multiline = false,
  rows = 4,
  placeholder,
  className,
  disabled,
  readOnly,
  ariaLabel,
}: TemplateAutocompleteProps) {
  const { hasPermission } = useAuth();
  const canReadSecrets = hasPermission('secrets.read');
  const fieldRef = useRef<FieldElement | null>(null);
  const dropdownRef = useRef<HTMLDivElement | null>(null);
  const [trigger, setTrigger] = useState<ActiveTrigger | null>(null);
  const [position, setPosition] = useState<DropdownPosition | null>(null);
  const [highlighted, setHighlighted] = useState(0);

  const secretsQuery = useQuery({
    queryKey: ['integration-secrets'],
    queryFn: () => api.listSecrets(),
    enabled: canReadSecrets,
  });

  const secretNames = useMemo(
    () => (secretsQuery.data?.result || []).filter((s) => s.active).map((s) => s.name),
    [secretsQuery.data],
  );

  const options = useMemo((): AutocompleteOption[] => {
    if (!trigger) return [];
    const secretMatch = /^secret:(.*)$/.exec(trigger.query);
    if (secretMatch) {
      const filter = secretMatch[1].toLowerCase();
      return secretNames
        .filter((name) => name.toLowerCase().includes(filter))
        .map((name) => ({
          id: name,
          label: name,
          insertText: `secret:${name}`,
          closeBraces: true,
        }));
    }
    return NAMESPACE_OPTIONS.filter((option) =>
      option.label.toLowerCase().startsWith(trigger.query.toLowerCase()),
    );
  }, [trigger, secretNames]);

  const updatePosition = useCallback(() => {
    const field = fieldRef.current;
    if (!field) return;
    const rect = field.getBoundingClientRect();
    setPosition({ top: rect.bottom + 4, left: rect.left, width: rect.width });
  }, []);

  const closeDropdown = useCallback(() => {
    setTrigger(null);
    setPosition(null);
    setHighlighted(0);
  }, []);

  const recomputeTrigger = useCallback(
    (text: string, cursor: number) => {
      const active = findActiveTrigger(text, cursor);
      if (!active) {
        closeDropdown();
        return;
      }
      setTrigger(active);
      setHighlighted(0);
      updatePosition();
    },
    [closeDropdown, updatePosition],
  );

  function handleChange(event: ChangeEvent<FieldElement>) {
    const nextValue = event.target.value;
    onChange(nextValue);
    recomputeTrigger(nextValue, event.target.selectionStart ?? nextValue.length);
  }

  function handleCursorMove(event: SyntheticEvent<FieldElement>) {
    const target = event.target as FieldElement;
    recomputeTrigger(target.value, target.selectionStart ?? target.value.length);
  }

  function applySelection(option: AutocompleteOption) {
    const field = fieldRef.current;
    if (!field || !trigger) return;
    const cursor = field.selectionStart ?? value.length;
    const prefixText = value.slice(0, trigger.start + 2);
    const suffixText = value.slice(cursor);

    let nextValue: string;
    let nextCursor: number;
    if (option.closeBraces) {
      const hasClosing = suffixText.startsWith('}}');
      nextValue =
        prefixText + option.insertText + '}}' + (hasClosing ? suffixText.slice(2) : suffixText);
      nextCursor = prefixText.length + option.insertText.length + 2;
      closeDropdown();
    } else {
      nextValue = prefixText + option.insertText + suffixText;
      nextCursor = prefixText.length + option.insertText.length;
    }

    onChange(nextValue);
    requestAnimationFrame(() => {
      field.focus();
      field.setSelectionRange(nextCursor, nextCursor);
      if (!option.closeBraces) {
        recomputeTrigger(nextValue, nextCursor);
      }
    });
  }

  function handleKeyDown(event: KeyboardEvent<FieldElement>) {
    if (!trigger || options.length === 0) return;
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setHighlighted((prev) => (prev + 1) % options.length);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setHighlighted((prev) => (prev - 1 + options.length) % options.length);
    } else if (event.key === 'Enter' || event.key === 'Tab') {
      event.preventDefault();
      applySelection(options[highlighted]);
    } else if (event.key === 'Escape') {
      event.preventDefault();
      closeDropdown();
    }
  }

  useEffect(() => {
    if (highlighted >= options.length && options.length > 0) {
      setHighlighted(0);
    }
  }, [options.length, highlighted]);

  useEffect(() => {
    if (!trigger) return;
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
  }, [trigger, updatePosition]);

  const isOpen = Boolean(trigger && position && options.length > 0);
  const listboxId = id ? `${id}-template-listbox` : undefined;

  const sharedProps = {
    id,
    value,
    placeholder,
    disabled,
    readOnly,
    'aria-label': ariaLabel,
    'aria-expanded': isOpen,
    'aria-autocomplete': 'list' as const,
    'aria-controls': isOpen ? listboxId : undefined,
    onChange: handleChange,
    onClick: handleCursorMove,
    onKeyUp: handleCursorMove,
    onKeyDown: handleKeyDown,
    onBlur: () => {
      window.setTimeout(closeDropdown, 120);
    },
  };

  return (
    <>
      {multiline ? (
        <textarea
          {...sharedProps}
          ref={(el) => {
            fieldRef.current = el;
          }}
          rows={rows}
          className={className}
        />
      ) : (
        <input
          {...sharedProps}
          ref={(el) => {
            fieldRef.current = el;
          }}
          type="text"
          className={className}
        />
      )}
      {isOpen && position ? (
        <Portal>
          <div
            ref={dropdownRef}
            id={listboxId}
            role="listbox"
            className="template-autocomplete-dropdown"
            style={{ top: position.top, left: position.left, minWidth: position.width }}
            onMouseDown={(event) => event.preventDefault()}
          >
            {options.map((option, index) => (
              <button
                key={option.id}
                type="button"
                role="option"
                aria-selected={index === highlighted}
                className={`template-autocomplete-option${
                  index === highlighted ? ' template-autocomplete-option--active' : ''
                }`}
                onMouseEnter={() => setHighlighted(index)}
                onClick={() => applySelection(option)}
              >
                <code>{option.label}</code>
                {option.description ? (
                  <span className="template-autocomplete-option-desc">{option.description}</span>
                ) : null}
              </button>
            ))}
          </div>
        </Portal>
      ) : null}
    </>
  );
}
