# CMDB class hierarchy

OpenFlake models configuration items (CIs) with a **class hierarchy**: each CI belongs to a leaf class (for example `cmdb_ci_linux_server`) and inherits field definitions from its ancestor classes. Every table and class in OpenFlake — plain physical tables and CMDB subclasses alike — shares one metadata layer, mirroring ServiceNow's `sys_db_object` / `sys_dictionary` design.

## Concepts

| Concept | Description |
|---------|-------------|
| **Class** | A named type in the hierarchy (stored in `sys_db_object`, alongside every physical table). |
| **Field definition** | A field declared on a specific class (stored in `sys_dictionary`). |
| **Record** | A CI row in `cmdb_ci` with `sys_class_name` set to its leaf class — every CMDB class uses single-table inheritance on `cmdb_ci`. |
| **Promoted column** | Common fields stored as typed SQL columns (`host_name`, `fqdn`, `os`, …). |
| **Attributes** | Extension fields stored in JSONB, validated when the class is registered. |
| **Class path** | `sys_class_path` — full ancestry path computed on write (e.g. `/cmdb/cmdb_ci/cmdb_ci_server/cmdb_ci_linux_server`). |
| **Extendable** | Whether a class can be the parent of a new subclass created through the admin Tables UI. |
| **User-defined** | Whether a class or field was created through the admin UI rather than the shipped base catalog. |

All field values for a record live on **one row**. Inherited fields are not stored on separate parent records — the hierarchy defines which fields are allowed, not where data is split.

## Shipped base catalog

Every backend image ships with a built-in CMDB class catalog — no configuration or extra files required. It covers common infrastructure, virtualization, database, and cloud classes:

```
cmdb_ci
├─ cmdb_ci_hardware
│  ├─ cmdb_ci_computer
│  │  └─ cmdb_ci_server
│  │     ├─ cmdb_ci_linux_server
│  │     ├─ cmdb_ci_unix_server
│  │     └─ cmdb_ci_win_server
│  ├─ cmdb_ci_storage_device
│  │  └─ cmdb_ci_storage_server
│  ├─ cmdb_ci_peripheral
│  │  └─ cmdb_ci_printer
│  └─ cmdb_ci_netgear
│     ├─ cmdb_ci_router
│     ├─ cmdb_ci_switch
│     ├─ cmdb_ci_ip_firewall
│     └─ cmdb_ci_lb
├─ cmdb_ci_vm_object
│  └─ cmdb_ci_vm_instance
├─ cmdb_ci_database
│  ├─ cmdb_ci_db_mysql_instance
│  ├─ cmdb_ci_db_ora_instance
│  └─ cmdb_ci_db_postgresql_instance
├─ cmdb_ci_appl
├─ cmdb_ci_service
└─ cmdb_ci_cloud_service
   ├─ cmdb_ci_cloud_service_account
   └─ cmdb_ci_cloud_resource
```

Each leaf class comes with a small set of illustrative fields (e.g. `cmdb_ci_linux_server.kernel_release`, `cmdb_ci_lb.algorithm`); use the admin Tables UI or `PUT /api/flake/admin/tables/{name}/fields` to add more.

Maintainers regenerate this catalog from a single spec file and commit the result — see `backend/AGENTS.md` for the workflow.

## Extending the hierarchy

There are two ways to add classes or fields beyond the shipped catalog:

1. **Admin Tables UI** (`/admin/tables`, requires `records.*.write`) — browse the full table/class tree, extend any class marked *extendable* into a new subclass, add fields to any registered class, and delete unused custom classes. Backed by `GET/POST/DELETE /api/flake/admin/tables` and `PUT /api/flake/admin/tables/{name}/fields`.
2. **Extra hierarchy directory** — set the `CMDB_HIERARCHY_EXTRA_DIR` environment variable to a directory of JSON hierarchy exports (the same `target_table` / `inheritance_path` / `fields` shape as the base catalog), scanned in addition to the base catalog on every startup. A relative path resolves against the repository root. Unset by default; local development sets it to a gitignored local directory so exported classes stay out of version control.

### Collision guardrails

Both extension paths are safe to combine:

