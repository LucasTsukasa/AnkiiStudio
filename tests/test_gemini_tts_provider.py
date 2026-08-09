from __future__ import annotations

import base64
import importlib
import sys
import types
from pathlib import Path

from ankiistudio.database import Database
from ankiistudio.services.gemini_tts_usage import GeminiTTSUsageTracker


def _load_provider(monkeypatch, create_impl):
    genai_stub = types.ModuleType("google.genai")

    class FakeInteractions:
        def create(self, **kwargs):
            return create_impl(**kwargs)

    class FakeClient:
        def __init__(self, api_key: str):
            self.api_key = api_key
            self.interactions = FakeInteractions()

    genai_stub.Client = FakeClient
    try:
        google_pkg = importlib.import_module("google")
    except ModuleNotFoundError:
        google_pkg = types.ModuleType("google")
        google_pkg.__path__ = []
        monkeypatch.setitem(sys.modules, "google", google_pkg)
    monkeypatch.setitem(sys.modules, "google.genai", genai_stub)
    setattr(google_pkg, "genai", genai_stub)

    module_name = "ankiistudio.services.audio.gemini_tts"
    sys.modules.pop(module_name, None)
    module = importlib.import_module(module_name)
    return module.GeminiTTSProvider


def test_auto_model_falls_back_after_quota_error(tmp_path: Path, monkeypatch) -> None:
    calls: list[str] = []

    def create_impl(**kwargs):
        model = kwargs["model"]
        calls.append(model)
        if model == "gemini-3.1-flash-tts-preview":
            raise RuntimeError("429 quota exceeded limit: 10 Please retry in 33s")
        return types.SimpleNamespace(
            output_audio=types.SimpleNamespace(data=base64.b64encode(b"\x00\x00" * 100).decode("ascii"))
        )

    Provider = _load_provider(monkeypatch, create_impl)
    db = Database(tmp_path / "db.sqlite")
    tracker = GeminiTTSUsageTracker(db)
    provider = Provider("key", "auto", "Kore", tracker)

    result = provider.generate("猫", tmp_path / "audio" / "card")
    assert Path(result.local_path).is_file()
    assert calls == ["gemini-3.1-flash-tts-preview", "gemini-2.5-flash-preview-tts"]
    assert tracker.status("gemini-3.1-flash-tts-preview")["temporarily_blocked"] is True
    assert tracker.status("gemini-2.5-flash-preview-tts")["successes_24h"] == 1
    assert "gemini-2.5-flash-preview-tts" in result.source_title
