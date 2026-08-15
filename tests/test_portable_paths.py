from __future__ import annotations

import sys
import types
from pathlib import Path

if "keyring" not in sys.modules:
    keyring_stub = types.ModuleType("keyring")
    keyring_stub.errors = types.SimpleNamespace(
        KeyringError=RuntimeError,
        PasswordDeleteError=RuntimeError,
    )
    keyring_stub.get_password = lambda *args, **kwargs: None
    keyring_stub.set_password = lambda *args, **kwargs: None
    keyring_stub.delete_password = lambda *args, **kwargs: None
    sys.modules["keyring"] = keyring_stub

from ankiistudio.config import AppPaths, SecretStore


def test_portable_paths_live_beside_application(tmp_path: Path) -> None:
    app_dir = tmp_path / "BenkyouStudio"
    paths = AppPaths(app_dir)
    assert paths.app_dir == app_dir.resolve()
    assert paths.base_dir == app_dir.resolve() / "data"
    assert paths.database_path == app_dir.resolve() / "data" / "database" / "ankiistudio.db"
    assert paths.images_dir == app_dir.resolve() / "data" / "media" / "images"
    assert paths.audio_dir == app_dir.resolve() / "data" / "media" / "audio"
    assert paths.logs_dir == app_dir.resolve() / "data" / "logs"
    paths.ensure()
    assert paths.database_dir.is_dir()
    assert paths.media_dir.is_dir()
    assert paths.cache_dir.is_dir()


def test_portable_config_does_not_use_appdata_or_platformdirs() -> None:
    source = Path("ankiistudio/config.py").read_text(encoding="utf-8")
    assert "platformdirs" not in source
    assert "user_data_dir" not in source
    assert "AppData" not in source
    assert 'self.base_dir = self.app_dir / "data"' in source


def test_secret_store_uses_keyring_not_dotenv_or_environment() -> None:
    source = Path("ankiistudio/config.py").read_text(encoding="utf-8")
    assert "keyring.get_password" in source
    assert "os.getenv" not in source
    assert "dotenv" not in source.casefold()
    assert SecretStore.SERVICE_NAME == "BenkyouStudio"
    assert "AnkiiStudio" in SecretStore.LEGACY_SERVICE_NAMES


def test_secret_store_migrates_legacy_ankiistudio_credential(monkeypatch) -> None:
    import ankiistudio.config as config_module

    values = {("AnkiiStudio", "GEMINI_API_KEY"): "legacy-secret"}
    writes: list[tuple[str, str, str]] = []

    monkeypatch.setattr(
        config_module.keyring,
        "get_password",
        lambda service, key: values.get((service, key)),
    )

    def set_password(service: str, key: str, value: str) -> None:
        writes.append((service, key, value))
        values[(service, key)] = value

    monkeypatch.setattr(config_module.keyring, "set_password", set_password)

    assert SecretStore.get("GEMINI_API_KEY") == "legacy-secret"
    assert ("BenkyouStudio", "GEMINI_API_KEY", "legacy-secret") in writes
    assert values[("AnkiiStudio", "GEMINI_API_KEY")] == "legacy-secret"


def test_secret_store_clear_removes_current_and_legacy_names(monkeypatch) -> None:
    import ankiistudio.config as config_module

    deleted: list[tuple[str, str]] = []
    monkeypatch.setattr(
        config_module.keyring,
        "delete_password",
        lambda service, key: deleted.append((service, key)),
    )

    SecretStore.set("GEMINI_API_KEY", "")

    assert ("BenkyouStudio", "GEMINI_API_KEY") in deleted
    assert ("AnkiiStudio", "GEMINI_API_KEY") in deleted
