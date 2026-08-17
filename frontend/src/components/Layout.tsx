import { useCallback, useMemo, useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useUserPreferences } from '../settings/UserPreferencesContext';
import openFlakeSm from '../assets/images/open_flake_sm.png';
import { isNavGroup, NAV, type NavEntry } from './navConfig';
import { PageHeaderProvider } from './PageHeaderContext';
import { TopNavbar } from './TopNavbar';
import './Layout.css';

function ChevronLeftIcon() {
  return (
    <svg width={18} height={18} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M15 18l-6-6 6-6"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ChevronRightIcon() {
  return (
    <svg width={18} height={18} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M9 18l6-6-6-6"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ChevronDownIcon() {
  return (
    <svg width={14} height={14} viewBox="0 0 24 24" fill="none" aria-hidden="true">
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

export function Layout() {
  const { hasPermission } = useAuth();
  const { sidebarExpanded, setSidebarExpanded, pinnedNavItems, setPinnedNavItems } =
    useUserPreferences();
  const location = useLocation();
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({
    catalog: true,
    integrations: true,
    access: true,
  });

  const visibleNav = useMemo((): NavEntry[] => {
    return NAV.flatMap((item): NavEntry[] => {
      if (!isNavGroup(item)) {
        return !item.permission || hasPermission(item.permission) ? [item] : [];
      }
      if (item.permission && !hasPermission(item.permission)) {
        return [];
      }
      const children = item.children.filter(
        (child) => !child.permission || hasPermission(child.permission),
      );
      if (!children.length) {
        return [];
      }
      return [{ ...item, children }];
    });
  }, [hasPermission]);

  const pinnedSet = useMemo(() => new Set(pinnedNavItems), [pinnedNavItems]);

  // Sidebar shows only favorited items. A group surfaces if its own route is
  // favorited and/or any of its children are — only the favorited children
  // are rendered underneath it. Groups with no `to` of their own (pure
  // containers like Integrations/Access) only ever appear via their children.
  const sidebarNav = useMemo((): NavEntry[] => {
    return visibleNav.flatMap((item): NavEntry[] => {
      if (!isNavGroup(item)) {
        return pinnedSet.has(item.to) ? [item] : [];
      }
      const children = item.children.filter((child) => pinnedSet.has(child.to));
      const parentPinned = Boolean(item.to && pinnedSet.has(item.to));
      if (!children.length && !parentPinned) {
        return [];
      }
      return [{ ...item, children }];
    });
  }, [visibleNav, pinnedSet]);

  const togglePin = useCallback(
    (to: string) => {
      setPinnedNavItems(
        pinnedSet.has(to) ? pinnedNavItems.filter((item) => item !== to) : [...pinnedNavItems, to],
      );
    },
    [pinnedNavItems, pinnedSet, setPinnedNavItems],
  );

  function toggleGroup(id: string) {
    setOpenGroups((prev) => ({ ...prev, [id]: !prev[id] }));
  }

  return (
    <PageHeaderProvider>
      <div className={`layout${sidebarExpanded ? '' : ' layout--sidebar-collapsed'}`}>
        <aside className={`sidebar${sidebarExpanded ? '' : ' sidebar--collapsed'}`}>
          <div className="sidebar-brand">
            <img src={openFlakeSm} alt="OpenFlake" width={32} height={32} />
            <span className="brand-text">OpenFlake</span>
          </div>
          <nav className="sidebar-nav">
            {sidebarNav.map((item) => {
              if (!isNavGroup(item)) {
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.to === '/'}
                    title={item.label}
                    className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
                  >
                    <span className="nav-link-icon">{item.icon}</span>
                    <span className="nav-link-label">{item.label}</span>
                  </NavLink>
                );
              }

              const childActive = item.children.some(
                (child) =>
                  location.pathname === child.to || location.pathname.startsWith(`${child.to}/`),
              );
              const parentActive = Boolean(
                item.to &&
                (location.pathname === item.to || location.pathname.startsWith(`${item.to}/`)),
              );
              const hasChildren = item.children.length > 0;
              const expanded = hasChildren && (openGroups[item.id] ?? childActive);

              if (!sidebarExpanded) {
                const target = item.to ?? item.children[0].to;
                return (
                  <NavLink
                    key={item.id}
                    to={target}
                    title={item.label}
                    className={() => `nav-link${parentActive || childActive ? ' active' : ''}`}
                  >
                    <span className="nav-link-icon">{item.icon}</span>
                    <span className="nav-link-label">{item.label}</span>
                  </NavLink>
                );
              }

              return (
                <div key={item.id} className="nav-group">
                  {item.to ? (
                    <div className="nav-group-row">
                      <NavLink
                        to={item.to}
                        title={item.label}
                        className={({ isActive }) =>
                          `nav-link nav-group-link${isActive ? ' active' : ''}`
                        }
                      >
                        <span className="nav-link-icon">{item.icon}</span>
                        <span className="nav-link-label">{item.label}</span>
                      </NavLink>
                      {hasChildren && (
                        <button
                          type="button"
                          className={`nav-group-chevron-btn${expanded ? ' open' : ''}`}
                          onClick={() => toggleGroup(item.id)}
                          aria-expanded={expanded}
                          aria-label={expanded ? `Collapse ${item.label}` : `Expand ${item.label}`}
                        >
                          <ChevronDownIcon />
                        </button>
                      )}
                    </div>
                  ) : (
                    <button
                      type="button"
                      className="nav-link nav-group-toggle"
                      onClick={() => toggleGroup(item.id)}
                      aria-expanded={expanded}
                    >
                      <span className="nav-link-icon">{item.icon}</span>
                      <span className="nav-link-label">{item.label}</span>
                      <span className={`nav-group-chevron${expanded ? ' open' : ''}`}>
                        <ChevronDownIcon />
                      </span>
                    </button>
                  )}
                  {expanded ? (
                    <div className="nav-sublinks">
                      {item.children.map((child) => (
                        <NavLink
                          key={child.to}
                          to={child.to}
                          title={child.label}
                          className={({ isActive }) =>
                            `nav-link nav-sublink${isActive ? ' active' : ''}`
                          }
                        >
                          <span className="nav-link-icon">{child.icon}</span>
                          <span className="nav-link-label">{child.label}</span>
                        </NavLink>
                      ))}
                    </div>
                  ) : null}
                </div>
              );
            })}
          </nav>
          <div className="sidebar-footer">
            <button
              type="button"
              className="nav-link sidebar-nav-toggle"
              onClick={() => setSidebarExpanded(!sidebarExpanded)}
              aria-label={sidebarExpanded ? 'Collapse sidebar' : 'Expand sidebar'}
              aria-expanded={sidebarExpanded}
            >
              <span className="nav-link-icon">
                {sidebarExpanded ? <ChevronLeftIcon /> : <ChevronRightIcon />}
              </span>
              {sidebarExpanded ? <span className="nav-link-label">Collapse</span> : null}
            </button>
          </div>
        </aside>
        <div className="main-column">
          <TopNavbar
            navItems={visibleNav}
            pinnedNavItems={pinnedNavItems}
            onTogglePin={togglePin}
          />
          <main className="content">
            <div className="content-body">
              <Outlet />
            </div>
          </main>
        </div>
      </div>
    </PageHeaderProvider>
  );
}
