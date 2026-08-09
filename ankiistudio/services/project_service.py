from __future__ import annotations

from ankiistudio.constants import DEFAULT_AUDIO_PROVIDERS, TEMPLATE_SECTIONS
from ankiistudio.data.japanese_seed import create_builtin_cards
from ankiistudio.database import Database
from ankiistudio.models import FlashcardData, ImportedDeck, ProjectData


class ProjectService:
    def __init__(self, database: Database) -> None:
        self.database = database

    @staticmethod
    def requested_groups(project: ProjectData) -> list[str]:
        if project.template_key == "custom":
            raw_items = list(project.custom_content)
        else:
            topic_items = [part.strip() for part in project.topic.split(",") if part.strip()]
            raw_items = topic_items if len(topic_items) > 1 else []

        result: list[str] = []
        seen: set[str] = set()
        for item in raw_items:
            cleaned = item.strip()
            if not cleaned:
                continue
            key = cleaned.casefold()
            if key in seen:
                continue
            seen.add(key)
            result.append(cleaned)
        return result

    @staticmethod
    def _default_section(project: ProjectData) -> str:
        labels = {
            "hiragana": "Silabário",
            "katakana": "Silabário",
            "basic_phrases": "Frases Básicas",
        }
        return labels.get(project.template_key, "Geral")

    @classmethod
    def sanitize_cards_for_structure(
        cls,
        project: ProjectData,
        cards: list[FlashcardData],
    ) -> list[FlashcardData]:
        selected = set(project.front_components + project.back_components)
        requested_groups = cls.requested_groups(project)
        default_section = cls._default_section(project)
        sanitized: list[FlashcardData] = []

        for card in cards:
            updates: dict[str, object] = {}
            section = card.section.strip()
            if not section:
                section = requested_groups[0] if len(requested_groups) == 1 else default_section
            updates["section"] = section

            if "reading" not in selected:
                updates["reading"] = ""
            if "romanization" not in selected:
                updates["romanization"] = ""
            if "translation" not in selected:
                updates["translation"] = ""

            if "example" not in selected:
                updates["example"] = ""
                updates["example_reading"] = ""
                updates["example_translation"] = ""
            if "explanation" not in selected:
                updates["explanation"] = ""
            if "mnemonic" not in selected:
                updates["mnemonic"] = ""

            # Metadados antigos continuam compatíveis no schema, mas não são componentes visuais.
            updates["part_of_speech"] = ""
            updates["level"] = ""
            updates["tags"] = []
            updates["image_search_terms"] = []
            if "image" not in selected:
                updates["image_path"] = ""

            if "audio" in selected:
                # Migra automaticamente áudio legado da frase para o componente único de áudio.
                if not card.word_audio_path and card.sentence_audio_path:
                    updates["word_audio_path"] = card.sentence_audio_path
                updates["sentence_audio_path"] = ""
            else:
                updates["word_audio_path"] = ""
                updates["sentence_audio_path"] = ""

            sanitized.append(card.model_copy(update=updates))
        return sanitized

    @classmethod
    def validate_requested_group_coverage(
        cls, project: ProjectData, cards: list[FlashcardData]
    ) -> None:
        requested = cls.requested_groups(project)
        if len(requested) <= 1:
            return
        present = {card.section.strip().casefold() for card in cards if card.section.strip()}
        missing = [item for item in requested if item.casefold() not in present]
        if missing:
            raise ValueError(
                "O conteúdo gerado não representou todos os itens obrigatórios solicitados. "
                "Ausentes: " + ", ".join(missing) + "."
            )

    @staticmethod
    def derive_sections(cards: list[FlashcardData]) -> list[str]:
        sections: list[str] = []
        seen: set[str] = set()
        for card in cards:
            section = card.section.strip()
            if not section:
                continue
            key = section.casefold()
            if key in seen:
                continue
            seen.add(key)
            sections.append(section)
        return sections

    @staticmethod
    def _ordered_sections(project: ProjectData, cards: list[FlashcardData]) -> list[str]:
        standard = list(TEMPLATE_SECTIONS.get(project.template_key, []))
        derived = ProjectService.derive_sections(cards)
        existing = {item.casefold() for item in standard}
        standard.extend(item for item in derived if item.casefold() not in existing)
        return standard or derived

    def create_builtin(self, project: ProjectData, quantity: int) -> int:
        if project.language != "ja":
            raise ValueError("Modelos padrão estão disponíveis somente para Japonês nesta versão.")
        if project.template_key not in TEMPLATE_SECTIONS:
            raise ValueError(
                "O modelo Personalizado deve ser criado com Gemini API, Importar de uma IA ou Projeto vazio."
            )
        cards = create_builtin_cards(project.template_key)
        if not cards:
            raise ValueError("O modelo selecionado não possui conteúdo para o recorte informado.")
        cards = self.sanitize_cards_for_structure(project, cards)
        self.validate_requested_group_coverage(project, cards)
        project.deck_sections = self._ordered_sections(project, cards)
        project_id = self.database.create_project(project)
        self.database.add_cards(project_id, cards)
        return project_id

    def create_from_import(self, project: ProjectData, imported: ImportedDeck) -> int:
        if imported.language != project.language:
            raise ValueError("O idioma do conteúdo importado não corresponde ao idioma do projeto.")
        cards = self.sanitize_cards_for_structure(project, imported.cards)
        self.validate_requested_group_coverage(project, cards)
        project.deck_sections = self._ordered_sections(project, cards)
        project_id = self.database.create_project(project)
        self.database.add_cards(project_id, cards)
        return project_id

    @staticmethod
    def defaults(project: ProjectData) -> ProjectData:
        if not project.audio_providers:
            project.audio_providers = list(DEFAULT_AUDIO_PROVIDERS)
        return project
