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
