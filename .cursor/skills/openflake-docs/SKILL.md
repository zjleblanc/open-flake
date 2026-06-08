---
name: openflake-docs
description: >-
  Maintains OpenFlake documentation structure: root README, docs/ guides,
  docs/README.md bundled view, scripts/docs/ references, and scripts/README.md
  bundled view. Use when creating or updating documentation, README files,
  guides under docs/, script references under scripts/docs/, or when the user
  asks to document features, scripts, installation, or development workflows.
---

# OpenFlake documentation

Keep documentation consistent across the repo. Individual topic files are the source of truth; index READMEs duplicate their content for a single-page reading experience.

## Layout

| Location | Role |
|----------|------|
| [README.md](../../README.md) | Slim landing page: intro, architecture, quick start, documentation tables |
| [docs/*.md](../../docs/) | Application guides (one topic per file) |
| [docs/README.md](../../docs/README.md) | Guide index table + inline single-page view |
| [scripts/docs/*.md](../../scripts/docs/) | Per-script reference (one script per file) |
| [scripts/README.md](../../scripts/README.md) | Script index table + quick reference + inline single-page view |
| [docs/ansible-examples/](../../docs/ansible-examples/) | Example Ansible playbooks |

Do **not** list utility scripts in `docs/README.md` — that belongs in `scripts/README.md` only.

## Index README structure

Both `docs/README.md` and `scripts/README.md` follow the same pattern:

1. **Title and intro** (scripts only)
2. **`[Go to single-page view](#on-this-page)`** — skip link above the index table
3. **Index table** — links to individual topic/script files
4. **Extra header content** (docs: example playbooks link; scripts: quick-reference commands)
5. **`## On this page`** — TOC with anchor links to each bundled section
6. **Bundled sections** — full content from individual files, separated by `---`

No HTML comments or generator markers between the header and bundled content.

### Heading levels in bundled sections

Demote every heading from the source file by one level when copying into an index README:

- Source `# Title` → bundled `## Title`
- Source `## Section` → bundled `### Section`

### Links in bundled sections

- Cross-references between guides/scripts in the same README → `#anchor` links (not `guide.md`)
- Links to files outside the bundle (deploy paths, root README, other README) → keep as normal relative links
- Script detail in application guides → link to `scripts/docs/<name>.md` or `scripts/README.md`; do not paste full script docs into `docs/`

### Section order

**docs/README.md** (after `## On this page`):

`installation` → `ssl-https` → `ansible-integration` → `api-compatibility` → `rbac` → `development` → `configuration` → `release-tagging`

**scripts/README.md**:

`podman-install` → `podman-upgrade` → `podman-update-scripts` → `publish-images` → `generate-dev-certs` → `ensure-postgres` → `start-backend` → `stop-backend`

## Workflows

### Update an application guide

1. Edit the source file in `docs/` (e.g. `installation.md`)
2. Update the matching bundled section in `docs/README.md`
3. Refresh the `## On this page` TOC entry if the title changed
4. Update the index table row if the one-line description changed
5. Update cross-links in other guides or bundled sections if needed
6. If the guide mentions a script, ensure `scripts/docs/` and `scripts/README.md` stay aligned

### Create an application guide

1. Add `docs/<topic>.md` following existing guide tone and structure
2. Add a row to the table in `docs/README.md`
3. Append the demoted content to `docs/README.md` (with `---` before it)
4. Add a TOC entry under `## On this page`
5. Link from root [README.md](../../README.md) documentation table if user-facing

### Update a utility script

1. Edit `scripts/docs/<script-name>.md` — see [script-doc-template.md](script-doc-template.md)
2. Update the matching bundled section in `scripts/README.md`
3. Refresh `scripts/README.md` table, quick reference, and TOC if needed
4. Update the relevant `docs/` guide when the script is user-facing (install, upgrade, publish, SSL, local dev) — cite one example command; link to script docs for detail

### Create a utility script

1. Add `scripts/docs/<script-name>.md` (strip `.sh` from basename)
2. Add a table row in `scripts/README.md`
3. Append bundled section and TOC entry in `scripts/README.md`
4. Update the matching `docs/` guide with a short example if user-facing
5. Keep root README utilities table in sync

### Delete a guide or script doc

1. Remove the source file
2. Remove the index table row, TOC entry, and bundled section from the index README
3. Remove links from root README, cross-references in other docs, and VS Code tasks if applicable

## Guide ↔ script mapping

| Topic | Application guide | Script docs |
|-------|-------------------|-------------|
| Podman install / upgrade | [installation.md](../../docs/installation.md) | podman-install, podman-upgrade, podman-update-scripts |
| Image publish | [installation.md](../../docs/installation.md) | publish-images |
| TLS / certs | [ssl-https.md](../../docs/ssl-https.md) | generate-dev-certs |
| Local dev | [development.md](../../docs/development.md) | ensure-postgres, start-backend, stop-backend |
| Release tagging | [release-tagging.md](../../docs/release-tagging.md) | publish-images |

## Root README

Keep the root README short. It should not duplicate full guide content — only:

- Architecture and quick start
- Documentation tables (application + utilities) linking to individual files
- `[Full documentation](docs/README.md)` and `[Full reference](scripts/README.md)` above each table

## Checklist

```
- [ ] Source file(s) in docs/ or scripts/docs/ updated
- [ ] Matching bundled section in docs/README.md or scripts/README.md synced
- [ ] Index table and ## On this page TOC current
- [ ] Cross-links use #anchors inside index READMEs, file links elsewhere
- [ ] No utility script table in docs/README.md
- [ ] Root README tables/descriptions still accurate
```

## Templates

- Script reference format: [script-doc-template.md](script-doc-template.md)
