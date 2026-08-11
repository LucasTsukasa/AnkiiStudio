from pathlib import Path

import httpx

from ankiistudio.services.audio.tatoeba_audio import TatoebaAudioProvider


def test_tatoeba_uses_exact_match_and_downloads_reusable_audio(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/sentences":
            assert request.url.params["lang"] == "jpn"
            assert request.url.params["has_audio"] == "yes"
            assert request.url.params["include"] == "audios"
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"id": 1, "text": "猫です。", "audios": [{"id": 10, "author": "Alice", "licence": "CC BY 4.0"}]},
                        {"id": 2, "text": "猫", "audios": [{"id": 20, "author": "Bob", "licence": "CC BY 4.0", "attribution_url": "https://example.invalid/attrib"}]},
                    ]
                },
            )
        if request.url.path == "/v1/audios/20/file":
            return httpx.Response(200, content=b"ID3audio", headers={"content-type": "audio/mpeg"})
        raise AssertionError(request.url)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = TatoebaAudioProvider("ja", client=client)
        result = provider.generate("猫", tmp_path / "card_audio")
    assert result is not None
    assert result.provider == "tatoeba"
    assert result.author == "Bob"
    assert result.license_name == "CC BY 4.0"
    assert Path(result.local_path).read_bytes() == b"ID3audio"


def test_tatoeba_skips_audio_forbidden_for_external_reuse(tmp_path: Path) -> None:
    calls: list[str] = []
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/v1/sentences":
            return httpx.Response(200, json={"data": [{"id": 2, "text": "猫", "audios": [{"id": 20}, {"id": 21, "author": "Allowed", "licence": "CC0 1.0"}]}]})
        if request.url.path == "/v1/audios/20/file":
            return httpx.Response(403)
        if request.url.path == "/v1/audios/21/file":
            return httpx.Response(200, content=b"OK", headers={"content-type": "audio/ogg"})
        raise AssertionError(request.url)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = TatoebaAudioProvider("ja", client=client).generate("猫", tmp_path / "audio")
    assert result is not None
    assert result.author == "Allowed"
    assert calls[-2:] == ["/v1/audios/20/file", "/v1/audios/21/file"]


def test_tatoeba_does_not_use_non_exact_sentence(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/sentences":
            return httpx.Response(200, json={"data": [{"id": 1, "text": "猫です。", "audios": [{"id": 10}]}]})
        raise AssertionError("audio endpoint must not be called")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = TatoebaAudioProvider("ja", client=client).generate("猫", tmp_path / "audio")
    assert result is None
