# Changelog

All notable changes to this project will be documented in this file.

## 2026-06-06 — SELinux label for pg_hba.conf bind mount

### Fixed

- Postgres could not load bind-mounted `pg_hba.conf` on SELinux hosts despite mode `644`; mount now uses `:Z` so the container can read the file.

### Changed

- Dev and registry compose and `ensure-postgres.sh` `podman run` fallback mount `pg_hba.conf` as `:ro,Z`.

## 2026-06-06 — Bind-mount deploy/pg_hba.conf for Postgres client access

### Added

- `deploy/pg_hba.conf` — loopback, container bridge (`10.0.0.0/8`, `172.16.0.0/12`), and common LAN subnets for the `openflake` user.

### Changed

- Dev and registry compose bind-mount `pg_hba.conf` and set `hba_file` / `listen_addresses` (replaces inline shell copy at container start).
- HBA file moved from `deploy/postgres/pg_hba.conf` to `deploy/pg_hba.conf`; `podman-install.sh` downloads it beside the compose files.
- `ensure-postgres.sh` `podman run` fallback matches compose HBA settings.
- `podman-upgrade.sh` requires `pg_hba.conf` in the install directory.

## 2026-06-06 — Inline Postgres HBA startup for rootless Podman

### Fixed

- Bind-mounted `docker-entrypoint.sh` also fails with permission denied under rootless Podman; compose and `ensure-postgres.sh` copy `pg_hba.conf` via inline shell instead of a mounted script.

### Changed

- `podman-install.sh` no longer downloads `postgres/docker-entrypoint.sh`; only `pg_hba.conf` is shipped to the install directory.

## 2026-06-06 — Fix Postgres pg_hba permission denied under rootless Podman

### Fixed

- Postgres entrypoint wrapper copies mounted `pg_hba.conf` into the data volume as `postgres:postgres` before startup (fixes `could not load /etc/postgresql/pg_hba.conf: Permission denied` when the bind mount is not readable by the container user).
- `podman-install.sh` downloads `postgres/pg_hba.conf` and `postgres/docker-entrypoint.sh` into the install directory (registry compose referenced them but install did not ship them).

### Changed

- Dev and registry compose, plus `ensure-postgres.sh` fallback `podman run`, mount HBA at `/etc/postgresql/pg_hba.conf.ro` and use `deploy/postgres/docker-entrypoint.sh` instead of `hba_file` on the bind mount.

## 2026-06-06 — Fix Podman upgrade backend recreation

### Fixed

- `podman-upgrade.sh` removes frontend before backend (compose `depends_on` blocks Podman from replacing backend while dependents exist), then recreates each service with `compose up --no-deps` instead of `--force-recreate`.

## 2026-06-06 — Restrict PostgreSQL client access to local subnets

### Added

- `deploy/postgres/pg_hba.conf` allowing loopback and RFC 1918 private subnets only (no catch-all public access).

### Changed

- Podman compose postgres service mounts `pg_hba.conf` and sets `hba_file` in dev and registry stacks.
- `ensure-postgres.sh` fallback `podman run` uses the same config; docs note container recreation to apply restrictions.

## 2026-06-06 — Tighten .dockerignore for container builds

### Changed

- Exclude docs, scripts (with exceptions for dev helper scripts), `.vscode`, `.github`, markdown files, and `.ansible` from the build context to shrink image build scope.

## 2026-06-05 — Fix rootless TLS permissions and backend SSL healthchecks

### Fixed

- Shared TLS readability hints explain rootless Podman needs host-readable cert files (mode `600` root keys), not only `container_file_t`; install and upgrade scripts fail early with `chmod 644` guidance.
- Backend healthcheck probes HTTPS when SSL is enabled (`OPENFLAKE_SSL_REQUIRED` or mounted certs), uses probe timeouts, and registry/SSL compose use `/app/backend-healthcheck.sh` (fixes HTTP probes hanging against TLS-only port 8000).
- SSL compose backend healthcheck sets a 90s start period for migrations; upgrade script polls `https://localhost:8000/health/ready` when SSL compose is active.

## 2026-06-05 — Fix backend TLS startup for Podman SSL deploy

### Fixed

