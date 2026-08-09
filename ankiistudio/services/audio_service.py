from __future__ import annotations

import hashlib
from pathlib import Path

from ankiistudio.config import AppPaths, SecretStore
from ankiistudio.constants import DEFAULT_VOICEVOX_URL, language_label
from ankiistudio.database import Database
from ankiistudio.models import FlashcardData, MediaAsset, ProjectData
from ankiistudio.services.audio.elevenlabs import ElevenLabsProvider
from ankiistudio.services.audio.gemini_tts import GeminiTTSProvider
from ankiistudio.services.audio.profile_pool import AudioProviderPool
from ankiistudio.services.audio.router import AudioRouter
from ankiistudio.services.audio.voicevox import VoicevoxProvider
from ankiistudio.services.audio.wikimedia_audio import WikimediaAudioProvider
from ankiistudio.services.audio_profile_service import AudioProfileService, AudioVoiceProfile
from ankiistudio.services.gemini_tts_usage import GeminiTTSUsageTracker
from ankiistudio.services.wikimedia_service import WikimediaService


class ProjectAudioService:
    def __init__(self, database: Database, paths: AppPaths) -> None:
        self.database = database
        self.paths = paths
        self.profile_service = AudioProfileService(database)
        # Perfis com falha determinística são ignorados pelo restante do lote.
        self._blocked_profiles: dict[str, str] = {}

    @staticmethod
    def _profile_runtime_key(profile: AudioVoiceProfile) -> str:
        payload = (
            f"{profile.id}|{profile.provider}|{profile.language}|{profile.model}|{profile.voice}|"
            f"{profile.stability}|{profile.similarity_boost}|{profile.style}|{profile.speed}|{profile.speaker_boost}"
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def reset_provider_failures(self) -> None:
        self._blocked_profiles.clear()

    def _gemini_pool(self, project: ProjectData) -> AudioProviderPool:
        api_key = SecretStore.get("GEMINI_API_KEY")
        profiles = self.profile_service.list_for("gemini", project.language)
        if project.audio_mode == "fixed" and project.fixed_audio_provider == "gemini":
            profiles = [p for p in profiles if p.id == project.fixed_audio_profile_id]
        providers = [
            (
                self._profile_runtime_key(profile),
                profile.name,
                GeminiTTSProvider(
                    api_key,
                    profile.model,
                    profile.voice,
                    GeminiTTSUsageTracker(self.database),
                    language_label(project.language),
                ),
            )
            for profile in profiles
        ]
        return AudioProviderPool("gemini", providers, self._blocked_profiles)

    def _eleven_pool(self, project: ProjectData) -> AudioProviderPool:
        api_key = SecretStore.get("ELEVENLABS_API_KEY")
        profiles = self.profile_service.list_for("elevenlabs", project.language)
        if project.audio_mode == "fixed" and project.fixed_audio_provider == "elevenlabs":
            profiles = [p for p in profiles if p.id == project.fixed_audio_profile_id]
        providers = [
            (
                self._profile_runtime_key(profile),
                profile.name,
                ElevenLabsProvider(
                    api_key,
                    profile.voice,
                    profile.model,
                    language=profile.language,
                    stability=profile.stability,
                    similarity_boost=profile.similarity_boost,
                    style=profile.style,
                    speed=profile.speed,
                    speaker_boost=profile.speaker_boost,
                ),
            )
            for profile in profiles
        ]
        return AudioProviderPool("elevenlabs", providers, self._blocked_profiles)

    def _build_router(self, project: ProjectData) -> AudioRouter:
        providers = {
            "voicevox": VoicevoxProvider(
                self.database.get_setting("voicevox_url", DEFAULT_VOICEVOX_URL),
                project.voicevox_style_id,
                speed_scale=project.voicevox_speed_scale,
                pitch_scale=project.voicevox_pitch_scale,
                intonation_scale=project.voicevox_intonation_scale,
                volume_scale=project.voicevox_volume_scale,
                pause_length_scale=project.voicevox_pause_length_scale,
            ),
            "wikimedia": WikimediaAudioProvider(
                WikimediaService(), language_label(project.language)
            ),
            "gemini": self._gemini_pool(project),
            "elevenlabs": self._eleven_pool(project),
        }
        return AudioRouter(providers)

    @staticmethod
    def _valid_file(path_text: str) -> bool:
        if not path_text:
            return False
        path = Path(path_text)
        return path.is_file() and path.stat().st_size > 0

    def generate_for_card(
        self,
        project: ProjectData,
        card: FlashcardData,
        *,
        words: bool | None = None,
        sentences: bool | None = None,
    ) -> FlashcardData:
        del words, sentences  # parâmetros mantidos apenas por compatibilidade com chamadas antigas
        if card.id is None or card.project_id is None:
            raise ValueError("O cartão precisa estar salvo antes de gerar áudio.")
        if not project.uses_audio:
            raise ValueError("A estrutura deste projeto não utiliza Áudio.")
        if not card.word.strip():
            raise ValueError("O cartão não possui conteúdo principal para sintetizar.")

        # Aproveita automaticamente um áudio legado se ele ainda existir no disco.
        if not self._valid_file(card.word_audio_path) and self._valid_file(card.sentence_audio_path):
            card.word_audio_path = card.sentence_audio_path
            card.sentence_audio_path = ""
            self.database.update_card(card)
        elif card.word_audio_path and not self._valid_file(card.word_audio_path):
            card.word_audio_path = ""

        if self._valid_file(card.word_audio_path):
            return card

        router = self._build_router(project)
        card_dir = self.paths.audio_dir / f"project_{card.project_id}"
        card_dir.mkdir(parents=True, exist_ok=True)
        result = router.generate(
            text=card.word,
            destination_stem=card_dir / f"card_{card.id}_audio",
            project=project,
            content_kind="content",
        )
        if not self._valid_file(result.local_path):
            raise RuntimeError("O provedor informou sucesso, mas o arquivo de áudio não foi criado corretamente.")
        card.word_audio_path = result.local_path
        card.sentence_audio_path = ""
        self._register_asset(project, card, result, "audio")
        self.database.update_card(card)
        return card

    def audio_status(self, project: ProjectData, card: FlashcardData) -> tuple[bool, list[str]]:
        if not project.uses_audio:
            return True, []
        if self._valid_file(card.audio_path):
            return True, []
        return False, ["áudio"]

    def _register_asset(self, project: ProjectData, card: FlashcardData, result, kind: str) -> None:
        if project.id is None:
            raise ValueError("O projeto precisa estar salvo antes de registrar mídia.")
        self.database.add_media_asset(
            MediaAsset(
                project_id=project.id,
                card_id=card.id,
                kind=kind,
                provider=result.provider,
                local_path=result.local_path,
                source_title=result.source_title,
                source_url=result.source_url,
                author=result.author,
                license_name=result.license_name,
                license_url=result.license_url,
                metadata_json=result.metadata_json,
            )
        )
