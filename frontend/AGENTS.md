# Frontend

React 18 + Vite admin UI, using TanStack Query for data fetching and React Router for navigation.

## Run

```bash
cd frontend
npm run dev
```

Or `../scripts/start-frontend.sh` / `../scripts/stop-frontend.sh`.

## Build, lint & format

```bash
npm run build       # production build
npm run lint         # ESLint
npm run typecheck    # tsc
npm run format       # Prettier (writes)
```

**Note:** Always run `npm run format` after edits to ensure pre-commit checks pass. See `.cursor/rules/frontend-formatting.mdc`.

## Layout

- `src/components/` — shared UI components
- `src/pages/` — route-level pages
- `src/api/` — API client
- `src/auth/` — AuthContext
- `src/settings/` — user preferences
- `src/theme/` — global CSS, design tokens, fonts

See `STYLE.md` for the brand/design system (colors, typography, component tokens).

## Detail page convention

Every record detail page (`src/pages/*DetailPage.tsx`) follows the same structure — new
resource detail pages should match it rather than inventing a new layout:

- Wrap the page in `<div className="detail-page-layout">` with a `detail-page-main` >
  `detail-sections-stack` column on the left and a `<DetailSectionNav sections={...} />`
  sibling on the right.
- Section order: **System** (via `ExpandableDetailSection`, collapsed by default) first,
  then **General** (`defaultOpen`) for the main fields, then any other sections (e.g.
  Variables), then the unified **Activity** section, then any **References** section
  last. Keep `sectionNavItems` in this same order.
- Name the main fields section "General", never "Details". Nested collapsible content
  inside a section (e.g. "Additional Properties") uses `NestedCollapsibleSection`
  (in `ExpandableDetailSection.tsx`), separated from the rest of the section by its
  built-in `<hr>`, and starts collapsed.
- For any section listing linked/child records, use `RelatedRecordsSection` titled
  "References" (its default) with a `typeLabel` prop describing the linked record type
  (e.g. `typeLabel="Change Task"`) — don't invent entity-specific section names/tables.
- For comments/attachments/field-history, mount a single `<RecordActivityFeed ... />`
  (in `RecordActivityFeed.tsx`) rather than separate attachments/comments/activity
  sections — it merges all three into one chronological message-style feed.

## Adding a new resource type

Every backend table that represents a business/ITSM record another record might
reference should get a real list + detail view, even if basic — never leave a
reference field pointing at a table with no page (a raw sys_id link goes nowhere).
To add one:

1. **Backend slug** — if the table has no `/api/v1/records/{resource}` slug yet,
   add one to `TABLE_ENDPOINTS` in `backend/app/api/v1/router.py`
   (`RESOURCE_BY_TABLE` derives automatically). A table with no owner/assignment
   fields falls through `resolve_record_permissions`/`assert_can_create_record` to
   open read/write for any authenticated user by default (see `sc_cat_item`) — only
   add it to `RBAC_RECORD_TABLES`/`PLATFORM_TABLES` in
   `backend/app/domain/registry.py` if it needs real per-record ACLs.
2. **Routes** — add `<resource>` (list, via `RecordListPage`) and
   `<resource>/:sysId` (detail, via `RecordDetailPage` unless it needs a fully
   custom page) in `frontend/src/App.tsx`. A new resource doesn't need a sidebar
   nav entry — `change-tasks`/`catalog-tasks`-style child resources are reached via
   reference links or direct URL only (see `src/components/navConfig.tsx`).
3. **Column catalog** — define an `ALL_<RESOURCE>_COLUMNS: ListColumn[]` covering
   every typed (non-JSONB) field on the model, excluding only `sys_id`,
   `other`/`attributes` (JSONB), the table's own constant `sys_class_name`, and any
   long-form `Text` column (notes/plans/descriptions). Pass it as the list route's
   `allColumns` prop so it's selectable via the column-config popover.
4. **Reference target** — if any field (existing or new) points at this table's
   `sys_id`, add the table to `RefTarget` and `REF_TARGET_BASE_PATH` in
   `src/utils/referenceFields.ts`, and map that field name to the new target in
   `REFERENCE_COLUMN_TARGETS` (`src/pages/RecordListPage.tsx`) so list columns
   resolve to a name + link instead of a raw sys_id.
5. **State labels** — if the model has a `state` field with its own state machine
   (codes/meaning distinct from the generic `STATE_LABELS` fallback), add a
   `TABLE_STATE_LABELS` entry and matching `stateBadge` branch in
   `src/api/client.ts`.
