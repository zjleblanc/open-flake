import { forwardRef } from 'react';
import type { OFSelectOption, OFSelectTheme } from './OFSelect';

export interface OFSelectDropdownPosition {
  top: number;
  left: number;
  width: number;
}

interface OFSelectDropdownProps {
  listboxId: string;
  options: OFSelectOption[];
  selectedValues: string[];
  highlightedIndex: number;
  multiple: boolean;
  theme: OFSelectTheme;
  position: OFSelectDropdownPosition;
  emptyMessage: string;
  onOptionClick: (option: OFSelectOption) => void;
  onOptionHover: (index: number) => void;
}

function CheckIcon() {
  return (
    <svg width={13} height={13} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M20 6L9 17l-5-5"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export const OFSelectDropdown = forwardRef<HTMLDivElement, OFSelectDropdownProps>(
  function OFSelectDropdown(
    {
      listboxId,
      options,
      selectedValues,
      highlightedIndex,
      multiple,
      theme,
      position,
      emptyMessage,
      onOptionClick,
      onOptionHover,
    },
    ref,
  ) {
    return (
      <div
        ref={ref}
        id={listboxId}
        role="listbox"
        aria-multiselectable={multiple || undefined}
        className={`of-select-dropdown of-select-dropdown--${theme}`}
        style={{ top: position.top, left: position.left, minWidth: position.width }}
        onMouseDown={(event) => event.preventDefault()}
      >
        {options.length === 0 ? (
          <div className="of-select-empty">{emptyMessage}</div>
        ) : (
          options.map((option, index) => {
            const isSelected = selectedValues.includes(option.value);
            const isHighlighted = index === highlightedIndex;
            return (
              <div
                key={option.value}
                id={`${listboxId}-option-${index}`}
                role="option"
                aria-selected={isSelected}
                aria-disabled={option.disabled || undefined}
                className={[
                  'of-select-option',
                  isHighlighted ? 'of-select-option--highlighted' : '',
                  isSelected ? 'of-select-option--selected' : '',
                  option.disabled ? 'of-select-option--disabled' : '',
                ]
                  .filter(Boolean)
                  .join(' ')}
                onMouseEnter={() => onOptionHover(index)}
                onClick={() => onOptionClick(option)}
              >
                {multiple ? (
                  <span className="of-select-option-checkbox" aria-hidden="true">
                    {isSelected ? <CheckIcon /> : null}
                  </span>
                ) : null}
                <span className="of-select-option-label">{option.label}</span>
                {!multiple && isSelected ? (
                  <span className="of-select-option-check" aria-hidden="true">
                    <CheckIcon />
                  </span>
                ) : null}
              </div>
            );
          })
        )}
      </div>
    );
  },
);
