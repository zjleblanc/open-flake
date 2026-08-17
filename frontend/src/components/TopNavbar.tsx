import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useUserPreferences } from '../settings/UserPreferencesContext';
import { Breadcrumbs } from './Breadcrumbs';
import { ColorSchemeSelector, LayoutDensitySelector, ToggleSwitch } from './DetailFieldControls';
import { MenuIcon, SignOutIcon } from './NavIcons';
import type { NavEntry } from './navConfig';
import { NavMenuDropdown } from './NavMenuDropdown';
import { usePageHeaderContext } from './PageHeaderContext';

function userInitials(userName: string): string {
  const parts = userName.split(/[.@_-]/).filter(Boolean);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return userName.slice(0, 2).toUpperCase();
}

interface TopNavbarProps {
  navItems: NavEntry[];
  pinnedNavItems: string[];
  onTogglePin: (to: string) => void;
}

export function TopNavbar({ navItems, pinnedNavItems, onTogglePin }: TopNavbarProps) {
  const { header } = usePageHeaderContext();
  const { user, logout: authLogout } = useAuth();
  const {
    dateDisplayFormat,
    setDateDisplayFormat,
    layoutDensity,
    setLayoutDensity,
    colorScheme,
    setColorScheme,
  } = useUserPreferences();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const [navMenuOpen, setNavMenuOpen] = useState(false);
  const navMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;

    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }

    function handleEscape(e: KeyboardEvent) {
      if (e.key === 'Escape') setMenuOpen(false);
    }

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [menuOpen]);

  // The trigger button and the dropdown share `navMenuRef` so a click on the
  // trigger itself never counts as "outside" -- see the `menuRef` pattern
  // above for the user menu, which this mirrors.
  useEffect(() => {
    if (!navMenuOpen) return;

    function handleClickOutside(e: MouseEvent) {
      if (navMenuRef.current && !navMenuRef.current.contains(e.target as Node)) {
        setNavMenuOpen(false);
      }
    }

    function handleEscape(e: KeyboardEvent) {
      if (e.key === 'Escape') setNavMenuOpen(false);
    }

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [navMenuOpen]);

  function logout() {
    setMenuOpen(false);
    authLogout();
    navigate('/login');
  }

  return (
    <header className="top-navbar">
      <div className="top-navbar-start">
        <div className="nav-menu-root" ref={navMenuRef}>
          <button
            type="button"
            className="nav-menu-trigger"
            onClick={() => setNavMenuOpen((open) => !open)}
            aria-expanded={navMenuOpen}
            aria-haspopup="menu"
            aria-label="Browse all OpenFlake pages"
            title="Browse all pages"
          >
            <MenuIcon size={18} />
          </button>
          {navMenuOpen && (
            <NavMenuDropdown
              items={navItems}
              pinnedNavItems={pinnedNavItems}
              onTogglePin={onTogglePin}
              onClose={() => setNavMenuOpen(false)}
            />
          )}
        </div>
        {header.breadcrumbs.length > 0 && <Breadcrumbs items={header.breadcrumbs} />}
        {header.badge && <div className="top-navbar-badge">{header.badge}</div>}
      </div>
      <div className="top-navbar-end">
        {header.actions && <div className="top-navbar-actions">{header.actions}</div>}
        {user && (
          <div className="user-menu" ref={menuRef}>
            <button
              type="button"
              className="user-menu-trigger"
              onClick={() => setMenuOpen((open) => !open)}
              aria-expanded={menuOpen}
              aria-haspopup="menu"
            >
              <span className="user-menu-avatar" aria-hidden="true">
                {userInitials(user.user_name)}
              </span>
              <span className="user-menu-name">{user.user_name}</span>
              <ChevronDownIcon />
            </button>
            {menuOpen && (
              <div className="user-menu-dropdown" role="menu">
                <div className="user-menu-dropdown-header">
                  <span className="user-menu-dropdown-name">{user.user_name}</span>
                </div>
                <div className="user-menu-preference">
                  <ColorSchemeSelector
                    idPrefix="user-menu-theme"
                    value={colorScheme}
                    onChange={setColorScheme}
                  />
                </div>
                <div className="user-menu-preference">
                  <LayoutDensitySelector
                    idPrefix="user-menu-layout"
                    value={layoutDensity}
                    onChange={setLayoutDensity}
                  />
                </div>
                <div className="user-menu-preference">
                  <ToggleSwitch
                    id="user-menu-date-local"
                    checked={dateDisplayFormat === 'local'}
                    onChange={(checked) => setDateDisplayFormat(checked ? 'local' : 'raw')}
                    label="Local Dates"
                  />
                </div>
                <button type="button" className="user-menu-item" role="menuitem" onClick={logout}>
                  <SignOutIcon size={16} />
                  Sign out
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </header>
  );
}

function ChevronDownIcon() {
  return (
    <svg
      className="user-menu-chevron"
      width={14}
      height={14}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M6 9l6 6 6-6"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
