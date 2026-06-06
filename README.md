# OpenFlake

OpenFlake is an open-source, lightweight ITSM platform with a ServiceNow-compatible REST API. It is designed to work with Ansible playbooks using the [servicenow.itsm](https://github.com/ansible-collections/servicenow.itsm) collection.

## Architecture

OpenFlake uses a standard **3-tier architecture** deployed as three containers:

| Tier | Container | Description |
|------|-----------|-------------|
| Presentation | `openflake-frontend` | nginx + React admin UI |
| Application | `openflake-backend` | FastAPI ServiceNow-compatible APIs |
| Data | `openflake-postgres` | PostgreSQL 16 |

## Quick Start (Podman)

```bash
podman compose -f deploy/podman-compose.yaml up -d --build
```

- **UI:** http://localhost:8080
- **API (direct):** http://localhost:8000
- **Default login:** `admin` / `admin`

## SSL / HTTPS

OpenFlake terminates TLS at nginx (Podman) or the Kubernetes Ingress. The backend stays on plain HTTP internally behind the reverse proxy.

### Podman with self-signed certificates

Generate local development certificates:

```bash
./scripts/generate-dev-certs.sh
```

Start with the SSL compose override (mounts `deploy/certs/` and publishes port 443):

```bash
podman compose -f deploy/podman-compose.yaml -f deploy/podman-compose.ssl.yaml up -d --build
```

- **UI:** https://localhost (accept the browser warning for self-signed certs)
- **HTTP redirect:** http://localhost:8080 redirects to HTTPS when certificates are mounted
- **API (direct):** http://localhost:8000 remains available for Ansible and direct clients

Set a custom domain in the certificate SAN:

```bash
OPENFLAKE_DOMAIN=openflake.example.com ./scripts/generate-dev-certs.sh
```

### Production certificates (Podman)

Mount your own certificate and key at:

- `deploy/certs/fullchain.pem`
- `deploy/certs/privkey.pem`

Then use the SSL compose override as above. Update `BASE_URL` and `CORS_ORIGINS` in `deploy/podman-compose.ssl.yaml` to match your public hostname.

### Local development HTTPS

Run the Vite dev server with a self-signed certificate:

```bash
cd frontend
npm run dev:https
```

Add `https://localhost:5173` to `CORS_ORIGINS` in `backend/.env`:

```bash
CORS_ORIGINS=http://localhost:8080,http://localhost:5173,https://localhost:5173
```

### Kubernetes

Apply the frontend Service and Ingress manifests in `deploy/k8s/`. TLS terminates at the Ingress:

```bash
kubectl apply -f deploy/k8s/frontend-service.yaml
kubectl apply -f deploy/k8s/ingress.yaml
```

Create a TLS secret from your certificates:

```bash
kubectl create secret tls openflake-tls \
  --cert=fullchain.pem --key=privkey.pem
```

For automatic certificates, install [cert-manager](https://cert-manager.io/) and uncomment the `cert-manager.io/cluster-issuer` annotation in `deploy/k8s/ingress.yaml`. See `deploy/k8s/tls-secret.example.yaml` for a manual secret template.

Set `BASE_URL` and `CORS_ORIGINS` in the `openflake-secrets` Secret to your public HTTPS hostname.

### Ansible with HTTPS

Continue using the direct API on port 8000 over HTTP, or route through nginx:

```yaml
- servicenow.itsm.incident:
    instance:
      host: https://localhost
      username: admin
      password: admin
    # ...
```

For self-signed certificates in development only:

```yaml
instance:
  host: https://localhost
  validate_certs: false
```

## Ansible Integration

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

Example playbooks: [`docs/ansible-examples/`](docs/ansible-examples/)

## API Compatibility (Phase 1)

| API | Path | Status |
|-----|------|--------|
| Table API | `/api/now/table/{table}` | Supported |
| Attachment API | `/api/now/attachment` | Supported |
| CMDB Instance API | `/api/now/cmdb/instance/{class}` | Supported |
| Service Catalog API | `/api/sn_sc/servicecatalog` | Minimal stubs |
| OAuth | `/oauth_token.do` | Supported |
| Basic Auth | `Authorization: Basic` | Supported |
| API Key | `x-sn-apikey` header | Supported |

### Supported Tables

`incident`, `problem`, `problem_task`, `change_request`, `change_task`, `cmdb_ci`, `sys_user`, `sys_user_group`, `sys_user_grmember`, `sc_request`, `sc_task`, `cmdb_rel_type`, `cmdb_rel_ci`, `std_change_producer_version`, `sys_attachment`, `record_access_grant`, `sys_comment`, `sys_role`, `sys_group_role`

## Role-Based Access Control (RBAC)

OpenFlake enforces permissions through a unified RBAC layer applied in the backend domain layer. Both the UI API (`/api/v1/*`) and the ServiceNow-compatible Table API (`/api/now/table/*`) share the same rules, so Ansible playbooks and API keys are evaluated as the linked user.

### Record ownership (business records)

Business records (incidents, problems, changes, tasks, CMDB CIs, catalog requests/tasks) support:

| Field | Description |
|-------|-------------|
| `owner` | User sys_id with read/write/delete |
| `owner_group` | Group sys_id; members get read/write/delete |

The creator becomes `owner` on create when not specified.

### View and comment grants

Additional access is granted per record via `record_access_grant`:

| `access_level` | Allows |
|----------------|--------|
| `view` | Read only |
| `comment` | Read + add comments (`sys_comment`) |

Grants can target a user or a group. Only record owners (or holders of write access) can manage grants.

### Platform roles

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

### Ansible example with ownership

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

### Query Limitations

Phase 1 supports `sysparm_query` with field equality, `LIKE`, and `^` (AND). Complex operators and dot-walking are deferred to Phase 2.

### Deferred (Phase 2)

- Problem scoped state API (`/api/x_rhtpp_ansible/problem/...`)
- TinyURL API
- mTLS authentication

## Development

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# Requires local PostgreSQL or use podman compose for postgres only
uvicorn app.main:app --reload --port 8000
```

### Lab seed data (optional)

After the base seed runs (on first backend startup), populate a demo ITIL environment with users, groups, CMDB CIs, incidents, problems, changes, and catalog requests:

```bash
cd backend
source .venv/bin/activate
openflake-seed-lab
# or: python -m app.seed.lab
```

Creates an **Acme Corp** lab with Linux/Windows servers, network devices, ITIL assignment groups, and mixed ticket states. Lab users share password `lab123` (e.g. `jsmith`, `mwilson`, `lchen`). Records are prefixed with `[LAB]` for easy identification. Re-running is skipped by default; use `--force` to seed again (creates duplicates).

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Tests

```bash
cd backend
pytest
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection |
| `SECRET_KEY` | `change-me-in-production` | JWT signing key |
| `ADMIN_USERNAME` | `admin` | Seed admin username |
| `ADMIN_PASSWORD` | `admin` | Seed admin password |
| `ATTACHMENTS_PATH` | `/data/attachments` | Attachment storage |
| `BASE_URL` | `http://localhost:8000` | Reference link base URL |
| `CORS_ORIGINS` | `http://localhost:8080,...` | Allowed CORS origins |
| `TRUSTED_PROXIES` | `*` | Trusted reverse-proxy IPs for `X-Forwarded-*` headers |

## License

Apache License 2.0
