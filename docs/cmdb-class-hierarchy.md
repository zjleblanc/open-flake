# CMDB class hierarchy

OpenFlake models configuration items (CIs) with a **class hierarchy**: each CI belongs to a leaf class (for example `cmdb_ci_linux_server`) and inherits field definitions from its ancestor classes.

## Concepts

| Concept | Description |
|---------|-------------|
| **Class** | A named type in the hierarchy (stored in `cmdb_class`). |
| **Field definition** | A field declared on a specific class (stored in `cmdb_class_field`). |
| **Record** | A CI row in `cmdb_ci` with `sys_class_name` set to its leaf class. |
| **Promoted column** | Common fields stored as typed SQL columns (`host_name`, `fqdn`, `os`, …). |
| **Attributes** | Extension fields stored in JSONB, validated when the class is registered. |
| **Class path** | `sys_class_path` — full ancestry path computed on write (e.g. `/cmdb/cmdb_ci/cmdb_ci_server/cmdb_ci_linux_server`). |

All field values for a record live on **one row**. Inherited fields are not stored on separate parent records — the hierarchy defines which fields are allowed, not where data is split.

## Registered vs unregistered classes

OpenFlake supports two modes:

### Registered classes

Classes registered in `cmdb_class` and `cmdb_class_field` at startup have:

- A defined position in the class tree
- Field definitions with labels and types
- **Strict validation** on create/update — unknown fields are rejected
- **Descendant queries** — listing `/api/now/table/cmdb_ci_server` returns records whose class is `cmdb_ci_server` or any subclass

### Unregistered classes

When a CI is created with a class that is not yet in the registry (via Table API or CMDB Instance API):

1. OpenFlake **auto-registers** the class with **`cmdb_ci` as the default parent**
2. Writes use **permissive validation** — promoted columns plus any snake_case keys in `attributes`
3. Queries against that class URL match **exact class only** until the class is added to the hierarchy with a proper parent chain
4. `sys_class_path` is computed as `/cmdb/cmdb_ci/{class_name}`

To upgrade an auto-registered class to strict mode, register a proper parent chain and field definitions in `cmdb_class` / `cmdb_class_field`, then restart the backend.

## Registered class metadata

Each registered class has a position in the inheritance tree and field definitions (label, type, and defining class). Example inheritance paths:

```
cmdb → cmdb_ci → cmdb_ci_hardware → cmdb_ci_computer → cmdb_ci_server → cmdb_ci_linux_server
cmdb → cmdb_ci → cmdb_ci_vm_object → cmdb_ci_vm_instance
```

Class metadata is loaded into `cmdb_class` and `cmdb_class_field` at backend startup.

## API behavior

| Endpoint | Behavior |
|----------|----------|
| `GET /api/now/table/cmdb_ci` | All CIs |
| `GET /api/now/table/cmdb_ci_server` | CIs whose class is `cmdb_ci_server` or any registered descendant |
| `POST /api/now/table/cmdb_ci_linux_server` | Creates a CI; forces `sys_class_name`; validates against merged schema |
| `GET /api/now/cmdb/instance/{class}/...` | Same class filtering as Table API |
| `GET /api/now/schema/cmdb/classes` | Full class tree |
| `GET /api/now/schema/cmdb/{class}` | Merged field schema for a registered class |

## Storage layout

The physical `cmdb_ci` table holds:

- Identity: `sys_id`, `name`, `sys_class_name`, `sys_class_path`
- Promoted columns for inventory and query (`host_name`, `fqdn`, `ip_address`, `os`, …)
- `attributes` JSONB for all other class fields
- Audit and ownership columns

Class metadata lives in `cmdb_class` and `cmdb_class_field`. CI-to-CI relationships use `cmdb_rel_ci` (separate from class inheritance).

## Ansible inventory

Dynamic inventory against a **parent** class (e.g. `table: cmdb_ci_server`) returns child-class records such as `cmdb_ci_linux_server` when those classes are registered in the hierarchy under that parent.

## See also

- [API compatibility](api-compatibility.md)
- [Ansible integration](ansible-integration.md)
