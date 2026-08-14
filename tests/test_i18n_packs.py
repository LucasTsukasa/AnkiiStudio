from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ROOT / "ankiistudio" / "languages"


def load(name: str) -> dict:
    return json.loads((LANGUAGES / name).read_text(encoding="utf-8"))


def test_language_packs_are_separate_valid_json_files() -> None:
    pt = load("pt_BR.json")
    en = load("en_US.json")
    assert pt["code"] == "pt_BR"
    assert pt["name"] == "Português (Brasil)"
    assert en["code"] == "en_US"
    assert en["name"] == "English"
    assert isinstance(pt["translations"], dict)
    assert isinstance(en["translations"], dict)
    assert isinstance(en["fragments"], list)


def test_english_pack_contains_core_navigation_and_new_search_labels() -> None:
    translations = load("en_US.json")["translations"]
    assert translations["Início"] == "Home"
    assert translations["Configurações"] == "Settings"
    assert translations["Pesquisar imagem"] == "Search image"
    assert translations["Filtrar fontes"] == "Filter sources"
    assert translations["Idioma da interface atualizado."] == "Interface language updated."


def test_obsolete_restart_requirement_is_not_present_in_active_translation_pack() -> None:
    translations = load("en_US.json")["translations"]
    assert "A alteração do idioma da interface será aplicada após reiniciar o AnkiiStudio." not in translations


def test_english_pack_contains_beta7_correction_ui_labels() -> None:
    translations = load("en_US.json")["translations"]
    assert translations["Carmesim"] == "Crimson"
    assert translations["Tema padrão dos flashcards"] == "Default flashcard theme"
    assert translations["Avançado"] == "Advanced"
    assert translations["Voz padrão"] == "Default voice"
    assert translations["Aplicar tema padrão global"] == "Apply global default theme"
