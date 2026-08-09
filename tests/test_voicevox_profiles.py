from __future__ import annotations

import httpx

from ankiistudio.services.audio.voicevox import VoicevoxProvider


class _Response:
    def __init__(self, payload):
        self._payload = payload
    def raise_for_status(self):
        return None
    def json(self):
        return self._payload


class _Client:
    def __init__(self, timeout=None):
        self.timeout = timeout
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def get(self, url):
        return _Response([
            {
                "name": "ずんだもん",
                "speaker_uuid": "abc",
                "styles": [
                    {"name": "ノーマル", "id": 3},
                    {"name": "あまあま", "id": 1},
                ],
            },
            {
                "name": "四国めたん",
                "speaker_uuid": "def",
                "styles": [{"name": "ノーマル", "id": 2}],
            },
        ])


def test_voicevox_speaker_styles_are_exposed_with_friendly_labels(monkeypatch) -> None:
    monkeypatch.setattr(httpx, "Client", _Client)
    styles = VoicevoxProvider.list_speaker_styles("127.0.0.1:50021")
    assert {style["id"] for style in styles} == {1, 2, 3}
    labels = {style["label"] for style in styles}
    assert "ずんだもん — ノーマル" in labels
    assert "四国めたん — ノーマル" in labels
