import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { api, getRecordPermissions, STATE_LABELS, stateBadge } from "../api/client";
import { DetailPageHeader } from "../components/DetailPageHeader";
import { DetailSection } from "../components/DetailSection";
import { OverviewIcon } from "../components/DetailIcons";
import {
  DetailFieldGroup,
  ReadOnlyFieldInput,
} from "../components/DetailFieldControls";
import { RecordCommentsSection } from "../components/RecordCommentsSection";
import { RecordSharePopover } from "../components/RecordSharePopover";
import "../components/Layout.css";

export interface DetailFieldConfig {
  key: string;
  label: string;
  type?: string;
  readOnly?: boolean;
}

interface RecordDetailProps {
  resource: string;
  title: string;
  listPath: string;
  fields: DetailFieldConfig[];
  sectionTitle?: string;
}

function formatReadOnlyValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "object" && value !== null && "value" in value) {
    return String((value as { value: string }).value);
  }
  return String(value);
}

export function RecordDetailPage({
  resource,
  title,
  listPath,
  fields,
  sectionTitle = "Details",
}: RecordDetailProps) {
  const { sysId } = useParams<{ sysId: string }>();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<Record<string, string>>({});

  const { data, isLoading } = useQuery({
    queryKey: ["record", resource, sysId],
    queryFn: () => api.getRecord(resource, sysId!),
    enabled: !!sysId,
  });

  useEffect(() => {
    if (!data) return;
    const nextForm: Record<string, string> = {};
    fields.forEach((field) => {
      if (!field.readOnly) {
        nextForm[field.key] = data[field.key] || "";
      }
    });
    setForm(nextForm);
  }, [data, fields]);

  const savedForm = useMemo(() => {
    if (!data) return {};
    const nextForm: Record<string, string> = {};
    fields.forEach((field) => {
      if (!field.readOnly) {
        nextForm[field.key] = data[field.key] || "";
      }
    });
    return nextForm;
  }, [data, fields]);

  const isDirty = useMemo(() => {
    for (const field of fields) {
      if (field.readOnly) continue;
      if ((form[field.key] ?? "") !== (savedForm[field.key] ?? "")) return true;
    }
    return false;
  }, [form, savedForm, fields]);

  const updateMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      api.updateRecord(resource, sysId!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["record", resource, sysId] });
      queryClient.invalidateQueries({ queryKey: ["records", resource] });
    },
  });

  const recordTitle = data?.number || data?.name || data?.sys_id || "Loading…";
  const permissions = data ? getRecordPermissions(data) : null;
  const canWrite = !!permissions?.write;
  const editableFields = fields.filter((field) => canWrite && !field.readOnly);
  const lockedFields = fields.filter((field) => !canWrite || field.readOnly);
  const showEditableDivider = lockedFields.length > 0 && editableFields.length > 0;

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
        actions={
          permissions?.read && sysId ? (
            <RecordSharePopover
              resource={resource}
              sysId={sysId}
              record={data}
              canWrite={canWrite}
            />
          ) : undefined
        }
      />

      <DetailSection title={sectionTitle} icon={<OverviewIcon />} accent="accent">
        <div className="detail-field-groups">
          {lockedFields.length > 0 && (
            <DetailFieldGroup>
              {lockedFields.map((field) => {
                const raw = data[field.key];
                const display =
                  field.type === "select-state"
                    ? STATE_LABELS[String(raw)] || formatReadOnlyValue(raw)
                    : raw;

                return (
                  <ReadOnlyFieldInput
                    key={field.key}
                    id={`field-${field.key}`}
                    label={field.label}
                    value={display}
                    multiline={field.type === "textarea"}
                    gridColumn={field.type === "textarea" ? "1 / -1" : undefined}
                  />
                );
              })}
            </DetailFieldGroup>
          )}

          {editableFields.length > 0 && (
            <DetailFieldGroup dividerTop={showEditableDivider}>
              {editableFields.map((field) => (
                <div
                  className="form-group"
                  key={field.key}
                  style={{
                    marginBottom: 0,
                    gridColumn: field.type === "textarea" ? "1 / -1" : undefined,
                  }}
                >
                  <label htmlFor={`field-${field.key}`}>{field.label}</label>
                  {field.type === "select-state" ? (
                    <select
                      id={`field-${field.key}`}
                      value={form[field.key] ?? ""}
                      onChange={(e) => setForm({ ...form, [field.key]: e.target.value })}
                    >
                      {Object.entries(STATE_LABELS).map(([val, label]) => (
                        <option key={val} value={val}>
                          {label}
                        </option>
                      ))}
                    </select>
                  ) : field.type === "textarea" ? (
                    <textarea
                      id={`field-${field.key}`}
                      rows={3}
                      value={form[field.key] ?? ""}
                      onChange={(e) => setForm({ ...form, [field.key]: e.target.value })}
                    />
                  ) : (
                    <input
                      id={`field-${field.key}`}
                      type="text"
                      value={form[field.key] ?? ""}
                      onChange={(e) => setForm({ ...form, [field.key]: e.target.value })}
                    />
                  )}
                </div>
              ))}
            </DetailFieldGroup>
          )}
        </div>

        {canWrite && editableFields.length > 0 && (
          <div style={{ marginTop: "1.25rem" }}>
            <button
              className="btn btn-primary"
              onClick={() => updateMutation.mutate(form)}
              disabled={!isDirty || updateMutation.isPending}
            >
              {updateMutation.isPending ? "Saving..." : "Save Changes"}
            </button>
          </div>
        )}
      </DetailSection>

      {sysId && (permissions?.comment || permissions?.write) && (
        <RecordCommentsSection
          resource={resource}
          sysId={sysId}
          canComment={!!(permissions?.comment || permissions?.write)}
        />
      )}
    </div>
  );
}
