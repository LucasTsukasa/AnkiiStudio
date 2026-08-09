from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from ankiistudio.constants import TEMPLATE_SECTIONS
from ankiistudio.models import FlashcardData

_DATA_FILE = Path(__file__).with_name("japanese_standard_content.json")


@lru_cache(maxsize=1)
def _load() -> dict[str, object]:
    return json.loads(_DATA_FILE.read_text(encoding="utf-8"))


def available_builtin_templates() -> tuple[str, ...]:
    return tuple(_load()["models"].keys())


def builtin_card_count(template_key: str) -> int:
    models = _load()["models"]
    if template_key not in models:
        return 0
    return len(models[template_key]["cards"])


def builtin_sections(template_key: str) -> list[str]:
    if template_key not in TEMPLATE_SECTIONS:
        return []
    return list(TEMPLATE_SECTIONS[template_key])


def create_builtin_cards(template_key: str, topic: str = "", quantity: int | None = None) -> list[FlashcardData]:
    models = _load()["models"]
    if template_key not in models:
        return []

    raw_cards = list(models[template_key]["cards"])
    topic_items = [part.strip().casefold() for part in topic.split(",") if part.strip()]
    if topic_items:
        filtered = [
            card
            for card in raw_cards
            if any(
                token in str(card.get("section", "")).casefold()
                or token in str(card.get("word", "")).casefold()
                or token in str(card.get("translation", "")).casefold()
                for token in topic_items
            )
        ]
        if filtered:
            raw_cards = filtered

    # A ordem do arquivo-base é pedagógica e deve ser preservada.
    # Chamadas sem quantity representam o fluxo do modelo padrão e usam toda a base.
    if quantity is not None:
        raw_cards = raw_cards[: max(0, quantity)]
    return [FlashcardData.model_validate(card) for card in raw_cards]
