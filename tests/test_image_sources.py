from __future__ import annotations

from pathlib import Path

import sys
import types

if "keyring" not in sys.modules:
    keyring_stub = types.ModuleType("keyring")
    keyring_stub.errors = types.SimpleNamespace(KeyringError=RuntimeError, PasswordDeleteError=RuntimeError)
    keyring_stub.get_password = lambda *args, **kwargs: None
    keyring_stub.set_password = lambda *args, **kwargs: None
    keyring_stub.delete_password = lambda *args, **kwargs: None
    sys.modules["keyring"] = keyring_stub

from ankiistudio.database import Database
from ankiistudio.services.image_sources import ImageSearchService


def test_wikimedia_is_only_image_source_enabled_by_default(tmp_path: Path) -> None:
    database = Database(tmp_path / "db.sqlite")
    service = ImageSearchService(database)
    assert service.enabled_provider_keys() == ["wikimedia"]


def test_optional_image_sources_follow_settings(tmp_path: Path) -> None:
    database = Database(tmp_path / "db.sqlite")
    database.set_setting("image_source_pixabay", "1")
    database.set_setting("image_source_pexels", "1")
    service = ImageSearchService(database)
    assert service.enabled_provider_keys() == ["wikimedia", "pixabay", "pexels"]


def test_wikimedia_can_be_disabled_when_another_source_is_enabled(tmp_path: Path) -> None:
    database = Database(tmp_path / "db.sqlite")
    database.set_setting("image_source_wikimedia", "0")
    database.set_setting("image_source_pixabay", "1")
    service = ImageSearchService(database)
    assert service.enabled_provider_keys() == ["pixabay"]


def test_manual_provider_filter_is_limited_to_globally_enabled_sources(tmp_path: Path) -> None:
    database = Database(tmp_path / "db.sqlite")
    database.set_setting("image_source_pixabay", "1")
    database.set_setting("image_source_pexels", "1")
    service = ImageSearchService(database)

    assert service._selected_provider_keys(["pexels"]) == ["pexels"]
    assert service._selected_provider_keys(["wikimedia", "unknown"]) == ["wikimedia"]
    assert service._selected_provider_keys(["pixabay", "pexels"]) == ["pixabay", "pexels"]


def test_pixabay_search_results_are_reused_from_24h_cache(tmp_path: Path) -> None:
    from ankiistudio.models import ImageSearchResult

    class FakePixabay:
        key = "pixabay"
        label = "Pixabay"

        def __init__(self) -> None:
            self.calls = 0

        def search(self, term: str, *, limit: int = 12):
            self.calls += 1
            return [
                ImageSearchResult(
                    provider="pixabay",
                    title=f"{term} result",
                    file_url="https://example.test/image.jpg",
                    thumbnail_url="https://example.test/thumb.jpg",
                )
            ]

    database = Database(tmp_path / "db.sqlite")
    service = ImageSearchService(database)
    provider = FakePixabay()

    first = service._provider_search(provider, "cat", limit=8)
    second = service._provider_search(provider, "cat", limit=8)

    assert provider.calls == 1
    assert second == first
