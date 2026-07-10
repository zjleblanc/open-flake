import { type ReactNode, useMemo, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useUserPreferences } from "../settings/UserPreferencesContext";
import openFlakeSm from "../assets/images/open_flake_sm.png";
import {
  CatalogIcon,
  ChangeIcon,
  ConfigurationItemIcon,
  DashboardIcon,
  IncidentIcon,
  IntegrationsIcon,
  ProblemIcon,
  SecretIcon,
  SettingsIcon,
  UsersIcon,
  WebhookIcon,
} from "./NavIcons";
import { PageHeaderProvider } from "./PageHeaderContext";
import { TopNavbar } from "./TopNavbar";
import "./Layout.css";

type NavLeaf = {
  to: string;
  label: string;
  icon: ReactNode;
  permission?: string;
};

type NavGroup = {
  id: string;
  label: string;
  icon: ReactNode;
  permission?: string;
  children: NavLeaf[];
};

type NavEntry = NavLeaf | NavGroup;

function isNavGroup(entry: NavEntry): entry is NavGroup {
  return "children" in entry;
}

const NAV: NavEntry[] = [
  { to: "/", label: "Dashboard", icon: <DashboardIcon /> },
  { to: "/catalog", label: "Service Catalog", icon: <CatalogIcon /> },
  { to: "/incidents", label: "Incidents", icon: <IncidentIcon /> },
  { to: "/problems", label: "Problems", icon: <ProblemIcon /> },
  { to: "/changes", label: "Changes", icon: <ChangeIcon /> },
  {
    to: "/configuration-items",
    label: "Configuration Items",
    icon: <ConfigurationItemIcon />,
  },
  {
    id: "integrations",
    label: "Integrations",
    icon: <IntegrationsIcon />,
    children: [
      { to: "/integrations/webhooks", label: "Webhooks", icon: <WebhookIcon /> },
      {
        to: "/integrations/secrets",
        label: "Secrets",
        icon: <SecretIcon />,
        permission: "secrets.read",
      },
    ],
  },
  { to: "/users", label: "Users & Groups", icon: <UsersIcon />, permission: "users.read" },
  { to: "/settings", label: "Settings", icon: <SettingsIcon /> },
];

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
  const { sidebarExpanded, setSidebarExpanded } = useUserPreferences();
  const location = useLocation();
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({
    integrations: true,
  });

  const visibleNav = useMemo(
    () =>
      NAV.flatMap((item) => {
        if (!isNavGroup(item)) {
          return !item.permission || hasPermission(item.permission) ? [item] : [];
        }
        if (item.permission && !hasPermission(item.permission)) {
          return [];
        }
        const children = item.children.filter(
          (child) => !child.permission || hasPermission(child.permission)
        );
        if (!children.length) {
          return [];
        }
        return [{ ...item, children }];
      }),
    [hasPermission]
  );

  function toggleGroup(id: string) {
    setOpenGroups((prev) => ({ ...prev, [id]: !prev[id] }));
  }

  return (
    <PageHeaderProvider>
      <div className={`layout${sidebarExpanded ? "" : " layout--sidebar-collapsed"}`}>
        <aside className={`sidebar${sidebarExpanded ? "" : " sidebar--collapsed"}`}>
          <div className="sidebar-brand">
            <img src={openFlakeSm} alt="OpenFlake" width={32} height={32} />
            <span className="brand-text">OpenFlake</span>
          </div>
          <nav className="sidebar-nav">
            {visibleNav.map((item) => {
              if (!isNavGroup(item)) {
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.to === "/"}
                    title={item.label}
                    className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
                  >
                    <span className="nav-link-icon">{item.icon}</span>
                    <span className="nav-link-label">{item.label}</span>
                  </NavLink>
                );
              }

              const childActive = item.children.some(
                (child) =>
                  location.pathname === child.to ||
                  location.pathname.startsWith(`${child.to}/`)
              );
              const expanded = openGroups[item.id] ?? childActive;

              if (!sidebarExpanded) {
                const firstChild = item.children[0];
                return (
                  <NavLink
                    key={item.id}
                    to={firstChild.to}
                    title={item.label}
                    className={() => `nav-link${childActive ? " active" : ""}`}
                  >
                    <span className="nav-link-icon">{item.icon}</span>
                    <span className="nav-link-label">{item.label}</span>
                  </NavLink>
                );
              }

              return (
                <div key={item.id} className="nav-group">
                  <button
                    type="button"
                    className={`nav-link nav-group-toggle${childActive ? " active" : ""}`}
                    onClick={() => toggleGroup(item.id)}
                    aria-expanded={expanded}
                  >
                    <span className="nav-link-icon">{item.icon}</span>
                    <span className="nav-link-label">{item.label}</span>
                    <span className={`nav-group-chevron${expanded ? " open" : ""}`}>
                      <ChevronDownIcon />
                    </span>
                  </button>
                  {expanded ? (
                    <div className="nav-sublinks">
                      {item.children.map((child) => (
                        <NavLink
                          key={child.to}
                          to={child.to}
                          title={child.label}
                          className={({ isActive }) =>
                            `nav-link nav-sublink${isActive ? " active" : ""}`
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
              aria-label={sidebarExpanded ? "Collapse sidebar" : "Expand sidebar"}
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
          <TopNavbar />
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
