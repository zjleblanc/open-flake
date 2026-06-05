import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { clearToken } from "../api/client";
import openFlakeSm from "../assets/images/open_flake_sm.png";
import "./Layout.css";

const NAV = [
  { to: "/", label: "Dashboard" },
  { to: "/incidents", label: "Incidents" },
  { to: "/problems", label: "Problems" },
  { to: "/changes", label: "Changes" },
  { to: "/configuration-items", label: "Configuration Items" },
  { to: "/users", label: "Users & Groups" },
  { to: "/settings", label: "Settings" },
];

export function Layout() {
  const navigate = useNavigate();

  function logout() {
    clearToken();
    navigate("/login");
  }

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <img src={openFlakeSm} alt="OpenFlake" width={32} height={32} />
          <span className="brand-text">OpenFlake</span>
        </div>
        <nav>
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <button className="btn-secondary logout-btn" onClick={logout}>
          Sign out
        </button>
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
