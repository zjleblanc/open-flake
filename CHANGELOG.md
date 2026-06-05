# Changelog

All notable changes to this project will be documented in this file.

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
