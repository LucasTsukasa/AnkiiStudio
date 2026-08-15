from __future__ import annotations

import json
import logging
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from ankiistudio.constants import (
    DEFAULT_ELEVEN_MODEL,
    DEFAULT_GEMINI_VOICE,
    GEMINI_TTS_AUTO_MODELS,
    language_label,
    normalize_language_code,
)
from ankiistudio.database import Database


logger = logging.getLogger(__name__)


class AudioVoiceProfile(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    provider: Literal["gemini", "elevenlabs"]
    language: str
    name: str
    model: str
    voice: str
    enabled: bool = True
    stability: float = Field(default=0.5, ge=0.0, le=1.0)
    similarity_boost: float = Field(default=0.75, ge=0.0, le=1.0)
    style: float = Field(default=0.0, ge=0.0, le=1.0)
    speed: float = Field(default=1.0, ge=0.7, le=1.2)
    speaker_boost: bool = True

    @field_validator("language", mode="before")
    @classmethod
    def _normalize_language(cls, value: object) -> str:
        return normalize_language_code(str(value or "ja"))

    @field_validator("speed", mode="before")
    @classmethod
    def _normalize_legacy_speed(cls, value: object) -> float:
        # A 0.7.0 aceitava uma faixa maior; limita valores antigos à faixa suportada
        # pela API atual sem descartar todos os perfis salvos.
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = 1.0
        return min(1.2, max(0.7, number))

    @property
    def language_label(self) -> str:
        return language_label(self.language)

    @property
    def display_name(self) -> str:
        return f"{self.language_label} · {self.name} · {self.model}"


class AudioProfileService:
    SETTING_KEY = "audio_voice_profiles_v1"

    def __init__(self, database: Database) -> None:
        self.database = database

    def load(self) -> list[AudioVoiceProfile]:
        raw = self.database.get_setting(self.SETTING_KEY, "")
        if raw:
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, TypeError) as exc:
                logger.warning(
                    "Não foi possível interpretar os perfis de áudio salvos; "
                    "a configuração original será preservada.",
                    exc_info=True,
                )
                return self._legacy_profiles()

            if not isinstance(data, list):
                logger.warning(
                    "Os perfis de áudio salvos não formam uma lista; "
                    "a configuração original será preservada."
                )
                return self._legacy_profiles()

            profiles: list[AudioVoiceProfile] = []
            invalid_count = 0
            for item in data:
                try:
                    profiles.append(AudioVoiceProfile.model_validate(item))
                except Exception:
                    invalid_count += 1
                    logger.warning(
                        "Perfil de áudio inválido ignorado durante o carregamento.",
                        exc_info=True,
                    )

            if invalid_count:
                logger.warning(
                    "%s perfil(is) de áudio inválido(s) foram ignorados sem sobrescrever "
                    "a configuração persistida.",
                    invalid_count,
                )

            if profiles or not data:
                return profiles

            return self._legacy_profiles()
        profiles = self._legacy_profiles()
        self.save(profiles)
        return profiles

    def save(self, profiles: list[AudioVoiceProfile]) -> None:
        payload = [profile.model_dump() for profile in profiles]
        self.database.set_setting(self.SETTING_KEY, json.dumps(payload, ensure_ascii=False))

    def list_for(
        self,
        provider: str,
        language: str,
        *,
        enabled_only: bool = True,
    ) -> list[AudioVoiceProfile]:
        language = normalize_language_code(language)
        result = [
            profile
            for profile in self.load()
            if profile.provider == provider and profile.language == language
        ]
        if enabled_only:
            result = [profile for profile in result if profile.enabled]
        return result

    def get(self, profile_id: str) -> AudioVoiceProfile | None:
        if not profile_id:
            return None
        return next((profile for profile in self.load() if profile.id == profile_id), None)

    def upsert(self, profile: AudioVoiceProfile) -> None:
        profiles = self.load()
        for index, existing in enumerate(profiles):
            if existing.id == profile.id:
                profiles[index] = profile
                break
        else:
            profiles.append(profile)
        self.save(profiles)

    def delete(self, profile_id: str) -> None:
        self.save([profile for profile in self.load() if profile.id != profile_id])

    def _legacy_profiles(self) -> list[AudioVoiceProfile]:
        profiles: list[AudioVoiceProfile] = []

        gemini_model = self.database.get_setting(
            "gemini_tts_model", "auto"
        )
        legacy_models = list(GEMINI_TTS_AUTO_MODELS) if gemini_model == "auto" else [gemini_model]
        legacy_gemini = [
            ("Natural A", self.database.get_setting("gemini_voice_natural_a", DEFAULT_GEMINI_VOICE)),
            ("Natural B", self.database.get_setting("gemini_voice_natural_b", "Charon")),
        ]
        seen_gemini: set[tuple[str, str]] = set()
        for name, voice in legacy_gemini:
            voice = voice.strip()
            if not voice:
                continue
            for model in legacy_models:
                dedupe_key = (voice.casefold(), model.casefold())
                if dedupe_key in seen_gemini:
                    continue
                seen_gemini.add(dedupe_key)
                suffix = model.replace("gemini-", "").replace("-preview", "")
                profiles.append(
                    AudioVoiceProfile(
                        provider="gemini",
                        language="ja",
                        name=f"{name} · {suffix}",
                        model=model,
                        voice=voice,
                    )
                )

        eleven_model = self.database.get_setting("elevenlabs_model", DEFAULT_ELEVEN_MODEL)
        for suffix, name in (("natural_a", "Natural A"), ("natural_b", "Natural B")):
            voice_id = self.database.get_setting(f"elevenlabs_voice_id_{suffix}", "").strip()
            if voice_id:
                profiles.append(
                    AudioVoiceProfile(
                        provider="elevenlabs",
                        language="ja",
                        name=name,
                        model=eleven_model,
                        voice=voice_id,
                    )
                )
        return profiles
