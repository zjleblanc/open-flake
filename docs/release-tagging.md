# Release and image tagging strategy

OpenFlake uses **git tags** to trigger container image publishes and **Quay image tags** for deployment. Keep them aligned so installs and upgrades are predictable.

## Principles

1. **Production installs pin an explicit tag** — never rely on `latest` in production.
2. **Git tags are immutable** — do not move or reuse a tag; cut a new patch release instead.
3. **Image tags match git tags** for official releases (`v1.2.3` → `quay.io/.../openflake-backend:v1.2.3`).
4. **`latest` is a convenience pointer** — updated only when a new **stable** release is published; not moved for pre-releases.

## Tag formats

| Type | Git tag example | Quay image tag | Moves `latest`? | Use for |
|------|-----------------|----------------|-----------------|---------|
| **Stable production** | `v1.0.0` | `v1.0.0` | Yes | Production deployments, change-controlled upgrades |
| **Patch fix** | `v1.0.1` | `v1.0.1` | Yes | Bugfix releases on a stable line |
| **Release candidate** | `v1.1.0-rc.1` | `v1.1.0-rc.1` | No | Staging / UAT before a minor/major |
| **Beta** | `v1.1.0-beta.2` | `v1.1.0-beta.2` | No | Early access testers |
| **Development snapshot** | `v0.2.0-dev.20260605` | same | No | Internal QA, short-lived integration tests |
| **Commit snapshot** | `dev-abc1234` | `dev-abc1234` | No | CI debugging, one-off shares (optional) |

