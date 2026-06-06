# shellcheck shell=sh
# Sourced by container entrypoints when mounted TLS files exist but are not readable.

ssl_print_unreadable_hint() {
  ssl_dir="$1"
  cert_name="$2"
  key_name="$3"
  cert_path="${ssl_dir}/${cert_name}"
  key_path="${ssl_dir}/${key_name}"

  echo "TLS certificate files are not readable inside the container." >&2
  ls -la "${cert_path}" "${key_path}" 2>&1 >&2 || ls -la "${ssl_dir}" 2>&1 >&2 || true
  echo "Rootless Podman checks bind-mount permissions as your host user, not container root." >&2
  echo "Files owned root:root mode 600 (typical after copying from Let's Encrypt) stay unreadable" >&2
  echo "even when the directory has SELinux context container_file_t." >&2
  echo "Fix on the host using OPENFLAKE_SSL_DIR from .env:" >&2
  echo "  sudo chmod 644 <OPENFLAKE_SSL_DIR>/${cert_name} <OPENFLAKE_SSL_DIR>/${key_name}" >&2
  echo "If SELinux is enforcing and chmod alone is not enough:" >&2
  echo "  sudo chcon -R -t container_file_t <OPENFLAKE_SSL_DIR>" >&2
}
