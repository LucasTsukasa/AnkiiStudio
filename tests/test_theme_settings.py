from __future__ import annotations

from pathlib import Path

from ankiistudio.database import Database
from ankiistudio.models import DeckThemeSettings
from ankiistudio.services.theme_settings import load_default_card_theme, save_default_card_theme
from ankiistudio.ui.theme import build_stylesheet


def test_default_card_theme_roundtrip(tmp_path: Path) -> None:
    database = Database(tmp_path / "default-theme.sqlite")
    expected = DeckThemeSettings(
        background="#111111",
        card_background="#222222",
        primary="#A4133C",
        layout_density="compact",
    )
    save_default_card_theme(database, expected)
    loaded = load_default_card_theme(database)
    assert loaded == expected


def test_crimson_application_theme_uses_requested_colors(tmp_path: Path) -> None:
    stylesheet = build_stylesheet(tmp_path, "crimson")
    assert "#1A1A1A" in stylesheet
    assert "#A4133C" in stylesheet
    assert "#C9184A" in stylesheet
    assert "check_crimson.svg" in stylesheet
    assert "radio_crimson.svg" in stylesheet
