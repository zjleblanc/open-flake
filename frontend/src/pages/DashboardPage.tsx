import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { usePageHeader } from '../components/PageHeaderContext';
import { ActivityHeatmap } from '../components/ActivityHeatmap';
import { YamlHighlight } from '../components/YamlHighlight';
import '../components/Layout.css';

const DASHBOARD_BREADCRUMBS = [{ label: 'Dashboard' }];

const ANSIBLE_EXAMPLE_PLAYBOOK = `---
- name: Manage an OpenFlake incident end-to-end
  hosts: localhost
  gather_facts: false

  vars:
    # Best Practice: source expected env vars SN_HOST, SN_USERNAME, SN_PASSWORD
    # from a custom credential type to avoid hardcoding credentials in the playbook
    of_instance:
      host: http://localhost:8000
      username: admin
      password: admin

  tasks:
    - name: Create a new incident
      register: incident
      servicenow.itsm.incident:
        instance: "{{ of_instance }}"
        state: new
        short_description: "Database connection pool exhausted"
        description: "App servers are timing out waiting for a free connection."
        impact: high
        urgency: high

    - name: Assign and start working the incident
      servicenow.itsm.incident:
        instance: "{{ of_instance }}"
        number: "{{ incident.record.number }}"
        state: in_progress
        assigned_to: "ops.oncall"
        comments: "Restarting the pool manager and scaling connections."

    - name: Resolve and close the incident
      servicenow.itsm.incident:
        instance: "{{ of_instance }}"
        number: "{{ incident.record.number }}"
        state: closed
        close_code: "Solved (Workaround)"
        close_notes: "Connection pool size increased; monitoring for recurrence."
`;

export function DashboardPage() {
  usePageHeader({ breadcrumbs: DASHBOARD_BREADCRUMBS });

  const { data, isLoading } = useQuery({
    queryKey: ['dashboard'],
    queryFn: api.dashboard,
  });

  if (isLoading) return <p className="empty-state">Loading…</p>;

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
      <div className="dashboard-welcome-row">
        <div className="card">
          <h2 className="section-title">Welcome to OpenFlake</h2>
          <p className="text-body">
            OpenFlake is an open-source, lightweight ITSM platform built to be automated. It
            provides a ServiceNow-compatible REST API for incidents, problems, changes, the service
            catalog, and your CMDB — so the tools your team already uses to manage ServiceNow work
            here too, with nothing more than a host and credential change.
          </p>
        </div>
        <div className="card">
          <h2 className="section-title">Recent Activity</h2>
          <ActivityHeatmap />
        </div>
      </div>
      <div className="card">
        <h2 className="section-title">Designed for Ansible</h2>
        <YamlHighlight code={ANSIBLE_EXAMPLE_PLAYBOOK} />
      </div>
    </div>
  );
}
