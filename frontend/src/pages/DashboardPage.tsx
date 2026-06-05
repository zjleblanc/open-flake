import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { usePageHeader } from "../components/PageHeaderContext";
import "../components/Layout.css";

const DASHBOARD_BREADCRUMBS = [{ label: "Dashboard" }];

export function DashboardPage() {
  usePageHeader({ breadcrumbs: DASHBOARD_BREADCRUMBS });

  const { data, isLoading } = useQuery({
    queryKey: ["dashboard"],
    queryFn: api.dashboard,
  });

  if (isLoading) return <p>Loading...</p>;

  return (
    <div>
      <div className="stats-grid">
        <div className="stat-card">
          <h3>Open Incidents</h3>
          <div className="value">{data?.incidents_open ?? 0}</div>
        </div>
        <div className="stat-card accent">
          <h3>Open Problems</h3>
          <div className="value">{data?.problems_open ?? 0}</div>
        </div>
        <div className="stat-card">
          <h3>Open Changes</h3>
          <div className="value">{data?.changes_open ?? 0}</div>
        </div>
        <div className="stat-card accent">
          <h3>Configuration Items</h3>
          <div className="value">{data?.cis_total ?? 0}</div>
        </div>
      </div>
      <div className="card">
        <h2 className="section-title">Welcome to OpenFlake</h2>
        <p className="text-body">
          Manage incidents, problems, changes, and configuration items. Ansible playbooks
          can target this instance using the servicenow.itsm collection with{" "}
          <code className="code-inline">SN_HOST</code> pointing to the backend API.
        </p>
      </div>
    </div>
  );
}
