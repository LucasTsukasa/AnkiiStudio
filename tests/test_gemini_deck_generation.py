from __future__ import annotations

import json
import sys
from types import ModuleType, SimpleNamespace

import pytest

try:
    from google import genai as _installed_genai  # type: ignore[attr-defined]
except ImportError:
    import google

    _installed_genai = ModuleType("google.genai")
    _installed_genai.Client = lambda **_kwargs: None  # type: ignore[attr-defined]
    sys.modules["google.genai"] = _installed_genai
    setattr(google, "genai", _installed_genai)

from ankiistudio.services.gemini_service import GeminiContentService, GeminiGeneratedDeck


def _payload(*, language: str = "en", translation_language: str = "pt", count: int = 2) -> dict:
    return {
        "format_version": "1.0",
        "language": language,
        "translation_language": translation_language,
        "category": "custom",
        "deck_name": "Test",
        "cards": [
            {
                "section": "Geral",
                "word": f"word-{index}",
                "translation": f"tradução-{index}",
            }
            for index in range(count)
        ],
    }


class FakeInteractions:
    def __init__(self, outputs: list[dict]) -> None:
        self.outputs = list(outputs)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        output = self.outputs.pop(0)
        return SimpleNamespace(output_text=json.dumps(output, ensure_ascii=False))


class FakeClient:
    def __init__(self, outputs: list[dict]) -> None:
        self.interactions = FakeInteractions(outputs)


def _service(monkeypatch, outputs: list[dict]) -> tuple[GeminiContentService, FakeClient]:
    client = FakeClient(outputs)
    monkeypatch.setattr(
        "ankiistudio.services.gemini_service.genai.Client",
        lambda api_key: client,
    )
    return GeminiContentService("test-key", "gemini-test"), client


def test_gemini_generation_schema_requires_languages() -> None:
    schema = GeminiGeneratedDeck.model_json_schema()
    required = set(schema.get("required", []))
    assert {"format_version", "language", "translation_language", "category", "deck_name", "cards"} <= required


def test_fixed_quantity_retries_once_and_accepts_exact_count(monkeypatch) -> None:
    service, client = _service(monkeypatch, [_payload(count=1), _payload(count=2)])

    deck = service.generate_deck(
        "prompt",
        expected_cards=2,
        expected_language="en",
        expected_translation_language="pt",
    )

    assert len(deck.cards) == 2
    assert deck.language == "en"
    assert deck.translation_language == "pt"
    assert len(client.interactions.calls) == 2
    assert "retorne exatamente 2 cartões" in client.interactions.calls[1]["input"]


def test_fixed_quantity_never_silently_accepts_incomplete_deck(monkeypatch) -> None:
    service, client = _service(monkeypatch, [_payload(count=1), _payload(count=1)])

    with pytest.raises(RuntimeError, match="1 de 10 cartões"):
        service.generate_deck(
            "prompt",
            expected_cards=10,
            expected_language="en",
            expected_translation_language="pt",
        )

    assert len(client.interactions.calls) == 2


def test_generation_retries_when_required_language_is_missing(monkeypatch) -> None:
    invalid = _payload(count=2)
    invalid.pop("language")
    service, client = _service(monkeypatch, [invalid, _payload(count=2)])

    deck = service.generate_deck(
        "prompt",
        expected_cards=2,
        expected_language="en",
        expected_translation_language="pt",
    )

    assert deck.language == "en"
    assert len(client.interactions.calls) == 2


def test_generation_rejects_wrong_target_language(monkeypatch) -> None:
    service, _client = _service(monkeypatch, [_payload(language="ja"), _payload(language="ja")])

    with pytest.raises(RuntimeError, match="idioma-alvo incorreto"):
        service.generate_deck(
            "prompt",
            expected_cards=2,
            expected_language="en",
            expected_translation_language="pt",
        )


def test_automatic_quantity_still_uses_safe_maximum(monkeypatch) -> None:
    service, _client = _service(monkeypatch, [_payload(count=3)])
    deck = service.generate_deck(
        "prompt",
        maximum_cards=200,
        expected_language="en",
        expected_translation_language="pt",
    )
    assert len(deck.cards) == 3


@pytest.mark.parametrize("language", ["es", "ko", "fr", "de", "pt"])
def test_generation_accepts_other_supported_target_languages(monkeypatch, language: str) -> None:
    service, _client = _service(monkeypatch, [_payload(language=language, count=2)])
    deck = service.generate_deck(
        "prompt",
        expected_cards=2,
        expected_language=language,
        expected_translation_language="pt",
    )
    assert deck.language == language
    assert len(deck.cards) == 2
