---
name: utility-script-docs
description: >-
  Keeps README.md and scripts/docs/ in sync when utility scripts under scripts/
  are created, modified, or deleted. Use when adding, changing, or removing
  files in scripts/, when the user asks to document a script, or when finishing
  work that touches deployment or dev helper scripts.
---

# Utility script documentation

When you create, modify, or delete a **utility script** in `scripts/`, update project documentation in the same change. Do not leave script docs stale.

## What counts as a utility script

- Shell or other runnable helpers in `scripts/` (e.g. `scripts/*.sh`)
- Not application code under `backend/` or `frontend/`
- Not one-off inline commands in README

## Required updates by action

### Create a script

1. Add `scripts/docs/<script-name>.md` (strip `.sh` for the basename, e.g. `foo.sh` → `foo.md`)
2. Add a row to the table in [scripts/README.md](scripts/README.md)
3. Update [README.md](README.md) when the script is user-facing (install, upgrade, publish, SSL, local dev) — add or refresh inline examples in the relevant section
4. Keep the Architecture link to `scripts/README.md` present in root README

### Modify a script

1. Update `scripts/docs/<script-name>.md` — prerequisites, usage, options, env vars, behavior
2. Update `scripts/README.md` if purpose or quick-reference commands changed
3. Update [README.md](README.md) if CLI flags, env vars, or workflows shown there changed

### Delete a script

1. Delete `scripts/docs/<script-name>.md`
2. Remove its row from `scripts/README.md`
3. Remove references from [README.md](README.md) (inline examples, mentions)
4. Search the repo for the script name and clean up remaining references (VS Code tasks, CHANGELOG only if part of the same batch)

## Doc file format

Follow [doc-template.md](doc-template.md). Match tone and structure of existing files in `scripts/docs/`.

Minimum sections:

- One-line purpose under the `# script-name.sh` heading
- **Prerequisites**
- **Usage** with copy-paste examples from repo root (`./scripts/...`)
- **Options** and/or **Environment variables** tables when the script accepts them
- **Related** links to other script docs and relevant README anchors

Read one existing doc in `scripts/docs/` before writing a new one.

## Root README guidance

| Script category | README sections to touch |
|-----------------|--------------------------|
| Podman install / upgrade | Install from Quay, Upgrade |
| Image publish | Publishing images (maintainers) |
| TLS / certs | SSL / HTTPS |
| Local dev (postgres, backend) | Development / Quick Start if referenced |
| Any new top-level workflow | Add a short subsection with one example command |

Do not duplicate full script docs in README — link to [scripts/README.md](scripts/README.md) or cite one example command. Full detail lives in `scripts/docs/`.

## Checklist

Before marking script work complete:

```
- [ ] scripts/docs/<name>.md created, updated, or deleted
- [ ] scripts/README.md table and quick reference current
- [ ] README.md examples and sections match script behavior
- [ ] No broken links to removed script docs
```

## Examples

**Added `scripts/backup-db.sh`:**

- Create `scripts/docs/backup-db.md`
- Add table row in `scripts/README.md`
- Add backup example under README Upgrade section if user-facing

**Changed `podman-install.sh` `--tag` default:**

- Update `scripts/docs/podman-install.md` env table
- Update README install examples if they mention the default

**Removed obsolete script:**

- Delete doc, table row, and README curl/invoke examples
