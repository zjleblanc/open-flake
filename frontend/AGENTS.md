# Frontend Agent Instructions

## Run Prettier and ESLint before committing

Pre-commit hooks for this repo **check** frontend files; they do not auto-fix them.
A commit fails if either hook reports a problem:

- `prettier` runs `npx prettier --check` against `src/**/*.{ts,tsx,css,json}` and
  frontend config files. It does **not** write.
- `eslint` runs `npx eslint --max-warnings 0 src/`. Warnings fail the hook the
  same as errors.

After creating or editing frontend files, from `frontend/`:

```bash
npm run format
npm run lint
```

`npm run format` uses this package's Prettier (`frontend/.prettierrc`:
`singleQuote`, `trailingComma: "all"`, `printWidth: 100`, `semi`). Do not rely on
a global Prettier or hand-wrap JSX/TS to look "nice" — if a tag, import, or
call fits in 100 columns, Prettier will put it on one line and `--check` will
fail if you left it split.

Do not leave `react-hooks/exhaustive-deps` warnings. Stabilize values used as
hook dependencies (`useMemo` for derived arrays/objects; destructure mutation
fields like `mutate` / `isPending` instead of listing the whole mutation object).
If a rule still needs a suppression, scope it to the line with a one-line
comment explaining why — never disable it project-wide.
