import { type ReactNode } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useUserPreferences } from "../settings/UserPreferencesContext";
import openFlakeSm from "../assets/images/open_flake_sm.png";
import {
  ChangeIcon,
  ConfigurationItemIcon,
  DashboardIcon,
  IncidentIcon,
  ProblemIcon,
  SettingsIcon,
  UsersIcon,
} from "./NavIcons";
import { PageHeaderProvider } from "./PageHeaderContext";
import { TopNavbar } from "./TopNavbar";
import "./Layout.css";

const NAV: { to: string; label: string; icon: ReactNode; permission?: string }[] = [
  { to: "/", label: "Dashboard", icon: <DashboardIcon /> },
  { to: "/incidents", label: "Incidents", icon: <IncidentIcon /> },
  { to: "/problems", label: "Problems", icon: <ProblemIcon /> },
  { to: "/changes", label: "Changes", icon: <ChangeIcon /> },
  { to: "/configuration-items", label: "Configuration Items", icon: <ConfigurationItemIcon /> },
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

export function Layout() {
  const { hasPermission } = useAuth();
  const { sidebarExpanded, setSidebarExpanded } = useUserPreferences();

  const visibleNav = NAV.filter((item) => !item.permission || hasPermission(item.permission));

  return (
    <PageHeaderProvider>
      <div className={`layout${sidebarExpanded ? "" : " layout--sidebar-collapsed"}`}>
        <aside className={`sidebar${sidebarExpanded ? "" : " sidebar--collapsed"}`}>
          <div className="sidebar-brand">
            <img src={openFlakeSm} alt="OpenFlake" width={32} height={32} />
            <span className="brand-text">OpenFlake</span>
          </div>
          <nav className="sidebar-nav">
            {visibleNav.map((item) => (
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
            ))}
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
