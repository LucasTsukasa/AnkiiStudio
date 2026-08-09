from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from ankiistudio.services.audio.base import AudioProvider, PermanentAudioProviderError
from ankiistudio.services.audio.elevenlabs import ElevenLabsProvider
from ankiistudio.services.audio.profile_pool import AudioProviderPool


class FakeResponse:
    def __init__(self, status_code: int, payload=None, content: bytes = b"audio") -> None:
        self.status_code = status_code
        self._payload = payload
        self.content = content
        self.text = "" if payload is None else str(payload)

    @property
    def is_error(self) -> bool:
        return self.status_code >= 400

    def json(self):
        if self._payload is None:
            raise ValueError("sem JSON")
        return self._payload


class FakeClient:
    response = FakeResponse(200, {"ok": True})
    last_post: dict | None = None
    last_get: dict | None = None

    def __init__(self, *args, **kwargs) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def post(self, url: str, *, params=None, json=None, headers=None):
        type(self).last_post = {"url": url, "params": params, "json": json, "headers": headers}
        return type(self).response

    def get(self, url: str, *, headers=None):
        type(self).last_get = {"url": url, "headers": headers}
        return type(self).response


def test_elevenlabs_400_preserves_real_api_reason(monkeypatch, tmp_path: Path) -> None:
    FakeClient.response = FakeResponse(
        400,
        {
            "detail": {
                "status": "voice_not_found",
                "message": "This voice is not available for free users.",
            }
        },
    )
    monkeypatch.setattr(httpx, "Client", FakeClient)
    provider = ElevenLabsProvider("key", "voice-id", "eleven_multilingual_v2")
    with pytest.raises(PermanentAudioProviderError) as exc_info:
        provider.generate("猫", tmp_path / "voice")
    message = str(exc_info.value)
    assert "This voice is not available for free users." in message
    assert "HTTP 400" not in message or "voice" in message.casefold()


def test_elevenlabs_sends_profile_voice_settings(monkeypatch, tmp_path: Path) -> None:
    FakeClient.response = FakeResponse(200, content=b"mp3-data")
    FakeClient.last_post = None
    monkeypatch.setattr(httpx, "Client", FakeClient)
    provider = ElevenLabsProvider(
        "key",
        "voice-id",
        "eleven_multilingual_v2",
        language="ja",
        stability=0.3,
        similarity_boost=0.8,
        style=0.2,
        speed=1.1,
        speaker_boost=False,
    )
    result = provider.generate("猫", tmp_path / "voice")
    assert result is not None
    assert Path(result.local_path).read_bytes() == b"mp3-data"
    request = FakeClient.last_post
    assert request is not None
    assert request["url"].endswith("/voice-id")
    assert request["params"] == {"output_format": "mp3_44100_128"}
    payload = request["json"]
    assert payload["text"] == "猫"
    assert payload["model_id"] == "eleven_multilingual_v2"
    assert payload["apply_text_normalization"] == "auto"
    assert "apply_language_text_normalization" not in payload
    assert "language_code" not in payload
    assert payload["voice_settings"] == {
        "stability": 0.3,
        "similarity_boost": 0.8,
        "style": 0.2,
        "use_speaker_boost": False,
        "speed": 1.1,
    }


def test_elevenlabs_non_japanese_does_not_force_japanese_normalization(monkeypatch, tmp_path: Path) -> None:
    FakeClient.response = FakeResponse(200, content=b"mp3-data")
    FakeClient.last_post = None
    monkeypatch.setattr(httpx, "Client", FakeClient)
    provider = ElevenLabsProvider("key", "voice-id", "eleven_multilingual_v2", language="en")
    provider.generate("hello", tmp_path / "voice")
    payload = FakeClient.last_post["json"]
    assert payload["apply_text_normalization"] == "auto"
    assert "apply_language_text_normalization" not in payload
    assert "language_code" not in payload


def test_elevenlabs_non_multilingual_v2_can_send_language_code(monkeypatch, tmp_path: Path) -> None:
    FakeClient.response = FakeResponse(200, content=b"mp3-data")
    FakeClient.last_post = None
    monkeypatch.setattr(httpx, "Client", FakeClient)
    provider = ElevenLabsProvider("key", "voice-id", "eleven_flash_v2_5", language="ja")
    provider.generate("猫", tmp_path / "voice")
    payload = FakeClient.last_post["json"]
    assert payload["language_code"] == "ja"
    assert payload["apply_text_normalization"] == "auto"
    assert payload["apply_language_text_normalization"] is True


class PermanentFailureProvider(AudioProvider):
    key = "fake"

    def __init__(self) -> None:
        self.calls = 0

    def is_available(self) -> bool:
        return True

    def generate(self, text: str, destination_stem: Path):
        self.calls += 1
        raise PermanentAudioProviderError("configuração recusada")


def test_permanent_profile_failure_is_not_retried_for_every_card(tmp_path: Path) -> None:
    blocked: dict[str, str] = {}
    provider = PermanentFailureProvider()
    first_pool = AudioProviderPool("elevenlabs", [("profile-key", "Voz A", provider)], blocked)
    with pytest.raises(RuntimeError, match="configuração recusada"):
        first_pool.generate("primeiro", tmp_path / "one")
    assert provider.calls == 1
    assert "profile-key" in blocked

    second_pool = AudioProviderPool("elevenlabs", [("profile-key", "Voz A", provider)], blocked)
    with pytest.raises(RuntimeError, match="configuração recusada"):
        second_pool.generate("segundo", tmp_path / "two")
    assert provider.calls == 1
