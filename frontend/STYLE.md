## OpenFlake Brand & UI Style Documentation

This style document establishes the visual identity, typography, and interface guidelines for **OpenFlake**, a lightweight, dark-themed open-source ITSM tool built for mock ServiceNow API automation testing.

---

### 1. Brand Identity & Design Principles

OpenFlake balances the raw utility of a developer tool with a premium, sleek open-source aesthetic. The visual theme is deliberately dark, mysterious, and high-velocity—utilizing sharp angles, geometric structure, and circuit-like details to evoke engineering precision.

> **Core Mantra:** Fast to deploy, invisible until called, explicitly developer-first.

---

### 2. Color Palette

All colors are defined as CSS custom properties in [`global.css`](./src/theme/global.css). Do not hardcode hex values in components—reference the tokens below.

| Token | Usage |
| --- | --- |
| `--of-bg` | Page background, code blocks, form inputs |
| `--of-surface` | Cards, panels, elevated containers |
| `--of-surface-hover` | Hover fills, closed-state badges |
| `--of-border` | Dividers, table rules, panel borders |
| `--of-text` | Primary body copy |
| `--of-text-muted` | Labels, table headers, secondary copy |
| `--of-primary` | Primary actions, brand accent, hover glow |
| `--of-primary-dark` | Primary button hover |
| `--of-primary-light` | Sidebar nav text, new-state badges |
| `--of-accent` | Links, stat values, secondary emphasis |
| `--of-accent-dark` | Link hover |
| `--of-danger` | Errors, destructive actions |
| `--of-danger-dark` | Darker danger (e.g. light-theme icon accents) |
| `--of-danger-light` | Lighter danger (e.g. dark-theme icon accents) |
| `--of-success` | Resolved states |
| `--of-switch-success` | Checked toggle / switch track accent |
| `--of-info` | Informational highlights |
| `--of-gradient` | Sidebar and login page background |
| `--of-sidebar-text` | Inactive sidebar navigation links |
| `--of-sidebar-active-bg` | Active/hover sidebar link background |
| `--of-row-hover` | Table row hover tint |

---

### 3. Typography Hierarchy (The GitHub Dev Look)

Font tokens and utility classes live in [`global.css`](./src/theme/global.css). Font files are vendored under [`src/assets/fonts/`](./src/assets/fonts/) and registered in [`fonts.css`](./src/theme/fonts.css) for fully offline deployments—do not add external font CDN links.

#### Primary Header Font: Hubot Sans

* **Token:** `--of-font-heading`
* **Usage:** App logo text, page titles (`h1`, `.h1`), section headers (`h2`, `.h2`), empty state callouts, primary brand elements.
* **Characteristics:** Geometric, wide tracking, structural, engineered layout.
* **CSS Implementation:**

```css
font-family: var(--of-font-heading);
font-weight: 700;
letter-spacing: 0.05em;
text-transform: uppercase;
```

Use the `.brand-text` class for logo lockups.

#### UI & Body Font: Mona Sans

* **Token:** `--of-font-ui` (also aliased as `--of-font`)
* **Usage:** Data tables, sidebar navigation, form labels, button text, and general interface copy.
* **Characteristics:** Highly legible at tiny scales, balanced x-height, industrial-grotesque roots.
* **CSS Implementation:**

```css
font-family: var(--of-font-ui);
font-weight: 400; /* Regular for body */
font-weight: 600; /* Semi-bold for UI actions and table headers */
```

#### Code & Payload Font: JetBrains Mono

* **Token:** `--of-font-mono`
* **Usage:** Code snippets, mock API payloads, integration logs, JSON schemas, webhooks, and URL endpoints.
* **Characteristics:** Increased letter height, distinct brackets, zero ambiguity between `0` and `O`.
* **CSS Implementation:**

```css
font-family: var(--of-font-mono);
font-weight: 400;
font-size: 13px;
line-height: 1.5;
```

Use `.code-inline` for inline references and `.code-block` for payload panels.

---

### 4. Layout & UI Element Specifications

#### App Logo & Iconography

* The tech snowflake should be isolated from its background canvas and used as a vector element floating at the top-left of the UI sidebar.
* When accompanied by text, the layout dictates: **[ Snowflake Icon ] `OPENFLAKE`** rendered with the `.brand-text` class (Hubot Sans Bold, uppercase).

#### Code Block & API Live Feed Style

To make mock integration responses feel real-time and responsive, API log panels must adopt a strict terminal appearance:

* **Background:** `var(--of-bg)` with a subtle `1px` border of `var(--of-border)`.
* **Inner Padding:** `16px` (use the `.code-block` class).
* **Interactive State:** Hovering over an API log block reveals a faint glowing corner indicator using `var(--of-primary)` and activates a floating "Copy Payload" button.

#### ITSM Data Tables (Incidents/Tickets)

* **Rows:** Alternating background fills are prohibited. Use clean divider lines (`1px solid var(--of-border)`) to keep the interface minimal.
* **Hover States:** Rows change background to `var(--of-row-hover)` on hover to allow developers to track dense JSON mapping fields horizontally across the monitor.

---

