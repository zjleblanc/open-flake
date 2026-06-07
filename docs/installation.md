# Installation

Pre-built images are published to [Quay.io](https://quay.io) (`quay.io/zleblanc/openflake-backend`, `quay.io/zleblanc/openflake-frontend`). Postgres still pulls from `docker.io/library/postgres:16-alpine`.

For a local build from source instead of Quay, see [Quick Start](../README.md#quick-start-podman) in the main README.

## Quick install (HTTPS + your certificates)

Place your TLS certificate and key on the host (defaults shown; filenames are configurable):

- Directory: e.g. `/etc/ssl/openflake`
- Certificate: `fullchain.pem` (override with `OPENFLAKE_SSL_CERT`)
- Private key: `privkey.pem` (override with `OPENFLAKE_SSL_KEY`)

Then run:

```bash
curl -fsSL https://raw.githubusercontent.com/zjleblanc/open-flake/main/scripts/podman-install.sh | \
  OPENFLAKE_DOMAIN=itsm.example.com \
  OPENFLAKE_SSL_DIR=/etc/ssl/openflake \
  bash
```

Or copy [deploy/openflake.env.example](../deploy/openflake.env.example) to `openflake.env` next to the install script and run without inline env vars.

The install script writes config to `~/.local/share/openflake/`, pulls images from Quay, and starts the stack with HTTPS on host port **8443** (rootless-safe; maps to nginx 443 in the container). Put a reverse proxy on 443 if you need the standard HTTPS port.

Pin a release tag:

```bash
OPENFLAKE_IMAGE_TAG=v0.1.0 OPENFLAKE_SSL_DIR=/etc/ssl/openflake bash -c "$(curl -fsSL .../podman-install.sh)"
```

HTTP-only (no certificates):

```bash
curl -fsSL https://raw.githubusercontent.com/zjleblanc/open-flake/main/scripts/podman-install.sh | bash -s -- --http-only
```

Full script reference: [scripts/docs/podman-install.md](../scripts/docs/podman-install.md).

## Advanced install (compose only)

```bash
mkdir openflake && cd openflake
curl -fsSLO https://raw.githubusercontent.com/zjleblanc/open-flake/main/deploy/{podman-compose.registry.yaml,podman-compose.ssl.yaml,.env.example}
cp .env.example .env
# Edit .env: OPENFLAKE_DOMAIN, OPENFLAKE_HTTPS_PORT, OPENFLAKE_SSL_DIR, OPENFLAKE_SSL_*_MOUNT, OPENFLAKE_SSL_CERT, OPENFLAKE_SSL_KEY, SECRET_KEY, POSTGRES_PASSWORD, ADMIN_PASSWORD
podman compose -f podman-compose.registry.yaml -f podman-compose.ssl.yaml --env-file .env up -d
```

## Upgrade

Pull a new release, redeploy containers, and apply database migrations (migrations run automatically when the backend starts):

```bash
curl -fsSL https://raw.githubusercontent.com/zjleblanc/open-flake/main/scripts/podman-upgrade.sh | \
  OPENFLAKE_IMAGE_TAG=v0.2.0 \
  bash
```

Or from an existing install:

```bash
OPENFLAKE_IMAGE_TAG=v0.2.0 ~/.local/share/openflake/podman-upgrade.sh
```

Optional PostgreSQL backup before upgrading:

```bash
OPENFLAKE_IMAGE_TAG=v0.2.0 OPENFLAKE_BACKUP=1 ~/.local/share/openflake/podman-upgrade.sh
```

Full script reference: [scripts/docs/podman-upgrade.md](../scripts/docs/podman-upgrade.md).

**Migrations:** Schema changes apply on backend startup (`create_all` plus incremental column additions). Data persists in the `openflake-pg-data` Podman volume across upgrades. No manual SQL step is required.

**Rollback:** Set `OPENFLAKE_IMAGE_TAG` in `~/.local/share/openflake/.env` to the previous version and re-run the upgrade script. Restore from a backup dump if needed.

## Publishing images (maintainers)

Tagging strategy for stable, pre-release, and dev images: [release-tagging.md](release-tagging.md).

Create public Quay repositories `openflake-backend` and `openflake-frontend`, then add GitHub Actions secrets `QUAY_USERNAME` and `QUAY_TOKEN` (robot account). Tag a release to publish:

```bash
git tag v0.1.0 && git push origin v0.1.0
```

Local build and push (multi-arch `linux/amd64` + `linux/arm64` by default):

```bash
QUAY_USERNAME=... QUAY_TOKEN=... ./scripts/publish-images.sh --push --tag v0.1.0
```

Host-native build only:

```bash
./scripts/publish-images.sh --single-arch
```

Full script reference: [scripts/docs/publish-images.md](../scripts/docs/publish-images.md).

Change default passwords and `SECRET_KEY` before production. Registry install does not publish PostgreSQL on the host (containers reach it on the internal network only).

## RHEL VM sizing

OpenFlake runs all three containers on a single host. These specs assume RHEL 9 with Podman.

| Profile | vCPU | RAM | Disk | Good for |
|---------|------|-----|------|----------|
| Lab / PoC | 2 | 4 GB | 40 GB | Dev, demos, &lt;10 users, light Ansible |
| Small production | 4 | 8 GB | 100 GB | Small IT team, steady UI and API use |
| Busier production | 4–8 | 16 GB | 200 GB+ | More users, larger CMDB, many attachments |

**4 vCPU / 8 GB RAM / 100 GB disk** is the recommended starting point for production.

Disk should cover PostgreSQL data, the attachments volume, OS/images, and `pg_dump` backups. Do not size disk for container images alone.

**RHEL setup:**

```bash
sudo dnf install -y podman podman-compose
sudo systemctl enable --now podman.socket
```

Install OpenFlake as the user that will run Podman (rootless is recommended). On Linux, the install script generates Podman Quadlets by default so each container starts on boot via systemd. For rootless Podman, the install user must have [lingering enabled](https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/containers_and_systemd_working-together/assembly_porting-containers-to-systemd_using-systemd-to-manage-containers) so user services run without an interactive login:

```bash
sudo loginctl enable-linger openflake
systemctl --user status openflake-backend.service
```

Use `--no-systemd` to install with Podman Compose instead, or manage a Quadlet install with `~/.local/share/openflake/openflake-quadlets.sh`.

**Firewall** (rootless Podman uses host port 8443 for HTTPS):

```bash
sudo firewall-cmd --permanent --add-port=8443/tcp
# Optional: direct API for Ansible on a trusted network
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```

| Port | Exposure | Purpose |
|------|----------|---------|
| 8443 | Public or load balancer | UI and API via nginx (HTTPS) |
| 8080 | Internal | HTTP redirect to HTTPS |
| 8000 | Internal / Ansible subnet | Direct API (optional) |

**SELinux and TLS permissions** (RHEL/Fedora host bind mounts): Compose mounts do not apply `:z` or `:Z` relabeling. Label TLS paths with `sudo chcon -R -t container_file_t /etc/ssl/openflake`. Rootless Podman also requires certificate files to be readable by the user running Podman — keys copied from Let's Encrypt as `root:root` mode `600` must be opened up, for example `sudo chmod 644 /etc/ssl/openflake/fullchain.pem /etc/ssl/openflake/privkey.pem`. If HTTPS on port 8443 resets the connection, check `podman logs openflake-frontend` for missing or unreadable certificate files.

Scale beyond a single VM when CPU stays above ~70% under normal load, Postgres memory pressure grows with CMDB size, or attachment storage nears disk capacity.

## See also

- [SSL / HTTPS](ssl-https.md) — TLS setup for Podman, Kubernetes, and Ansible
- [Configuration](configuration.md) — environment variables
- [scripts/README.md](../scripts/README.md) — utility scripts index
