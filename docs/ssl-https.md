# SSL / HTTPS

OpenFlake terminates TLS at nginx (Podman) or the Kubernetes Ingress. When the SSL compose override is used, the same certificate directory is mounted into the backend and nginx; the backend serves HTTPS on port 8000 and nginx proxies to it over TLS internally.

## Podman with self-signed certificates

Generate local development certificates:

```bash
./scripts/generate-dev-certs.sh
```

Full script reference: [scripts/docs/generate-dev-certs.md](../scripts/docs/generate-dev-certs.md).

Start with the SSL compose override (nginx listens on 443 in the container; publish **8443** on the host for rootless Podman):

```bash
OPENFLAKE_HTTPS_PORT=8443 \
OPENFLAKE_SSL_DIR=deploy/certs \
OPENFLAKE_SSL_BACKEND_MOUNT=deploy/certs:/etc/openflake/certs:ro \
OPENFLAKE_SSL_FRONTEND_MOUNT=deploy/certs:/etc/nginx/certs:ro \
podman compose -f deploy/podman-compose.yaml -f deploy/podman-compose.ssl.yaml up -d --build
```

Custom certificate filenames:

```bash
OPENFLAKE_SSL_DIR=/etc/ssl/openflake \
OPENFLAKE_SSL_CERT=cert.pem \
OPENFLAKE_SSL_KEY=key.pem \
podman compose -f deploy/podman-compose.registry.yaml -f deploy/podman-compose.ssl.yaml --env-file .env up -d
```

- **UI:** https://localhost:8443 (accept the browser warning for self-signed certs)
- **HTTP redirect:** http://localhost:8080 redirects to HTTPS when certificates are mounted
- **API (direct):** https://localhost:8000 when certificates are mounted (http://localhost:8000 without the SSL override)

Set a custom domain in the certificate SAN:

```bash
OPENFLAKE_DOMAIN=openflake.example.com ./scripts/generate-dev-certs.sh
```

## Production certificates (Podman)

Mount your own certificate and key into a host directory (defaults: `fullchain.pem` and `privkey.pem` in that directory). Set `OPENFLAKE_SSL_DIR` and the matching `OPENFLAKE_SSL_BACKEND_MOUNT` / `OPENFLAKE_SSL_FRONTEND_MOUNT` in `.env` (install script writes these automatically), and optionally `OPENFLAKE_SSL_CERT` / `OPENFLAKE_SSL_KEY`, then use the SSL compose override as above. Set `OPENFLAKE_BASE_URL` and `OPENFLAKE_CORS_ORIGINS` in `deploy/.env.example` (or pass them via `--env-file`) to match your public hostname.

For registry installs with your own certificates, see [Installation](installation.md#quick-install-https--your-certificates).

## Local development HTTPS

Run the Vite dev server with a self-signed certificate:

```bash
cd frontend
npm run dev:https
```

Add `https://localhost:5173` to `CORS_ORIGINS` in `backend/.env`:

```bash
CORS_ORIGINS=http://localhost:8080,http://localhost:5173,https://localhost:5173
```

## Kubernetes

Apply the frontend Service and Ingress manifests in `deploy/k8s/`. TLS terminates at the Ingress:

```bash
kubectl apply -f deploy/k8s/frontend-service.yaml
kubectl apply -f deploy/k8s/ingress.yaml
```

Create a TLS secret from your certificates:

```bash
kubectl create secret tls openflake-tls \
  --cert=fullchain.pem --key=privkey.pem
```

For automatic certificates, install [cert-manager](https://cert-manager.io/) and uncomment the `cert-manager.io/cluster-issuer` annotation in `deploy/k8s/ingress.yaml`. See `deploy/k8s/tls-secret.example.yaml` for a manual secret template.

Set `BASE_URL` and `CORS_ORIGINS` in the `openflake-secrets` Secret to your public HTTPS hostname.

## Ansible with HTTPS

Use the UI hostname through nginx, or the direct API on port 8000 (HTTPS when the SSL compose override mounts certificates):

```yaml
- servicenow.itsm.incident:
    instance:
      host: https://localhost:8000
      username: admin
      password: admin
    # ...
```

Or route API calls through nginx on host port 8443:

```yaml
- servicenow.itsm.incident:
    instance:
      host: https://localhost:8443
      username: admin
      password: admin
    # ...
```

For self-signed certificates in development only:

```yaml
instance:
  host: https://localhost:8443
  validate_certs: false
```

More Ansible examples: [ansible-integration.md](ansible-integration.md).

## See also

- [Installation](installation.md) — Quay install with HTTPS
- [Configuration](configuration.md) — `BASE_URL`, `CORS_ORIGINS`, and related settings
