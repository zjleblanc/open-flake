import type { ReactNode } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import openFlakeSm from "../assets/images/open_flake_sm.png";
import {
  ChangeIcon,
  ConfigurationItemIcon,
  DashboardIcon,
  IncidentIcon,
  ProblemIcon,
  SettingsIcon,
  SignOutIcon,
  UsersIcon,
} from "./NavIcons";
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
  const navigate = useNavigate();
  const { hasPermission, logout: authLogout } = useAuth();

  function logout() {
    authLogout();
    navigate("/login");
  }

  const visibleNav = NAV.filter((item) => !item.permission || hasPermission(item.permission));

  return (
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
        <div className="sidebar-footer">
          <button className="btn-secondary logout-btn" onClick={logout}>
            <SignOutIcon size={16} />
            Sign out
          </button>
        </div>
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
