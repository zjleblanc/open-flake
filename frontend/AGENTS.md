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

## Layout

- `src/components/` — shared UI components
- `src/pages/` — route-level pages
- `src/api/` — API client
- `src/auth/` — AuthContext
- `src/settings/` — user preferences
- `src/theme/` — global CSS, design tokens, fonts

See `STYLE.md` for the brand/design system (colors, typography, component tokens).
