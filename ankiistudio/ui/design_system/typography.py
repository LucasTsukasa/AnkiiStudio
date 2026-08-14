from __future__ import annotations

from dataclasses import dataclass

from .tokens import Typography


@dataclass(frozen=True, slots=True)
class TextStyle:
    size: int
    weight: int = 400


TEXT_STYLES: dict[str, TextStyle] = {
    "caption": TextStyle(Typography.CAPTION, 500),
    "field": TextStyle(Typography.FIELD, 650),
    "body": TextStyle(Typography.BODY, 400),
    "body-strong": TextStyle(Typography.BODY, 650),
    "section": TextStyle(Typography.SECTION, 750),
    "heading": TextStyle(Typography.HEADING, 800),
    "title": TextStyle(Typography.TITLE, 800),
    "hero": TextStyle(Typography.HERO, 850),
}


def text_style(name: str) -> TextStyle:
    return TEXT_STYLES.get(name, TEXT_STYLES["body"])
