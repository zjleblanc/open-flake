# publish-images.sh

Build OpenFlake backend and frontend container images from the repository Containerfiles. Supports multi-arch manifests (`linux/amd64` and `linux/arm64`) and optional push to Quay.io.

## Prerequisites

- **Podman** with build and manifest support
- Repository checkout at the project root (script runs builds from repo root)
- For **multi-arch** builds: QEMU emulation configured in Podman
  - macOS: Podman machine with Rosetta/QEMU
  - Linux: `qemu-user-static` for cross-arch builds
- For **`--push`**:
  - Quay.io repositories: `openflake-backend`, `openflake-frontend`
  - `QUAY_USERNAME` and `QUAY_TOKEN` (robot account token)

## Usage

### Multi-arch build (local only)

```bash
./scripts/publish-images.sh
```

Builds `quay.io/zleblanc/openflake-backend:latest` and `openflake-frontend:latest` as manifest lists for amd64 and arm64.

### Multi-arch build and push

```bash
QUAY_USERNAME=myuser QUAY_TOKEN=... ./scripts/publish-images.sh --push --tag v0.1.0
```

### Host-native build only

Faster for local testing; no manifest list:

```bash
./scripts/publish-images.sh --single-arch
```

### Custom platforms

```bash
OPENFLAKE_PLATFORMS=linux/arm64 ./scripts/publish-images.sh --single-arch
# or multiple:
./scripts/publish-images.sh --platforms linux/amd64,linux/arm64 --push --tag v0.1.0
```

### Custom registry

```bash
OPENFLAKE_REGISTRY=quay.io/myorg ./scripts/publish-images.sh --push --tag v0.1.0
```

## Options

| Option | Description |
|--------|-------------|
| `--push` | Log in to Quay and push images after build |
| `--tag TAG` | Image tag (default: `latest`) |
| `--registry REGISTRY` | Registry prefix (default: `quay.io/zleblanc`) |
| `--platforms LIST` | Comma-separated platforms (default: `linux/amd64,linux/arm64`) |
| `--single-arch` | Build for host CPU only |
| `-h`, `--help` | Show help |

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENFLAKE_REGISTRY` | `quay.io/zleblanc` | Registry prefix |
| `OPENFLAKE_IMAGE_TAG` | `latest` | Image tag |
| `OPENFLAKE_PLATFORMS` | `linux/amd64,linux/arm64` | Target platforms |
| `QUAY_USERNAME` | — | Required with `--push` |
| `QUAY_TOKEN` | — | Required with `--push` |

## Images produced

| Image | Containerfile |
|-------|---------------|
| `<registry>/openflake-backend:<tag>` | `deploy/Containerfile.backend` |
| `<registry>/openflake-frontend:<tag>` | `deploy/Containerfile.frontend` |

Multi-arch builds create per-arch images (`<tag>-amd64`, `<tag>-arm64`) and assemble a manifest pushed as `<tag>`.

## CI alternative

Tagged releases are also published by GitHub Actions (`.github/workflows/publish-images.yml`) on `v*` tags. That workflow uses Docker Buildx with QEMU and does not require this script.

```bash
git tag v0.1.0 && git push origin v0.1.0
```

Stable tags (`vMAJOR.MINOR.PATCH`) also update the `latest` image tag on Quay. Pre-release tags (`-rc`, `-beta`, `-dev`) do not. See [docs/release-tagging.md](../../docs/release-tagging.md) for the full strategy.

## Related

- [Release and image tagging](../../docs/release-tagging.md) — production vs development tags
- [README — Publishing images](../../README.md#publishing-images-maintainers)
- [podman-install.sh](podman-install.md) — consumes published images
