from __future__ import annotations

import html
from pathlib import Path

from ankiistudio.models import DeckThemeSettings, FlashcardData


COMPONENT_FIELDS = {
    "image": "Image",
    "word": "Word",
    "reading": "Reading",
    "romanization": "Romanization",
    "translation": "Translation",
    "audio": "WordAudio",
    "example": "Example",
    "explanation": "Explanation",
    "mnemonic": "Mnemonic",
    "part_of_speech": "PartOfSpeech",
    "level": "Level",
    "tags": "Tags",
}

COMPONENT_CLASSES = {
    "image": "media image",
    "word": "word",
    "reading": "reading",
    "romanization": "romanization",
    "translation": "translation",
    "audio": "audio",
    "example": "example",
    "explanation": "explanation",
    "mnemonic": "mnemonic",
    "part_of_speech": "meta",
    "level": "meta",
    "tags": "tags",
}


def render_components_template(components: list[str]) -> str:
    blocks: list[str] = ['<div class="ankiistudio-card">']
    for component in components:
        if component == "example":
            blocks.append(
                '{{#Example}}<div class="component example">{{Example}}</div>'
                '{{#ExampleReading}}<div class="component example-reading">{{ExampleReading}}</div>{{/ExampleReading}}'
                '{{#ExampleTranslation}}<div class="component example-translation">{{ExampleTranslation}}</div>{{/ExampleTranslation}}'
                '{{/Example}}'
            )
            continue
        field = COMPONENT_FIELDS.get(component)
        if not field:
            continue
        css_class = COMPONENT_CLASSES.get(component, "")
        blocks.append(
            f'{{{{#{field}}}}}<div class="component {css_class}">{{{{{field}}}}}</div>{{{{/{field}}}}}'
        )
    blocks.append("</div>")
    return "\n".join(blocks)


def build_card_css(theme: DeckThemeSettings) -> str:
    return f"""
.card {{
  font-family: {theme.font_family};
  font-size: 20px;
  text-align: center;
  color: {theme.text};
  background: {theme.background};
  padding: 28px;
}}
.ankiistudio-card {{
  max-width: 760px;
  margin: 0 auto;
  padding: 28px;
  border: 1px solid {theme.border};
  border-radius: 20px;
  background: {theme.card_background};
}}
.component {{ margin: 12px 0; }}
.word {{ font-size: {theme.word_size}px; font-weight: 750; color: {theme.primary}; }}
.reading {{ font-size: 24px; color: {theme.secondary_text}; }}
.romanization {{ font-size: 17px; color: {theme.secondary_text}; }}
.translation {{ font-size: {theme.translation_size}px; font-weight: 650; color: {theme.text}; }}
.example {{ font-size: 25px; margin-top: 24px; }}
.example-reading, .example-translation {{ font-size: 18px; color: {theme.secondary_text}; }}
.explanation, .mnemonic {{ text-align: left; line-height: 1.55; background: {theme.background}; padding: 16px; border-radius: 12px; }}
.meta, .tags {{ font-size: 14px; color: {theme.secondary_text}; }}
.image img {{ max-width: 100%; max-height: 420px; border-radius: 16px; }}
.audio {{ margin: 16px 0; }}
hr#answer {{ border: 0; border-top: 1px solid {theme.border}; margin: 24px 0; }}
"""


def _file_url(path_text: str) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    if not path.is_file():
        return ""
    try:
        return path.resolve().as_uri()
    except ValueError:
        return ""


def _sample_value(component: str, card: FlashcardData | None) -> str:
    values = {
        "word": (card.word if card else "猫") or "猫",
        "reading": (card.reading if card else "ねこ") or "ねこ",
        "romanization": (card.romanization if card else "neko") or "neko",
        "translation": (card.translation if card else "gato") or "gato",
        "example": (card.example if card else "猫が好きです。") or "猫が好きです。",
        "example_reading": (card.example_reading if card else "ねこがすきです。") or "ねこがすきです。",
        "example_translation": (card.example_translation if card else "Eu gosto de gatos.") or "Eu gosto de gatos.",
        "explanation": (card.explanation if card else "Exemplo de explicação curta do conteúdo.") or "Exemplo de explicação curta do conteúdo.",
        "mnemonic": (card.mnemonic if card else "Uma associação curta para ajudar a memorizar.") or "Uma associação curta para ajudar a memorizar.",
        "part_of_speech": (card.part_of_speech if card else "Substantivo") or "Substantivo",
        "level": (card.level if card else "Iniciante") or "Iniciante",
        "tags": ", ".join(card.tags) if card and card.tags else "japonês · estudo",
    }
    return html.escape(values.get(component, ""))


def render_preview_document(
    components: list[str],
    theme: DeckThemeSettings,
    card: FlashcardData | None = None,
) -> str:
    blocks: list[str] = []
    for component in components:
        css_class = COMPONENT_CLASSES.get(component, "")
        if component == "image":
            source = _file_url(card.image_path if card else "")
            if source:
                value = f'<img src="{html.escape(source)}">'
            else:
                value = '<div class="preview-image">Imagem</div>'
        elif component == "audio":
            value = '<span class="preview-audio">▶ Áudio</span>'
        elif component == "example":
            example = _sample_value("example", card)
            reading = _sample_value("example_reading", card)
            translation = _sample_value("example_translation", card)
            value = (
                f'<div class="example">{example}</div>'
                f'<div class="example-reading">{reading}</div>'
                f'<div class="example-translation">{translation}</div>'
            )
        else:
            value = _sample_value(component, card)
        blocks.append(f'<div class="component {css_class}">{value}</div>')

    if not blocks:
        blocks.append('<div class="preview-empty">Nenhum componente selecionado.</div>')

    extra_css = f"""
.preview-image {{
  padding: 58px 10px; text-align: center;
  border: 1px dashed {theme.border}; border-radius: 14px; color: {theme.secondary_text};
  background: {theme.background};
}}
.preview-audio {{
  display: inline-block; padding: 9px 14px; border: 1px solid {theme.border};
  border-radius: 999px; color: {theme.primary}; background: {theme.background};
}}
.preview-empty {{ color: {theme.secondary_text}; padding: 30px 10px; }}
"""
    return (
        "<html><head><style>"
        + build_card_css(theme)
        + extra_css
        + "</style></head><body class='card'><div class='ankiistudio-card'>"
        + "".join(blocks)
        + "</div></body></html>"
    )
