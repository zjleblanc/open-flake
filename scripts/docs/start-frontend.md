# start-frontend.sh

Run the OpenFlake Vite frontend dev server locally. Intended for development alongside the FastAPI backend.

## Prerequisites

- **Node.js** and frontend dependencies installed:

```bash
cd frontend && npm install
```

## Usage

From the repository root:

```bash
./scripts/start-frontend.sh
```

The dev server binds to `http://localhost:5173` with hot module reload. Requests to `/api`, `/oauth_token.do`, and `/health` are proxied to the backend on `http://localhost:8000`.

VS Code tasks in `.vscode/tasks.json` use this workflow; [stop-frontend.sh](stop-frontend.md) tears down Vite after debug sessions.

## Environment

For HTTPS during local development, run `npm run dev:https` directly instead — see [SSL / HTTPS — Local development HTTPS](../../docs/ssl-https.md#local-development-https).

## Troubleshooting

**`node_modules` not found:** Run `npm install` in `frontend/` as shown in Prerequisites.

**API requests failing:** Start the backend first — see [start-backend.sh](start-backend.md).

## Related

- [start-backend.sh](start-backend.md) — run the API alongside the frontend
- [stop-frontend.sh](stop-frontend.md) — stop the dev server on port 5173
- [Development](../../docs/development.md)
