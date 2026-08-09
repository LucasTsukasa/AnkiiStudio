from __future__ import annotations

import sys
from pathlib import Path

import keyring

from ankiistudio.constants import APP_NAME


def application_root() -> Path:
    """Pasta física da versão portátil.

    Em um build PyInstaller, usa a pasta do executável. Em execução pelo código-fonte,
    usa a raiz do projeto que contém o pacote ``ankiistudio``.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


class AppPaths:
    """Caminhos persistentes do modo portátil.

    Todos os dados não sensíveis ficam em ``<AnkiiStudio>/data``. Credenciais nunca
    são gravadas nessa pasta: permanecem no gerenciador seguro do sistema.
    """

    def __init__(self, root_dir: Path | None = None) -> None:
        self.app_dir = (root_dir or application_root()).resolve()
        self.base_dir = self.app_dir / "data"
        self.database_dir = self.base_dir / "database"
        self.database_path = self.database_dir / "ankiistudio.db"
        self.media_dir = self.base_dir / "media"
        self.images_dir = self.media_dir / "images"
        self.audio_dir = self.media_dir / "audio"
        self.exports_dir = self.base_dir / "exports"
        self.cache_dir = self.base_dir / "cache"
        self.logs_dir = self.base_dir / "logs"
        downloads = Path.home() / "Downloads"
        self.downloads_dir = downloads if downloads.exists() else Path.home()

    def ensure(self) -> None:
        for directory in (
            self.base_dir,
            self.database_dir,
            self.media_dir,
            self.images_dir,
            self.audio_dir,
            self.exports_dir,
            self.cache_dir,
            self.logs_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)


class SecretStore:
    SERVICE_NAME = APP_NAME

    @classmethod
    def get(cls, key: str) -> str:
        try:
            return keyring.get_password(cls.SERVICE_NAME, key) or ""
        except keyring.errors.KeyringError:
            return ""

    @classmethod
    def set(cls, key: str, value: str) -> None:
        try:
            if value:
                keyring.set_password(cls.SERVICE_NAME, key, value)
            else:
                try:
                    keyring.delete_password(cls.SERVICE_NAME, key)
                except keyring.errors.PasswordDeleteError:
                    pass
        except keyring.errors.KeyringError as exc:
            raise RuntimeError(
                "Não foi possível salvar a credencial no gerenciador seguro do sistema."
            ) from exc
