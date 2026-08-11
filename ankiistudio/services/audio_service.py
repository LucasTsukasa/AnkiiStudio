from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from ankiistudio.config import AppPaths, SecretStore
from ankiistudio.constants import DEFAULT_VOICEVOX_URL, language_label
from ankiistudio.database import Database
from ankiistudio.models import FlashcardData, MediaAsset, ProjectData
from ankiistudio.services.audio.elevenlabs import ElevenLabsProvider
from ankiistudio.services.audio.gemini_tts import GeminiTTSProvider
from ankiistudio.services.audio.profile_pool import AudioProviderPool
from ankiistudio.services.audio.router import AudioRouter
from ankiistudio.services.audio.tatoeba_audio import TatoebaAudioProvider
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
            "tatoeba": TatoebaAudioProvider(project.language),
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
        if not project.card_uses_component(card, "audio"):
            raise ValueError("A estrutura deste cartão não utiliza Áudio.")
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
        self.database.update_card(card)
        self.database.delete_media_assets_for_card(card.id, "audio")
        self._register_asset(project, card, result, "audio")
        return card

    def import_audio_file(
        self,
        project: ProjectData,
        card: FlashcardData,
        source: Path,
    ) -> FlashcardData:
        if project.id is None or card.id is None or card.project_id is None:
            raise ValueError("O projeto e o cartão precisam estar salvos antes de importar áudio.")
        if not project.card_uses_component(card, "audio"):
            raise ValueError("A estrutura deste cartão não utiliza Áudio.")
        source = Path(source)
        if not source.is_file() or source.stat().st_size <= 0:
            raise ValueError("O arquivo de áudio selecionado não existe ou está vazio.")
        suffix = source.suffix.lower() or ".audio"
        digest = hashlib.sha256(source.read_bytes()).hexdigest()[:16]
        destination_dir = self.paths.audio_dir / f"project_{project.id}"
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / f"card_{card.id}_import_{digest}{suffix}"
        if not destination.exists():
            shutil.copy2(source, destination)
        previous_paths = {path for path in (card.word_audio_path, card.sentence_audio_path) if path}
        card.word_audio_path = str(destination)
        card.sentence_audio_path = ""
        self.database.update_card(card)
        self.database.delete_media_assets_for_card(card.id, "audio")
        self.database.add_media_asset(
            MediaAsset(
                project_id=project.id,
                card_id=card.id,
                kind="audio",
                provider="import",
                local_path=str(destination),
                source_title=source.name,
                metadata_json=json.dumps(
                    {"original_filename": source.name, "imported": True},
                    ensure_ascii=False,
                ),
            )
        )
        for old_path in previous_paths:
            if old_path != str(destination):
                self._delete_unreferenced_audio(old_path)
        return card

    def remove_audio(self, card: FlashcardData) -> FlashcardData:
        if card.id is None:
            raise ValueError("Cartão sem identificador.")
        previous_paths = {path for path in (card.word_audio_path, card.sentence_audio_path) if path}
        card.word_audio_path = ""
        card.sentence_audio_path = ""
        self.database.update_card(card)
        self.database.delete_media_assets_for_card(card.id, "audio")
        for old_path in previous_paths:
            self._delete_unreferenced_audio(old_path)
        return card

    def _delete_unreferenced_audio(self, raw_path: str) -> None:
        if not raw_path or self.database.count_card_media_path_references(raw_path, "audio") > 0:
            return
        path = Path(raw_path)
        try:
            resolved = path.resolve()
            audio_root = self.paths.audio_dir.resolve()
            if path.is_file() and (resolved.parent == audio_root or audio_root in resolved.parents):
                path.unlink()
        except OSError:
            pass

    def audio_status(self, project: ProjectData, card: FlashcardData) -> tuple[bool, list[str]]:
        if not project.card_uses_component(card, "audio"):
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
