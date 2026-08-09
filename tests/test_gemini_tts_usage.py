from pathlib import Path

from ankiistudio.database import Database
from ankiistudio.services.gemini_tts_usage import GeminiTTSUsageTracker


def test_tracker_detects_limit_and_estimates_current_window(tmp_path: Path) -> None:
    db = Database(tmp_path / "usage.db")
    tracker = GeminiTTSUsageTracker(db)
    model = "gemini-3.1-flash-tts-preview"
    for _ in range(3):
        tracker.record_success(model)
    tracker.record_quota_error(
        model,
        "Error 429 quota exceeded, limit: 10, model: gemini-3.1-flash-tts-preview. Please retry in 33.9s",
    )
    status = tracker.status(model)
    assert status["detected_limit"] == 10
    assert status["estimated_remaining"] == 7
    assert status["temporarily_blocked"] is True
    assert 1 <= status["retry_remaining_seconds"] <= 34
    assert status["successes_24h"] == 3


def test_tracker_keeps_models_independent(tmp_path: Path) -> None:
    db = Database(tmp_path / "usage.db")
    tracker = GeminiTTSUsageTracker(db)
    tracker.record_success("model-a")
    tracker.record_quota_error("model-a", "429 limit: 10 Please retry in 20s")
    assert tracker.status("model-a")["detected_limit"] == 10
    assert tracker.status("model-b")["detected_limit"] is None
    assert tracker.is_temporarily_blocked("model-a") is True
    assert tracker.is_temporarily_blocked("model-b") is False
