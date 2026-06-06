# API Compatibility (Phase 1)

| API | Path | Status |
|-----|------|--------|
| Table API | `/api/now/table/{table}` | Supported |
| Attachment API | `/api/now/attachment` | Supported |
| CMDB Instance API | `/api/now/cmdb/instance/{class}` | Supported |
| Service Catalog API | `/api/sn_sc/servicecatalog` | Minimal stubs |
| OAuth | `/oauth_token.do` | Supported |
| Basic Auth | `Authorization: Basic` | Supported |
| API Key | `x-sn-apikey` header | Supported |

## Supported Tables

`incident`, `problem`, `problem_task`, `change_request`, `change_task`, `cmdb_ci`, `sys_user`, `sys_user_group`, `sys_user_grmember`, `sc_request`, `sc_task`, `cmdb_rel_type`, `cmdb_rel_ci`, `std_change_producer_version`, `sys_attachment`, `record_access_grant`, `sys_comment`, `sys_role`, `sys_group_role`

## Query Limitations

Phase 1 supports `sysparm_query` with field equality, `LIKE`, and `^` (AND). Complex operators and dot-walking are deferred to Phase 2.

## Deferred (Phase 2)

- Problem scoped state API (`/api/x_rhtpp_ansible/problem/...`)
- TinyURL API
- mTLS authentication

## See also

- [Ansible integration](ansible-integration.md) — collection setup and examples
- [RBAC](rbac.md) — permissions for Table API and UI API
