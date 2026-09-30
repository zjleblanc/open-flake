/**
 * Static Markdown content for `HelpPage.tsx`, rendered through `MarkdownRenderer`.
 * Kept separate from the page component so the JSX in `HelpPage.tsx` stays focused
 * on layout/structure while this file stays focused on prose.
 *
 * This is a curated, in-app summary — not a copy of the full docs. Each section
 * links out to the fuller reference in `docs/` on GitHub for anyone who wants the
 * complete picture. State-code mappings are intentionally NOT hardcoded here; see
 * `HelpPage.tsx`'s Field Reference section, which renders them live from
 * `STATE_LABELS` / `TABLE_STATE_LABELS` in `api/client.ts` so they can never drift.
 */

export const OVERVIEW_CONTENT = `
OpenFlake is a lightweight, open-source ITSM platform with a **ServiceNow-compatible
REST API**. If you already write Ansible playbooks, integrations, or reports against
ServiceNow's Table API, most of that tooling works against OpenFlake with just a host
and credential change.

### Core object model

| Object | What it's for |
|---|---|
| **Incidents** | Unplanned interruptions to a service |
| **Problems** | Root-cause investigations behind one or more incidents |
| **Changes** | Planned, approved modifications to the environment (with Change Tasks) |
| **Service Catalog** | Requestable items (Requests → Requested Items → Catalog Tasks) |
| **Configuration Items (CMDB)** | Inventory of the infrastructure/services being managed, organized in a class hierarchy |
| **Users & Groups** | Identity and team assignment, backing ownership and access control |

Every record carries the same audit trail (\`sys_created_on\`, \`sys_updated_by\`, ...), the
same comments/attachments/history feed, and the same ownership + access-grant model —
learn one table and the rest follow the same shape.
`;

export const CONFIGURING_CONTENT = `
OpenFlake is configured almost entirely through environment variables read by the
backend at startup.

| Variable | Default | Purpose |
|---|---|---|
| \`DATABASE_URL\` | \`postgresql+asyncpg://...\` | PostgreSQL connection |
| \`SECRET_KEY\` | *(change in production)* | JWT signing key |
| \`ADMIN_USERNAME\` / \`ADMIN_PASSWORD\` | \`admin\` / \`admin\` | Seed admin account |
| \`BASE_URL\` | \`http://localhost:8000\` | Base URL used when building reference links |
| \`CORS_ORIGINS\` | \`http://localhost:8080,...\` | Allowed browser origins |
| \`ATTACHMENTS_PATH\` | \`/data/attachments\` | Attachment storage directory |
| \`TRUSTED_PROXIES\` | \`*\` | Trusted reverse-proxy IPs for \`X-Forwarded-*\` |
| \`CMDB_HIERARCHY_EXTRA_DIR\` | *(unset)* | Extra CMDB class hierarchy JSON exports, layered on top of the shipped catalog |

Change the default passwords and \`SECRET_KEY\` before running in production.

### In-app configuration

- **Settings** (top-right user menu) — theme, layout density, date display format, and
  where you manage your own **API keys** and **OAuth clients** for scripted access.
- **Admin → Tables** *(requires \`records.*.write\`)* — browse the table/class registry,
  extend CMDB classes, and add fields to any registered table.

### Access control (RBAC)

Permissions are assigned to **groups** via platform roles, and every business record
also supports an \`owner\` and \`owner_group\` for record-level ownership.

| Permission | Meaning |
|---|---|
| \`records.*.read\` / \`records.*.write\` | Read/write all business records |
| \`users.read\` / \`users.write\` | List/manage users |
| \`groups.read\` / \`groups.write\` / \`groups.manage\` | List, create, or manage group membership |

Additional per-record \`view\`/\`comment\` access can be granted to a specific user or
group without giving them a platform role.
`;

