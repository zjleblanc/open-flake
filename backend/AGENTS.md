# Backend Agent Instructions

## Ruff lint suppressions must be scoped, never generic

Do not add rule codes to the top-level `[tool.ruff.lint] ignore = [...]` list in
`pyproject.toml`. A blanket ignore silences a rule for the entire codebase,
which hides real issues in files that were never audited and quietly permits
the same mistake everywhere in the future.

Instead, scope every suppression to the specific file(s) where it is actually
justified, using `[tool.ruff.lint.per-file-ignores]`:

```toml
# Bad -- disables B008 project-wide, even for future non-API code.
[tool.ruff.lint]
ignore = ["B008"]

# Good -- disables B008 only where FastAPI's Depends()/Query() pattern applies.
[tool.ruff.lint.per-file-ignores]
"app/api/**" = ["B008"]
```

Before adding any suppression:

1. Run `ruff check --select <RULE>` to find every real violation and confirm
   which file(s) actually need it.
2. Add the code under `per-file-ignores` scoped to those file(s) or glob,
   with a one-line comment explaining *why* it's justified there.
3. If a rule has zero current violations, don't add a suppression for it at
   all -- there's nothing to scope, and pre-emptive ignores just rot.
4. Prefer fixing the code over ignoring the rule when the fix is
   straightforward and doesn't hurt readability.

This applies to every linter/formatter config in this project (ruff, mypy,
pylint, etc.) -- not just the current `ignore` list.