### 5. Consistency Rules

#### List-view tables must use the card wrapper

Every page that renders a list table—including integration sub-tabs (Webhooks, Secrets), catalog admin, configuration items, and incidents—must wrap the `<table>` in a `.card` with zero padding and hidden overflow. This ensures uniform border-radius, background, and border treatment across all list views:

```tsx
<div className="card" style={{ padding: 0, overflow: "hidden" }}>
  <table>…</table>
</div>
```

Do **not** use `<section className="panel">` or the `.data-table` class for list tables; these are legacy patterns. If the table needs a description paragraph, place it *above* the card wrapper, not inside it.

#### Field hints use tooltips, not muted text

When a form field needs supplemental guidance (allowed characters, optional context, format examples), present it with the shared [`FieldTooltip`](./src/components/FieldTooltip.tsx) component next to the label—**not** as a `<p className="catalog-help-text">` paragraph below the input.

```tsx
<span className="field-label-with-tooltip">
  <label htmlFor="my-field">Label</label>
  <FieldTooltip ariaLabel="Field info">
    Hint content here.
  </FieldTooltip>
</span>
```

Rules for tooltips:

- Use `FieldTooltip` for every field hint so typography, spacing, and behavior stay consistent.
- Only one tooltip is open at a time; opening another closes the previous.
- Tooltips dismiss on scroll, resize, Escape, and when the pointer leaves the trigger/tooltip.
- Plain string children render as muted body text. Pass React nodes (`<strong>`, `<p>`, `<ul>`, `<code>`) for structured rich content, or set `rich` with a markdown string to render via `MarkdownRenderer`.
- Tooltips portal to `document.body` at `z-index: 1100` so they remain visible above the sidebar.
- Elevation uses the theme token `--of-tooltip-shadow` (darker lift in dark mode, softer lift in light mode).

Reserve `catalog-help-text` for transient loading/status indicators inside builders (e.g. "Loading fields…") where a tooltip is not appropriate.

#### No redundant section titles

If the page header breadcrumbs already communicate the page identity (e.g. **Integrations → Secrets**), do not repeat that same label as an `<h3>` section title inside the page body. Create sections should use `<h2 className="section-title">New {Entity}</h2>` inside a `.card`, matching the pattern used in `RecordListPage`.

#### Buttons: primary solid, secondary outlined

Use the global button classes in [`global.css`](./src/theme/global.css). Do not invent per-page button skins.

| Class | Role | Appearance |
| --- | --- | --- |
| `.btn-primary` | Main actions (Save, Create, Submit, primary page CTAs) | Solid primary fill |
| `.btn-secondary` | Sub-actions in forms and tables (Cancel, Add row, Clear, **row Edit**) | Surface fill + primary outline; solid primary fill on hover |
| `.btn-danger` | Destructive sub-actions (**row Delete**, Remove, attachment Delete) | Surface fill + danger outline; solid danger fill on hover |
| `.btn-danger-solid` | Main destructive actions (confirm dialog confirm, bulk delete header CTA, record Delete) | Solid danger fill |

```tsx
{/* Main action */}
<button type="submit" className="btn btn-primary">Save</button>

{/* Sub-action */}
<button type="button" className="btn btn-secondary">Cancel</button>

{/* Row delete */}
<button type="button" className="btn btn-danger btn-sm">Delete</button>
```

Rules:

- Page-header and form submit actions use `.btn-primary`.
- Cancel, Add header/row, Clear filter, and **row Edit** use `.btn-secondary`.
- **Delete / Remove controls** use the danger theme—not the primary/app accent. Prefer `.btn btn-danger` (outline) for in-row and inline deletes; use `.btn-danger-solid` for confirmed or page-level destructive CTAs.
- **Every delete/remove of persisted data** must open [`ConfirmDialog`](./src/components/ConfirmDialog.tsx) before calling the API. Do not delete immediately on click, and do not use `window.confirm`. Name the item in the dialog message. Form-only row removers (e.g. clearing an unsaved header row) do not need confirmation.
- Do not restyle `.btn-secondary` or `.btn-danger` back to a muted gray fill; the accent/danger outlines are intentional and app-wide.
- Mode switches that are not actions (e.g. markdown Edit/Preview) must use tabs (`.markdown-editor-tabs` / `.markdown-editor-tab`), not secondary buttons.
#### Markdown editor mode uses tabs

Edit/Preview (and any similar content-mode switcher) must use a `role="tablist"` control, not `.btn-secondary`:

```tsx
<div className="markdown-editor-tabs" role="tablist" aria-label="Description editor mode">
  <button type="button" role="tab" aria-selected={mode === "edit"} className={`markdown-editor-tab${mode === "edit" ? " markdown-editor-tab--active" : ""}`}>
    Edit
  </button>
  <button type="button" role="tab" aria-selected={mode === "preview"} className={`markdown-editor-tab${mode === "preview" ? " markdown-editor-tab--active" : ""}`}>
    Preview
  </button>
</div>
```

Do **not** reuse `.toggle-group` with `.btn-secondary.active` for this pattern; that legacy approach is removed.
#### Select boxes use `OFSelect`, not native `<select>`

