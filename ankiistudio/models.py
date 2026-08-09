from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ankiistudio.constants import LEGACY_COMPONENT_ALIASES, normalize_language_code


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class DeckThemeSettings(BaseModel):
    background: str = "#080B0A"
    card_background: str = "#0E1411"
    primary: str = "#29F08B"
    text: str = "#F3F7F4"
    secondary_text: str = "#B7C7BE"
    border: str = "#26332C"
    font_family: str = '"Noto Sans JP", "Yu Gothic", "Meiryo", sans-serif'
    word_size: int = Field(default=44, ge=18, le=96)
    translation_size: int = Field(default=30, ge=14, le=72)

    @field_validator(
        "background", "card_background", "primary", "text", "secondary_text", "border"
    )
    @classmethod
    def validate_hex_color(cls, value: str) -> str:
        value = value.strip().upper()
        if len(value) != 7 or not value.startswith("#"):
            raise ValueError("As cores devem usar o formato hexadecimal #RRGGBB.")
        try:
            int(value[1:], 16)
        except ValueError as exc:
            raise ValueError("As cores devem usar o formato hexadecimal #RRGGBB.") from exc
        return value


class FlashcardData(BaseModel):
    id: int | None = None
    project_id: int | None = None
    section: str = Field(default="", max_length=160)
    word: str = Field(min_length=1, max_length=300)
    reading: str = Field(default="", max_length=500)
    romanization: str = Field(default="", max_length=500)
    translation: str = Field(default="", max_length=800)
    example: str = Field(default="", max_length=1200)
    example_reading: str = Field(default="", max_length=1600)
    example_translation: str = Field(default="", max_length=1600)
    explanation: str = Field(default="", max_length=3000)
    mnemonic: str = Field(default="", max_length=2000)
    part_of_speech: str = Field(default="", max_length=120)
    level: str = Field(default="", max_length=120)
    tags: list[str] = Field(default_factory=list)
    image_search_terms: list[str] = Field(default_factory=list)
    image_path: str = ""
    # word_audio_path é o armazenamento canônico do componente único "Áudio".
    # sentence_audio_path permanece apenas para compatibilidade com projetos antigos.
    word_audio_path: str = ""
    sentence_audio_path: str = ""
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)

    @field_validator("tags", "image_search_terms", mode="before")
    @classmethod
    def normalize_list(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        if isinstance(value, list):
            return [str(part).strip() for part in value if str(part).strip()]
        raise TypeError("O campo deve ser uma lista ou texto separado por vírgulas.")

    @property
    def audio_path(self) -> str:
        """Áudio utilizável, incluindo fallback de projetos 0.7 ou anteriores."""
        return self.word_audio_path or self.sentence_audio_path


class ProjectData(BaseModel):
    id: int | None = None
    name: str = Field(min_length=1, max_length=160)
    language: str = "ja"
    template_key: str
    topic: str = ""
    custom_content: list[str] = Field(default_factory=list)
    creation_mode: Literal["builtin", "gemini", "import", "manual"] = "builtin"
    front_components: list[str]
    back_components: list[str]
    deck_sections: list[str] = Field(default_factory=list)
    card_theme: DeckThemeSettings = Field(default_factory=DeckThemeSettings)
    audio_mode: Literal["intelligent", "fixed", "random"] = "intelligent"
    audio_providers: list[str] = Field(default_factory=list)
    fixed_audio_provider: str = "voicevox"
    fixed_audio_profile_id: str = ""
    voicevox_style_id: int = 0
    voicevox_style_label: str = ""
    voicevox_speed_scale: float = Field(default=1.0, ge=0.5, le=2.0)
    voicevox_pitch_scale: float = Field(default=0.0, ge=-0.15, le=0.15)
    voicevox_intonation_scale: float = Field(default=1.0, ge=0.0, le=2.0)
    voicevox_volume_scale: float = Field(default=1.0, ge=0.0, le=2.0)
    voicevox_pause_length_scale: float = Field(default=1.0, ge=0.0, le=2.0)
    voice_variant: Literal["natural_a", "natural_b"] = "natural_a"
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)

    @field_validator("language", mode="before")
    @classmethod
    def normalize_project_language(cls, value: object) -> str:
        return normalize_language_code(str(value or "ja"))

    @field_validator("front_components", "back_components", mode="before")
    @classmethod
    def normalize_components(cls, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in value:
            key = str(raw).strip()
            alias = LEGACY_COMPONENT_ALIASES.get(key, key)
            if not alias or alias in seen:
                continue
            seen.add(alias)
            normalized.append(alias)
        return normalized

    def uses_component(self, component: str) -> bool:
        return component in self.front_components or component in self.back_components

    @property
    def uses_images(self) -> bool:
        return self.uses_component("image")

    @property
    def uses_audio(self) -> bool:
        return self.uses_component("audio")

    # Compatibilidade para chamadas antigas dentro de extensões/testes.
    @property
    def uses_word_audio(self) -> bool:
        return self.uses_audio

    @property
    def uses_sentence_audio(self) -> bool:
        return False


class ImportedDeck(BaseModel):
    format_version: str = "1.0"
    language: str = "ja"
    category: str
    deck_name: str
    cards: list[FlashcardData]

    @field_validator("language")
    @classmethod
    def normalize_language(cls, value: str) -> str:
        return normalize_language_code(value)


class MediaAsset(BaseModel):
    id: int | None = None
    project_id: int
    card_id: int | None = None
    kind: Literal["image", "audio"]
    provider: str
    local_path: str
    source_title: str = ""
    source_url: str = ""
    author: str = ""
    license_name: str = ""
    license_url: str = ""
    modifications: str = ""
    metadata_json: str = "{}"
    created_at: str = Field(default_factory=utc_now_iso)

    @property
    def path(self) -> Path:
        return Path(self.local_path)


class WikimediaMediaResult(BaseModel):
    title: str
    page_id: int | None = None
    file_url: str
    thumbnail_url: str = ""
    description_url: str = ""
    mime: str = ""
    width: int | None = None
    height: int | None = None
    author: str = ""
    license_name: str = ""
    license_url: str = ""
    credit: str = ""
    description: str = ""