- Backend entrypoint runs as root, copies mounted TLS files into `/run/openflake/certs` with `openflake`-owned permissions, and starts uvicorn via `gosu` (fixes exit when host keys are root-only or unreadable by uid 1001).
- SSL compose keeps the attachments volume when overriding backend volumes.
- Install and upgrade scripts validate certificate files on the `OPENFLAKE_SSL_BACKEND_MOUNT` host path before compose up; backend entrypoint lists mount directory contents when `OPENFLAKE_SSL_REQUIRED` is set but certs are missing.

## 2026-06-05 — Fix Podman SSL nginx startup and healthchecks

### Fixed

- SSL compose sets `OPENFLAKE_SSL_REQUIRED` and validates readable certificate files before nginx/backend start (avoids HTTP-only fallback while host port 8443 maps to closed container 443).
- nginx HTTP redirect includes `OPENFLAKE_HTTPS_PORT`; frontend healthcheck uses `nc` on port 443 instead of wget with unsupported certificate flags.

## 2026-06-05 — Rootless Podman ports for registry install

### Changed

- HTTPS publishes on host port `8443` by default (`OPENFLAKE_HTTPS_PORT` maps to nginx 443 in the container); install script derives `BASE_URL` and CORS with the host port.
- Registry compose no longer publishes PostgreSQL on the host (internal network only).

## 2026-06-05 — Remove automatic SELinux relabeling from Podman mounts

### Changed

- Install and upgrade scripts use read-only TLS mounts (`:ro`) and plain attachment bind mounts without `:z` or `:Z`; removed Let's Encrypt path rejection tied to relabel failures.

## 2026-06-05 — Reject Let's Encrypt paths for Podman TLS mounts

### Fixed

- Install and upgrade scripts reject `OPENFLAKE_SSL_DIR` under `/etc/letsencrypt/` and keep `:ro,z` SELinux relabeling on supported paths; copy certificates to e.g. `/etc/ssl/openflake` instead (fixes Podman `lsetxattr ... operation not permitted`).

## 2026-06-05 — Export compose env for podman-compose SSL volume mounts

### Fixed

- Install and upgrade scripts export `.env` before compose and validate `OPENFLAKE_SSL_*_MOUNT` so `podman-compose` resolves SSL volume paths (fixes empty certificate mounts and "container directory cannot be empty").

## 2026-06-05 — Precompute SSL volume mounts for podman-compose

### Fixed

- SSL compose uses `OPENFLAKE_SSL_BACKEND_MOUNT` and `OPENFLAKE_SSL_FRONTEND_MOUNT` from `.env` instead of inline `${OPENFLAKE_SSL_DIR:-...}` substitution; install and upgrade scripts write or backfill these so certificate paths no longer get a stray `}` on `podman-compose`.

## 2026-06-05 — Fix Podman Compose SSL directory mount parsing

### Fixed

- Replace nested `${OPENFLAKE_SSL_DIR:-${OPENFLAKE_CERT_DIR:-...}}` in SSL compose with `${OPENFLAKE_SSL_DIR:-./certs}` so `podman-compose` no longer appends a stray `}` to certificate paths (fixes `statfs ...}` and backend/frontend failing to start).

## 2026-06-05 — Optional openflake.env config for Podman install and upgrade

### Added

- `podman-install.sh` and `podman-upgrade.sh` source an adjacent `openflake.env` before CLI flags and environment variables.
- `deploy/openflake.env.example` template for install and upgrade settings.

## 2026-06-05 — Fix Podman Compose attachment volume mount parsing

### Fixed

- Replace unsupported `${VAR:+:Z}` Compose expansion with `OPENFLAKE_ATTACHMENTS_MOUNT`; install script writes the full mount spec (including `:Z` on SELinux) so `podman-compose` pull/up no longer fails with `could not parse mount`.

## 2026-06-05 — SELinux volume relabeling for Podman

### Added

- Optional `OPENFLAKE_ATTACHMENTS_DIR` host bind mount for backend attachment storage; Compose appends `:Z` on SELinux systems when set.
- Install script `--attachments-dir` / `OPENFLAKE_ATTACHMENTS_DIR` passthrough to deployment `.env`.

### Changed

- SSL compose certificate mounts use `:ro,z` (shared read-only label) so nginx and the backend can mount the same TLS directory on RHEL/Fedora.

