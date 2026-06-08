const TOKEN_KEY = "openflake_token";

export interface RecordPermissions {
  read: boolean;
  write: boolean;
  comment: boolean;
  delete: boolean;
}

export interface AuthMe {
  sys_id: string;
  user_name: string;
  permissions: string[];
  group_ids: string[];
}

export function getRecordPermissions(record: Record<string, unknown>): RecordPermissions {
  const p = record._permissions;
  if (p && typeof p === "object") {
    const perms = p as Record<string, unknown>;
    return {
      read: coerceBool(perms.read),
      write: coerceBool(perms.write),
      comment: coerceBool(perms.comment),
      delete: coerceBool(perms.delete),
    };
  }
  return { read: true, write: true, comment: true, delete: true };
}

function coerceBool(value: unknown): boolean {
  if (value === true || value === "true") return true;
  if (value === false || value === "false") return false;
  return Boolean(value);
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const res = await fetch(path, { ...options, headers });
  if (res.status === 401) {
    clearToken();
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }
  if (res.status === 204) {
    return undefined as T;
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

export const api = {
  login: (username: string, password: string) =>
    request<{ access_token: string; user_name: string; sys_id: string }>(
      "/api/v1/auth/login",
      {
        method: "POST",
        body: JSON.stringify({ username, password }),
      }
    ),

  me: () => request<AuthMe>("/api/v1/auth/me"),

  dashboard: () =>
    request<{
      incidents_open: number;
      problems_open: number;
      changes_open: number;
      cis_total: number;
    }>("/api/v1/dashboard"),

  listRecords: (resource: string, params?: { state?: string }) => {
    const qs = new URLSearchParams();
    if (params?.state) qs.set("state", params.state);
    return request<{ records: Record<string, string>[]; total: number }>(
      `/api/v1/records/${resource}?${qs}`
    );
  },

  getRecord: (resource: string, sysId: string) =>
    request<Record<string, string>>(`/api/v1/records/${resource}/${sysId}`),

  createRecord: (resource: string, data: Record<string, unknown>) =>
    request<Record<string, string>>(`/api/v1/records/${resource}`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateRecord: (resource: string, sysId: string, data: Record<string, unknown>) =>
    request<Record<string, string>>(`/api/v1/records/${resource}/${sysId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  deleteRecord: (resource: string, sysId: string) =>
    request<void>(`/api/v1/records/${resource}/${sysId}`, { method: "DELETE" }),

  createUser: (data: {
    user_name: string;
    password: string;
    first_name?: string;
    last_name?: string;
    email?: string;
  }) =>
    request<Record<string, string>>("/api/v1/users", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  listApiKeys: () =>
    request<{ sys_id: string; name: string; active: boolean }[]>("/api/v1/settings/api-keys"),

  createApiKey: (name: string) =>
    request<{ sys_id: string; name: string; api_key: string }>("/api/v1/settings/api-keys", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),

  listOAuthClients: () =>
    request<{ sys_id: string; client_id: string; name: string; active: boolean }[]>(
      "/api/v1/settings/oauth-clients"
    ),

  createOAuthClient: (data: { name: string; client_id: string; client_secret: string }) =>
    request<{ sys_id: string; client_id: string; name: string }>(
      "/api/v1/settings/oauth-clients",
      { method: "POST", body: JSON.stringify(data) }
    ),

  listGrants: (resource: string, sysId: string) =>
    request<
      {
        sys_id: string;
        access_level: string;
        user_sys_id: string;
        group_sys_id: string;
      }[]
    >(`/api/v1/records/${resource}/${sysId}/grants`),

  createGrant: (
    resource: string,
    sysId: string,
    data: { access_level: string; user_sys_id?: string; group_sys_id?: string }
  ) =>
    request<Record<string, string>>(`/api/v1/records/${resource}/${sysId}/grants`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  deleteGrant: (resource: string, sysId: string, grantSysId: string) =>
    request<void>(`/api/v1/records/${resource}/${sysId}/grants/${grantSysId}`, {
      method: "DELETE",
    }),

  listComments: (resource: string, sysId: string) =>
    request<
      { sys_id: string; comment: string; sys_created_by: string; sys_created_on: string }[]
    >(`/api/v1/records/${resource}/${sysId}/comments`),

  createComment: (resource: string, sysId: string, comment: string) =>
    request<Record<string, string>>(`/api/v1/records/${resource}/${sysId}/comments`, {
      method: "POST",
      body: JSON.stringify({ comment }),
    }),

  listAttachments: (resource: string, sysId: string) =>
    request<
      {
        sys_id: string;
        file_name: string;
        content_type: string;
        size_bytes: string;
        sys_created_on: string;
      }[]
    >(`/api/v1/records/${resource}/${sysId}/attachments`),

  uploadAttachment: async (resource: string, sysId: string, file: File) => {
    const token = getToken();
    const formData = new FormData();
    formData.append("file", file);
    const headers: Record<string, string> = {};
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    const res = await fetch(`/api/v1/records/${resource}/${sysId}/attachments`, {
      method: "POST",
      headers,
      body: formData,
    });
    if (res.status === 401) {
      clearToken();
      window.location.href = "/login";
      throw new Error("Unauthorized");
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Upload failed");
    }
    return res.json() as Promise<{
      sys_id: string;
      file_name: string;
      content_type: string;
      size_bytes: string;
      sys_created_on: string;
    }>;
  },

  deleteAttachment: (resource: string, sysId: string, attachmentSysId: string) =>
    request<void>(`/api/v1/records/${resource}/${sysId}/attachments/${attachmentSysId}`, {
      method: "DELETE",
    }),

  fetchAttachmentBlob: async (resource: string, sysId: string, attachmentSysId: string) => {
    const token = getToken();
    const headers: Record<string, string> = {};
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    const res = await fetch(
      `/api/v1/records/${resource}/${sysId}/attachments/${attachmentSysId}/file`,
      { headers }
    );
    if (res.status === 401) {
      clearToken();
      window.location.href = "/login";
      throw new Error("Unauthorized");
    }
    if (!res.ok) {
      throw new Error("Failed to load attachment");
    }
    return res.blob();
  },
};

export const STATE_LABELS: Record<string, string> = {
  "1": "New",
  "2": "In Progress",
  "3": "On Hold",
  "6": "Resolved",
  "7": "Closed",
  "8": "Canceled",
  "-5": "New",
  "-4": "Assess",
  "-3": "Authorize",
  "-2": "Scheduled",
  "-1": "Implement",
  "0": "Review",
};

export function stateBadge(state: string): string {
  if (state === "1" || state === "-5") return "badge-new";
  if (state === "2" || state === "-4" || state === "-3") return "badge-progress";
  if (state === "6" || state === "0") return "badge-resolved";
  if (state === "7") return "badge-closed";
  return "badge-new";
}
