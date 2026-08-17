import { type ReactNode, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FilterIcon, FlakeIcon } from './NavIcons';
import { isNavGroup, type NavEntry } from './navConfig';

interface NavMenuDropdownProps {
  items: NavEntry[];
  pinnedNavItems: string[];
  onTogglePin: (to: string) => void;
  onClose: () => void;
}

/**
 * Comprehensive dropdown of every OpenFlake page, opened from the menu icon
 * next to the breadcrumbs. Clicking a row navigates there; clicking the
 * flake on the right toggles whether that item is favorited (pinned to the
 * sidebar). Pure container groups (no route of their own, e.g.
 * Integrations/Access) render as non-interactive section labels — they
 * cannot be favorited directly.
 *
 * Outside-click and Escape handling live in the parent (`TopNavbar`), which
 * wraps both the trigger button and this dropdown in one ref — see the
 * `menuRef` pattern there for the user menu.
 */
export function NavMenuDropdown({
  items,
  pinnedNavItems,
  onTogglePin,
  onClose,
}: NavMenuDropdownProps) {
  const [filter, setFilter] = useState('');
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const pinnedSet = useMemo(() => new Set(pinnedNavItems), [pinnedNavItems]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const query = filter.trim().toLowerCase();

  function matches(label: string): boolean {
    return !query || label.toLowerCase().includes(query);
  }

  function handleNavigate(to: string) {
    navigate(to);
    onClose();
  }

  return (
    <div className="nav-menu-dropdown" role="menu">
      <div className="nav-menu-filter">
        <FilterIcon size={14} />
        <input
          ref={inputRef}
          type="search"
          placeholder="Filter pages…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          aria-label="Filter OpenFlake pages"
        />
      </div>
      <div className="nav-menu-list">
        {items.map((item) => {
          if (!isNavGroup(item)) {
            if (!matches(item.label)) return null;
            return (
              <NavMenuRow
                key={item.to}
                to={item.to}
                label={item.label}
                icon={item.icon}
                pinned={pinnedSet.has(item.to)}
                onNavigate={handleNavigate}
                onTogglePin={onTogglePin}
              />
            );
          }

          const headerMatches = matches(item.label);
          const children = headerMatches
            ? item.children
            : item.children.filter((child) => matches(child.label));
          if (!headerMatches && children.length === 0) return null;

          return (
            <div className="nav-menu-group" key={item.id}>
              {item.to ? (
                <NavMenuRow
                  to={item.to}
                  label={item.label}
                  icon={item.icon}
                  pinned={pinnedSet.has(item.to)}
                  onNavigate={handleNavigate}
                  onTogglePin={onTogglePin}
                />
              ) : (
                <div className="nav-menu-group-label">
                  <span className="nav-menu-item-icon">{item.icon}</span>
                  {item.label}
                </div>
              )}
              <div className="nav-menu-group-children">
                {children.map((child) => (
                  <NavMenuRow
                    key={child.to}
                    to={child.to}
                    label={child.label}
                    icon={child.icon}
                    pinned={pinnedSet.has(child.to)}
                    onNavigate={handleNavigate}
                    onTogglePin={onTogglePin}
                    indented
                  />
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

interface NavMenuRowProps {
  to: string;
  label: string;
  icon: ReactNode;
  pinned: boolean;
  indented?: boolean;
  onNavigate: (to: string) => void;
  onTogglePin: (to: string) => void;
}

function NavMenuRow({
  to,
  label,
  icon,
  pinned,
  indented,
  onNavigate,
  onTogglePin,
}: NavMenuRowProps) {
  return (
    <div className={`nav-menu-item${indented ? ' nav-menu-item--child' : ''}`}>
      <button type="button" className="nav-menu-item-link" onClick={() => onNavigate(to)}>
        <span className="nav-menu-item-icon">{icon}</span>
        <span className="nav-menu-item-label">{label}</span>
      </button>
      <button
        type="button"
        className={`nav-menu-item-flake${pinned ? ' flake-active' : ' flake-muted'}`}
        onClick={(e) => {
          e.stopPropagation();
          onTogglePin(to);
        }}
        aria-pressed={pinned}
        aria-label={pinned ? `Remove ${label} from sidebar` : `Pin ${label} to sidebar`}
        title={pinned ? `Unpin ${label}` : `Pin ${label}`}
      >
        <FlakeIcon size={14} />
      </button>
    </div>
  );
}
