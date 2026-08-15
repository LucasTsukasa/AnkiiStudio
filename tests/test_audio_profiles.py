from __future__ import annotations

import sys
import types
from pathlib import Path
from types import SimpleNamespace

if "keyring" not in sys.modules:
    keyring_stub = types.ModuleType("keyring")
    keyring_stub.errors = types.SimpleNamespace(
        KeyringError=RuntimeError, PasswordDeleteError=RuntimeError
    )
    keyring_stub.get_password = lambda *args, **kwargs: None
    keyring_stub.set_password = lambda *args, **kwargs: None
    keyring_stub.delete_password = lambda *args, **kwargs: None
    sys.modules["keyring"] = keyring_stub

if "google.genai" not in sys.modules:
    genai_stub = types.ModuleType("google.genai")
    genai_stub.Client = object
    sys.modules["google.genai"] = genai_stub

from ankiistudio.database import Database
from ankiistudio.models import ProjectData
from ankiistudio.services.audio_profile_service import AudioProfileService, AudioVoiceProfile
from ankiistudio.services.audio_service import ProjectAudioService


def test_unlimited_profiles_are_grouped_by_provider_and_language(tmp_path: Path) -> None:
    database = Database(tmp_path / "profiles.sqlite")
    service = AudioProfileService(database)
    profiles = [
        AudioVoiceProfile(provider="gemini", language="ja", name=f"JA {i}", model="gemini-model", voice=f"Voice{i}")
        for i in range(6)
    ] + [
        AudioVoiceProfile(provider="gemini", language="en", name="EN", model="gemini-model", voice="EnglishVoice"),
        AudioVoiceProfile(provider="elevenlabs", language="ja", name="Eleven JA", model="eleven_multilingual_v2", voice="voice-id"),
    ]
    service.save(profiles)
    assert len(service.list_for("gemini", "ja")) == 6
    assert len(service.list_for("gemini", "en")) == 1
    assert len(service.list_for("elevenlabs", "ja")) == 1


def test_voice_profiles_accept_languages_beyond_original_four(tmp_path: Path) -> None:
    database = Database(tmp_path / "profiles-many.sqlite")
    service = AudioProfileService(database)
    profiles = [
        AudioVoiceProfile(provider="elevenlabs", language="fr", name="FR", model="eleven_multilingual_v2", voice="fr-id"),
        AudioVoiceProfile(provider="gemini", language="de", name="DE", model="gemini-model", voice="Kore"),
        AudioVoiceProfile(provider="gemini", language="ar", name="AR", model="gemini-model", voice="Kore"),
    ]
    service.save(profiles)
    assert service.list_for("elevenlabs", "fr")[0].language == "fr"
    assert service.list_for("gemini", "de")[0].language == "de"
    assert service.list_for("gemini", "ar")[0].language == "ar"


def test_disabled_profile_is_not_used_by_default(tmp_path: Path) -> None:
    database = Database(tmp_path / "profiles.sqlite")
    service = AudioProfileService(database)
    service.save([
        AudioVoiceProfile(provider="gemini", language="ja", name="Ativa", model="m1", voice="v1", enabled=True),
        AudioVoiceProfile(provider="gemini", language="ja", name="Desativada", model="m2", voice="v2", enabled=False),
    ])
    assert [profile.name for profile in service.list_for("gemini", "ja")] == ["Ativa"]
    assert len(service.list_for("gemini", "ja", enabled_only=False)) == 2


def test_project_audio_service_builds_only_language_profiles(tmp_path: Path, monkeypatch) -> None:
    database = Database(tmp_path / "profiles.sqlite")
    profile_service = AudioProfileService(database)
    profile_service.save([
        AudioVoiceProfile(provider="gemini", language="ja", name="JP", model="model-jp", voice="Kore"),
        AudioVoiceProfile(provider="gemini", language="en", name="EN", model="model-en", voice="Kore"),
    ])
    monkeypatch.setattr("ankiistudio.services.audio_service.SecretStore.get", lambda key: "test-key")
    project = ProjectData(
        name="Japanese",
        language="ja",
        template_key="custom",
        creation_mode="manual",
        front_components=["word"],
        back_components=["audio"],
        audio_providers=["gemini"],
    )
    audio = ProjectAudioService(database, SimpleNamespace(audio_dir=tmp_path / "audio"))
    pool = audio._gemini_pool(project)
    assert len(pool.providers) == 1
    assert pool.providers[0][0] == "JP"


def test_fixed_gemini_profile_limits_pool_to_selected_profile(tmp_path: Path, monkeypatch) -> None:
    database = Database(tmp_path / "profiles.sqlite")
    profile_service = AudioProfileService(database)
    first = AudioVoiceProfile(provider="gemini", language="ja", name="A", model="m1", voice="v1")
    second = AudioVoiceProfile(provider="gemini", language="ja", name="B", model="m2", voice="v2")
    profile_service.save([first, second])
    monkeypatch.setattr("ankiistudio.services.audio_service.SecretStore.get", lambda key: "test-key")
    project = ProjectData(
        name="Japanese",
        language="ja",
        template_key="custom",
        creation_mode="manual",
        front_components=["word"],
        back_components=["audio"],
        audio_mode="fixed",
        audio_providers=["gemini"],
        fixed_audio_provider="gemini",
        fixed_audio_profile_id=second.id,
    )
    audio = ProjectAudioService(database, SimpleNamespace(audio_dir=tmp_path / "audio"))
    pool = audio._gemini_pool(project)
    assert len(pool.providers) == 1
    assert pool.providers[0][0] == "B"


