import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { ToastBanner } from "../components/ToastBanner";
import "../components/Layout.css";

const CMDB_CI_FIELDS: { key: string; label: string }[] = [
  { key: "name", label: "Name" },
  { key: "short_description", label: "Short Description" },
  { key: "sys_class_name", label: "Class" },
  { key: "asset_tag", label: "Asset Tag" },
  { key: "serial_number", label: "Serial Number" },
  { key: "install_status", label: "Install Status" },
  { key: "operational_status", label: "Operational Status" },
  { key: "environment", label: "Environment" },
  { key: "ip_address", label: "IP Address" },
  { key: "mac_address", label: "MAC Address" },
  { key: "category", label: "Category" },
  { key: "assigned_to", label: "Assigned To" },
];

const CMDB_CI_SYSTEM_FIELDS: { key: string; label: string }[] = [
  { key: "sys_id", label: "Sys ID" },
  { key: "sys_created_on", label: "Created" },
  { key: "sys_updated_on", label: "Updated" },
  { key: "sys_created_by", label: "Created By" },
  { key: "sys_updated_by", label: "Updated By" },
];

const EDITABLE_FIELDS: { key: string; label: string }[] = [
  { key: "name", label: "Name" },
  { key: "short_description", label: "Short Description" },
  { key: "asset_tag", label: "Asset Tag" },
  { key: "serial_number", label: "Serial Number" },
  { key: "install_status", label: "Install Status" },
  { key: "operational_status", label: "Operational Status" },
  { key: "environment", label: "Environment" },
  { key: "ip_address", label: "IP Address" },
  { key: "mac_address", label: "MAC Address" },
  { key: "category", label: "Category" },
];

const KNOWN_FIELD_KEYS = new Set([
  ...CMDB_CI_FIELDS.map((f) => f.key),
  ...CMDB_CI_SYSTEM_FIELDS.map((f) => f.key),
]);

type SaveMessage = { type: "success" | "error"; text: string };

function formatFieldValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "object") {
    const ref = value as { value?: string; link?: string };
    if (ref.value) return ref.value;
    return JSON.stringify(value, null, 2);
  }
  return String(value);
}

