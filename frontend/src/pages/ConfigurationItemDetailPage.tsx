import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { api, getRecordPermissions } from "../api/client";
import { DetailPageHeader } from "../components/DetailPageHeader";
import { DetailSection } from "../components/DetailSection";
import { PlusCircleIcon, PropertiesIcon, SystemIcon } from "../components/DetailIcons";
import {
  DetailFieldGroup,
  ReadOnlyFieldInput,
  resolveUserLabel,
  ToggleSwitch,
} from "../components/DetailFieldControls";
import { RecordCommentsSection } from "../components/RecordCommentsSection";
import { RecordSharePopover } from "../components/RecordSharePopover";
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

const EDITABLE_FIELD_KEYS = new Set(EDITABLE_FIELDS.map((f) => f.key));

const USER_REFERENCE_FIELDS = new Set(["assigned_to", "sys_created_by", "sys_updated_by"]);

const RBAC_FIELD_KEYS = new Set(["owner", "owner_group", "_permissions"]);

const KNOWN_FIELD_KEYS = new Set([
  ...CMDB_CI_FIELDS.map((f) => f.key),
  ...CMDB_CI_SYSTEM_FIELDS.map((f) => f.key),
  ...RBAC_FIELD_KEYS,
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

function recordsEqual(a: Record<string, string>, b: Record<string, string>): boolean {
  const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
  for (const key of keys) {
    if ((a[key] ?? "") !== (b[key] ?? "")) return false;
  }
  return true;
}

function buildFormFromData(data: Record<string, string>): Record<string, string> {
  const nextForm: Record<string, string> = {};
  EDITABLE_FIELDS.forEach((field) => {
    nextForm[field.key] = data[field.key] || "";
  });
  return nextForm;
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

function resolveLockedFieldValue(
  key: string,
  value: unknown,
  userLabels: Record<string, string>
): unknown {
  if (USER_REFERENCE_FIELDS.has(key)) {
    return resolveUserLabel(value, userLabels);
  }
  return value;
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
  const [showSystemProperties, setShowSystemProperties] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["record", resource, sysId],
    queryFn: () => api.getRecord(resource, sysId!),
    enabled: !!sysId,
  });

  const { data: usersData } = useQuery({
    queryKey: ["records", "users"],
    queryFn: () => api.listRecords("users"),
  });

  const userLabels = useMemo(
    () =>
      Object.fromEntries((usersData?.records || []).map((user) => [user.sys_id, user.user_name])),
    [usersData]
  );

  useEffect(() => {
    if (!data) return;
    setForm(buildFormFromData(data));
    setOtherForm(extractOtherFields(data));
  }, [data]);

  const savedForm = useMemo(() => (data ? buildFormFromData(data) : {}), [data]);
  const savedOther = useMemo(() => (data ? extractOtherFields(data) : {}), [data]);
  const isDirty = useMemo(
    () => !recordsEqual(form, savedForm) || !recordsEqual(otherForm, savedOther),
    [form, otherForm, savedForm, savedOther]
  );

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

  const itemTitle = data?.name || data?.sys_id || "Loading…";
  const otherPropertyKeys = Object.keys(otherForm).sort();
  const statusLabel = data?.operational_status || data?.install_status || data?.sys_class_name;
  const permissions = data ? getRecordPermissions(data) : null;
  const canWrite = !!permissions?.write;
  const editableCiFields = CMDB_CI_FIELDS.filter(
    (field) => canWrite && EDITABLE_FIELD_KEYS.has(field.key)
  );
  const lockedCiFields = CMDB_CI_FIELDS.filter(
    (field) => !canWrite || !EDITABLE_FIELD_KEYS.has(field.key)
  );
  const readOnlyFields = [
    ...lockedCiFields,
    ...(showSystemProperties ? CMDB_CI_SYSTEM_FIELDS : []),
  ];
  const showEditableDivider = readOnlyFields.length > 0 && editableCiFields.length > 0;

  if (isLoading || !data) {
    return (
      <div className="detail-page">
        <DetailPageHeader
          breadcrumbs={[
            { label: "Configuration Items", to: "/configuration-items" },
            { label: "Loading…" },
          ]}
          title="Loading…"
        />
      </div>
    );
  }

  const handleSave = () => {
    setSaveMessage(null);
    const otherValidationError = validateOtherFormKeys(otherForm);
    if (otherValidationError) {
      setSaveMessage({ type: "error", text: otherValidationError });
      return;
    }
    const payload: Record<string, unknown> = { ...form };
    if (!recordsEqual(otherForm, savedOther)) {
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

      <div className="detail-page">
        <DetailPageHeader
          breadcrumbs={[
            { label: "Configuration Items", to: "/configuration-items" },
            { label: itemTitle },
          ]}
          title={itemTitle}
          badge={statusLabel ? <span className="badge badge-closed">{statusLabel}</span> : undefined}
          actions={
            permissions?.read && sysId ? (
              <RecordSharePopover
                resource={resource}
                sysId={sysId}
                record={data}
                canWrite={!!permissions?.write}
              />
            ) : undefined
          }
        />

      <DetailSection
        title="Properties"
        icon={<PropertiesIcon />}
        accent="accent"
        headerActions={
          <ToggleSwitch
            id="ci-show-system-properties"
            checked={showSystemProperties}
            onChange={setShowSystemProperties}
            icon={<SystemIcon size={14} />}
            label="System properties"
          />
        }
      >
        <div className="detail-field-groups">
          {readOnlyFields.length > 0 && (
            <DetailFieldGroup>
              {readOnlyFields.map((field) => (
                <ReadOnlyFieldInput
                  key={field.key}
                  id={`ci-${field.key}`}
                  label={field.label}
                  value={resolveLockedFieldValue(field.key, data[field.key], userLabels)}
                />
              ))}
            </DetailFieldGroup>
          )}

          {editableCiFields.length > 0 && (
            <DetailFieldGroup dividerTop={showEditableDivider}>
              {editableCiFields.map((field) => (
                <div className="form-group" key={field.key} style={{ marginBottom: 0 }}>
                  <label htmlFor={`ci-${field.key}`}>{field.label}</label>
                  <input
                    id={`ci-${field.key}`}
                    type="text"
                    value={form[field.key] ?? ""}
                    onChange={(e) => setForm({ ...form, [field.key]: e.target.value })}
                  />
                </div>
              ))}
            </DetailFieldGroup>
          )}
        </div>

        <details className="property-panel property-panel--accent" style={{ marginTop: "1.25rem" }}>
          <summary>
            <span className="property-panel-summary-icon">
              <PlusCircleIcon size={14} />
            </span>
            Additional Properties
            <span className="property-panel-count">{otherPropertyKeys.length}</span>
          </summary>
          <div className="property-panel-body">
            {otherPropertyKeys.length > 0 && (
              <DetailFieldGroup style={{ marginBottom: canWrite ? "1.25rem" : 0 }}>
                {otherPropertyKeys.map((key) => {
                  if (canWrite) {
                    return (
                      <div className="form-group" key={key} style={{ marginBottom: 0 }}>
                        <label htmlFor={`ci-other-${key}`}>{humanizeFieldKey(key)}</label>
                        <input
                          id={`ci-other-${key}`}
                          type="text"
                          value={otherForm[key] ?? ""}
                          onChange={(e) => setOtherForm({ ...otherForm, [key]: e.target.value })}
                        />
                      </div>
                    );
                  }
                  return (
                    <ReadOnlyFieldInput
                      key={key}
                      id={`ci-other-${key}`}
                      label={humanizeFieldKey(key)}
                      value={data[key]}
                    />
                  );
                })}
              </DetailFieldGroup>
            )}

            {!permissions?.write && otherPropertyKeys.length === 0 && (
              <p className="text-muted text-sm">No additional properties.</p>
            )}

            {permissions?.write && (
              <>
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
              </>
            )}
          </div>
        </details>

        {permissions?.write && (
          <div style={{ marginTop: "1.25rem" }}>
            <button
              className="btn btn-primary"
              onClick={handleSave}
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
    </>
  );
}