## 2026-06-05 — Backend TLS certificate support

### Added

- Backend container entrypoint enables HTTPS on port 8000 when TLS files are mounted at `/etc/openflake/certs` (same `OPENFLAKE_SSL_DIR`, `OPENFLAKE_SSL_CERT`, and `OPENFLAKE_SSL_KEY` as nginx).
- SSL-aware backend healthcheck and Podman SSL compose override mounts certificates into the backend service.

### Changed

- nginx HTTPS config proxies to the backend over TLS when the SSL stack is active (`proxy_ssl_verify off` for internal mesh traffic).

## 2026-06-05 — Fix frontend multi-arch container builds

### Fixed

- Frontend image build uses `$BUILDPLATFORM` for the Node builder stage so esbuild runs natively when cross-publishing from Apple Silicon (avoids QEMU `write EPIPE` failures).
- Added `.dockerignore` to exclude host `node_modules` and dev artifacts from the build context; frontend builder uses `npm ci`.

## 2026-06-05 — Correct default Quay registry path

### Changed

- Default image registry updated from `quay.io/zjleblanc` to `quay.io/zleblanc` across compose files, install/publish scripts, CI workflow, and docs.

## 2026-06-05 — Configurable TLS certificate paths

### Changed

- TLS mount directory renamed to `OPENFLAKE_SSL_DIR` (with `OPENFLAKE_CERT_DIR` still accepted as a deprecated alias).
- Certificate and key filenames are configurable via `OPENFLAKE_SSL_CERT` and `OPENFLAKE_SSL_KEY` (defaults: `fullchain.pem`, `privkey.pem`).
- nginx SSL entrypoint resolves cert/key paths from environment variables at container start.

## 2026-06-05 — Multi-arch image publish and release tagging

### Added

- Release and image tagging guide (`docs/release-tagging.md`) for stable, pre-release, and dev tags, including when Quay `latest` is updated.
- Scripts index (`scripts/README.md`) and per-script reference docs under `scripts/docs/`.

### Changed

- `publish-images.sh` builds multi-arch manifests (`linux/amd64`, `linux/arm64`) by default; adds `--single-arch`, `--platforms`, and `OPENFLAKE_PLATFORMS`.
- GitHub Actions publish workflow uses Buildx and QEMU for multi-arch builds; updates `latest` only for stable semver tags (`vMAJOR.MINOR.PATCH`).
- README links to scripts docs and release tagging guide; documents multi-arch publish and host-native `--single-arch` builds.

## 2026-06-05 — Quay registry install and upgrade for Podman

### Added

- Registry-based Podman compose (`deploy/podman-compose.registry.yaml`) pulling `quay.io/zleblanc/openflake-backend` and `openflake-frontend` images.
- Deployment env template (`deploy/.env.example`) for registry URL, image tag, TLS cert path, and production secrets.
- Install script (`scripts/podman-install.sh`) for one-line Quay pull-and-run with BYO certificates or HTTP-only mode.
- Upgrade script (`scripts/podman-upgrade.sh`) to pull new images, recreate backend then frontend, wait for migrations, and optionally `pg_dump` backup.
- Image publish script (`scripts/publish-images.sh`) and GitHub Actions workflow (`.github/workflows/publish-images.yml`) to push tagged releases to Quay.io.

### Changed

- Podman SSL compose override uses env-driven `OPENFLAKE_CERT_DIR`, `OPENFLAKE_BASE_URL`, and `OPENFLAKE_CORS_ORIGINS` (defaults preserve local dev behavior).
- README documents Quay install, upgrade, rollback, maintainer publish workflow, and RHEL VM sizing for single-host Podman deployments.

## 2026-06-05 — SSL / HTTPS support

### Added

- Self-signed certificate generator (`scripts/generate-dev-certs.sh`) and `deploy/certs/` mount path for production certificates.
- nginx TLS termination with conditional SSL entrypoint: HTTPS on port 443 when certs are mounted, HTTP-only fallback on port 8080.
- Podman SSL compose override (`deploy/podman-compose.ssl.yaml`) for HTTPS without changing the default HTTP quick start.
- Kubernetes Ingress, frontend Service, and TLS secret example manifests.
- Vite HTTPS dev mode (`npm run dev:https`) via `@vitejs/plugin-basic-ssl`.
- Backend `ProxyHeadersMiddleware` and `TRUSTED_PROXIES` setting for reverse-proxy `X-Forwarded-Proto` support.

