# podman-update-scripts.sh

Download updated OpenFlake install helper scripts into an existing install directory. Does not change secrets in `.env`, pull container images, or restart containers unless `--deploy` is passed on a Quadlet install.

## Prerequisites

- An existing install created by [podman-install.sh](podman-install.md)
- **curl** — to download scripts from GitHub

Install directory must contain `.env`.

## Usage

### Update scripts from main

```bash
~/.local/share/openflake/podman-update-scripts.sh
```

From the repository copy:

```bash
./scripts/podman-update-scripts.sh
```

One-liner from GitHub:

```bash
curl -fsSL https://raw.githubusercontent.com/zjleblanc/open-flake/main/scripts/podman-update-scripts.sh | bash
```

### Pin a git branch, tag, or commit

```bash
./scripts/podman-update-scripts.sh --branch v0.2.0
```

Or:

```bash
OPENFLAKE_BRANCH=main ~/.local/share/openflake/podman-update-scripts.sh
```

### Apply Quadlet unit changes after update

```bash
~/.local/share/openflake/podman-update-scripts.sh --deploy
```

## Options

| Option | Description |
|--------|-------------|
| `--branch REF` | Git branch, tag, or commit on GitHub (default: `main`) |
| `--ref REF` | Alias for `--branch` |
| `--install-dir PATH` | Install directory (default: `~/.local/share/openflake`) |
| `--deploy` | Run `openflake-quadlets.sh deploy` after updating (Quadlet installs only) |
| `-h`, `--help` | Show help |

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENFLAKE_INSTALL_DIR` | `~/.local/share/openflake` | Install directory |
| `OPENFLAKE_BRANCH` | `main` | Git ref for script downloads |
| `OPENFLAKE_VERSION` | — | Deprecated alias for `OPENFLAKE_BRANCH` |
| `OPENFLAKE_GITHUB_REPO` | `zjleblanc/open-flake` | GitHub repository for raw downloads |

## What it updates

Always:

- `podman-upgrade.sh`
- `podman-update-scripts.sh`
- `pg_hba.conf`

For Quadlet installs (`OPENFLAKE_DEPLOY_METHOD=quadlet`):

- `openflake-quadlets.sh`

For Compose installs:

- `podman-compose.registry.yaml`
- `podman-compose.ssl.yaml`
- `openflake-stack.sh`

If the deploy method cannot be detected, all of the above are updated.

The script sets `OPENFLAKE_GITHUB_REF` in `.env` to the ref that was downloaded. Other `.env` values (passwords, `SECRET_KEY`, domain, image tag) are not modified.

When run from a repository checkout under `scripts/`, files are copied from the checkout instead of downloaded. When run from the install directory, files are always fetched from GitHub.

## Related

- [podman-install.sh](podman-install.md) — initial install
- [podman-upgrade.sh](podman-upgrade.md) — pull new container images
- [Installation — Upgrade](../../docs/installation.md#upgrade)
