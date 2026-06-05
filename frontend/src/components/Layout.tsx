import type { ReactNode } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
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

export function Layout() {
  const { hasPermission } = useAuth();

  const visibleNav = NAV.filter((item) => !item.permission || hasPermission(item.permission));

  return (
    <PageHeaderProvider>
      <div className="layout">
        <aside className="sidebar">
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
                className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
              >
                <span className="nav-link-icon">{item.icon}</span>
                <span className="nav-link-label">{item.label}</span>
              </NavLink>
            ))}
          </nav>
        </aside>
        <div className="main-column">
          <main className="content">
            <TopNavbar />
            <div className="content-body">
              <Outlet />
            </div>
          </main>
        </div>
      </div>
    </PageHeaderProvider>
  );
}