function humanizeFieldKey(key: string): string {
  return key
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function extractOtherFields(data: Record<string, string>): Record<string, string> {
  const other: Record<string, string> = {};
  for (const [key, value] of Object.entries(data)) {
    if (!KNOWN_FIELD_KEYS.has(key)) {
      other[key] = formatFieldValue(value) === "—" ? "" : formatFieldValue(value);
    }
  }
  return other;
}

const SNAKE_CASE_PATTERN = /^[a-z][a-z0-9]*(_[a-z0-9]+)*$/;

function normalizePropertyKey(key: string): string {
  return key.trim().replace(/\s+/g, "_").toLowerCase();
}

function isSnakeCaseKey(key: string): boolean {
  return SNAKE_CASE_PATTERN.test(key);
}

function validatePropertyKey(key: string, otherForm: Record<string, string>): string | null {
  if (!key) return "Property name is required.";
  if (!isSnakeCaseKey(key)) {
    return "Property name must be snake_case (e.g. model_number).";
  }
  if (KNOWN_FIELD_KEYS.has(key)) return `"${key}" is a reserved field and cannot be added here.`;
  if (key in otherForm) return `"${key}" already exists.`;
  return null;
}

function validateOtherFormKeys(otherForm: Record<string, string>): string | null {
  for (const key of Object.keys(otherForm)) {
    if (!isSnakeCaseKey(key)) {
      return `Invalid property name "${key}": must be snake_case (e.g. model_number).`;
    }
  }
  return null;
}

function PropertyField({ label, value }: { label: string; value: unknown }) {
  const formatted = formatFieldValue(value);
  const isMultiline = formatted.includes("\n");

  return (
    <div>
      <p className="field-label">{label}</p>
      {isMultiline ? (
        <pre className="code-block" style={{ margin: 0 }}>
          {formatted}
        </pre>
      ) : (
        <p>{formatted}</p>
      )}
    </div>
  );
}

export function ConfigurationItemDetailPage() {
  const { sysId } = useParams<{ sysId: string }>();
  const queryClient = useQueryClient();
  const resource = "configuration-items";

  const [form, setForm] = useState<Record<string, string>>({});
  const [otherForm, setOtherForm] = useState<Record<string, string>>({});
  const [newPropertyKey, setNewPropertyKey] = useState("");
  const [newPropertyValue, setNewPropertyValue] = useState("");
  const [addPropertyError, setAddPropertyError] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<SaveMessage | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["record", resource, sysId],
    queryFn: () => api.getRecord(resource, sysId!),
    enabled: !!sysId,
  });

  useEffect(() => {
    if (!data) return;
    const nextForm: Record<string, string> = {};
    EDITABLE_FIELDS.forEach((field) => {
      nextForm[field.key] = data[field.key] || "";
    });
    setForm(nextForm);
    setOtherForm(extractOtherFields(data));
  }, [data]);

  const updateMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      api.updateRecord(resource, sysId!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["record", resource, sysId] });
      queryClient.invalidateQueries({ queryKey: ["records", resource] });
      setSaveMessage({ type: "success", text: "Changes saved successfully." });
    },
    onError: (error: Error) => {
      setSaveMessage({ type: "error", text: error.message || "Failed to save changes." });
    },
  });

  if (isLoading || !data) return <p>Loading...</p>;

  const otherPropertyKeys = Object.keys(otherForm).sort();
  const statusLabel = data.operational_status || data.install_status || data.sys_class_name;

  const handleSave = () => {
    setSaveMessage(null);
    const otherValidationError = validateOtherFormKeys(otherForm);
    if (otherValidationError) {
      setSaveMessage({ type: "error", text: otherValidationError });
      return;
    }
    const payload: Record<string, unknown> = { ...form };
    if (otherPropertyKeys.length > 0) {
      payload.other = { ...otherForm };
    }
    updateMutation.mutate(payload);
  };

  const handleAddProperty = () => {
    const key = normalizePropertyKey(newPropertyKey);
    const validationError = validatePropertyKey(key, otherForm);
    if (validationError) {
      setAddPropertyError(validationError);
      return;
    }
    setOtherForm({ ...otherForm, [key]: newPropertyValue });
    setNewPropertyKey("");
    setNewPropertyValue("");
    setAddPropertyError(null);
  };

  return (
    <>
      {saveMessage && (
        <ToastBanner
          message={saveMessage.text}
          type={saveMessage.type}
          onDismiss={() => setSaveMessage(null)}
          durationMs={saveMessage.type === "success" ? 2500 : 4000}
        />
      )}

      <div>
        <div className="page-header">
        <div>
          <Link to="/configuration-items" className="text-sm">
            ← Back to Configuration Items
          </Link>
          <h1>{data.name || data.sys_id}</h1>
        </div>
        {statusLabel && <span className="badge badge-closed">{statusLabel}</span>}
      </div>

      <div className="card">
        <h2 className="section-title">Properties</h2>
        <div className="detail-grid">
          {CMDB_CI_FIELDS.map((field) => (
            <PropertyField key={field.key} label={field.label} value={data[field.key]} />
          ))}
          {otherPropertyKeys.map((key) => (
            <PropertyField key={key} label={humanizeFieldKey(key)} value={data[key]} />
          ))}
        </div>
      </div>

      <details className="property-panel" style={{ marginTop: "1rem" }}>
        <summary>Show system properties</summary>
        <div className="property-panel-body">
          <div className="detail-grid">
            {CMDB_CI_SYSTEM_FIELDS.map((field) => (
              <PropertyField key={field.key} label={field.label} value={data[field.key]} />
            ))}
          </div>
        </div>
      </details>

      <div className="card" style={{ marginTop: "1rem" }}>
        <h2 className="section-title">Update</h2>
        <div className="detail-grid">
          {EDITABLE_FIELDS.map((field) => (
            <div className="form-group" key={field.key} style={{ marginBottom: 0 }}>
              <label>{field.label}</label>
              <input
                type="text"
                value={form[field.key] ?? ""}
                onChange={(e) => setForm({ ...form, [field.key]: e.target.value })}
              />
            </div>
          ))}
        </div>

        <details className="property-panel" style={{ marginTop: "1.25rem" }}>
          <summary>
            Additional Properties
            <span className="property-panel-count">{otherPropertyKeys.length}</span>
          </summary>
          <div className="property-panel-body">
            {otherPropertyKeys.length > 0 && (
              <div className="detail-grid" style={{ marginBottom: "1.25rem" }}>
                {otherPropertyKeys.map((key) => (
                  <div className="form-group" key={key} style={{ marginBottom: 0 }}>
                    <label>{humanizeFieldKey(key)}</label>
                    <input
                      type="text"
                      value={otherForm[key] ?? ""}
                      onChange={(e) =>
                        setOtherForm({ ...otherForm, [key]: e.target.value })
                      }
                    />
                  </div>
                ))}
              </div>
            )}

            <div className="property-add-row">
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label htmlFor="new-property-key">Property Name</label>
                <input
                  id="new-property-key"
                  type="text"
                  placeholder="e.g. model_number"
                  value={newPropertyKey}
                  onChange={(e) => {
                    setNewPropertyKey(e.target.value);
                    setAddPropertyError(null);
                  }}
                  onBlur={() => {
                    if (newPropertyKey.trim()) {
                      setNewPropertyKey(normalizePropertyKey(newPropertyKey));
                    }
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      handleAddProperty();
                    }
                  }}
                />
              </div>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label htmlFor="new-property-value">Value</label>
                <input
                  id="new-property-value"
                  type="text"
                  placeholder="Property value"
                  value={newPropertyValue}
                  onChange={(e) => setNewPropertyValue(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      handleAddProperty();
                    }
                  }}
                />
              </div>
              <div className="property-add-action">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={handleAddProperty}
                >
                  Add Property
                </button>
              </div>
            </div>
            {addPropertyError && <p className="error">{addPropertyError}</p>}
          </div>
        </details>

        <div style={{ marginTop: "1.25rem" }}>
          <button
            className="btn btn-primary"
            onClick={handleSave}
            disabled={updateMutation.isPending}
          >
            {updateMutation.isPending ? "Saving..." : "Save Changes"}
          </button>
        </div>
      </div>
      </div>
    </>
  );
}
