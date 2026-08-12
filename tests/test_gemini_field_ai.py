from __future__ import annotations

import json
import sys
from types import ModuleType, SimpleNamespace

import pytest

# O ambiente de validação pode não ter google-genai instalado. O serviço é testado
# com um cliente falso, então disponibilizamos apenas o módulo mínimo para importação.
try:
    from google import genai as _installed_genai  # type: ignore[attr-defined]
except ImportError:
    import google

    _installed_genai = ModuleType("google.genai")
    _installed_genai.Client = lambda **_kwargs: None  # type: ignore[attr-defined]
    sys.modules["google.genai"] = _installed_genai
    setattr(google, "genai", _installed_genai)

from ankiistudio.models import FlashcardData, ProjectData
from ankiistudio.services.gemini_service import GeminiContentService


def _project() -> ProjectData:
    return ProjectData(
        name="Japonês",
        language="ja",
        translation_language="pt",
        template_key="custom",
        front_components=["word"],
        back_components=["translation", "example", "explanation", "mnemonic"],
    )


def _card() -> FlashcardData:
    return FlashcardData(
        id=7,
        project_id=1,
        word="猫",
        reading="ねこ",
        translation="gato",
        example="猫が好きです。",
        explanation="Explicação atual.",
        mnemonic="Mnemônico atual.",
    )


class FakeInteractions:
    def __init__(self, output: dict[str, str]) -> None:
        self.output = output
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(output_text=json.dumps(self.output, ensure_ascii=False))


class FakeClient:
    def __init__(self, output: dict[str, str]) -> None:
        self.interactions = FakeInteractions(output)


def _service(monkeypatch, output: dict[str, str]) -> tuple[GeminiContentService, FakeClient]:
    client = FakeClient(output)
    monkeypatch.setattr(
        "ankiistudio.services.gemini_service.genai.Client",
        lambda api_key: client,
    )
    return GeminiContentService("test-key", "gemini-test"), client


def test_field_ai_generates_only_requested_explanation_component(monkeypatch) -> None:
    service, client = _service(
        monkeypatch,
        {"value": "Explicação nova.", "example_reading": "", "example_translation": ""},
    )
    result = service.generate_card_field(_project(), _card(), "explanation")
    assert result.value == "Explicação nova."
    assert len(client.interactions.calls) == 1
    call = client.interactions.calls[0]
    assert call["model"] == "gemini-test"
    assert "SOMENTE para o componente `Explicação`" in call["input"]
    assert "Conteúdo principal: 猫" in call["input"]
    assert "Idioma da tradução: Português (pt)" in call["input"]


def test_field_ai_example_returns_consistent_internal_example_data(monkeypatch) -> None:
    service, _client = _service(
        monkeypatch,
        {
            "value": "猫が窓のそばで寝ています。",
            "example_reading": "ねこがまどのそばでねています。",
            "example_translation": "O gato está dormindo perto da janela.",
        },
    )
    result = service.generate_card_field(_project(), _card(), "example")
    assert result.value == "猫が窓のそばで寝ています。"
    assert result.example_reading == "ねこがまどのそばでねています。"
    assert result.example_translation == "O gato está dormindo perto da janela."


def test_field_ai_rejects_fields_outside_supported_scope(monkeypatch) -> None:
    service, _client = _service(monkeypatch, {"value": "x"})
    with pytest.raises(ValueError, match="não suportado"):
        service.generate_card_field(_project(), _card(), "translation")  # type: ignore[arg-type]


def test_field_ai_rejects_component_not_used_by_card_structure(monkeypatch) -> None:
    service, _client = _service(monkeypatch, {"value": "x"})
    project = _project().model_copy(update={"back_components": ["translation"]})
    with pytest.raises(ValueError, match="não faz parte"):
        service.generate_card_field(project, _card(), "mnemonic")
