import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, getRecordPermissions, type RecordPermissions } from "../api/client";

function refValue(field: unknown): string {
  if (!field) return "";
  if (typeof field === "object" && field !== null && "value" in field) {
    return String((field as { value: string }).value);
  }
  return String(field);
}

function formatPermissions(perms: RecordPermissions): string[] {
  const labels: string[] = [];
  if (perms.write) labels.push("Write");
  else if (perms.comment) labels.push("Comment");
  else if (perms.read) labels.push("View");
  if (perms.delete && perms.write) labels.push("Delete");
  return labels.length > 0 ? labels : ["None"];
}

interface RecordSharePanelProps {
  resource: string;
  sysId: string;
  record: Record<string, unknown>;
  canWrite: boolean;
}

export function RecordSharePanel({ resource, sysId, record, canWrite }: RecordSharePanelProps) {
  const queryClient = useQueryClient();
  const permissions = getRecordPermissions(record);
  const [accessLevel, setAccessLevel] = useState<"view" | "comment">("view");
  const [granteeType, setGranteeType] = useState<"user" | "group">("user");
  const [granteeId, setGranteeId] = useState("");
  const [owner, setOwner] = useState(refValue(record.owner));
  const [ownerGroup, setOwnerGroup] = useState(refValue(record.owner_group));

  useEffect(() => {
    setOwner(refValue(record.owner));
    setOwnerGroup(refValue(record.owner_group));
  }, [record.owner, record.owner_group]);

  const { data: grants = [] } = useQuery({
    queryKey: ["grants", resource, sysId],
    queryFn: () => api.listGrants(resource, sysId),
    enabled: canWrite,
  });

  const users = useQuery({
    queryKey: ["records", "users"],
    queryFn: () => api.listRecords("users"),
  });

  const groups = useQuery({
    queryKey: ["records", "groups"],
    queryFn: () => api.listRecords("groups"),
  });

  const userLabels = Object.fromEntries(
    (users.data?.records || []).map((u) => [u.sys_id, u.user_name])
  );
  const groupLabels = Object.fromEntries(
    (groups.data?.records || []).map((g) => [g.sys_id, g.name])
  );

  const ownerMutation = useMutation({
    mutationFn: (payload: { owner?: string; owner_group?: string }) =>
      api.updateRecord(resource, sysId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["record", resource, sysId] });
    },
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api.createGrant(resource, sysId, {
        access_level: accessLevel,
        user_sys_id: granteeType === "user" ? granteeId : undefined,
        group_sys_id: granteeType === "group" ? granteeId : undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["grants", resource, sysId] });
      setGranteeId("");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (grantSysId: string) => api.deleteGrant(resource, sysId, grantSysId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["grants", resource, sysId] });
    },
  });

  const granteeOptions =
    granteeType === "user"
      ? (users.data?.records || []).map((u) => ({ id: u.sys_id, label: u.user_name }))
      : (groups.data?.records || []).map((g) => ({ id: g.sys_id, label: g.name }));

  const ownerLabel = userLabels[owner] || owner || "—";
  const ownerGroupLabel = groupLabels[ownerGroup] || ownerGroup || "—";
  const permissionLabels = formatPermissions(permissions);

  return (
    <div className="share-panel">
      <section className="share-panel-section">
        <h3 className="share-panel-section-title">Your access</h3>
        <div className="share-permission-badges">
          {permissionLabels.map((label) => (
            <span key={label} className="share-permission-badge">
              {label}
            </span>
          ))}
        </div>
      </section>

      <section className="share-panel-section">
        <h3 className="share-panel-section-title">Ownership</h3>
        {canWrite ? (
          <div className="share-ownership-form">
            <div className="form-group">
              <label htmlFor={`owner-${sysId}`}>Owner</label>
              <select
                id={`owner-${sysId}`}
                value={owner}
                onChange={(e) => setOwner(e.target.value)}
              >
                <option value="">None</option>
                {(users.data?.records || []).map((u) => (
                  <option key={u.sys_id} value={u.sys_id}>
                    {u.user_name}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label htmlFor={`owner-group-${sysId}`}>Owner group</label>
              <select
                id={`owner-group-${sysId}`}
                value={ownerGroup}
                onChange={(e) => setOwnerGroup(e.target.value)}
              >
                <option value="">None</option>
                {(groups.data?.records || []).map((g) => (
                  <option key={g.sys_id} value={g.sys_id}>
                    {g.name}
                  </option>
                ))}
              </select>
            </div>
            <button
              className="btn btn-secondary btn-sm"
              type="button"
              disabled={ownerMutation.isPending}
              onClick={() =>
                ownerMutation.mutate({
                  owner: owner || "",
                  owner_group: ownerGroup || "",
                })
              }
            >
              Save ownership
            </button>
          </div>
        ) : (
          <dl className="share-ownership-readonly">
            <div>
              <dt>Owner</dt>
              <dd>{ownerLabel}</dd>
            </div>
            <div>
              <dt>Owner group</dt>
              <dd>{ownerGroupLabel}</dd>
            </div>
          </dl>
        )}
      </section>

      {canWrite && (
        <section className="share-panel-section">
          <h3 className="share-panel-section-title">Additional access</h3>
          <p className="share-panel-intro text-muted text-sm">
            Grant view or comment access to other users and groups.
          </p>

          {grants.length === 0 ? (
            <p className="text-muted text-sm">No additional access grants.</p>
          ) : (
            <ul className="sharing-grant-list">
              {grants.map((g) => {
                const grantee =
                  (g.user_sys_id && userLabels[g.user_sys_id]) ||
                  (g.group_sys_id && groupLabels[g.group_sys_id]) ||
                  g.user_sys_id ||
                  g.group_sys_id;
                const granteeKind = g.user_sys_id ? "User" : "Group";
                return (
                  <li key={g.sys_id} className="sharing-grant-item">
                    <div className="sharing-grant-info">
                      <span className="sharing-grant-level">{g.access_level}</span>
                      <span className="sharing-grant-name">
                        {granteeKind}: {grantee}
                      </span>
                    </div>
                    <button
                      className="btn btn-secondary btn-sm"
                      type="button"
                      onClick={() => deleteMutation.mutate(g.sys_id)}
                      disabled={deleteMutation.isPending}
                    >
                      Remove
                    </button>
                  </li>
                );
              })}
            </ul>
          )}

          <div className="sharing-grant-form">
            <div className="form-group">
              <label htmlFor={`grant-level-${sysId}`}>Access level</label>
              <select
                id={`grant-level-${sysId}`}
                value={accessLevel}
                onChange={(e) => setAccessLevel(e.target.value as "view" | "comment")}
              >
                <option value="view">View</option>
                <option value="comment">Comment</option>
              </select>
            </div>
            <div className="form-group">
              <label htmlFor={`grantee-type-${sysId}`}>Grant to</label>
              <select
                id={`grantee-type-${sysId}`}
                value={granteeType}
                onChange={(e) => {
                  setGranteeType(e.target.value as "user" | "group");
                  setGranteeId("");
                }}
              >
                <option value="user">User</option>
                <option value="group">Group</option>
              </select>
            </div>
            <div className="form-group">
              <label htmlFor={`grantee-id-${sysId}`}>
                {granteeType === "user" ? "User" : "Group"}
              </label>
              <select
                id={`grantee-id-${sysId}`}
                value={granteeId}
                onChange={(e) => setGranteeId(e.target.value)}
              >
                <option value="">Select…</option>
                {granteeOptions.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
            <button
              className="btn btn-primary"
              type="button"
              disabled={!granteeId || createMutation.isPending}
              onClick={() => createMutation.mutate()}
            >
              Add access
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
