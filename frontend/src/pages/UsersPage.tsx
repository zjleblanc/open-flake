import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { usePageHeader } from "../components/PageHeaderContext";
import { EmptyValue, isEmptyDisplayValue } from "../components/EmptyValue";

export function UsersPage() {
  const { hasPermission } = useAuth();
  const canReadUsers = hasPermission("users.read");
  const canWriteUsers = hasPermission("users.write");
  const canReadGroups = hasPermission("groups.read");
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    user_name: "",
    password: "",
    first_name: "",
    last_name: "",
    email: "",
  });
  const queryClient = useQueryClient();

  const users = useQuery({
    queryKey: ["records", "users"],
    queryFn: () => api.listRecords("users"),
    enabled: canReadUsers,
  });
  const groups = useQuery({
    queryKey: ["records", "groups"],
    queryFn: () => api.listRecords("groups"),
    enabled: canReadGroups,
  });

  const createMutation = useMutation({
    mutationFn: () => api.createUser(form),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["records", "users"] });
      setShowCreate(false);
      setForm({ user_name: "", password: "", first_name: "", last_name: "", email: "" });
    },
  });

  const headerBreadcrumbs = useMemo(() => [{ label: "Users & Groups" }], []);
  const headerActions = useMemo(
    () =>
      canWriteUsers && (canReadUsers || canReadGroups) ? (
        <button className="btn btn-primary" onClick={() => setShowCreate(!showCreate)}>
          {showCreate ? "Cancel" : "New User"}
        </button>
      ) : undefined,
    [canWriteUsers, canReadUsers, canReadGroups, showCreate]
  );

  usePageHeader({ breadcrumbs: headerBreadcrumbs, actions: headerActions });

  if (!canReadUsers && !canReadGroups) {
    return (
      <div>
        <p className="text-muted">You do not have permission to view users or groups.</p>
      </div>
    );
  }

  return (
    <div>
      {showCreate && canWriteUsers && (
        <div className="card" style={{ marginBottom: "1.5rem" }}>
          <h2 className="section-title">Create User</h2>
          {(["user_name", "password", "first_name", "last_name", "email"] as const).map((key) => (
            <div className="form-group" key={key}>
              <label>{key.replace("_", " ")}</label>
              <input
                type={key === "password" ? "password" : "text"}
                value={form[key]}
                onChange={(e) => setForm({ ...form, [key]: e.target.value })}
              />
            </div>
          ))}
          <button
            className="btn btn-primary"
            onClick={() => createMutation.mutate()}
            disabled={createMutation.isPending}
          >
            Create
          </button>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem" }}>
        {canReadUsers && (
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <h2 className="card-section-title">Users</h2>
          <table>
            <thead>
              <tr>
                <th>Username</th>
                <th>Name</th>
                <th>Email</th>
              </tr>
            </thead>
            <tbody>
              {(users.data?.records || []).length === 0 ? (
                <tr>
                  <td colSpan={3} className="empty-state">
                    No users yet
                  </td>
                </tr>
              ) : (
                (users.data?.records || []).map((u) => (
                  <tr key={u.sys_id}>
                    <td>{u.user_name}</td>
                    <td>
                      {u.first_name} {u.last_name}
                    </td>
                    <td>{u.email}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        )}

        {canReadGroups && (
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <h2 className="card-section-title">Groups</h2>
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Description</th>
                <th>Owner</th>
              </tr>
            </thead>
            <tbody>
              {(groups.data?.records || []).length === 0 ? (
                <tr>
                  <td colSpan={3} className="empty-state">
                    No groups yet
                  </td>
                </tr>
              ) : (
                (groups.data?.records || []).map((g) => (
                  <tr key={g.sys_id}>
                    <td>{g.name}</td>
                    <td>{g.description}</td>
                    <td>
                      {isEmptyDisplayValue(g.owner) ? (
                        <EmptyValue />
                      ) : typeof g.owner === "object" ? (
                        (g.owner as { value?: string }).value
                      ) : (
                        g.owner
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        )}
      </div>
    </div>
  );
}
