from __future__ import annotations

import hashlib
import json
import unicodedata
from pathlib import Path

import httpx

from ankiistudio.constants import APP_USER_AGENT
from ankiistudio.services.audio.base import AudioGenerationResult, AudioProvider
from ankiistudio.services.tatoeba_language_codes import tatoeba_language_code


_API_BASE = "https://api.tatoeba.org"
_TATOEBA_SENTENCE_URL = "https://tatoeba.org/en/sentences/show/{sentence_id}"
_LICENSE_URLS = {
    "CC0 1.0": "https://creativecommons.org/publicdomain/zero/1.0/",
    "CC BY 2.0 FR": "https://creativecommons.org/licenses/by/2.0/fr/",
    "CC BY 3.0": "https://creativecommons.org/licenses/by/3.0/",
    "CC BY 4.0": "https://creativecommons.org/licenses/by/4.0/",
    "CC BY-NC 3.0": "https://creativecommons.org/licenses/by-nc/3.0/",
    "CC BY-NC 4.0": "https://creativecommons.org/licenses/by-nc/4.0/",
}


def _normalize_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value or "").split()).casefold()


class TatoebaAudioProvider(AudioProvider):
    key = "tatoeba"

    def __init__(
        self,
        language: str,
        *,
        client: httpx.Client | None = None,
        timeout: float = 20.0,
    ) -> None:
        self.language = language
        self.tatoeba_language = tatoeba_language_code(language)
        self._external_client = client
        self.timeout = timeout

    def is_available(self) -> bool:
        return bool(self.tatoeba_language)

    def _client(self) -> tuple[httpx.Client, bool]:
        if self._external_client is not None:
            return self._external_client, False
        return (
            httpx.Client(
                timeout=self.timeout,
                follow_redirects=True,
                headers={"User-Agent": APP_USER_AGENT},
            ),
            True,
        )

    @staticmethod
    def _search_params(text: str, language: str) -> dict[str, str | int]:
        return {
            "lang": language,
            "q": text,
            "has_audio": "yes",
            "is_unapproved": "no",
            "include": "audios",
            "showtrans": "none",
            "sort": "relevance",
            "limit": 20,
        }

    @staticmethod
    def _suffix(response: httpx.Response) -> str:
        content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        return {
            "audio/mpeg": ".mp3",
            "audio/mp3": ".mp3",
            "audio/ogg": ".ogg",
            "audio/wav": ".wav",
            "audio/x-wav": ".wav",
            "audio/mp4": ".m4a",
            "audio/aac": ".aac",
            "audio/flac": ".flac",
        }.get(content_type, ".mp3")

    def _download_audio(
        self,
        client: httpx.Client,
        audio: dict[str, object],
        destination_stem: Path,
        sentence: dict[str, object],
    ) -> AudioGenerationResult | None:
        audio_id = audio.get("id")
        if audio_id is None:
            return None
        response = client.get(f"{_API_BASE}/v1/audios/{int(audio_id)}/file")
        if response.status_code == 403:
            # O autor não permite reutilização fora do Tatoeba.
            return None
        if response.status_code == 404:
            return None
        response.raise_for_status()
        raw = response.content
        if not raw:
            return None

        digest = hashlib.sha256(raw).hexdigest()[:16]
        suffix = self._suffix(response)
        destination = destination_stem.parent / f"{destination_stem.name}_{digest}{suffix}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            destination.write_bytes(raw)

        sentence_id = int(sentence.get("id") or 0)
        author = str(audio.get("author") or "")
        license_name = str(audio.get("licence") or "")
        attribution_url = str(audio.get("attribution_url") or "")
        source_url = _TATOEBA_SENTENCE_URL.format(sentence_id=sentence_id) if sentence_id else "https://tatoeba.org/"
        metadata = {
            "sentence_id": sentence_id,
            "sentence_text": str(sentence.get("text") or ""),
            "audio_id": int(audio_id),
            "author": author,
            "licence": license_name,
            "attribution_url": attribution_url,
            "download_url": str(audio.get("download_url") or ""),
            "created": audio.get("created"),
            "modified": audio.get("modified"),
            "tatoeba_language": self.tatoeba_language,
        }
        return AudioGenerationResult(
            provider=self.key,
            local_path=str(destination),
            source_title=f"Tatoeba · sentença {sentence_id}" if sentence_id else "Tatoeba",
            source_url=source_url,
            author=author,
            license_name=license_name,
            license_url=_LICENSE_URLS.get(license_name, attribution_url),
            metadata_json=json.dumps(metadata, ensure_ascii=False),
        )

    def generate(self, text: str, destination_stem: Path) -> AudioGenerationResult | None:
        query = text.strip()
        if not query or not self.is_available():
            return None

        client, owns_client = self._client()
        try:
            response = client.get(
                f"{_API_BASE}/v1/sentences",
                params=self._search_params(query, self.tatoeba_language),
            )
            if response.status_code == 400:
                escaped = query.replace('"', r'\"')
                params = self._search_params(f'"{escaped}"', self.tatoeba_language)
                response = client.get(f"{_API_BASE}/v1/sentences", params=params)
            response.raise_for_status()
            payload = response.json()
            target = _normalize_text(query)
            for sentence in payload.get("data", []):
                if not isinstance(sentence, dict):
                    continue
                if _normalize_text(str(sentence.get("text") or "")) != target:
                    continue
                audios = sentence.get("audios") or []
                if not isinstance(audios, list):
                    continue
                for audio in audios:
                    if not isinstance(audio, dict):
                        continue
                    result = self._download_audio(client, audio, destination_stem, sentence)
                    if result is not None:
                        return result
            return None
        finally:
            if owns_client:
                client.close()
