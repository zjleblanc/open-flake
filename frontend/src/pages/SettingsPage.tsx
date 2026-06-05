import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";

export function SettingsPage() {
  const [apiKeyName, setApiKeyName] = useState("");
  const [newKey, setNewKey] = useState<string | null>(null);
  const [oauthForm, setOauthForm] = useState({ name: "", client_id: "", client_secret: "" });
  const queryClient = useQueryClient();

  const apiKeys = useQuery({ queryKey: ["api-keys"], queryFn: api.listApiKeys });
  const oauthClients = useQuery({ queryKey: ["oauth-clients"], queryFn: api.listOAuthClients });

  const createKeyMutation = useMutation({
    mutationFn: () => api.createApiKey(apiKeyName),
    onSuccess: (data) => {
      setNewKey(data.api_key);
      setApiKeyName("");
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
    },
  });

  const createOAuthMutation = useMutation({
    mutationFn: () => api.createOAuthClient(oauthForm),
    onSuccess: () => {
      setOauthForm({ name: "", client_id: "", client_secret: "" });
      queryClient.invalidateQueries({ queryKey: ["oauth-clients"] });
    },
  });

  return (
    <div>
      <div className="page-header">
        <h1>Settings</h1>
      </div>

      <div className="card" style={{ marginBottom: "1.5rem" }}>
        <h2 className="section-title">API Keys</h2>
        <p className="text-body" style={{ marginBottom: "1rem" }}>
          API keys are sent via the <code className="code-inline">x-sn-apikey</code> header for Ansible automation.
        </p>
        <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
          <input
            placeholder="Key name"
            value={apiKeyName}
            onChange={(e) => setApiKeyName(e.target.value)}
            style={{ flex: 1 }}
          />
          <button
            className="btn btn-primary"
            onClick={() => createKeyMutation.mutate()}
            disabled={!apiKeyName || createKeyMutation.isPending}
          >
            Generate
          </button>
        </div>
        {newKey && (
          <div className="code-block" style={{ marginBottom: "1rem" }}>
            <p className="text-xs text-muted" style={{ marginBottom: "0.5rem" }}>
              Copy this key now — it won't be shown again:
            </p>
            {newKey}
          </div>
        )}
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {(apiKeys.data || []).map((k) => (
              <tr key={k.sys_id}>
                <td>{k.name}</td>
                <td>{k.active ? "Active" : "Inactive"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2 className="section-title">OAuth Clients</h2>
        <div className="detail-grid" style={{ marginBottom: "1rem" }}>
          {(["name", "client_id", "client_secret"] as const).map((key) => (
            <div className="form-group" key={key}>
              <label>{key.replace("_", " ")}</label>
              <input
                value={oauthForm[key]}
                onChange={(e) => setOauthForm({ ...oauthForm, [key]: e.target.value })}
              />
            </div>
          ))}
        </div>
        <button
          className="btn btn-primary"
          onClick={() => createOAuthMutation.mutate()}
          disabled={createOAuthMutation.isPending}
        >
          Add Client
        </button>
        <table style={{ marginTop: "1rem" }}>
          <thead>
            <tr>
              <th>Name</th>
              <th>Client ID</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {(oauthClients.data || []).map((c) => (
              <tr key={c.sys_id}>
                <td>{c.name}</td>
                <td>{c.client_id}</td>
                <td>{c.active ? "Active" : "Inactive"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
