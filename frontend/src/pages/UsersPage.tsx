import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";

export function UsersPage() {
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    user_name: "",
    password: "",
    first_name: "",
    last_name: "",
    email: "",
  });
  const queryClient = useQueryClient();

  const users = useQuery({ queryKey: ["records", "users"], queryFn: () => api.listRecords("users") });
  const groups = useQuery({ queryKey: ["records", "groups"], queryFn: () => api.listRecords("groups") });

  const createMutation = useMutation({
    mutationFn: () => api.createUser(form),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["records", "users"] });
      setShowCreate(false);
      setForm({ user_name: "", password: "", first_name: "", last_name: "", email: "" });
    },
  });

  return (
    <div>
      <div className="page-header">
        <h1>Users & Groups</h1>
        <button className="btn btn-primary" onClick={() => setShowCreate(!showCreate)}>
          {showCreate ? "Cancel" : "New User"}
        </button>
      </div>

      {showCreate && (
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
              {(users.data?.records || []).map((u) => (
                <tr key={u.sys_id}>
                  <td>{u.user_name}</td>
                  <td>
                    {u.first_name} {u.last_name}
                  </td>
                  <td>{u.email}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <h2 className="card-section-title">Groups</h2>
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              {(groups.data?.records || []).map((g) => (
                <tr key={g.sys_id}>
                  <td>{g.name}</td>
                  <td>{g.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
