# Role-Based Access Control (RBAC)

OpenFlake enforces permissions through a unified RBAC layer applied in the backend domain layer. Both the UI API (`/api/v1/*`) and the ServiceNow-compatible Table API (`/api/now/table/*`) share the same rules, so Ansible playbooks and API keys are evaluated as the linked user.

## Record ownership (business records)

Business records (incidents, problems, changes, tasks, CMDB CIs, catalog requests/tasks) support:

| Field | Description |
|-------|-------------|
| `owner` | User sys_id with read/write/delete |
| `owner_group` | Group sys_id; members get read/write/delete |

The creator becomes `owner` on create when not specified.

## View and comment grants

Additional access is granted per record via `record_access_grant`:

| `access_level` | Allows |
|----------------|--------|
| `view` | Read only |
| `comment` | Read + add comments (`sys_comment`) |

Grants can target a user or a group. Only record owners (or holders of write access) can manage grants.

## Platform roles

Roles (`sys_role`) are assigned to groups (`sys_group_role`). Group membership grants permissions:

| Permission | Meaning |
|------------|---------|
| `records.*.read` | Read all business records |
| `records.*.write` | Write all business records |
| `users.read` / `users.write` | List/manage users |
| `users.write.self` | Update own user record |
| `groups.read` / `groups.write` | List/create/delete groups |
| `groups.manage` | Update group and membership (group owner or role) |

The seeded `admin` group receives the `platform_admin` role with all permissions — evaluated through the same checker, not a hardcoded bypass.

Groups have an `owner` field (user sys_id). Only the group owner or users with `groups.write` may manage group membership.

## Ansible example with ownership

```yaml
- servicenow.itsm.incident:
    instance:
      host: "{{ openflake_host }}"
      username: "{{ openflake_user }}"
      password: "{{ openflake_pass }}"
    state: new
    short_description: "Automated incident"
    other:
      owner: "{{ caller_sys_id }}"
      owner_group: "{{ team_group_sys_id }}"
```

API key and OAuth requests inherit the permissions of the associated user.

## See also

- [Ansible integration](ansible-integration.md) — collection setup and examples
- [API compatibility](api-compatibility.md) — supported tables including `record_access_grant`
