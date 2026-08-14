from __future__ import annotations

from ankiistudio.database import Database
from ankiistudio.models import DeckThemeSettings


DEFAULT_CARD_THEME_SETTING = "default_card_theme_v1"


def load_default_card_theme(database: Database) -> DeckThemeSettings:
    raw = database.get_setting(DEFAULT_CARD_THEME_SETTING, "")
    if not raw:
        return DeckThemeSettings()
    try:
        return DeckThemeSettings.model_validate_json(raw)
    except Exception:
        return DeckThemeSettings()


def save_default_card_theme(database: Database, theme: DeckThemeSettings) -> None:
    database.set_setting(DEFAULT_CARD_THEME_SETTING, theme.model_dump_json())
