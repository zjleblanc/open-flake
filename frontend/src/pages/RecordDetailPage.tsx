import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api, STATE_LABELS, stateBadge } from "../api/client";

interface RecordDetailProps {
  resource: string;
  title: string;
  listPath: string;
  editableFields?: { key: string; label: string; type?: string }[];
}

export function RecordDetailPage({ resource, title, listPath, editableFields }: RecordDetailProps) {
  const { sysId } = useParams<{ sysId: string }>();
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["record", resource, sysId],
    queryFn: () => api.getRecord(resource, sysId!),
    enabled: !!sysId,
  });

  const updateMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      api.updateRecord(resource, sysId!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["record", resource, sysId] });
      queryClient.invalidateQueries({ queryKey: ["records", resource] });
    },
  });

  if (isLoading || !data) return <p>Loading...</p>;

  return (
    <div>
      <div className="page-header">
        <div>
          <Link to={listPath} className="text-sm">
            ← Back to {title}
          </Link>
          <h1>{data.number || data.name || data.sys_id}</h1>
        </div>
        <span className={`badge ${stateBadge(data.state || "1")}`}>
          {STATE_LABELS[data.state] || data.state || "—"}
        </span>
      </div>

      <div className="card">
        <div className="detail-grid">
          <div>
            <p className="field-label">Short Description</p>
            <p>{data.short_description || "—"}</p>
          </div>
          <div>
            <p className="field-label">Priority</p>
            <p>{data.priority || "—"}</p>
          </div>
          {data.description && (
            <div style={{ gridColumn: "1 / -1" }}>
              <p className="field-label">Description</p>
              <p>{data.description}</p>
            </div>
          )}
          {data.sys_class_name && (
            <div>
              <p className="field-label">Class</p>
              <p>{data.sys_class_name}</p>
            </div>
          )}
        </div>
      </div>

      {editableFields && (
        <div className="card" style={{ marginTop: "1rem" }}>
          <h2 className="section-title">Update</h2>
          {editableFields.map((f) => (
            <div className="form-group" key={f.key}>
              <label>{f.label}</label>
              {f.type === "select-state" ? (
                <select
                  defaultValue={data[f.key] || "1"}
                  id={`field-${f.key}`}
                >
                  {Object.entries(STATE_LABELS).map(([val, label]) => (
                    <option key={val} value={val}>
                      {label}
                    </option>
                  ))}
                </select>
              ) : f.type === "textarea" ? (
                <textarea rows={3} defaultValue={data[f.key] || ""} id={`field-${f.key}`} />
              ) : (
                <input type="text" defaultValue={data[f.key] || ""} id={`field-${f.key}`} />
              )}
            </div>
          ))}
          <button
            className="btn btn-primary"
            onClick={() => {
              const payload: Record<string, string> = {};
              editableFields.forEach((f) => {
                const el = document.getElementById(`field-${f.key}`) as
                  | HTMLInputElement
                  | HTMLSelectElement
                  | HTMLTextAreaElement;
                if (el) payload[f.key] = el.value;
              });
              updateMutation.mutate(payload);
            }}
            disabled={updateMutation.isPending}
          >
            Save Changes
          </button>
        </div>
      )}
    </div>
  );
}
