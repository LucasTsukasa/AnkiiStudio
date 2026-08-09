from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

from ankiistudio.services.audio.base import AudioGenerationResult, AudioProvider
from ankiistudio.services.wikimedia_service import WikimediaService


class WikimediaAudioProvider(AudioProvider):
    key = "wikimedia"

    def __init__(self, service: WikimediaService, language_label: str = "Japanese") -> None:
        self.service = service
        self.language_label = language_label.strip() or "Japanese"

    def is_available(self) -> bool:
        return True

    def generate(self, text: str, destination_stem: Path) -> AudioGenerationResult | None:
        if not text.strip():
            return None
        search_terms = [
            f'"{text}" {self.language_label} pronunciation',
            f'{self.language_label} pronunciation {text}',
            text,
        ]
        results = []
        for term in search_terms:
            results = self.service.search(term, kind="audio", limit=5)
            if results:
                break
        if not results:
            return None

        selected = results[0]
        raw, content_type = self.service.download(selected.file_url)
        suffix = Path(urlparse(selected.file_url).path).suffix.lower() or ".ogg"
        digest = hashlib.sha256(raw).hexdigest()[:16]
        destination = destination_stem.parent / f"{destination_stem.name}_{digest}{suffix}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            destination.write_bytes(raw)
        metadata = selected.model_dump()
        metadata["content_type"] = content_type
        return AudioGenerationResult(
            provider=self.key,
            local_path=str(destination),
            source_title=selected.title,
            source_url=selected.description_url,
            author=selected.author,
            license_name=selected.license_name,
            license_url=selected.license_url,
            metadata_json=json.dumps(metadata, ensure_ascii=False),
        )
