# Frontend Agent Instructions

## Run Prettier and ESLint before committing

Pre-commit hooks for this repo **check** frontend files; they do not auto-fix them.
A commit fails if either hook reports a problem:

- `prettier` runs `npx prettier --check` against `src/**/*.{ts,tsx,css,json}` and
  frontend config files. It does **not** write.
- `eslint` runs `npx eslint --max-warnings 0 src/`. Warnings fail the hook the
  same as errors.

After creating or editing frontend files, and **before considering the work done**, from `frontend/`:

```bash
npm run format
npm run lint
```

`npm run format` writes this package's Prettier config. Confirm `npx prettier --check` would pass on the files you touched — that is the same check the pre-commit hook runs. Do not stop at "looks formatted."

Do not leave `react-hooks/exhaustive-deps` warnings. Stabilize values used as
hook dependencies (`useMemo` for derived arrays/objects; destructure mutation
fields like `mutate` / `isPending` instead of listing the whole mutation object).
If a rule still needs a suppression, scope it to the line with a one-line
comment explaining why — never disable it project-wide.

## Expand/collapse indicators

Use the up/down chevron icons (`ChevronDownIcon` / `ChevronUpIcon` in
`src/components/DetailIcons.tsx`) for expand/collapse affordances, not
plus/minus glyphs or characters. See `ExpandableDetailSection.tsx` for the
reference implementation (two icons toggled via the `[open]` attribute in
`Layout.css`). Keep this consistent across the app — do not introduce new
`+`/`−` toggle indicators.

## Edit / Delete actions

When Edit and Delete actions appear together (e.g. table row actions, manage
mode), use icon buttons — `EditIcon` / `DeleteIcon` from
`src/components/DetailIcons.tsx` at `size={14}`, with `btn-icon` and
`btn-icon btn-icon-danger` classes respectively — rather than text buttons
(`btn btn-secondary` / `btn btn-danger`). See the manage actions in
`CatalogBrowsePage.tsx` for the reference pattern. Always include a
descriptive `aria-label` (e.g. `Edit ${name}`, `Delete ${name}`) since the
buttons no longer carry visible text.

## Resolving references (sys_id) to a name + link

Never display a raw `sys_id` for a field that references another record (a
user, group, CI, request, etc.). Resolve it to a human-readable label and
link to that object's display view instead.

- The v1 records API attaches a `<field>_display_value` sibling key next to
  every populated reference field (see `attach_reference_display_values` in
  `backend/app/domain/table_service.py`) — e.g. a group's `owner` field comes
  with `owner_display_value: "jdoe"`. Use `referenceDisplayValue(record, field)`
  from `src/utils/referenceFields.ts` to read it (it falls back to the sys_id
  if no label was resolved).
- Build the link target with `referenceHref(target, sysId)` from the same
  file, where `target` is a `RefTarget` (`'user' | 'group' | 'cmdb_ci' |
  'incident' | 'problem' | 'change_request' | 'sc_request' | 'sc_req_item' |
  'sc_cat_item'`). Every table has a real detail route, including
  `/users/:sysId` (`UserDetailPage.tsx`) and `/groups/:sysId`
  (`GroupDetailPage.tsx`).
- In a table cell, use the `<ReferenceLink value={record[field]} record={record}
  field={field} target="..." />` component (`src/components/ReferenceLink.tsx`).
  See the Groups table "Owner" column in `UsersPage.tsx`.
- In a detail page's readonly field grid, pass `href={referenceHref(...)}` to
  `ReadOnlyFieldInput` (`src/components/DetailFieldControls.tsx`) instead of
  rendering a plain value — see the `refTarget` fields on `LOCKED_FIELDS` /
  `CMDB_CI_ASSIGNMENT_FIELDS` in `RequestDetailPage.tsx`,
  `RequestedItemDetailPage.tsx`, and `ConfigurationItemDetailPage.tsx`.
- **Exception:** leave the "System" section (`sys_id`, `sys_created_by`,
  `sys_updated_by`, `sys_class_name`, etc.) as plain raw values. Showing the
  literal system identifiers there is intentional, not an oversight.
- Link styling: use the `reference-link` class (or `readonly-input-link` for
  the boxed readonly-field variant) — no underline, only a color change on
  hover, matching the global `a`/`a:hover` rule in `src/theme/global.css`. Do
  not add `text-decoration: underline` on hover for these links.