def test_elevenlabs_profile_voice_settings_are_persisted(tmp_path: Path) -> None:
    database = Database(tmp_path / "eleven-settings.sqlite")
    service = AudioProfileService(database)
    profile = AudioVoiceProfile(
        provider="elevenlabs",
        language="ja",
        name="JP",
        model="eleven_multilingual_v2",
        voice="voice-id",
        stability=0.25,
        similarity_boost=0.82,
        style=0.18,
        speed=1.1,
        speaker_boost=False,
    )
    service.save([profile])
    loaded = service.load()[0]
    assert loaded.stability == 0.25
    assert loaded.similarity_boost == 0.82
    assert loaded.style == 0.18
    assert loaded.speed == 1.1
    assert loaded.speaker_boost is False


def test_legacy_elevenlabs_speed_is_clamped_instead_of_dropping_profile() -> None:
    profile = AudioVoiceProfile.model_validate(
        {
            "provider": "elevenlabs",
            "language": "ja",
            "name": "Legado",
            "model": "eleven_multilingual_v2",
            "voice": "voice-id",
            "speed": 1.8,
        }
    )
    assert profile.speed == 1.2


def test_preferred_gemini_profile_limits_intelligent_pool(tmp_path: Path, monkeypatch) -> None:
    database = Database(tmp_path / "preferred-gemini.sqlite")
    profile_service = AudioProfileService(database)
    first = AudioVoiceProfile(provider="gemini", language="en", name="A", model="m1", voice="v1")
    second = AudioVoiceProfile(provider="gemini", language="en", name="B", model="m2", voice="v2")
    profile_service.save([first, second])
    monkeypatch.setattr("ankiistudio.services.audio_service.SecretStore.get", lambda key: "test-key")
    project = ProjectData(
        name="English",
        language="en",
        template_key="custom",
        creation_mode="manual",
        front_components=["word"],
        back_components=["audio"],
        audio_mode="intelligent",
        audio_providers=["gemini"],
        audio_profile_preferences={"gemini": second.id},
    )
    audio = ProjectAudioService(database, SimpleNamespace(audio_dir=tmp_path / "audio"))
    pool = audio._gemini_pool(project)
    assert [name for name, _provider in pool.providers] == ["B"]


def test_voicevox_global_defaults_roundtrip_preserves_zero_values(tmp_path: Path) -> None:
    from ankiistudio.services.audio_preferences import (
        VoicevoxSettingsData,
        load_voicevox_defaults,
        save_voicevox_defaults,
    )

    database = Database(tmp_path / "voicevox-defaults.sqlite")
    expected = VoicevoxSettingsData(
        style_id=46,
        style_label="Teste - Normal",
        speed_scale=1.15,
        pitch_scale=0.0,
        intonation_scale=0.95,
        volume_scale=1.0,
        pause_length_scale=0.0,
    )
    save_voicevox_defaults(database, expected)
    loaded = load_voicevox_defaults(database)
    assert loaded == expected


def test_audio_pool_explains_missing_profile_for_project_language(tmp_path: Path, monkeypatch) -> None:
    database = Database(tmp_path / "missing-profile.sqlite")
    profile_service = AudioProfileService(database)
    profile_service.save([
        AudioVoiceProfile(provider="elevenlabs", language="ja", name="JP", model="eleven_multilingual_v2", voice="jp-id")
    ])
    monkeypatch.setattr("ankiistudio.services.audio_service.SecretStore.get", lambda key: "test-key")
    project = ProjectData(
        name="English",
        language="en",
        template_key="custom",
        creation_mode="manual",
        front_components=["word"],
        back_components=["audio"],
        audio_mode="fixed",
        audio_providers=["elevenlabs"],
        fixed_audio_provider="elevenlabs",
    )
    audio = ProjectAudioService(database, SimpleNamespace(audio_dir=tmp_path / "audio"))
    pool = audio._eleven_pool(project)
    assert pool.is_available() is False
    message = pool.availability_error()
    assert "Nenhum perfil ElevenLabs habilitado" in message
    assert "Inglês" in message


def test_audio_pool_explains_missing_api_key(tmp_path: Path, monkeypatch) -> None:
    database = Database(tmp_path / "missing-key.sqlite")
    profile_service = AudioProfileService(database)
    profile_service.save([
        AudioVoiceProfile(provider="gemini", language="en", name="EN", model="model", voice="Kore")
    ])
    monkeypatch.setattr("ankiistudio.services.audio_service.SecretStore.get", lambda key: "")
    project = ProjectData(
        name="English",
        language="en",
        template_key="custom",
        creation_mode="manual",
        front_components=["word"],
        back_components=["audio"],
        audio_providers=["gemini"],
    )
    audio = ProjectAudioService(database, SimpleNamespace(audio_dir=tmp_path / "audio"))
    pool = audio._gemini_pool(project)
    assert pool.is_available() is False
    assert "chave da Gemini API" in pool.availability_error()


def test_audio_router_surfaces_profile_configuration_reason(tmp_path: Path) -> None:
    from ankiistudio.services.audio.profile_pool import AudioProviderPool
    from ankiistudio.services.audio.router import AudioRouter

    message = "Nenhum perfil ElevenLabs habilitado para Inglês. Abra Configurações → Áudio."
    pool = AudioProviderPool("elevenlabs", [], unavailable_message=message)
    router = AudioRouter({"elevenlabs": pool})
    project = ProjectData(
        name="English",
        language="en",
        template_key="custom",
        creation_mode="manual",
        front_components=["word"],
        back_components=["audio"],
        audio_mode="fixed",
        audio_providers=["elevenlabs"],
        fixed_audio_provider="elevenlabs",
    )
    try:
        router.generate(
            text="apple",
            destination_stem=tmp_path / "apple",
            project=project,
        )
    except RuntimeError as exc:
        assert message in str(exc)
    else:
        raise AssertionError("O router deveria explicar por que o provedor está indisponível.")