All dropdown/select fields must use the shared [`OFSelect`](./src/components/OFSelect/OFSelect.tsx) component, not a raw `<select>`/`<option>` pair. `OFSelect` is a fully custom combobox (trigger + portal-rendered listbox, styled like [`TemplateAutocomplete`](./src/components/TemplateAutocomplete.tsx)) so behavior and theming stay consistent across the app, and so features unavailable to native selects (autocomplete filtering, tag-based multi-select) are available everywhere.

```tsx
import { OFSelect } from '../components/OFSelect';

<OFSelect
  id="wh-method"
  aria-label="HTTP method"
  options={[
    { value: 'POST', label: 'POST' },
    { value: 'PUT', label: 'PUT' },
    { value: 'PATCH', label: 'PATCH' },
  ]}
  value={form.method}
  onChange={(value) => setForm({ ...form, method: value as string })}
/>
```

Props:

| Prop | Type | Default | Notes |
| --- | --- | --- | --- |
| `options` | `{ value, label, disabled? }[]` | — | Required |
| `value` / `defaultValue` | `string \| string[]` | uncontrolled `''`/`[]` | Use `string[]` only when `multiple` |
| `onChange` | `(value: string \| string[]) => void` | — | Cast the callback arg to `string` or `string[]` at the call site |
| `size` | `'sm' \| 'md' \| 'lg'` | `'md'` | Match surrounding field density; filter bars typically use `sm` |
| `theme` | `'primary' \| 'secondary'` | `'primary'` | `primary` for form fields/main filters; `secondary` for lower-emphasis inline controls |
| `multiple` | `boolean` | `false` | Renders selections as removable tags in the trigger and keeps the listbox open on select |
| `autocomplete` | `boolean` | `false` | Renders the trigger as a text input that filters `options` by label as the user types |
| `disabled` | `boolean` | `false` | Dims the trigger and blocks interaction (matches `.btn:disabled` opacity) |
| `placeholder` | `string` | `'Select…'` | Shown when nothing is selected |

Rules:

- Do not build a new native `<select>`, and do not hand-roll another custom dropdown — extend `OFSelect` if it's missing a capability you need.
- Reference/async-loaded options (e.g. catalog variable choices) should still fetch via `useQuery` as before, but render results through `OFSelect`'s `options` prop instead of `<option>` children.
- Catalog `multi_select` variables must render with `multiple` so shoppers can pick more than one value (previously these fell through to a plain text input).
- Filter-bar instances that previously used `width: auto; min-width: …` on a native `<select>` should instead pass `size="sm"` and constrain width via a wrapping element, not by overriding `OFSelect`'s internal layout.

#### Form grids keep inputs aligned when tooltips are mixed with plain labels

`.catalog-form-grid` uses `align-items: end` so that a field with a `.field-label-with-tooltip` label row stays level with neighboring plain-label fields. When adding new multi-column form layouts, prefer this grid (or the same `align-items: end` + column flex pattern) so tooltip icons never push inputs out of horizontal alignment.

#### Empty tables show a centered message

Every list `<table>` that can render zero rows must include an empty-state row:

```tsx
{items.length === 0 && (
  <tr>
    <td colSpan={N} className="empty-state">
      No {items} yet
    </td>
  </tr>
)}
```

Use the plural noun for the entity (`No webhooks yet`, `No secrets yet`, `No variables yet`). Do not leave an empty `<tbody>`, and do not use left-aligned `text-muted` cells for this purpose.

#### Loading states use `.empty-state`

Page-level and section-level loading copy must use `<p className="empty-state">Loading…</p>` (or a more specific variant such as `Loading catalog…`). Do not use a bare `<p>Loading...</p>`.

---

### 6. Enforcement Checklist

Before merging UI changes, verify:

- [ ] List tables are wrapped in `.card` with `padding: 0; overflow: hidden` (no `.panel` / `.data-table`)
- [ ] Empty tables render `<td colSpan={N} className="empty-state">No {items} yet</td>`
- [ ] Field guidance uses `FieldTooltip` (not muted paragraphs under inputs; not hand-rolled tooltip markup)
- [ ] `catalog-help-text` appears only for transient loading/status copy
- [ ] Selects use `OFSelect` (no raw `<select>`/`<option>`, no hand-rolled dropdown)
- [ ] Multi-column form grids keep inputs aligned when some labels have tooltips (`align-items: end`)
- [ ] Loading states use `<p className="empty-state">…</p>`
- [ ] Page body does not repeat breadcrumb identity as a redundant section title
- [ ] Main actions use `.btn-primary`; form/table sub-actions use `.btn-secondary` (accent outline, solid fill on hover)
- [ ] Table-row Edit uses `.btn-secondary`; Delete/Remove uses `.btn-danger` (danger outline, not primary)
- [ ] Delete/Remove of persisted data opens `ConfirmDialog` (no immediate mutate, no `window.confirm`)
- [ ] Confirm/bulk destructive CTAs use `.btn-danger-solid`
- [ ] Content mode switchers (Edit/Preview) use `.markdown-editor-tabs`, not secondary buttons
