from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import shutil
from pathlib import Path
from typing import Iterator

import httpx

from ankiistudio.config import AppPaths, SecretStore
from ankiistudio.constants import APP_USER_AGENT, DEFAULT_VOICEVOX_URL, language_label
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
        preferred = project.audio_profile_preferences.get("gemini", "")
        if project.audio_mode == "fixed" and project.fixed_audio_provider == "gemini":
            preferred = project.fixed_audio_profile_id or preferred
        unavailable_message = ""
        if preferred:
            profiles = [p for p in profiles if p.id == preferred]
            if not profiles:
                unavailable_message = (
                    f"A voz Gemini TTS selecionada não está habilitada para {language_label(project.language)}. "
                    "Abra Configurações → Áudio e selecione/crie um perfil compatível."
                )
        elif not profiles:
            unavailable_message = (
                f"Nenhum perfil Gemini TTS habilitado para {language_label(project.language)}. "
                "Abra Configurações → Áudio e adicione uma voz para esse idioma."
            )
        if profiles and not api_key.strip():
            unavailable_message = "A chave da Gemini API não está configurada nas Configurações."
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
        return AudioProviderPool(
            "gemini", providers, self._blocked_profiles, unavailable_message=unavailable_message
        )

    def _eleven_pool(
        self,
        project: ProjectData,
        *,
        http_client: httpx.Client | None = None,
    ) -> AudioProviderPool:
        api_key = SecretStore.get("ELEVENLABS_API_KEY")
        profiles = self.profile_service.list_for("elevenlabs", project.language)
        preferred = project.audio_profile_preferences.get("elevenlabs", "")
        if project.audio_mode == "fixed" and project.fixed_audio_provider == "elevenlabs":
            preferred = project.fixed_audio_profile_id or preferred
        unavailable_message = ""
        if preferred:
            profiles = [p for p in profiles if p.id == preferred]
            if not profiles:
                unavailable_message = (
                    f"A voz ElevenLabs selecionada não está habilitada para {language_label(project.language)}. "
                    "Abra Configurações → Áudio e selecione/crie um perfil compatível."
                )
        elif not profiles:
            unavailable_message = (
                f"Nenhum perfil ElevenLabs habilitado para {language_label(project.language)}. "
                "Abra Configurações → Áudio e adicione uma voz para esse idioma."
            )
        if profiles and not api_key.strip():
            unavailable_message = "A chave da ElevenLabs não está configurada nas Configurações."
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
                    client=http_client,
                ),
            )
            for profile in profiles
        ]
        return AudioProviderPool(
            "elevenlabs", providers, self._blocked_profiles, unavailable_message=unavailable_message
        )

    def _build_router(
        self,
        project: ProjectData,
        *,
        http_client: httpx.Client | None = None,
    ) -> AudioRouter:
        providers = {
            "tatoeba": TatoebaAudioProvider(project.language, client=http_client),
            "voicevox": VoicevoxProvider(
                self.database.get_setting("voicevox_url", DEFAULT_VOICEVOX_URL),
                project.voicevox_style_id,
                speed_scale=project.voicevox_speed_scale,
                pitch_scale=project.voicevox_pitch_scale,
                intonation_scale=project.voicevox_intonation_scale,
                volume_scale=project.voicevox_volume_scale,
                pause_length_scale=project.voicevox_pause_length_scale,
                client=http_client,
            ),
            "wikimedia": WikimediaAudioProvider(
                WikimediaService(client=http_client), language_label(project.language)
            ),
            "gemini": self._gemini_pool(project),
            "elevenlabs": self._eleven_pool(project, http_client=http_client),
        }
        return AudioRouter(providers)

    @contextmanager
    def batch_router(self, project: ProjectData) -> Iterator[AudioRouter]:
        """Cria provedores uma vez e reaproveita conexões durante um lote."""
        with httpx.Client(
            timeout=120,
            follow_redirects=True,
            headers={"User-Agent": APP_USER_AGENT},
        ) as client:
            yield self._build_router(project, http_client=client)

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
        router: AudioRouter | None = None,
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
            self.database.update_card_media(card.id, project_id=card.project_id, word_audio_path=card.word_audio_path, sentence_audio_path=card.sentence_audio_path, update_audio=True)
        elif card.word_audio_path and not self._valid_file(card.word_audio_path):
            card.word_audio_path = ""

        if self._valid_file(card.word_audio_path):
            return card

        router = router or self._build_router(project)
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
        asset = self._asset_from_result(project, card, result, "audio")
        self.database.replace_card_media_asset(
            card.id,
            asset,
            project_id=card.project_id,
            word_audio_path=card.word_audio_path,
            sentence_audio_path=card.sentence_audio_path,
            update_audio=True,
        )
        return card

    @staticmethod
    def _sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(chunk_size):
                digest.update(chunk)
        return digest.hexdigest()

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
        digest = self._sha256_file(source)[:16]
        destination_dir = self.paths.audio_dir / f"project_{project.id}"
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / f"card_{card.id}_import_{digest}{suffix}"
        if not destination.exists():
            shutil.copy2(source, destination)
        previous_paths = {path for path in (card.word_audio_path, card.sentence_audio_path) if path}
        card.word_audio_path = str(destination)
        card.sentence_audio_path = ""
        asset = MediaAsset(
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
        self.database.replace_card_media_asset(
            card.id,
            asset,
            project_id=card.project_id,
            word_audio_path=card.word_audio_path,
            sentence_audio_path=card.sentence_audio_path,
            update_audio=True,
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
        self.database.clear_card_media_asset(
            card.id,
            "audio",
            project_id=card.project_id,
            word_audio_path=card.word_audio_path,
            sentence_audio_path=card.sentence_audio_path,
            update_audio=True,
        )
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

    def _asset_from_result(
        self,
        project: ProjectData,
        card: FlashcardData,
        result,
        kind: str,
    ) -> MediaAsset:
        if project.id is None:
            raise ValueError("O projeto precisa estar salvo antes de registrar mídia.")
        return MediaAsset(
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
