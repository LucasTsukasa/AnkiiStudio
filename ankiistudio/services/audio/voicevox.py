from __future__ import annotations

import hashlib
from contextlib import contextmanager
from collections.abc import Iterator
from pathlib import Path

import httpx

from ankiistudio.services.audio.base import AudioGenerationResult, AudioProvider


class VoicevoxProvider(AudioProvider):
    key = "voicevox"

    def __init__(
        self,
        base_url: str,
        speaker_id: int = 0,
        *,
        speed_scale: float = 1.0,
        pitch_scale: float = 0.0,
        intonation_scale: float = 1.0,
        volume_scale: float = 1.0,
        pause_length_scale: float = 1.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = self.normalize_base_url(base_url)
        self.speaker_id = int(speaker_id)
        self.speed_scale = float(speed_scale)
        self.pitch_scale = float(pitch_scale)
        self.intonation_scale = float(intonation_scale)
        self.volume_scale = float(volume_scale)
        self.pause_length_scale = float(pause_length_scale)
        self._external_client = client
        self._availability: bool | None = None

    @contextmanager
    def _client(self, timeout: float) -> Iterator[httpx.Client]:
        if self._external_client is not None:
            yield self._external_client
            return
        with httpx.Client(timeout=timeout) as client:
            yield client

    @staticmethod
    def normalize_base_url(base_url: str) -> str:
        normalized = base_url.strip().rstrip("/")
        if not normalized:
            raise ValueError("Informe a URL local do VOICEVOX.")
        if not normalized.startswith(("http://", "https://")):
            normalized = f"http://{normalized}"
        return normalized

    @classmethod
    def get_version(cls, base_url: str, timeout: float = 5.0) -> str:
        url = cls.normalize_base_url(base_url)
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.get(f"{url}/version")
                response.raise_for_status()
        except httpx.ConnectError as exc:
            raise RuntimeError(
                "Não foi possível encontrar o VOICEVOX. Abra o aplicativo/engine e confirme a URL local configurada."
            ) from exc
        except httpx.TimeoutException as exc:
            raise RuntimeError("O VOICEVOX não respondeu dentro do tempo limite.") from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"O VOICEVOX respondeu com erro HTTP {exc.response.status_code}."
            ) from exc
        except httpx.HTTPError as exc:
            raise RuntimeError("Não foi possível comunicar com o VOICEVOX.") from exc
        version = response.text.strip().strip('"')
        return version or "desconhecida"

    @classmethod
    def list_speaker_styles(cls, base_url: str, timeout: float = 8.0) -> list[dict[str, object]]:
        url = cls.normalize_base_url(base_url)
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.get(f"{url}/speakers")
                response.raise_for_status()
                payload = response.json()
        except httpx.ConnectError as exc:
            raise RuntimeError("Não foi possível encontrar o VOICEVOX. Abra o aplicativo/engine e tente novamente.") from exc
        except httpx.TimeoutException as exc:
            raise RuntimeError("O VOICEVOX não respondeu dentro do tempo limite.") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError("Não foi possível carregar as vozes do VOICEVOX.") from exc

        result: list[dict[str, object]] = []
        for speaker in payload if isinstance(payload, list) else []:
            speaker_name = str(speaker.get("name", "VOICEVOX")).strip() or "VOICEVOX"
            speaker_uuid = str(speaker.get("speaker_uuid", ""))
            for style in speaker.get("styles", []) or []:
                try:
                    style_id = int(style.get("id"))
                except (TypeError, ValueError):
                    continue
                style_name = str(style.get("name", "Normal")).strip() or "Normal"
                result.append(
                    {
                        "id": style_id,
                        "speaker": speaker_name,
                        "style": style_name,
                        "label": f"{speaker_name} — {style_name}",
                        "speaker_uuid": speaker_uuid,
                    }
                )
        result.sort(key=lambda item: (str(item["speaker"]).casefold(), str(item["style"]).casefold()))
        return result

    def is_available(self) -> bool:
        if self._availability is not None:
            return self._availability
        try:
            if self._external_client is not None:
                response = self._external_client.get(f"{self.base_url}/version")
                response.raise_for_status()
            else:
                self.get_version(self.base_url, timeout=3)
        except (httpx.HTTPError, RuntimeError, ValueError):
            self._availability = False
        else:
            self._availability = True
        return self._availability

    def generate(self, text: str, destination_stem: Path) -> AudioGenerationResult | None:
        if not text.strip():
            return None
        digest = hashlib.sha256(
            (
                f"voicevox:{self.speaker_id}:{self.speed_scale}:{self.pitch_scale}:"
                f"{self.intonation_scale}:{self.volume_scale}:{self.pause_length_scale}:{text}"
            ).encode("utf-8")
        ).hexdigest()[:16]
        destination = destination_stem.parent / f"{destination_stem.name}_{digest}.wav"
        if destination.exists() and destination.stat().st_size > 0:
            return AudioGenerationResult(provider=self.key, local_path=str(destination))

        try:
            with self._client(90) as client:
                query_response = client.post(
                    f"{self.base_url}/audio_query",
                    params={"text": text, "speaker": self.speaker_id},
                )
                query_response.raise_for_status()
                query = query_response.json()
                # Ajustes definidos no AnkiiStudio são aplicados sobre o AudioQuery do engine.
                query["speedScale"] = self.speed_scale
                query["pitchScale"] = self.pitch_scale
                query["intonationScale"] = self.intonation_scale
                query["volumeScale"] = self.volume_scale
                query["pauseLengthScale"] = self.pause_length_scale
                synthesis_response = client.post(
                    f"{self.base_url}/synthesis",
                    params={"speaker": self.speaker_id},
                    json=query,
                )
                synthesis_response.raise_for_status()
        except httpx.ConnectError as exc:
            raise RuntimeError("VOICEVOX não está acessível. Abra o aplicativo/engine e tente novamente.") from exc
        except httpx.TimeoutException as exc:
            raise RuntimeError("O VOICEVOX demorou demais para responder.") from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"VOICEVOX não conseguiu gerar o áudio (HTTP {exc.response.status_code}). Confira a voz/estilo selecionado."
            ) from exc
        except httpx.HTTPError as exc:
            raise RuntimeError("Falha de comunicação com o VOICEVOX.") from exc

        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(synthesis_response.content)
        if not destination.is_file() or destination.stat().st_size <= 0:
            raise RuntimeError("VOICEVOX retornou um arquivo de áudio vazio.")
        return AudioGenerationResult(
            provider=self.key,
            local_path=str(destination),
            source_title=f"VOICEVOX style {self.speaker_id}",
            license_name="Consulte os termos da voz selecionada no VOICEVOX",
        )
