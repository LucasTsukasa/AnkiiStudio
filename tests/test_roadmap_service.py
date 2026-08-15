from __future__ import annotations

import json
from pathlib import Path

from ankiistudio.services.roadmap_service import ROADMAP_REMOTE_URL, RoadmapService


def test_roadmap_targets_benkyoustudio_repository() -> None:
    assert ROADMAP_REMOTE_URL.startswith(
        "https://api.github.com/repos/LucasTsukasa/BenkyouStudio/contents/"
    )


def _payload(title: str = "Teste") -> dict:
    return {
        "schema_version": 2,
        "updated_at": "2026-08-11",
        "items": [
            {
                "id": "test",
                "status": "planned",
                "current": False,
                "title": title,
                "description": "Descrição",
                "details": ["Item"],
            }
        ],
    }


def test_roadmap_loads_embedded_file_when_cache_is_absent(tmp_path: Path) -> None:
    local = tmp_path / "roadmap.json"
    local.write_text(json.dumps(_payload("Local")), encoding="utf-8")
    service = RoadmapService(local, tmp_path / "cache" / "roadmap.json")
    loaded = service.load_available()
    assert loaded["items"][0]["title"] == "Local"


def test_roadmap_prefers_cached_copy(tmp_path: Path) -> None:
    local = tmp_path / "roadmap.json"
    cache = tmp_path / "cache" / "roadmap.json"
    cache.parent.mkdir()
    local.write_text(json.dumps(_payload("Local")), encoding="utf-8")
    cache.write_text(json.dumps(_payload("Cache")), encoding="utf-8")
    service = RoadmapService(local, cache)
    loaded = service.load_available()
    assert loaded["items"][0]["title"] == "Cache"


def test_roadmap_preserves_editable_content_exactly_as_written(tmp_path: Path) -> None:
    payload = _payload("Título em português")
    payload["items"][0]["description"] = "Texto livre sem tradução automática."
    payload["items"][0]["details"] = ["Primeiro item", "Second item intentionally"]
    local = tmp_path / "roadmap.json"
    local.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    service = RoadmapService(local, tmp_path / "cache.json")
    loaded = service.load_available()["items"][0]
    assert loaded["title"] == "Título em português"
    assert loaded["description"] == "Texto livre sem tradução automática."
    assert loaded["details"] == ["Primeiro item", "Second item intentionally"]


def test_roadmap_rejects_legacy_localized_content_schema(tmp_path: Path) -> None:
    payload = _payload()
    payload["items"][0]["title"] = {"pt_BR": "Teste", "en_US": "Test"}
    path = tmp_path / "roadmap.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    service = RoadmapService(path, tmp_path / "cache.json")
    assert service.load_available()["items"] == []


def test_roadmap_rejects_unknown_status(tmp_path: Path) -> None:
    payload = _payload()
    payload["items"][0]["status"] = "unknown"
    path = tmp_path / "roadmap.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    service = RoadmapService(path, tmp_path / "cache.json")
    assert service.load_available()["items"] == []


def test_roadmap_fetch_remote_validates_and_updates_cache(monkeypatch, tmp_path: Path) -> None:
    payload = _payload("Remoto")

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return payload

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(
        "ankiistudio.services.roadmap_service.httpx.Client",
        FakeClient,
    )
    local = tmp_path / "roadmap.json"
    cache = tmp_path / "cache" / "roadmap.json"
    local.write_text(json.dumps(_payload("Local")), encoding="utf-8")
    service = RoadmapService(local, cache)
    loaded = service.fetch_remote()
    assert loaded["items"][0]["title"] == "Remoto"
    assert json.loads(cache.read_text(encoding="utf-8"))["items"][0]["title"] == "Remoto"


def test_roadmap_prefers_newer_embedded_copy_over_stale_cache(tmp_path: Path) -> None:
    local_payload = _payload("Local novo")
    local_payload["updated_at"] = "2026-08-12"
    cache_payload = _payload("Cache antigo")
    cache_payload["updated_at"] = "2026-08-11"
    local = tmp_path / "roadmap.json"
    cache = tmp_path / "cache" / "roadmap.json"
    cache.parent.mkdir()
    local.write_text(json.dumps(local_payload), encoding="utf-8")
    cache.write_text(json.dumps(cache_payload), encoding="utf-8")
    service = RoadmapService(local, cache)
    loaded = service.load_available()
    assert loaded["items"][0]["title"] == "Local novo"
