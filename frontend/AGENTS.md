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
