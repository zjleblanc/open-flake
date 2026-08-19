import type { UserPreferencesApi } from '../settings/userPreferences';

const TOKEN_KEY = 'openflake_token';

export interface RecordPermissions {
  read: boolean;
  write: boolean;
  comment: boolean;
  delete: boolean;
}

export type { UserPreferencesApi } from '../settings/userPreferences';

export interface AuthMe {
  sys_id: string;
  user_name: string;
  permissions: string[];
  group_ids: string[];
  preferences: UserPreferencesApi;
}

export function getRecordPermissions(record: Record<string, unknown>): RecordPermissions {
  const p = record._permissions;
  if (p && typeof p === 'object') {
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
  if (value === true || value === 'true') return true;
  if (value === false || value === 'false') return false;
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

export interface CmdbClassFieldSchema {
  name: string;
  label: string | null;
  type: string | null;
  defined_on: string;
  origin: string;
  storage: string;
}

export interface CmdbClassSchema {
  class_name: string;
  inheritance_path: string[];
  fields: CmdbClassFieldSchema[];
  registered: boolean;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const res = await fetch(path, { ...options, headers });
  if (res.status === 401) {
    clearToken();
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }
  if (res.status === 204) {
    return undefined as T;
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

export const api = {
  login: (username: string, password: string) =>
    request<{ access_token: string; user_name: string; sys_id: string }>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),

  me: () => request<AuthMe>('/api/v1/auth/me'),

  getPreferences: () => request<UserPreferencesApi>('/api/v1/settings/preferences'),

  updatePreferences: (preferences: Partial<UserPreferencesApi>) =>
    request<UserPreferencesApi>('/api/v1/settings/preferences', {
      method: 'PATCH',
      body: JSON.stringify(preferences),
    }),

  dashboard: () =>
    request<{
      incidents_open: number;
      problems_open: number;
      changes_open: number;
      cis_total: number;
    }>('/api/v1/dashboard'),

  listRecords: (resource: string, params?: { state?: string; query?: string }) => {
    const qs = new URLSearchParams();
    if (params?.state) qs.set('state', params.state);
    if (params?.query) qs.set('query', params.query);
    return request<{ records: Record<string, string>[]; total: number }>(
      `/api/v1/records/${resource}?${qs}`,
    );
  },

  getRecord: (resource: string, sysId: string) =>
    request<Record<string, string>>(`/api/v1/records/${resource}/${sysId}`),

  listRecordVariables: (resource: string, sysId: string) =>
    request<RecordVariable[]>(`/api/v1/records/${resource}/${sysId}/variables`),

  createRecord: (resource: string, data: Record<string, unknown>) =>
    request<Record<string, string>>(`/api/v1/records/${resource}`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updateRecord: (resource: string, sysId: string, data: Record<string, unknown>) =>
    request<Record<string, string>>(`/api/v1/records/${resource}/${sysId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  deleteRecord: (resource: string, sysId: string, refMode?: 'clear' | 'cascade') => {
    const qs = refMode ? `?ref_mode=${refMode}` : '';
    return request<void>(`/api/v1/records/${resource}/${sysId}${qs}`, { method: 'DELETE' });
  },

  getCascadePreview: (resource: string, sysId: string) =>
    request<CascadePreview>(`/api/v1/records/${resource}/${sysId}/cascade-preview`),

  createUser: (data: {
    user_name: string;
    password: string;
    first_name?: string;
    last_name?: string;
    email?: string;
  }) =>
    request<Record<string, string>>('/api/v1/users', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  listApiKeys: () =>
    request<{ sys_id: string; name: string; active: boolean }[]>('/api/v1/settings/api-keys'),

  createApiKey: (name: string) =>
    request<{ sys_id: string; name: string; api_key: string }>('/api/v1/settings/api-keys', {
      method: 'POST',
      body: JSON.stringify({ name }),
    }),

  listOAuthClients: () =>
    request<{ sys_id: string; client_id: string; name: string; active: boolean }[]>(
      '/api/v1/settings/oauth-clients',
    ),

  createOAuthClient: (data: { name: string; client_id: string; client_secret: string }) =>
    request<{ sys_id: string; client_id: string; name: string }>('/api/v1/settings/oauth-clients', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

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
    data: { access_level: string; user_sys_id?: string; group_sys_id?: string },
  ) =>
    request<Record<string, string>>(`/api/v1/records/${resource}/${sysId}/grants`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  deleteGrant: (resource: string, sysId: string, grantSysId: string) =>
    request<void>(`/api/v1/records/${resource}/${sysId}/grants/${grantSysId}`, {
      method: 'DELETE',
    }),

  listComments: (resource: string, sysId: string) =>
    request<{ sys_id: string; comment: string; sys_created_by: string; sys_created_on: string }[]>(
      `/api/v1/records/${resource}/${sysId}/comments`,
    ),

  listActivity: (resource: string, sysId: string) =>
    request<{ activity: ActivityEntry[] }>(`/api/v1/records/${resource}/${sysId}/activity`),

  createComment: (resource: string, sysId: string, comment: string) =>
    request<Record<string, string>>(`/api/v1/records/${resource}/${sysId}/comments`, {
      method: 'POST',
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
        sys_created_by?: string;
      }[]
    >(`/api/v1/records/${resource}/${sysId}/attachments`),

  uploadAttachment: async (resource: string, sysId: string, file: File) => {
    const token = getToken();
    const formData = new FormData();
    formData.append('file', file);
    const headers: Record<string, string> = {};
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    const res = await fetch(`/api/v1/records/${resource}/${sysId}/attachments`, {
      method: 'POST',
      headers,
      body: formData,
    });
    if (res.status === 401) {
      clearToken();
      window.location.href = '/login';
      throw new Error('Unauthorized');
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Upload failed');
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
      method: 'DELETE',
    }),

  fetchAttachmentBlob: async (resource: string, sysId: string, attachmentSysId: string) => {
    const token = getToken();
    const headers: Record<string, string> = {};
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    const res = await fetch(
      `/api/v1/records/${resource}/${sysId}/attachments/${attachmentSysId}/file`,
      { headers },
    );
    if (res.status === 401) {
      clearToken();
      window.location.href = '/login';
      throw new Error('Unauthorized');
    }
    if (!res.ok) {
      throw new Error('Failed to load attachment');
    }
    return res.blob();
  },

  getCmdbClassSchema: (className: string) =>
    request<{ result: CmdbClassSchema }>(`/api/flake/schema/cmdb/${encodeURIComponent(className)}`),

  listCatalogItems: () =>
    request<{ result: CatalogItemSummary[] }>('/api/sn_sc/servicecatalog/items'),

  getCatalogItem: (itemId: string) =>
    request<{ result: CatalogItemDetail }>(`/api/sn_sc/servicecatalog/items/${itemId}`),

  orderCatalogItem: (
    itemId: string,
    data: {
      variables?: Record<string, unknown>;
      quantity?: number;
      requested_for?: string;
      cmdb_ci?: string;
      short_description?: string;
    },
  ) =>
    request<{ result: CatalogOrderResult }>(`/api/sn_sc/servicecatalog/items/${itemId}/order_now`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getVariableOptions: (itemId: string, varName: string, dependsOn?: string) => {
    const qs = new URLSearchParams();
    if (dependsOn) qs.set('depends_on', dependsOn);
    const suffix = qs.toString() ? `?${qs}` : '';
    return request<{ result: { options: CatalogChoice[]; total: number } }>(
      `/api/sn_sc/servicecatalog/items/${itemId}/variables/${encodeURIComponent(varName)}/options${suffix}`,
    );
  },

  getBatchVariableOptions: (itemId: string, variables: Record<string, string>) =>
    request<{ result: Record<string, { options: CatalogChoice[]; total: number }> }>(
      `/api/sn_sc/servicecatalog/items/${itemId}/variables/options`,
      { method: 'POST', body: JSON.stringify({ variables }) },
    ),

  adminListCatalogItems: () =>
    request<{ result: CatalogItemSummary[] }>('/api/flake/catalog/admin/items'),

  adminGetCatalogItem: (itemId: string) =>
    request<{ result: CatalogItemSummary }>(`/api/flake/catalog/admin/items/${itemId}`),

  adminCreateCatalogItem: (data: Record<string, unknown>) =>
    request<{ result: CatalogItemSummary }>('/api/flake/catalog/admin/items', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  adminUpdateCatalogItem: (itemId: string, data: Record<string, unknown>) =>
    request<{ result: CatalogItemSummary }>(`/api/flake/catalog/admin/items/${itemId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  adminDeleteCatalogItem: (itemId: string) =>
    request<void>(`/api/flake/catalog/admin/items/${itemId}`, { method: 'DELETE' }),

  adminListVariables: (itemId: string) =>
    request<{ result: CatalogVariable[] }>(`/api/flake/catalog/admin/items/${itemId}/variables`),

  adminCreateVariable: (itemId: string, data: Record<string, unknown>) =>
    request<{ result: CatalogVariable }>(`/api/flake/catalog/admin/items/${itemId}/variables`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  adminUpdateVariable: (itemId: string, varId: string, data: Record<string, unknown>) =>
    request<{ result: CatalogVariable }>(
      `/api/flake/catalog/admin/items/${itemId}/variables/${varId}`,
      { method: 'PATCH', body: JSON.stringify(data) },
    ),

  adminDeleteVariable: (itemId: string, varId: string) =>
    request<void>(`/api/flake/catalog/admin/items/${itemId}/variables/${varId}`, {
      method: 'DELETE',
    }),

  adminListTables: () => request<{ result: TableInfo[] }>('/api/flake/catalog/admin/tables'),

  adminListTableFields: (table: string) =>
    request<{ result: TableField[] }>(
      `/api/flake/catalog/admin/tables/${encodeURIComponent(table)}/fields`,
    ),

  listTableRegistry: () =>
    request<{ result: TableRegistryEntry[]; import_warnings: TableImportWarning[] }>(
      '/api/flake/admin/tables',
    ),

  getTableSchema: (name: string) =>
    request<{ result: CmdbClassSchema }>(
      `/api/flake/admin/tables/${encodeURIComponent(name)}/schema`,
    ),

  createTableClass: (data: Record<string, unknown>) =>
    request<{ result: CmdbClassSchema }>('/api/flake/admin/tables', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  addTableClassField: (name: string, data: Record<string, unknown>) =>
    request<{ result: CmdbClassSchema }>(
      `/api/flake/admin/tables/${encodeURIComponent(name)}/fields`,
      { method: 'PUT', body: JSON.stringify(data) },
    ),

  deleteTableClass: (name: string) =>
    request<void>(`/api/flake/admin/tables/${encodeURIComponent(name)}`, { method: 'DELETE' }),

  adminListConditions: (itemId: string, varId: string) =>
    request<{ result: CatalogCondition[] }>(
      `/api/flake/catalog/admin/items/${itemId}/variables/${varId}/conditions`,
    ),

  adminCreateCondition: (itemId: string, varId: string, data: Record<string, unknown>) =>
    request<{ result: CatalogCondition }>(
      `/api/flake/catalog/admin/items/${itemId}/variables/${varId}/conditions`,
      { method: 'POST', body: JSON.stringify(data) },
    ),

  adminUpdateCondition: (
    itemId: string,
    varId: string,
    condId: string,
    data: Record<string, unknown>,
  ) =>
    request<{ result: CatalogCondition }>(
      `/api/flake/catalog/admin/items/${itemId}/variables/${varId}/conditions/${condId}`,
      { method: 'PATCH', body: JSON.stringify(data) },
    ),

  adminDeleteCondition: (itemId: string, varId: string, condId: string) =>
    request<void>(
      `/api/flake/catalog/admin/items/${itemId}/variables/${varId}/conditions/${condId}`,
      { method: 'DELETE' },
    ),

  adminListWebhooks: () =>
    request<{ result: CatalogWebhook[] }>('/api/flake/catalog/admin/webhooks'),

  adminGetWebhook: (webhookId: string) =>
    request<{ result: CatalogWebhook }>(`/api/flake/catalog/admin/webhooks/${webhookId}`),

  adminCreateWebhook: (data: Record<string, unknown>) =>
    request<{ result: CatalogWebhook }>('/api/flake/catalog/admin/webhooks', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  adminUpdateWebhook: (webhookId: string, data: Record<string, unknown>) =>
    request<{ result: CatalogWebhook }>(`/api/flake/catalog/admin/webhooks/${webhookId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  adminDeleteWebhook: (webhookId: string) =>
    request<void>(`/api/flake/catalog/admin/webhooks/${webhookId}`, {
      method: 'DELETE',
    }),

  listSecrets: () => request<{ result: IntegrationSecret[] }>('/api/flake/secrets'),

  getSecret: (secretId: string) =>
    request<{ result: IntegrationSecret }>(`/api/flake/secrets/${secretId}`),

  createSecret: (data: Record<string, unknown>) =>
    request<{ result: IntegrationSecret }>('/api/flake/secrets', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updateSecret: (secretId: string, data: Record<string, unknown>) =>
    request<{ result: IntegrationSecret }>(`/api/flake/secrets/${secretId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  deleteSecret: (secretId: string) =>
    request<void>(`/api/flake/secrets/${secretId}`, {
      method: 'DELETE',
    }),

  adminListItemWebhooks: (itemId: string) =>
    request<{ result: CatalogWebhookAttachment[] }>(
      `/api/flake/catalog/admin/items/${itemId}/webhooks`,
    ),

  adminAttachItemWebhook: (itemId: string, data: Record<string, unknown>) =>
    request<{ result: CatalogWebhookAttachment }>(
      `/api/flake/catalog/admin/items/${itemId}/webhooks`,
      { method: 'POST', body: JSON.stringify(data) },
    ),

  adminUpdateItemWebhook: (itemId: string, attachmentId: string, data: Record<string, unknown>) =>
    request<{ result: CatalogWebhookAttachment }>(
      `/api/flake/catalog/admin/items/${itemId}/webhooks/${attachmentId}`,
      { method: 'PATCH', body: JSON.stringify(data) },
    ),

  adminDetachItemWebhook: (itemId: string, attachmentId: string) =>
    request<void>(`/api/flake/catalog/admin/items/${itemId}/webhooks/${attachmentId}`, {
      method: 'DELETE',
    }),

  adminPayloadPreview: (template?: string) => {
    const qs = new URLSearchParams();
    if (template) qs.set('template', template);
    const suffix = qs.toString() ? `?${qs}` : '';
    return request<{
      result: {
        preview: Record<string, unknown> | string;
        variables: { name: string; description: string }[];
      };
    }>(`/api/flake/catalog/admin/payload-preview${suffix}`);
  },
};

export type RecordVariable = {
  sys_id: string;
  name: string;
  question_text: string;
  type: string;
  value: string;
};

export type CatalogChoice = { value: string; label: string; record?: Record<string, unknown> };

export type TableInfo = {
  name: string;
  label?: string;
  super_class?: string | null;
  is_extendable?: boolean;
};
export type TableField = { name: string; type: string };

export type TableRegistryEntry = {
  name: string;
  label: string;
  super_class: string | null;
  is_logical: boolean;
  is_extendable: boolean;
  storage_type: string;
  base_table: string | null;
  user_defined: boolean;
  active: boolean;
  children_count: number;
};

// A hierarchy definition (base catalog or extra dir) skipped on the last
// startup import because a same-named class/field was already created via
// the admin UI -- see backend `registry.get_import_warnings()`.
export type TableImportWarning = {
  message: string;
  class_name: string;
  field_name: string | null;
};

export type CatalogVariable = {
  sys_id: string;
  cat_item: string;
  name: string;
  question_text: string;
  type: string;
  mandatory: boolean;
  default_value: string;
  order: number;
  reference_table: string;
  reference_filter: string;
  reference_display_field: string;
  choice_list: CatalogChoice[];
  help_text: string;
  read_only: boolean;
  hidden: boolean;
  active: boolean;
};

export type CatalogCondition = {
  sys_id: string;
  variable: string;
  condition_type: string;
  depends_on: string;
  operator: string;
  value: string;
  filter_override: string;
  active: boolean;
};

export type CatalogItemSummary = {
  sys_id: string;
  name: string;
  short_description: string;
  description?: string;
  price: string;
  category?: string;
  subcategory?: string;
  icon?: string;
  order?: number;
  catalog_sys_id?: string;
  fulfillment_group?: string;
  active?: boolean;
};

export type CatalogItemDetail = CatalogItemSummary & {
  variables: CatalogVariable[];
  conditions: CatalogCondition[];
};

export type CatalogOrderRecordRef = {
  sys_id: string;
  number?: string;
  short_description?: string;
};

export type CatalogOrderResult = {
  request_id: string;
  request_number: string;
  request: CatalogOrderRecordRef;
  request_item: CatalogOrderRecordRef;
  task: CatalogOrderRecordRef | null;
};

export type CatalogWebhook = {
  sys_id: string;
  name: string;
  url: string;
  method: string;
  headers: Record<string, string>;
  description?: string;
  active: boolean;
  has_secret?: boolean;
};

export type IntegrationSecret = {
  sys_id: string;
  name: string;
  description?: string;
  active: boolean;
  has_value?: boolean;
};

export type CatalogWebhookAttachment = {
  sys_id: string;
  cat_item: string;
  webhook: string;
  payload_template: string;
  trigger_on: string;
  active: boolean;
  payload_preview?: Record<string, unknown> | string;
  webhook_name?: string;
  webhook_url?: string;
  webhook_method?: string;
  webhook_active?: boolean;
};

export type CascadeChildRelationship = { direction: 'outgoing' | 'incoming'; type: string };

export type LooseReferenceRecord = {
  sys_id: string;
  label: string;
  relationship?: CascadeChildRelationship;
};

export type CascadeChildPreview = {
  table: string;
  label: string;
  count: number;
  records: LooseReferenceRecord[];
};

export type LooseReferencePreview = {
  table: string;
  resource: string | null;
  label: string;
  field: string;
  records: LooseReferenceRecord[];
};

export type CascadePreview = {
  target: { table: string; sys_id: string; label: string };
  cascade_children: CascadeChildPreview[];
  loose_references: LooseReferencePreview[];
  peripheral: Record<string, number>;
};

export type ActivityChange = {
  field: string;
  old_value: string;
  new_value: string;
  old_display_value?: string;
  new_display_value?: string;
};

export type ActivityEntry = {
  id: string;
  type: 'created' | 'update' | 'comment';
  user: string;
  timestamp: string;
  changes?: ActivityChange[];
  comment?: string;
};

/**
 * Generic fallback state labels, historically shared by every table. State
 * codes are NOT globally consistent across ServiceNow tables — e.g. code `3`
 * means "On Hold" for incident/problem but "Closed" for change_request. Use
 * `TABLE_STATE_LABELS` (keyed by the `/api/v1/records/{resource}` slug) for
 * tables with their own state machine, and fall back to this map otherwise.
 */
export const STATE_LABELS: Record<string, string> = {
  '1': 'New',
  '2': 'In Progress',
  '3': 'On Hold',
  '6': 'Resolved',
  '7': 'Closed',
  '8': 'Canceled',
  '-5': 'New',
  '-4': 'Assess',
  '-3': 'Authorize',
  '-2': 'Scheduled',
  '-1': 'Implement',
  '0': 'Review',
};

/** Per-resource state label overrides for tables whose state codes collide with other tables. */
export const TABLE_STATE_LABELS: Record<string, Record<string, string>> = {
  'change-requests': {
    '-5': 'New',
    '-4': 'Assess',
    '-3': 'Authorize',
    '-2': 'Scheduled',
    '-1': 'Implement',
    '0': 'Review',
    '3': 'Closed',
    '4': 'Canceled',
  },
  'change-tasks': {
    '1': 'Open',
    '2': 'In Progress',
    '3': 'Closed Complete',
    '4': 'Closed Incomplete',
    '7': 'Closed Skipped',
  },
};

/** The full set of state options valid for a given resource's state field. */
export function stateLabelsFor(resource?: string): Record<string, string> {
  if (resource && TABLE_STATE_LABELS[resource]) {
    return TABLE_STATE_LABELS[resource];
  }
  return STATE_LABELS;
}

export function stateOptionsFor(resource?: string): { value: string; label: string }[] {
  return Object.entries(stateLabelsFor(resource)).map(([value, label]) => ({ value, label }));
}

export function stateLabel(state: string, resource?: string): string {
  const scoped = resource ? TABLE_STATE_LABELS[resource] : undefined;
  return scoped?.[state] || STATE_LABELS[state] || state;
}

export function stateBadge(state: string, resource?: string): string {
  if (resource === 'change-requests') {
    if (state === '-5') return 'badge-new';
    if (state === '-4' || state === '-3' || state === '-2' || state === '-1') {
      return 'badge-progress';
    }
    if (state === '0') return 'badge-resolved';
    if (state === '3' || state === '4') return 'badge-closed';
    return 'badge-new';
  }
  if (resource === 'change-tasks') {
    if (state === '1') return 'badge-new';
    if (state === '2') return 'badge-progress';
    if (state === '3' || state === '4' || state === '7') return 'badge-closed';
    return 'badge-new';
  }
  if (state === '1' || state === '-5') return 'badge-new';
  if (state === '2' || state === '-4' || state === '-3') return 'badge-progress';
  if (state === '6' || state === '0') return 'badge-resolved';
  if (state === '7') return 'badge-closed';
  return 'badge-new';
}