### Changed

- README documents SSL setup for Podman, Kubernetes, local dev, and Ansible.

## 2026-06-05 — Sticky navbar, login redirect, and debug teardown

### Added

- Sticky glass top navbar with breadcrumbs, status badges, page actions, and a top-right user profile menu (sign out in dropdown).
- `PageHeaderContext`, `TopNavbar`, and `usePageHeader` so pages register navbar breadcrumbs, badges, and actions without per-page headers.
- `scripts/stop-backend.sh` and a VS Code Stop Backend Server post-debug task to tear down uvicorn after launch sessions end.

### Changed

- Replaced per-page `<h1>` headers and `DetailPageHeader` with the centralized sticky navbar; sidebar sign-out footer removed.
- Navbar sits inside the scrolling content area so page content blurs through the translucent backdrop while scrolling.
- Record and CI status badges render after breadcrumbs; share and create actions stay on the right.
- VS Code backend launch configs use `killBehavior: forceful` and `postDebugTask` for reliable process cleanup.
- Updated OpenFlake logo assets; removed unused `logo.svg`.

### Fixed

- Drop `WWW-Authenticate: Basic` on 401 responses so the SPA redirects to `/login` instead of opening the native browser auth dialog.
- `usePageHeader` infinite update loops from effect cleanup and unstable breadcrumb references.

## 2026-06-05 — Record-level RBAC and inline detail editing

### Added

- Record-level RBAC with ownership, owner groups, platform roles, per-record view/comment grants, and comments on business records.
- `SysRole`, `SysGroupRole`, `RecordAccessGrant`, and `SysComment` models with startup backfill and admin role seed.
- RBAC enforcement in the table service for create/list/get/update/delete across UI and Table API routes.
- `/api/v1/auth/me`, record grant CRUD, and comment list/create endpoints.
- `test_rbac.py` coverage and README RBAC documentation.
- Frontend `AuthContext`, permission-gated navigation and forms, share popover (ownership, grants, your access), and comments section.
- Shared detail field controls: grouped read-only fields with lock indicators, header toggle switch, and dirty-state save button.
- VS Code backend debug configurations, `start-backend.sh` task, and `debugpy` dev dependency.

### Changed

- Record and CI detail pages use inline editing in a single section; read-only fields grouped above editable fields with a divider.
- CI detail page keeps additional properties and RBAC fields out of the main grid; system properties controlled by a header toggle and merged into the read-only group.
- `assigned_to` and audit user references resolve to display names on the CI detail page.
- Save Changes stays disabled until the form has pending edits.
- VS Code launch/tasks reworked so backend debugging starts reliably without preLaunchTask loops.

### Fixed

- CI detail page crash from missing `EDITABLE_FIELD_KEYS` constant.
- Comments section icon not rendering on detail pages.

## 2026-06-05

### Added

- Table API support for CMDB subclass tables (e.g. `cmdb_ci_server`) so the `servicenow.itsm.configuration_item` Ansible module works against OpenFlake.
- Attachment list endpoint (`GET /api/now/attachment`) required for idempotent Ansible CI updates.
- Dedicated configuration item detail page showing all standard fields, collapsible system metadata, and editable additional properties with add-key/value support.
- Snake_case validation for additional property keys on the API (422) and in the CI editor.
- Top-right toast banner for save success and error feedback on the CI detail page.
- Sidebar navigation icons for Dashboard, Incidents, Problems, Changes, Configuration Items, Users & Groups, Settings, and Sign out.
- Accent-colored detail sections with icons on record and configuration item detail pages.
- Breadcrumb navigation and sticky translucent detail page headers on record and CI detail views.

### Changed

- App shell uses a fixed viewport layout so the sidebar and sign-out button stay visible while only the main content area scrolls.
- Detail view back links replaced with breadcrumbs; detail headers pin flush to the top with a glass backdrop as content scrolls underneath.
- CI updates merge `other` JSON payloads into existing stored properties instead of replacing the whole object.
- Ansible `configuration_item.yml` smoke test assertion now matches the CI name created by the playbook.
