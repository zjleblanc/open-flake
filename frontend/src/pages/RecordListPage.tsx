import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, STATE_LABELS, stateBadge } from "../api/client";
import "../components/Layout.css";

interface RecordListProps {
  resource: string;
  title: string;
  basePath: string;
  createFields?: { key: string; label: string; type?: string }[];
}

export function RecordListPage({ resource, title, basePath, createFields }: RecordListProps) {
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState<Record<string, string>>({});
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["records", resource],
    queryFn: () => api.listRecords(resource),
  });

  const createMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) => api.createRecord(resource, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["records", resource] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      setShowCreate(false);
      setForm({});
    },
  });

  if (isLoading) return <p>Loading...</p>;

  return (
    <div>
      <div className="page-header">
        <h1>{title}</h1>
        {createFields && (
          <button className="btn btn-primary" onClick={() => setShowCreate(!showCreate)}>
            {showCreate ? "Cancel" : "Create"}
          </button>
        )}
      </div>

      {showCreate && createFields && (
        <div className="card" style={{ marginBottom: "1.5rem" }}>
          <h2 className="section-title">New {title.slice(0, -1)}</h2>
          {createFields.map((f) => (
            <div className="form-group" key={f.key}>
              <label>{f.label}</label>
              {f.type === "textarea" ? (
                <textarea
                  rows={3}
                  value={form[f.key] || ""}
                  onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
                />
              ) : (
                <input
                  type={f.type || "text"}
                  value={form[f.key] || ""}
                  onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
                />
              )}
            </div>
          ))}
          <button
            className="btn btn-primary"
            onClick={() => createMutation.mutate(form)}
            disabled={createMutation.isPending}
          >
            Save
          </button>
        </div>
      )}

      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        <table>
          <thead>
            <tr>
              <th>Number</th>
              <th>Short Description</th>
              <th>State</th>
              <th>Priority</th>
            </tr>
          </thead>
          <tbody>
            {(data?.records || []).map((r) => (
              <tr key={r.sys_id}>
                <td>
                  <Link to={`${basePath}/${r.sys_id}`}>{r.number || r.name || r.sys_id}</Link>
                </td>
                <td>{r.short_description}</td>
                <td>
                  <span className={`badge ${stateBadge(r.state || "1")}`}>
                    {STATE_LABELS[r.state] || r.state}
                  </span>
                </td>
                <td>{r.priority || "—"}</td>
              </tr>
            ))}
            {(data?.records || []).length === 0 && (
              <tr>
                <td colSpan={4} className="empty-state">
                  No records found
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
