from __future__ import annotations

import sys
from pathlib import Path

import keyring

from ankiistudio.constants import APP_NAME, DATABASE_FILENAME, LEGACY_APP_NAME


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

    Todos os dados não sensíveis ficam em ``<BenkyouStudio>/data``. Credenciais nunca
    são gravadas nessa pasta: permanecem no gerenciador seguro do sistema.
    """

    def __init__(self, root_dir: Path | None = None) -> None:
        self.app_dir = (root_dir or application_root()).resolve()
        self.base_dir = self.app_dir / "data"
        self.database_dir = self.base_dir / "database"
        self.database_path = self.database_dir / DATABASE_FILENAME
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
    """Credenciais do aplicativo com migração transparente do nome legado.

    A versão 0.11.0 renomeou o produto para BenkyouStudio. Credenciais já salvas
    sob o serviço ``AnkiiStudio`` continuam válidas e são copiadas para o novo
    serviço no primeiro acesso bem-sucedido.
    """

    SERVICE_NAME = APP_NAME
    LEGACY_SERVICE_NAMES = (LEGACY_APP_NAME,)

    @classmethod
    def get(cls, key: str) -> str:
        try:
            value = keyring.get_password(cls.SERVICE_NAME, key) or ""
            if value:
                return value

            for service_name in cls.LEGACY_SERVICE_NAMES:
                if service_name == cls.SERVICE_NAME:
                    continue
                legacy_value = keyring.get_password(service_name, key) or ""
                if not legacy_value:
                    continue
                try:
                    keyring.set_password(cls.SERVICE_NAME, key, legacy_value)
                except keyring.errors.KeyringError:
                    # A leitura da credencial antiga ainda é melhor do que tratá-la
                    # como ausente quando o backend não permite a migração.
                    pass
                return legacy_value
            return ""
        except keyring.errors.KeyringError:
            return ""

    @classmethod
    def set(cls, key: str, value: str) -> None:
        try:
            if value:
                keyring.set_password(cls.SERVICE_NAME, key, value)
                return

            # Ao limpar uma credencial, remova também a cópia legada para impedir
            # que o fallback a restaure na próxima leitura.
            for service_name in dict.fromkeys((cls.SERVICE_NAME, *cls.LEGACY_SERVICE_NAMES)):
                try:
                    keyring.delete_password(service_name, key)
                except keyring.errors.PasswordDeleteError:
                    pass
        except keyring.errors.KeyringError as exc:
            raise RuntimeError(
                "Não foi possível salvar a credencial no gerenciador seguro do sistema."
            ) from exc
