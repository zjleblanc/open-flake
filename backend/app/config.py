from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://openflake:openflake@localhost:5432/openflake"
    secret_key: str = "change-me-in-production"
    attachments_path: str = "/data/attachments"
    cors_origins: str = "http://localhost:8080,http://localhost:5173"
    admin_username: str = "admin"
    admin_password: str = "admin"
    base_url: str = "http://localhost:8000"
    access_token_expire_minutes: int = 60
    oauth_token_expire_seconds: int = 3600
    log_level: str = "INFO"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
