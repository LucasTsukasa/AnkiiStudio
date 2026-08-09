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
    app_dir = tmp_path / "AnkiiStudio"
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
    assert SecretStore.SERVICE_NAME == "AnkiiStudio"
