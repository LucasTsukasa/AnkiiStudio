from __future__ import annotations

import base64
import hashlib
import re
import wave
from pathlib import Path

from google import genai

from ankiistudio.constants import GEMINI_TTS_AUTO_MODELS
from ankiistudio.services.audio.base import AudioGenerationResult, AudioProvider
from ankiistudio.services.gemini_tts_usage import GeminiTTSUsageTracker


class GeminiTTSProvider(AudioProvider):
    key = "gemini"

    def __init__(
        self,
        api_key: str,
        model: str,
        voice: str,
        usage_tracker: GeminiTTSUsageTracker | None = None,
        language_label: str = "Japanese",
    ) -> None:
        self.api_key = api_key.strip()
        self.model = model.strip() or "auto"
        self.voice = voice.strip()
        self.usage_tracker = usage_tracker
        self.language_label = language_label.strip() or "Japanese"

    def is_available(self) -> bool:
        return bool(self.api_key and self.model and self.voice)

    @staticmethod
    def _write_wave(path: Path, pcm: bytes) -> None:
        with wave.open(str(path), "wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(24000)
            stream.writeframes(pcm)

    @staticmethod
    def _is_quota_error(exc: Exception) -> bool:
        text = str(exc).lower()
        return any(term in text for term in ("429", "resource_exhausted", "quota", "too_many_requests"))

    @staticmethod
    def _short_error(exc: Exception) -> str:
        text = str(exc).replace("\n", " ")
        text = re.sub(r"\s+", " ", text).strip()
        if GeminiTTSProvider._is_quota_error(exc):
            return "limite temporário atingido"
        return text[:180] or exc.__class__.__name__

    def _candidate_models(self) -> list[str]:
        if self.model != "auto":
            return [self.model]
        candidates = list(GEMINI_TTS_AUTO_MODELS)
        if self.usage_tracker:
            available = [model for model in candidates if not self.usage_tracker.is_temporarily_blocked(model)]
            return available or candidates
        return candidates

    def generate(self, text: str, destination_stem: Path) -> AudioGenerationResult | None:
        if not text.strip():
            return None
        if not self.is_available():
            raise RuntimeError("Configure a chave da Gemini API.")

        client = genai.Client(api_key=self.api_key)
        errors: list[str] = []
        candidates = self._candidate_models()
        if not candidates:
            raise RuntimeError("Nenhum modelo Gemini TTS está disponível no momento.")

        for model in candidates:
            digest = hashlib.sha256(
                f"gemini:{model}:{self.voice}:{text}".encode("utf-8")
            ).hexdigest()[:16]
            destination = destination_stem.parent / f"{destination_stem.name}_{digest}.wav"
            if destination.exists() and destination.stat().st_size > 0:
                return AudioGenerationResult(
                    provider=self.key,
                    local_path=str(destination),
                    source_title=f"Gemini TTS {model} / {self.voice}",
                    metadata_json=f'{{"model":"{model}","cached":true}}',
                )

            try:
                interaction = client.interactions.create(
                    model=model,
                    input=(
                        f"Sintetize somente a fala do texto em {self.language_label} abaixo, com pronúncia natural e clara. "
                        "Não leia estas instruções. Texto a ser falado: " + text
                    ),
                    response_format={"type": "audio"},
                    generation_config={"speech_config": [{"voice": self.voice}]},
                )
                if not interaction.output_audio or not interaction.output_audio.data:
                    raise RuntimeError("A Gemini TTS não retornou áudio.")
                raw = base64.b64decode(interaction.output_audio.data)
                destination.parent.mkdir(parents=True, exist_ok=True)
                self._write_wave(destination, raw)
                if self.usage_tracker:
                    self.usage_tracker.record_success(model)
                return AudioGenerationResult(
                    provider=self.key,
                    local_path=str(destination),
                    source_title=f"Gemini TTS {model} / {self.voice}",
                    metadata_json=f'{{"model":"{model}","cached":false}}',
                )
            except Exception as exc:
                if self.usage_tracker:
                    if self._is_quota_error(exc):
                        self.usage_tracker.record_quota_error(model, str(exc))
                    else:
                        self.usage_tracker.record_error(model, self._short_error(exc))
                errors.append(f"{model}: {self._short_error(exc)}")
                if self.model != "auto":
                    break

        if errors and all("limite temporário atingido" in item for item in errors):
            raise RuntimeError(
                "Limite temporário da Gemini atingido para os modelos selecionados. "
                "Os áudios já criados foram preservados; tente novamente quando a cota estiver disponível."
            )
        raise RuntimeError("Gemini TTS indisponível. " + "; ".join(errors))