Use [Semantic Versioning](https://semver.org/) for stable tags: `vMAJOR.MINOR.PATCH`.

- **MAJOR** — breaking API or upgrade/migration changes operators must plan for
- **MINOR** — backward-compatible features
- **PATCH** — backward-compatible fixes

Pre-release suffixes use a hyphen after the patch: `-rc.1`, `-beta.1`, `-dev.<date>`.

## Production releases (stable)

### When to cut a stable tag

- CHANGELOG entry is ready for the release
- `backend/pyproject.toml` `version` matches the tag (without the `v` prefix)
- Images build and basic smoke tests pass
- Database migrations are idempotent (backend startup handles them today)

### Maintainer workflow

```bash
# 1. Ensure main is ready; version bumped in pyproject.toml (e.g. 1.0.0)
# 2. Update CHANGELOG.md with the release section

git tag -a v1.0.0 -m "OpenFlake 1.0.0"
git push origin v1.0.0
```

Pushing `v*` triggers [`.github/workflows/publish-images.yml`](../.github/workflows/publish-images.yml), which publishes multi-arch images to Quay as:

- `quay.io/zleblanc/openflake-backend:v1.0.0`
- `quay.io/zleblanc/openflake-frontend:v1.0.0`
- `quay.io/zleblanc/openflake-backend:latest` (stable `vMAJOR.MINOR.PATCH` only)
- `quay.io/zleblanc/openflake-frontend:latest`

### Production install / upgrade

Pin the stable tag explicitly:

```bash
OPENFLAKE_IMAGE_TAG=v1.0.0 ./scripts/podman-install.sh --ssl-dir /etc/ssl/openflake --domain itsm.example.com
```

```bash
OPENFLAKE_IMAGE_TAG=v1.0.1 ~/.local/share/openflake/podman-upgrade.sh --backup
```

Record the pinned tag in your runbook. Roll back by re-running the upgrade script with the previous tag.

## Development and pre-production

### Release candidates and betas

Use when `main` is feature-complete but not yet declared stable:

```bash
git tag -a v1.1.0-rc.1 -m "Release candidate 1 for 1.1.0"
git push origin v1.1.0-rc.1
```

Install in a **non-production** environment:

```bash
OPENFLAKE_IMAGE_TAG=v1.1.0-rc.1 ./scripts/podman-install.sh --http-only
```

RC tags publish to Quay but **do not** update `latest`, so production installs that mistakenly use `latest` are not pulled onto an RC.

### Development snapshots

For frequent integration testing without implying release quality:

**Option A — dated dev tag (recommended for shared dev environments):**

```bash
git tag -a v0.2.0-dev.20260605 -m "Dev snapshot 2026-06-05"
git push origin v0.2.0-dev.20260605
```

**Option B — manual CI publish (no git tag):**

GitHub Actions → **Publish container images** → `workflow_dispatch` with tag e.g. `dev-main-20260605` or `sha-850cb5d`.

```bash
# Local equivalent
QUAY_USERNAME=... QUAY_TOKEN=... ./scripts/publish-images.sh --push --tag dev-main-20260605
```

Use dev tags only in lab/staging. Delete or stop using old dev image tags when no longer needed (Quay retention policy).

### Local development without registry tags

Contributors typically **do not** need Quay tags:

```bash
podman compose -f deploy/podman-compose.yaml up -d --build   # build from source
./scripts/ensure-postgres.sh && ./scripts/start-backend.sh   # native backend
```

## Version alignment checklist

Before tagging `vX.Y.Z`:

| Artifact | Location | Example |
|----------|----------|---------|
| Git tag | `vX.Y.Z` | `v1.0.0` |
| Python package version | `backend/pyproject.toml` | `version = "1.0.0"` |
| Quay image tag | install/upgrade env | `OPENFLAKE_IMAGE_TAG=v1.0.0` |
| Changelog | `CHANGELOG.md` | `## YYYY-MM-DD — Summary` for the release |
| Installed version file | `~/.local/share/openflake/installed-version` | written by install/upgrade scripts |

## Branch vs tag policy

| Branch | Purpose | Publishes images? |
|--------|---------|-------------------|
| `main` | Integration; always deployable from source | No (unless manual `workflow_dispatch`) |
| Tags `v*` | Official images on Quay | Yes (CI on push) |

Do not auto-publish every commit to `main` as `latest` — that makes production pinning meaningless.

## Operator guidance

| Environment | Recommended `OPENFLAKE_IMAGE_TAG` |
|-------------|----------------------------------|
| Production | Pin stable tag (`v1.0.0`, `v1.0.1`, …) |
| Staging / UAT | Pin RC or beta (`v1.1.0-rc.1`) |
| Lab / dev | Dev snapshot, `workflow_dispatch` tag, or build from source |
| **Avoid in production** | `latest` |

## Hotfix workflow

1. Branch from the release tag (or cherry-pick onto `main` if policy allows)
2. Fix, bump **patch** in `pyproject.toml`, update CHANGELOG
3. Tag `v1.0.1`, push tag
4. Upgrade production with `OPENFLAKE_IMAGE_TAG=v1.0.1` and optional `--backup`

## Anti-patterns

- Reusing or force-moving a git tag after it has been pushed
- Running production on `latest` without a documented rollback tag
- Publishing `-rc` or `-dev` tags and expecting `latest` to point at them
- Tagging without updating `CHANGELOG.md` or `pyproject.toml` version
- Letting `installed-version` on hosts drift from the tag in `.env` (upgrade script keeps them in sync)

## Quick reference

```bash
# Stable production release
git tag -a v1.0.0 -m "OpenFlake 1.0.0" && git push origin v1.0.0

# Release candidate (staging)
git tag -a v1.1.0-rc.1 -m "RC1" && git push origin v1.1.0-rc.1

# Dev snapshot
git tag -a v0.2.0-dev.20260605 -m "Dev snapshot" && git push origin v0.2.0-dev.20260605

# Manual dev publish (no git tag)
# GitHub Actions workflow_dispatch, tag: dev-main-20260605
```

See also: [scripts/docs/publish-images.md](../scripts/docs/publish-images.md), [Installation — Publishing images](installation.md#publishing-images-maintainers).
