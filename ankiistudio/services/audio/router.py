from __future__ import annotations

import random
from pathlib import Path

from ankiistudio.models import ProjectData
from ankiistudio.services.audio.base import AudioGenerationResult, AudioProvider


class AudioRouter:
    PRIORITY = ["tatoeba", "wikimedia", "voicevox", "gemini", "elevenlabs"]

    def __init__(self, providers: dict[str, AudioProvider]) -> None:
        self.providers = providers

    def generate(
        self,
        *,
        text: str,
        destination_stem: Path,
        project: ProjectData,
        content_kind: str = "content",
    ) -> AudioGenerationResult:
        del content_kind
        enabled = [key for key in project.audio_providers if key in self.providers]
        if project.language != "ja":
            enabled = [key for key in enabled if key != "voicevox"]
        if not enabled:
            raise RuntimeError("Nenhum provedor de áudio está habilitado para o projeto.")

        if project.audio_mode == "fixed":
            order = [project.fixed_audio_provider]
        elif project.audio_mode == "random":
            order = list(enabled)
            random.SystemRandom().shuffle(order)
        else:
            order = [key for key in self.PRIORITY if key in enabled]

        errors: list[str] = []
        for key in order:
            provider = self.providers.get(key)
            if provider is None or not provider.is_available():
                errors.append(f"{key}: indisponível")
                continue
            try:
                result = provider.generate(text, destination_stem)
            except Exception as exc:
                errors.append(f"{key}: {exc}")
                continue
            if result is not None:
                path = Path(result.local_path)
                if not path.is_file() or path.stat().st_size <= 0:
                    errors.append(f"{key}: retornou um arquivo de áudio inexistente ou vazio")
                    continue
                return result
            errors.append(f"{key}: nenhum áudio encontrado")

        details = "; ".join(errors) if errors else "sem detalhes"
        raise RuntimeError(f"Nenhum provedor conseguiu gerar o áudio. {details}")
