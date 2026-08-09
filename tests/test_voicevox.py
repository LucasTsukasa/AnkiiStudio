import httpx
import pytest

from ankiistudio.services.audio.voicevox import VoicevoxProvider


class _FakeResponse:
    def __init__(self, text: str = '"0.22.0"', status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("GET", "http://127.0.0.1:50021/version")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("erro", request=request, response=response)


class _FakeClient:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def get(self, url: str):
        return _FakeResponse()


def test_voicevox_version_success(monkeypatch) -> None:
    monkeypatch.setattr(httpx, "Client", _FakeClient)
    assert VoicevoxProvider.get_version("127.0.0.1:50021") == "0.22.0"


def test_voicevox_connection_error_is_friendly(monkeypatch) -> None:
    class FailingClient(_FakeClient):
        def get(self, url: str):
            request = httpx.Request("GET", url)
            raise httpx.ConnectError("[WinError 10061]", request=request)

    monkeypatch.setattr(httpx, "Client", FailingClient)
    with pytest.raises(RuntimeError) as exc_info:
        VoicevoxProvider.get_version("http://127.0.0.1:50021")
    message = str(exc_info.value)
    assert "Não foi possível encontrar o VOICEVOX" in message
    assert "WinError" not in message


class _GenerateResponse:
    def __init__(self, *, payload=None, content=b"RIFFvoice", status_code: int = 200) -> None:
        self._payload = payload
        self.content = content
        self.status_code = status_code
        self.text = ""

    def json(self):
        return dict(self._payload or {})

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("POST", "http://127.0.0.1:50021/synthesis")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("erro", request=request, response=response)


class _GenerateClient:
    synthesis_json = None

    def __init__(self, *args, **kwargs) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def post(self, url: str, *, params=None, json=None):
        if url.endswith("/audio_query"):
            return _GenerateResponse(
                payload={
                    "speedScale": 1.0,
                    "pitchScale": 0.0,
                    "intonationScale": 1.0,
                    "volumeScale": 1.0,
                    "pauseLengthScale": 1.0,
                }
            )
        type(self).synthesis_json = dict(json or {})
        return _GenerateResponse(content=b"RIFFvoice")


def test_voicevox_applies_project_voice_settings(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(httpx, "Client", _GenerateClient)
    _GenerateClient.synthesis_json = None
    provider = VoicevoxProvider(
        "127.0.0.1:50021",
        3,
        speed_scale=1.15,
        pitch_scale=0.05,
        intonation_scale=1.3,
        volume_scale=0.9,
        pause_length_scale=1.2,
    )
    result = provider.generate("こんにちは", tmp_path / "voice")
    assert result is not None
    assert _GenerateClient.synthesis_json == {
        "speedScale": 1.15,
        "pitchScale": 0.05,
        "intonationScale": 1.3,
        "volumeScale": 0.9,
        "pauseLengthScale": 1.2,
    }
