from app import db
from app.config import BACKEND_ROOT, resolve_env_file, settings_from_env_file


def test_resolve_env_file_prefers_cwd_relative_path(tmp_path, monkeypatch):
    env_file = tmp_path / "custom.env"
    env_file.write_text("DATABASE_URL=postgresql+asyncpg://example/test\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    assert resolve_env_file("custom.env") == env_file.resolve()


def test_resolve_env_file_falls_back_to_backend_root(tmp_path, monkeypatch):
    env_file = BACKEND_ROOT / "openflake.env"
    if not env_file.is_file():
        env_file.write_text("DATABASE_URL=postgresql+asyncpg://example/test\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    assert resolve_env_file("openflake.env") == env_file.resolve()


def test_resolve_env_file_accepts_backend_prefixed_path_from_repo_root(monkeypatch):
    monkeypatch.chdir(BACKEND_ROOT.parent)
    assert resolve_env_file("backend/openflake.env") == (BACKEND_ROOT / "openflake.env").resolve()


def test_settings_from_env_file_loads_database_url(tmp_path):
    env_file = tmp_path / "seed.env"
    env_file.write_text(
        "DATABASE_URL=postgresql+asyncpg://remote-host:5432/openflake\n",
        encoding="utf-8",
    )

    settings = settings_from_env_file(env_file)
    assert settings.database_url == "postgresql+asyncpg://remote-host:5432/openflake"


def test_configure_database_updates_module_engine():
    original_engine = db.engine
    db.configure_database("postgresql+asyncpg://other-host:5432/openflake")
    try:
        assert db.engine is not original_engine
        assert "other-host" in str(db.engine.url)
    finally:
        # `str(url)` masks the password as a literal "***"; render it
        # unmasked so the restored engine keeps working real credentials
        # for tests that run after this one in the same session.
        db.configure_database(original_engine.url.render_as_string(hide_password=False))