export const INTEGRATING_CONTENT = `
OpenFlake speaks the same wire protocol ServiceNow integrations expect, so existing
tooling (Ansible, custom scripts, reporting) can usually point at OpenFlake with just a
host and credential change.

| API | Path | Notes |
|---|---|---|
| Table API | \`/api/now/table/{table}\` | Full CRUD, \`sysparm_query\` filtering |
| Attachment API | \`/api/now/attachment\` | File upload/download |
| CMDB Instance API | \`/api/now/cmdb/instance/{class}\` | Class-aware CI reads |
| OAuth | \`/oauth_token.do\` | Client-credentials/password grant |
| API Key | \`x-sn-apikey\` header | Generate one from **Settings** |

Supported tables include \`incident\`, \`problem\`, \`problem_task\`, \`change_request\`,
\`change_task\`, \`cmdb_ci\` (and its subclasses), \`sys_user\`, \`sys_user_group\`,
\`sc_request\`, \`sc_task\`, \`sys_attachment\`, and more.

### Webhooks & Secrets

Outbound integrations live under **Integrations**: **Webhooks** fire on record events,
and **Secrets** store credentials those webhooks (or catalog automations) can reference
without exposing them in plain text.

### Ansible

Point the [\`servicenow.itsm\`](https://github.com/ansible-collections/servicenow.itsm)
collection straight at OpenFlake:

\`\`\`yaml
- servicenow.itsm.incident:
    instance:
      host: http://localhost:8000
      username: admin
      password: admin
    state: new
    short_description: "Network outage"
    impact: high
    urgency: high
\`\`\`

API key and OAuth requests inherit the permissions of the associated OpenFlake user, so
scoped service accounts behave the same way they would against ServiceNow.
`;

export const BUILDING_PROCESSES_CONTENT = `
### Service Catalog

Catalog items define **variables** (the intake form) and, optionally, a workflow of
**Catalog Tasks**. Submitting an item creates a **Request**, which contains one or more
**Requested Items**, each of which can spawn its own Catalog Tasks — the same fan-out
ServiceNow uses for fulfillment.

### Incident / Problem / Change lifecycle

Each of these tables drives forward through a **State** field (see *Field Reference*
below for the exact codes). Changes additionally support **Change Tasks** for the
individual implementation steps, and a Change Template can pre-fill the standard fields
for a recurring, pre-approved change.

### Collaboration on a record

- **Comments, attachments, and field history** all show up together in one
  chronological **Activity** feed on every detail page.
- **Ownership** (\`owner\` / \`owner_group\`) determines who can write/delete a record by
  default.
- **Access grants** let an owner extend \`view\` or \`comment\` access to a specific user
  or group without changing ownership or granting a platform role.

### Configuration items & relationships

CMDB CIs are organized in a class hierarchy (e.g. \`cmdb_ci_server\` →
\`cmdb_ci_linux_server\`) and can be linked to each other and to business records, so an
incident or change can point at exactly which CIs it affects.
`;

export const DEVELOPER_REFERENCE_CONTENT = `
This page covers the highlights. The full reference docs live in the repository:

- [Documentation index](https://github.com/zjleblanc/open-flake/blob/main/docs/README.md)
- [API compatibility](https://github.com/zjleblanc/open-flake/blob/main/docs/api-compatibility.md)
- [RBAC](https://github.com/zjleblanc/open-flake/blob/main/docs/rbac.md)
- [Ansible integration](https://github.com/zjleblanc/open-flake/blob/main/docs/ansible-integration.md)
- [CMDB class hierarchy](https://github.com/zjleblanc/open-flake/blob/main/docs/cmdb-class-hierarchy.md)
- [Development setup](https://github.com/zjleblanc/open-flake/blob/main/docs/development.md)
- [Installation](https://github.com/zjleblanc/open-flake/blob/main/docs/installation.md)

Contributions, bug reports, and feature requests are welcome on
[GitHub](https://github.com/zjleblanc/open-flake).
`;
