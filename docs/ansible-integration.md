# Ansible Integration

OpenFlake is designed to work with Ansible playbooks using the [servicenow.itsm](https://github.com/ansible-collections/servicenow.itsm) collection.

Point the collection at OpenFlake:

```yaml
- servicenow.itsm.incident:
    instance:
      host: http://localhost:8000
      username: admin
      password: admin
    state: new
    short_description: "Network outage"
    impact: high
    urgency: high
```

Environment variables:

```bash
export SN_HOST=http://localhost:8000
export SN_USERNAME=admin
export SN_PASSWORD=admin
```

## HTTPS

When TLS is enabled, use `https://` for the instance host. See [SSL / HTTPS — Ansible with HTTPS](ssl-https.md#ansible-with-https) for port and certificate options.

## Ownership and RBAC

API key and OAuth requests inherit the permissions of the associated user. To set record ownership from a playbook:

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

Full permission model: [RBAC](rbac.md).

## Example playbooks

Ready-to-run examples live in [`ansible-examples/`](ansible-examples/):

- `incident.yml` — create an incident
- `configuration_item.yml` — CMDB CI operations
- `attachment_upload.yml` — file attachment upload
- `sys_user_lookup.yml` — user lookup

## See also

- [API compatibility](api-compatibility.md) — supported endpoints and tables
- [RBAC](rbac.md) — record ownership and platform roles
