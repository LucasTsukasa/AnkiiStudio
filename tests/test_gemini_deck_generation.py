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

def test_generation_retries_when_selected_components_are_empty(monkeypatch) -> None:
    first = _payload(count=1)
    first["cards"][0].update(
        {
            "example": "",
            "example_translation": "",
            "explanation": "",
            "mnemonic": "",
        }
    )
    second = _payload(count=1)
    second["cards"][0].update(
        {
            "example": "I study every day.",
            "example_translation": "Eu estudo todos os dias.",
            "explanation": "Uma explicação útil.",
            "mnemonic": "Associe a palavra a uma rotina diária.",
        }
    )
    service, client = _service(monkeypatch, [first, second])

    deck = service.generate_deck(
        "prompt",
        expected_cards=1,
        expected_language="en",
        expected_translation_language="pt",
        required_components=["word", "translation", "example", "explanation", "mnemonic"],
    )

    assert deck.cards[0].example == "I study every day."
    assert deck.cards[0].explanation == "Uma explicação útil."
    assert deck.cards[0].mnemonic == "Associe a palavra a uma rotina diária."
    assert len(client.interactions.calls) == 2
    retry_prompt = client.interactions.calls[1]["input"]
    assert "componentes selecionados" in retry_prompt
    assert "Exemplo" in retry_prompt
    assert "Explicação" in retry_prompt
    assert "Mnemônico" in retry_prompt


def test_generation_does_not_require_unselected_optional_components(monkeypatch) -> None:
    service, client = _service(monkeypatch, [_payload(count=1)])
    deck = service.generate_deck(
        "prompt",
        expected_cards=1,
        expected_language="en",
        expected_translation_language="pt",
        required_components=["word", "translation", "image", "audio"],
    )
    assert len(deck.cards) == 1
    assert deck.cards[0].example == ""
    assert len(client.interactions.calls) == 1


def test_generation_requires_example_translation_with_example_component(monkeypatch) -> None:
    invalid = _payload(count=1)
    invalid["cards"][0].update({"example": "Hello!", "example_translation": ""})
    valid = _payload(count=1)
    valid["cards"][0].update({"example": "Hello!", "example_translation": "Olá!"})
    service, client = _service(monkeypatch, [invalid, valid])

    deck = service.generate_deck(
        "prompt",
        expected_cards=1,
        expected_language="en",
        expected_translation_language="pt",
        required_components=["word", "translation", "example"],
    )

    assert deck.cards[0].example_translation == "Olá!"
    assert len(client.interactions.calls) == 2



def test_structured_output_schema_requires_selected_components(monkeypatch) -> None:
    payload = _payload(count=1)
    payload["cards"][0].update(
        {
            "example": "I like apples.",
            "example_translation": "Eu gosto de maçãs.",
            "explanation": "Exemplo de uso.",
            "mnemonic": "Associe apple a maçã.",
        }
    )
    service, client = _service(monkeypatch, [payload])
    service.generate_deck(
        "prompt",
        expected_cards=1,
        expected_language="en",
        expected_translation_language="pt",
        required_components=["word", "translation", "example", "explanation", "mnemonic"],
    )
    schema = client.interactions.calls[0]["response_format"]["schema"]
    card_schema = schema["$defs"]["FlashcardData"]
    required = set(card_schema["required"])
    assert {"word", "translation", "example", "example_translation", "explanation", "mnemonic"} <= required
    for field in ("word", "translation", "example", "example_translation", "explanation", "mnemonic"):
        assert "Obrigatório nesta geração" in card_schema["properties"][field]["description"]
    assert schema["properties"]["cards"]["minItems"] == 1
    assert schema["properties"]["cards"]["maxItems"] == 1


def test_structured_output_schema_does_not_require_unselected_text_fields(monkeypatch) -> None:
    service, client = _service(monkeypatch, [_payload(count=1)])
    service.generate_deck(
        "prompt",
        expected_cards=1,
        expected_language="en",
        expected_translation_language="pt",
        required_components=["word", "translation"],
    )
    card_schema = client.interactions.calls[0]["response_format"]["schema"]["$defs"]["FlashcardData"]
    required = set(card_schema["required"])
    assert {"word", "translation"} <= required
    assert "example" not in required
    assert "explanation" not in required
    assert "mnemonic" not in required
