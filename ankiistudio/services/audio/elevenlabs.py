from __future__ import annotations

import hashlib
import json
from pathlib import Path

import httpx

from ankiistudio.services.audio.base import (
    AudioGenerationResult,
    AudioProvider,
    PermanentAudioProviderError,
    TemporaryAudioProviderError,
)


class ElevenLabsProvider(AudioProvider):
    key = "elevenlabs"

    def __init__(
        self,
        api_key: str,
        voice_id: str,
        model_id: str,
        *,
        language: str = "ja",
        stability: float = 0.5,
        similarity_boost: float = 0.75,
        style: float = 0.0,
        speed: float = 1.0,
        speaker_boost: bool = True,
    ) -> None:
        self.api_key = api_key.strip()
        self.voice_id = voice_id.strip()
        self.model_id = model_id.strip()
        self.language = language.strip().casefold()
        self.stability = float(stability)
        self.similarity_boost = float(similarity_boost)
        self.style = float(style)
        self.speed = float(speed)
        self.speaker_boost = bool(speaker_boost)

    def is_available(self) -> bool:
        return bool(self.api_key and self.voice_id and self.model_id)

    @staticmethod
    def _error_detail(response: httpx.Response) -> tuple[str, str]:
        status = ""
        message = ""
        try:
            payload = response.json()
        except Exception:
            payload = None
        detail = payload.get("detail") if isinstance(payload, dict) else payload
        if isinstance(detail, dict):
            status = str(detail.get("status") or detail.get("code") or "")
            message = str(detail.get("message") or detail.get("detail") or "")
        elif isinstance(detail, str):
            message = detail
            # Algumas respostas encapsulam JSON dentro de detail.
            try:
                nested = json.loads(detail)
                if isinstance(nested, dict):
                    status = str(nested.get("status") or nested.get("code") or "")
                    message = str(nested.get("message") or nested.get("detail") or detail)
            except Exception:
                pass
        elif isinstance(payload, dict):
            status = str(payload.get("status") or payload.get("code") or "")
            message = str(payload.get("message") or "")
        if not message:
            message = response.text.strip()[:500]
        return status.strip(), message.strip()

    @classmethod
    def _http_error(cls, response: httpx.Response) -> RuntimeError:
        code = response.status_code
        status, message = cls._error_detail(response)
        normalized = status.casefold()
        detail = message or status or f"HTTP {code}"

        if code == 429 or normalized in {"quota_exceeded", "too_many_requests"}:
            return TemporaryAudioProviderError(f"Limite da ElevenLabs atingido: {detail}")
        if code in (401, 403) or normalized == "invalid_api_key":
            return PermanentAudioProviderError(
                f"ElevenLabs recusou a credencial/permissão: {detail}"
            )
        if code == 404 or normalized == "voice_not_found":
            return PermanentAudioProviderError(
                f"Voz ElevenLabs não encontrada ou não disponível para esta conta: {detail}"
            )
        if code in (400, 422):
            return PermanentAudioProviderError(
                f"ElevenLabs recusou a configuração da voz ({code}): {detail}"
            )
        if 500 <= code < 600:
            return TemporaryAudioProviderError(f"ElevenLabs indisponível (HTTP {code}): {detail}")
        return PermanentAudioProviderError(f"ElevenLabs respondeu com erro HTTP {code}: {detail}")

    def validate_voice(self, timeout: float = 20.0) -> dict[str, object]:
        if not self.is_available():
            raise PermanentAudioProviderError(
                "Configure a API key, o modelo e o Voice ID da ElevenLabs."
            )
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.get(
                    f"https://api.elevenlabs.io/v1/voices/{self.voice_id}",
                    headers={"xi-api-key": self.api_key},
                )
        except httpx.ConnectError as exc:
            raise TemporaryAudioProviderError("Não foi possível conectar à ElevenLabs.") from exc
        except httpx.TimeoutException as exc:
            raise TemporaryAudioProviderError("A ElevenLabs demorou demais para responder.") from exc
        except httpx.HTTPError as exc:
            raise TemporaryAudioProviderError("Falha de comunicação com a ElevenLabs.") from exc
        if response.is_error:
            raise self._http_error(response)
        try:
            payload = response.json()
        except Exception:
            payload = {}
        return payload if isinstance(payload, dict) else {}

    def generate(self, text: str, destination_stem: Path) -> AudioGenerationResult | None:
        if not text.strip():
            return None
        if not self.is_available():
            raise PermanentAudioProviderError(
                "Configure a API key, o modelo e o Voice ID da ElevenLabs."
            )
        digest = hashlib.sha256(
            (
                f"elevenlabs:{self.voice_id}:{self.model_id}:{self.language}:"
                f"{self.stability}:{self.similarity_boost}:{self.style}:{self.speed}:"
                f"{self.speaker_boost}:{text}"
            ).encode("utf-8")
        ).hexdigest()[:16]
        destination = destination_stem.parent / f"{destination_stem.name}_{digest}.mp3"
        if destination.exists() and destination.stat().st_size > 0:
            return AudioGenerationResult(
                provider=self.key,
                local_path=str(destination),
                source_title=f"ElevenLabs {self.voice_id} / {self.model_id}",
            )

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
        params = {"output_format": "mp3_44100_128"}
        payload: dict[str, object] = {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": self.stability,
                "similarity_boost": self.similarity_boost,
                "style": self.style,
                "use_speaker_boost": self.speaker_boost,
                "speed": self.speed,
            },
        }
        # multilingual_v2 não aceita language_code. Forçar a normalização específica
        # sem um language_code válido faz a API responder 400 (language code 'None').
        # Nesses modelos deixamos a normalização geral em modo automático.
        multilingual_v2 = self.model_id.casefold() in {
            "eleven_multilingual_v2",
            "eleven_multilingual_v1",
        }
        if multilingual_v2:
            payload["apply_text_normalization"] = "auto"
        elif len(self.language) == 2 and self.language.isalpha():
            payload["language_code"] = self.language
            payload["apply_text_normalization"] = "auto"
            if self.language == "ja":
                payload["apply_language_text_normalization"] = True
        headers = {"xi-api-key": self.api_key, "Content-Type": "application/json"}
        try:
            with httpx.Client(timeout=120) as client:
                response = client.post(url, params=params, json=payload, headers=headers)
        except httpx.ConnectError as exc:
            raise TemporaryAudioProviderError("Não foi possível conectar à ElevenLabs.") from exc
        except httpx.TimeoutException as exc:
            raise TemporaryAudioProviderError("A ElevenLabs demorou demais para responder.") from exc
        except httpx.HTTPError as exc:
            raise TemporaryAudioProviderError("Falha de comunicação com a ElevenLabs.") from exc
        if response.is_error:
            raise self._http_error(response)

        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(response.content)
        if not destination.is_file() or destination.stat().st_size <= 0:
            raise TemporaryAudioProviderError("ElevenLabs retornou um arquivo de áudio vazio.")
        return AudioGenerationResult(
            provider=self.key,
            local_path=str(destination),
            source_title=f"ElevenLabs {self.voice_id} / {self.model_id}",
        )
