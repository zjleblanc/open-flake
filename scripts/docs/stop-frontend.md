# stop-frontend.sh

Stop the local OpenFlake Vite development server listening on port 5173. Used by VS Code post-task teardown and manual cleanup after [start-frontend.sh](start-frontend.md).

## Prerequisites

- None. Uses `lsof` when available, otherwise `pkill`.

## Usage

From the repository root:

```bash
./scripts/stop-frontend.sh
```

Safe to run when no server is active — exits silently if nothing is listening.

## Behavior

1. Find PIDs listening on TCP port 5173 via `lsof` and send `TERM`, then `KILL` if needed
2. Fall back to `pkill` matching `vite`

## VS Code integration

`.vscode/tasks.json` defines a **Stop Frontend Server** task that runs this script, and a **Stop Full Stack (Backend + Frontend)** task that runs it alongside [stop-backend.sh](stop-backend.md).

## Related

- [start-frontend.sh](start-frontend.md) — start the dev server
