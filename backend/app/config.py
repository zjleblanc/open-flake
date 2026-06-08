from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LAB_ENV_FILE = BACKEND_ROOT / "local.env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://openflake:openflake@localhost:5432/openflake"
    secret_key: str = "change-me-in-production"
    attachments_path: str = "/data/attachments"
    cors_origins: str = "http://localhost:8080,http://localhost:5173"
    admin_username: str = "admin"
    admin_password: str = "admin"
    base_url: str = "http://localhost:8000"
    trusted_proxies: str = "*"
    access_token_expire_minutes: int = 60
    oauth_token_expire_seconds: int = 3600
    log_level: str = "INFO"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def trusted_proxy_list(self) -> list[str] | str:
        hosts = [p.strip() for p in self.trusted_proxies.split(",") if p.strip()]
        if len(hosts) == 1 and hosts[0] == "*":
            return "*"
        return hosts


def resolve_env_file(env_file: str | Path) -> Path:
    path = Path(env_file)
    if path.is_absolute():
        return path.resolve()
    cwd_candidate = path.resolve()
    if cwd_candidate.is_file():
        return cwd_candidate
    return (BACKEND_ROOT / path).resolve()


def settings_from_env_file(env_file: str | Path) -> Settings:
    path = resolve_env_file(env_file)
    if not path.is_file():
        raise FileNotFoundError(f"Env file not found: {path}")
    return Settings(_env_file=str(path), _env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
