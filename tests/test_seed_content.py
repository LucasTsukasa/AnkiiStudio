import json
from pathlib import Path

from ankiistudio.constants import TEMPLATE_SECTIONS
from ankiistudio.data.japanese_seed import (
    available_builtin_templates,
    create_builtin_cards,
)


ROOT = Path(__file__).resolve().parents[1]


def test_only_reviewed_japanese_standard_templates_are_available() -> None:
    assert available_builtin_templates() == ("hiragana", "katakana", "basic_phrases")


def test_standard_content_file_contains_reviewed_models() -> None:
    path = ROOT / "ankiistudio" / "data" / "japanese_standard_content.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert set(payload["models"]) == {"hiragana", "katakana", "basic_phrases"}
    assert len(payload["models"]["hiragana"]["cards"]) >= 150
    assert len(payload["models"]["katakana"]["cards"]) >= 180
    assert len(payload["models"]["basic_phrases"]["cards"]) >= 150


def test_all_standard_templates_create_cards() -> None:
    topics = {
        "hiragana": "Silabário",
        "katakana": "Sons Estrangeiros",
        "basic_phrases": "Restaurante",
    }
    for key, topic in topics.items():
        cards = create_builtin_cards(key, topic, 10)
        assert cards
        assert len(cards) <= 10
        assert all(card.word for card in cards)
        assert all(card.section for card in cards)


def test_standard_sections_follow_defined_structure() -> None:
    hiragana = create_builtin_cards("hiragana", "Silabário", 46)
    assert len(hiragana) == 46
    assert all(card.section == "Silabário" for card in hiragana)
    assert hiragana[0].word == "あ"
    assert hiragana[0].romanization == "a"
    assert hiragana[0].translation == "A"
    assert "som" not in hiragana[0].translation.casefold()

    phrases = create_builtin_cards("basic_phrases", "Saudações", 20)
    assert phrases
    assert all(card.section == "Saudações" for card in phrases)
    assert phrases[0].word == "おはよう。"

    assert TEMPLATE_SECTIONS["hiragana"][0] == "Silabário"
    assert TEMPLATE_SECTIONS["katakana"][0] == "Silabário"
    assert TEMPLATE_SECTIONS["basic_phrases"][0] == "Saudações"
