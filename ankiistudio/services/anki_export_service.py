from __future__ import annotations

import hashlib
from pathlib import Path

import genanki

from ankiistudio.constants import COMPONENT_LABELS
from ankiistudio.models import FlashcardData, ProjectData
from ankiistudio.services.card_template_service import build_card_css, render_components_template


_FIELD_ORDER = [
    "Word",
    "Reading",
    "Romanization",
    "Translation",
    "Example",
    "ExampleReading",
    "ExampleTranslation",
    "Explanation",
    "Mnemonic",
    "PartOfSpeech",
    "Level",
    "Tags",
    "Image",
    "WordAudio",
    "SentenceAudio",
]


_CARD_ATTRS = {
    "word": "word",
    "reading": "reading",
    "romanization": "romanization",
    "translation": "translation",
    "example": "example",
    "example_reading": "example_reading",
    "example_translation": "example_translation",
    "explanation": "explanation",
    "mnemonic": "mnemonic",
    "part_of_speech": "part_of_speech",
    "level": "level",
}


def _stable_id(prefix: str, value: str) -> int:
    digest = hashlib.sha256(f"{prefix}:{value}".encode("utf-8")).digest()
    raw = int.from_bytes(digest[:4], "big")
    return (1 << 30) + (raw % (1 << 30))

def _valid_file(path_text: str) -> bool:
    if not path_text:
        return False
    path = Path(path_text)
    return path.is_file() and path.stat().st_size > 0


def _component_has_value(component: str, card: FlashcardData) -> bool:
    if component == "image":
        return _valid_file(card.image_path)
    if component == "audio":
        return _valid_file(card.audio_path)
    if component == "tags":
        return bool(card.tags)
    attr = _CARD_ATTRS.get(component)
    if not attr:
        return False
    return bool(str(getattr(card, attr, "")).strip())


def _note_guid_key(project: ProjectData, card: FlashcardData) -> str:
    if card.id is not None:
        return f"ankiistudio:{project.id or project.name}:card:{card.id}"
    content = "|".join(
        [
            card.section,
            card.word,
            card.reading,
            card.romanization,
            card.translation,
            card.example,
            card.example_translation,
        ]
    )
    return f"ankiistudio:{project.id or project.name}:content:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"


class StableNote(genanki.Note):
    def __init__(self, *, guid_key: str, **kwargs) -> None:
        self._ankiistudio_guid_key = guid_key
        super().__init__(**kwargs)

    @property
    def guid(self) -> str:
        return genanki.guid_for(self._ankiistudio_guid_key)


class AnkiExportService:
    @staticmethod
    def analyze_cards(project: ProjectData, cards: list[FlashcardData]) -> tuple[list[str], list[str]]:
        if not cards:
            return ["Não há cartões selecionados para exportar."], []
        errors: list[str] = []
        warnings: list[str] = []
        for card in cards:
            front_has_content = any(
                _component_has_value(component, card) for component in project.front_components
            )
            if not front_has_content:
                errors.append(f"{card.word}: a frente do cartão ficaria vazia")
                continue
            missing = [
                component
                for component in dict.fromkeys(project.front_components + project.back_components)
                if not _component_has_value(component, card)
            ]
            if missing:
                labels = ", ".join(COMPONENT_LABELS.get(item, item) for item in missing)
                warnings.append(f"{card.word}: faltando {labels}")
        return errors, warnings

    @classmethod
    def validate_cards(cls, project: ProjectData, cards: list[FlashcardData]) -> list[str]:
        errors, warnings = cls.analyze_cards(project, cards)
        if errors:
            preview = errors[:8]
            suffix = "" if len(errors) <= 8 else "\n..."
            raise ValueError(
                "A exportação foi interrompida porque alguns cartões ficariam sem conteúdo na frente.\n\n"
                + "\n".join(f"• {item}" for item in preview)
                + suffix
            )
        return warnings

    def export(
        self,
        project: ProjectData,
        cards: list[FlashcardData],
        destination: Path,
    ) -> Path:
        self.validate_cards(project, cards)
        destination.parent.mkdir(parents=True, exist_ok=True)

        model = genanki.Model(
            _stable_id("model", f"{project.id}:{project.name}"),
            f"AnkiiStudio - {project.name}",
            fields=[{"name": field} for field in _FIELD_ORDER],
            templates=[
                {
                    "name": "Cartão AnkiiStudio",
                    "qfmt": render_components_template(project.front_components),
                    "afmt": render_components_template(project.back_components),
                }
            ],
            css=build_card_css(project.card_theme),
        )

        section_order = {name.casefold(): index for index, name in enumerate(project.deck_sections)}
        grouped: dict[str, list[FlashcardData]] = {}
        for card in cards:
            grouped.setdefault(card.section.strip(), []).append(card)

        ordered_sections = sorted(
            grouped,
            key=lambda name: (
                0 if not name else 1,
                section_order.get(name.casefold(), 10_000),
                name.casefold(),
            ),
        )
        decks: list[genanki.Deck] = []
        media_files: set[str] = set()

        for section in ordered_sections:
            deck_name = project.name if not section else f"{project.name}::{section}"
            deck = genanki.Deck(
                _stable_id("deck", f"{project.id}:{project.name}:{section}"),
                deck_name,
            )
            for card in grouped[section]:
                image_html = ""
                if _valid_file(card.image_path):
                    media_files.add(card.image_path)
                    image_html = f'<img src="{Path(card.image_path).name}">'
                word_audio = ""
                audio_path = card.audio_path
                if _valid_file(audio_path):
                    media_files.add(audio_path)
                    word_audio = f"[sound:{Path(audio_path).name}]"
                sentence_audio = ""

                fields = [
                    card.word,
                    card.reading,
                    card.romanization,
                    card.translation,
                    card.example,
                    card.example_reading,
                    card.example_translation,
                    card.explanation,
                    card.mnemonic,
                    card.part_of_speech,
                    card.level,
                    " ".join(card.tags),
                    image_html,
                    word_audio,
                    sentence_audio,
                ]
                deck.add_note(
                    StableNote(
                        model=model,
                        fields=fields,
                        tags=card.tags,
                        guid_key=_note_guid_key(project, card),
                    )
                )
            decks.append(deck)

        package = genanki.Package(decks if len(decks) > 1 else decks[0])
        package.media_files = sorted(media_files)
        package.write_to_file(str(destination))
        if not destination.is_file() or destination.stat().st_size <= 0:
            raise RuntimeError("O arquivo .apkg não foi criado corretamente.")
        return destination
