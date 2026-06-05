# Changelog

All notable changes to this project will be documented in this file.

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
