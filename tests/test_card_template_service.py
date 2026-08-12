from ankiistudio.models import DeckThemeSettings, FlashcardData
from ankiistudio.services.card_template_service import (
    build_card_css,
    render_components_template,
    render_preview_document,
)


def test_preview_uses_real_card_values_and_audio_visualization() -> None:
    card = FlashcardData(word="猫", translation="gato", example="猫が好きです。")
    html = render_preview_document(
        ["word", "translation", "audio"],
        DeckThemeSettings(),
        card,
    )
    assert "猫" in html
    assert "gato" in html
    assert "▶ Áudio" in html
    assert "ankiistudio-card" in html


def test_export_template_and_preview_share_component_classes() -> None:
    template = render_components_template(["word", "translation"])
    css = build_card_css(DeckThemeSettings())
    assert 'class="component word"' in template
    assert 'class="component translation"' in template
    assert ".word" in css
    assert ".translation" in css


def test_example_is_rendered_as_one_cohesive_component() -> None:
    template = render_components_template(["example"])
    assert "{{Example}}" in template
    assert "{{ExampleReading}}" in template
    assert "{{ExampleTranslation}}" in template
    assert 'class="component example"' in template


def test_card_css_respects_advanced_theme_dimensions() -> None:
    theme = DeckThemeSettings(
        reading_size=22,
        romanization_size=15,
        example_size=23,
        explanation_size=18,
        mnemonic_size=19,
        image_max_height=260,
        card_max_width=640,
        card_padding=14,
        component_spacing=6,
        layout_density="compact",
    )
    css = build_card_css(theme)
    assert ".reading { font-size: 22px" in css
    assert ".romanization { font-size: 15px" in css
    assert ".example { font-size: 23px" in css
    assert ".explanation { font-size: 18px" in css
    assert ".mnemonic { font-size: 19px" in css
    assert "max-height: 260px" in css
    assert "max-width: 640px" in css
    assert "padding: 14px" in css
    assert ".component { margin: 6px 0; }" in css