- Creating a class or field with a name that's already registered (whether by the base catalog or a previous custom table) is rejected immediately, and the error names the conflict's origin — "already defined by the built-in class hierarchy" vs. "already created as a custom table". The admin Tables UI checks this client-side as you type a new class name, before you submit.
- The reverse direction is also guarded: if the base catalog or an extra-dir file defines a class or field name that an admin already customized through the UI, the startup import skips that specific definition rather than overwriting it, and records a warning. `GET /api/flake/admin/tables` returns these warnings, and the admin Tables UI surfaces them as a dismissible banner so admins know exactly what was skipped and why.

### Registered vs unregistered classes

OpenFlake supports two modes:

#### Registered classes

Classes registered in `sys_db_object` and `sys_dictionary` at startup have:

- A defined position in the class tree
- Field definitions with labels and types
- **Schema-aware routing** on create/update — fields defined on the class (or an ancestor) are stored as their declared column/attribute; snake_case fields not in the schema are still accepted and stored in `attributes` (matching ServiceNow's tolerance of undeclared fields); non-snake_case field names are rejected
- **Descendant queries** — listing `/api/now/table/cmdb_ci_server` returns records whose class is `cmdb_ci_server` or any subclass
- **Reference-field selection** — a reference field's target table can be set to any registered CMDB subclass (e.g. `cmdb_ci_server`), not just `cmdb_ci`; the catalog variable/reference picker shows the full hierarchy as an indented tree

#### Unregistered classes

When a CI is created with a class that is not yet in the registry (via Table API or CMDB Instance API):

1. OpenFlake **auto-registers** the class with **`cmdb_ci` as the default parent**
2. Writes use **permissive validation** — promoted columns plus any snake_case keys in `attributes`
3. Queries against that class URL match **exact class only** until the class is added to the hierarchy with a proper parent chain
4. `sys_class_path` is computed as `/cmdb/cmdb_ci/{class_name}`

To upgrade an auto-registered class to schema-aware routing, register a proper parent chain and field definitions (via the admin Tables UI, or an extra-dir export), then restart the backend.

## Registered class metadata

Each registered class has a position in the inheritance tree and field definitions (label, type, and defining class). Example inheritance paths:

```
cmdb → cmdb_ci → cmdb_ci_hardware → cmdb_ci_computer → cmdb_ci_server → cmdb_ci_linux_server
cmdb → cmdb_ci → cmdb_ci_vm_object → cmdb_ci_vm_instance
```

Class metadata is loaded into `sys_db_object` and `sys_dictionary` at backend startup.

## API behavior

| Endpoint | Behavior |
|----------|----------|
| `GET /api/now/table/cmdb_ci` | All CIs |
| `GET /api/now/table/cmdb_ci_server` | CIs whose class is `cmdb_ci_server` or any registered descendant |
| `POST /api/now/table/cmdb_ci_linux_server` | Creates a CI; forces `sys_class_name`; validates against merged schema |
| `GET /api/now/cmdb/instance/{class}/...` | Same class filtering as Table API |
| `GET /api/now/schema/cmdb/classes` | Full class tree |
| `GET /api/now/schema/cmdb/{class}` | Merged field schema for a registered class |
| `GET /api/flake/admin/tables` | Full table/class registry, plus any startup import warnings |
| `GET /api/flake/admin/tables/{name}/schema` | Merged field schema for a registered table/class |
| `POST /api/flake/admin/tables` | Create a new CMDB class extended from an extendable parent |
| `PUT /api/flake/admin/tables/{name}/fields` | Add or edit a field on a registered table/class |
| `DELETE /api/flake/admin/tables/{name}` | Delete a user-defined class with no subclasses or records |

## Storage layout

The physical `cmdb_ci` table holds:

- Identity: `sys_id`, `name`, `sys_class_name`, `sys_class_path`
- Promoted columns for inventory and query (`host_name`, `fqdn`, `ip_address`, `os`, …)
- `attributes` JSONB for all other class fields
- Audit and ownership columns

Class metadata lives in `sys_db_object` and `sys_dictionary` — the same tables used for every other OpenFlake table, not a CMDB-only overlay. CI-to-CI relationships use `cmdb_rel_ci` (separate from class inheritance).

## Ansible inventory

Dynamic inventory against a **parent** class (e.g. `table: cmdb_ci_server`) returns child-class records such as `cmdb_ci_linux_server` when those classes are registered in the hierarchy under that parent.

## See also

- [API compatibility](api-compatibility.md)
- [Ansible integration](ansible-integration.md)
