from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from pathlib import Path

from ankiistudio.models import FlashcardData, ProjectData
from ankiistudio.services.audio_service import ProjectAudioService


SUPPORTED_AUDIO_EXTENSIONS = {
    ".mp3",
    ".wav",
    ".ogg",
    ".m4a",
    ".aac",
    ".flac",
    ".opus",
    ".mp4",
    ".webm",
}

MATCH_FIELDS: dict[str, str] = {
    "word": "Conteúdo principal",
    "reading": "Leitura",
    "romanization": "Romaji / Romanização",
    "translation": "Tradução",
}


def normalize_match_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "")
    return " ".join(normalized.split()).casefold()


@dataclass(slots=True)
class AudioImportMatch:
    source_path: Path
    source_name: str
    card_id: int | None
    card_word: str
    match_value: str
    status: str
    existing_audio: bool = False

    @property
    def matched(self) -> bool:
        return self.status == "matched" and self.card_id is not None


@dataclass(slots=True)
class AudioImportSummary:
    imported: int = 0
    skipped_existing: int = 0
    unmatched: int = 0
    ambiguous: int = 0
    unsupported: int = 0
    errors: int = 0


class AudioImportService:
    def __init__(self, project_audio_service: ProjectAudioService) -> None:
        self.project_audio_service = project_audio_service

    @staticmethod
    def supported_files_in_folder(folder: Path) -> list[Path]:
        folder = Path(folder)
        if not folder.is_dir():
            return []
        return sorted(
            [
                item
                for item in folder.iterdir()
                if item.is_file() and item.suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS
            ],
            key=lambda item: item.name.casefold(),
        )

    @staticmethod
    def _field_value(card: FlashcardData, field: str) -> str:
        if field not in MATCH_FIELDS:
            raise ValueError("Campo de correspondência inválido.")
        return str(getattr(card, field, "") or "")

    def preview(
        self,
        project: ProjectData,
        cards: list[FlashcardData],
        files: list[Path],
        field: str = "word",
    ) -> list[AudioImportMatch]:
        if field not in MATCH_FIELDS:
            raise ValueError("Campo de correspondência inválido.")

        index: dict[str, list[FlashcardData]] = {}
        for card in cards:
            if card.id is None or not project.card_uses_component(card, "audio"):
                continue
            raw = self._field_value(card, field)
            normalized = normalize_match_text(raw)
            if normalized:
                index.setdefault(normalized, []).append(card)

        results: list[AudioImportMatch] = []
        for raw_path in files:
            source = Path(raw_path)
            if source.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
                results.append(
                    AudioImportMatch(
                        source_path=source,
                        source_name=source.name,
                        card_id=None,
                        card_word="",
                        match_value=source.stem,
                        status="unsupported",
                    )
                )
                continue

            normalized_stem = normalize_match_text(source.stem)
            matches = index.get(normalized_stem, [])
            if not matches:
                results.append(
                    AudioImportMatch(
                        source_path=source,
                        source_name=source.name,
                        card_id=None,
                        card_word="",
                        match_value=source.stem,
                        status="unmatched",
                    )
                )
                continue
            if len(matches) > 1:
                results.append(
                    AudioImportMatch(
                        source_path=source,
                        source_name=source.name,
                        card_id=None,
                        card_word=" / ".join(card.word for card in matches[:3]),
                        match_value=source.stem,
                        status="ambiguous",
                    )
                )
                continue

            card = matches[0]
            results.append(
                AudioImportMatch(
                    source_path=source,
                    source_name=source.name,
                    card_id=card.id,
                    card_word=card.word,
                    match_value=self._field_value(card, field),
                    status="matched",
                    existing_audio=self.project_audio_service._valid_file(card.audio_path),
                )
            )

        target_counts: dict[int, int] = {}
        for result in results:
            if result.matched and result.card_id is not None:
                target_counts[result.card_id] = target_counts.get(result.card_id, 0) + 1
        for result in results:
            if result.card_id is not None and target_counts.get(result.card_id, 0) > 1:
                result.status = "ambiguous"
                result.card_id = None
        return results

    def apply(
        self,
        project: ProjectData,
        matches: list[AudioImportMatch],
        *,
        conflict_policy: str = "skip",
    ) -> AudioImportSummary:
        if conflict_policy not in {"skip", "replace"}:
            raise ValueError("Política de conflito inválida.")

        summary = AudioImportSummary()
        for match in matches:
            if match.status == "unmatched":
                summary.unmatched += 1
                continue
            if match.status == "ambiguous":
                summary.ambiguous += 1
                continue
            if match.status == "unsupported":
                summary.unsupported += 1
                continue
            if not match.matched:
                continue
            if match.existing_audio and conflict_policy == "skip":
                summary.skipped_existing += 1
                continue

            card = self.project_audio_service.database.get_card(int(match.card_id))
            if card is None:
                summary.errors += 1
                continue
            try:
                self.project_audio_service.import_audio_file(project, card, match.source_path)
            except Exception:
                summary.errors += 1
            else:
                summary.imported += 1
        return summary
