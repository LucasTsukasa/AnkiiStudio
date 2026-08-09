from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel


class PermanentAudioProviderError(RuntimeError):
    """Falha que não deve ser repetida para todos os cartões do mesmo lote."""


class TemporaryAudioProviderError(RuntimeError):
    """Falha temporária que pode ser tentada novamente em outro momento."""


class AudioGenerationResult(BaseModel):
    provider: str
    local_path: str
    source_title: str = ""
    source_url: str = ""
    author: str = ""
    license_name: str = ""
    license_url: str = ""
    metadata_json: str = "{}"

    @property
    def path(self) -> Path:
        return Path(self.local_path)


class AudioProvider(ABC):
    key: str

    @abstractmethod
    def is_available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def generate(self, text: str, destination_stem: Path) -> AudioGenerationResult | None:
        raise NotImplementedError
