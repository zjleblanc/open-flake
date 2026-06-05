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
| `--of-surface-hover` | Secondary buttons, closed-state badges |
| `--of-border` | Dividers, table rules, panel borders |
| `--of-text` | Primary body copy |
| `--of-text-muted` | Labels, table headers, secondary copy |
| `--of-primary` | Primary actions, brand accent, hover glow |
| `--of-primary-dark` | Primary button hover |
| `--of-primary-light` | Sidebar nav text, new-state badges |
| `--of-accent` | Links, stat values, secondary emphasis |
| `--of-accent-dark` | Link hover |
| `--of-danger` | Errors, destructive actions |
| `--of-success` | Resolved states |
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
