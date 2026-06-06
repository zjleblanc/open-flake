# stop-backend.sh

Stop the local OpenFlake uvicorn development server listening on port 8000. Used by VS Code post-debug tasks and manual teardown after [start-backend.sh](start-backend.md).

## Prerequisites

- None. Uses `lsof` when available, otherwise `pkill`.

## Usage

From the repository root:

```bash
./scripts/stop-backend.sh
```

Safe to run when no server is active — exits silently if nothing is listening.

## Behavior

1. Find PIDs listening on TCP port 8000 via `lsof` and send `TERM`, then `KILL` if needed
2. Fall back to `pkill` matching `uvicorn app.main:app` on `127.0.0.1:8000`

Handles uvicorn `--reload` parent and child processes.

## VS Code integration

`.vscode/launch.json` references a **Stop Backend Server** post-debug task that runs this script after backend debug sessions end.

## Related

- [start-backend.sh](start-backend.md) — start the dev server
