from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from ankiistudio.database import Database


_USAGE_KEY = "gemini_tts_usage_v1"
_LIMIT_RE = re.compile(r"\blimit:\s*(\d+)\b", re.IGNORECASE)
_RETRY_RE = re.compile(r"(?:retry(?:\s+in)?|retryDelay[^0-9]*)\s*([0-9]+(?:\.[0-9]+)?)\s*s", re.IGNORECASE)


class GeminiTTSUsageTracker:
    """Registra somente o uso observado pelo BenkyouStudio.

    A Gemini não expõe nesta integração um contador autoritativo de cota restante.
    Os valores exibidos são portanto locais/estimados e limites detectados em erros 429.
    """

    def __init__(self, database: Database) -> None:
        self.database = database

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _load(self) -> dict[str, Any]:
        raw = self.database.get_setting(_USAGE_KEY, "{}")
        try:
            data = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _save(self, data: dict[str, Any]) -> None:
        self.database.set_setting(_USAGE_KEY, json.dumps(data, ensure_ascii=False, separators=(",", ":")))

    @staticmethod
    def _clean_timestamps(values: list[str], now: datetime) -> list[str]:
        keep_after = now - timedelta(hours=24)
        result: list[str] = []
        for value in values:
            try:
                stamp = datetime.fromisoformat(value)
            except (TypeError, ValueError):
                continue
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            if stamp >= keep_after:
                result.append(stamp.astimezone(timezone.utc).isoformat())
        return result

    def record_success(self, model: str) -> None:
        now = self._now()
        data = self._load()
        entry = data.setdefault(model, {})
        timestamps = self._clean_timestamps(list(entry.get("success_timestamps", [])), now)
        timestamps.append(now.isoformat())
        entry["success_timestamps"] = timestamps
        entry["last_success"] = now.isoformat()
        entry["last_error"] = ""
        entry["blocked_until"] = ""
        self._save(data)

    def record_quota_error(self, model: str, message: str) -> dict[str, Any]:
        now = self._now()
        data = self._load()
        entry = data.setdefault(model, {})
        entry["success_timestamps"] = self._clean_timestamps(list(entry.get("success_timestamps", [])), now)
        limit_match = _LIMIT_RE.search(message)
        retry_match = _RETRY_RE.search(message)
        if limit_match:
            entry["detected_limit"] = int(limit_match.group(1))
        retry_seconds = float(retry_match.group(1)) if retry_match else 60.0
        entry["retry_seconds"] = retry_seconds
        entry["blocked_until"] = (now + timedelta(seconds=max(1.0, retry_seconds))).isoformat()
        entry["last_error"] = "Limite temporário da Gemini atingido."
        entry["last_quota_error"] = now.isoformat()
        # Retentativas curtas normalmente representam uma janela de taxa; só estimamos
        # restante quando a própria resposta indica uma espera curta.
        entry["estimated_window_seconds"] = 60 if retry_seconds <= 120 else 0
        self._save(data)
        return self.status(model)

    def record_error(self, model: str, message: str) -> None:
        data = self._load()
        entry = data.setdefault(model, {})
        entry["last_error"] = message[:240]
        self._save(data)

    def is_temporarily_blocked(self, model: str) -> bool:
        entry = self._load().get(model, {})
        raw = entry.get("blocked_until")
        if not raw:
            return False
        try:
            until = datetime.fromisoformat(str(raw))
        except ValueError:
            return False
        if until.tzinfo is None:
            until = until.replace(tzinfo=timezone.utc)
        return until > self._now()

    def status(self, model: str) -> dict[str, Any]:
        now = self._now()
        entry = self._load().get(model, {})
        timestamps = self._clean_timestamps(list(entry.get("success_timestamps", [])), now)
        detected_limit = entry.get("detected_limit")
        window_seconds = int(entry.get("estimated_window_seconds") or 0)
        blocked_until = None
        retry_remaining = 0
        if raw := entry.get("blocked_until"):
            try:
                blocked_until = datetime.fromisoformat(str(raw))
                if blocked_until.tzinfo is None:
                    blocked_until = blocked_until.replace(tzinfo=timezone.utc)
                retry_remaining = max(0, int((blocked_until - now).total_seconds()))
            except ValueError:
                blocked_until = None

        recent = len(timestamps)
        estimated_remaining = None
        if detected_limit and window_seconds:
            threshold = now - timedelta(seconds=window_seconds)
            recent = sum(datetime.fromisoformat(value) >= threshold for value in timestamps)
            estimated_remaining = max(0, int(detected_limit) - recent)

        return {
            "model": model,
            "successes_24h": len(timestamps),
            "requests_in_estimated_window": recent,
            "detected_limit": int(detected_limit) if detected_limit else None,
            "estimated_remaining": estimated_remaining,
            "retry_remaining_seconds": retry_remaining,
            "temporarily_blocked": retry_remaining > 0,
            "last_error": str(entry.get("last_error") or ""),
            "last_success": str(entry.get("last_success") or ""),
            "estimate": True,
        }
