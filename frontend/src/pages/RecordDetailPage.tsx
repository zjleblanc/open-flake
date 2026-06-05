import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { api, STATE_LABELS, stateBadge } from "../api/client";
import { DetailPageHeader } from "../components/DetailPageHeader";
import { DetailSection } from "../components/DetailSection";
import { EditIcon, OverviewIcon } from "../components/DetailIcons";
import "../components/Layout.css";

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

  const recordTitle = data?.number || data?.name || data?.sys_id || "Loading…";

  if (isLoading || !data) {
    return (
      <div className="detail-page">
        <DetailPageHeader
          breadcrumbs={[
            { label: title, to: listPath },
            { label: "Loading…" },
          ]}
          title="Loading…"
        />
      </div>
    );
  }

  return (
    <div className="detail-page">
      <DetailPageHeader
        breadcrumbs={[
          { label: title, to: listPath },
          { label: recordTitle },
        ]}
        title={recordTitle}
        badge={
          <span className={`badge ${stateBadge(data.state || "1")}`}>
            {STATE_LABELS[data.state] || data.state || "—"}
          </span>
        }
      />

      <DetailSection title="Overview" icon={<OverviewIcon />} accent="accent">
        <div className="detail-grid">
          <div className="detail-field">
            <p className="field-label">Short Description</p>
            <p>{data.short_description || "—"}</p>
          </div>
          <div className="detail-field">
            <p className="field-label">Priority</p>
            <p>{data.priority || "—"}</p>
          </div>
          {data.description && (
            <div className="detail-field" style={{ gridColumn: "1 / -1" }}>
              <p className="field-label">Description</p>
              <p>{data.description}</p>
            </div>
          )}
          {data.sys_class_name && (
            <div className="detail-field">
              <p className="field-label">Class</p>
              <p>{data.sys_class_name}</p>
            </div>
          )}
        </div>
      </DetailSection>

      {editableFields && (
        <DetailSection
          title="Update"
          icon={<EditIcon />}
          accent="primary"
          style={{ marginTop: "1rem" }}
        >
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
        </DetailSection>
      )}
    </div>
  );
}
