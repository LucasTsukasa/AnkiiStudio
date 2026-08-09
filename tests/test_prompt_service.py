import pytest

from ankiistudio.services.prompt_service import PromptService


def test_prompt_contains_schema_language_and_constraints() -> None:
    prompt = PromptService.build(
        language="ja",
        template_key="hiragana",
        topic="Silabário",
        quantity=10,
        deck_name="Hiragana",
        front_components=["word"],
        back_components=["romanization", "translation"],
    )
    assert "Crie exatamente 10 cartões" in prompt
    assert "Idioma-alvo: Japonês" in prompt
    assert 'O campo `language` deve ser exatamente "ja"' in prompt
    assert "Romaji" in prompt
    assert "Tradução" in prompt
    assert "VALIDAÇÃO FINAL SILENCIOSA" in prompt
    assert "JSON SCHEMA OBRIGATÓRIO" in prompt


def test_custom_prompt_keeps_content_separate_from_topic() -> None:
    prompt = PromptService.build(
        template_key="custom",
        topic="ambiente de trabalho",
        quantity=30,
        deck_name="Japonês Personalizado",
        front_components=["word"],
        back_components=["translation"],
        custom_content=["Kanjis avançados", "Verbos N3", "Kanjis avançados"],
    )
    assert "Modelo: Personalizado" in prompt
    assert "Tema ou contexto: ambiente de trabalho" in prompt
    assert "Conteúdos personalizados obrigatórios:" in prompt
    assert "- Kanjis avançados" in prompt
    assert "- Verbos N3" in prompt
    assert prompt.count("- Kanjis avançados") == 1
    assert '`category` deve ser "custom"' in prompt


def test_custom_prompt_requires_at_least_one_custom_item() -> None:
    with pytest.raises(ValueError, match="Personalizado"):
        PromptService.build(
            template_key="custom",
            topic="",
            quantity=10,
            deck_name="Teste",
            front_components=["word"],
            back_components=["translation"],
            custom_content=[],
        )


def test_prompt_forces_unselected_fields_empty() -> None:
    prompt = PromptService.build(
        template_key="hiragana",
        topic="",
        quantity=5,
        deck_name="Estrutura exata",
        front_components=["word"],
        back_components=["romanization"],
    )
    assert "Como `reading` não foi selecionado" in prompt
    assert "Como `translation` não foi selecionado" in prompt
    assert "Como `explanation` não foi selecionado" in prompt
    assert '`image_search_terms: []`' in prompt
    assert '`word_audio_path: ""` e `sentence_audio_path: ""`' in prompt


def test_comma_topic_items_are_mandatory_sections() -> None:
    prompt = PromptService.build(
        template_key="custom",
        topic="Katakana, letras, palavra",
        quantity=30,
        deck_name="Katakana",
        front_components=["word"],
        back_components=["translation"],
        custom_content=["Katakana", "letras", "palavra"],
    )
    assert "Cada item separado por vírgula" in prompt
    assert "Use exatamente estes nomes no campo `section`" in prompt
    assert "Katakana, letras, palavra" in prompt


def test_single_topic_remains_context_instead_of_forced_section() -> None:
    prompt = PromptService.build(
        template_key="basic_phrases",
        topic="Restaurante",
        quantity=10,
        deck_name="Frases",
        front_components=["word"],
        back_components=["translation"],
    )
    assert "Tema ou contexto: Restaurante" in prompt
    assert "Use exatamente estes nomes no campo `section`, respeitando a grafia fornecida: Restaurante" not in prompt


def test_prompt_supports_multiple_catalog_languages() -> None:
    for code, label in (("ja", "Japonês"), ("en", "Inglês"), ("es", "Espanhol"), ("ko", "Coreano"), ("fr", "Francês"), ("ar", "Árabe"), ("sw", "Suaíli")):
        prompt = PromptService.build(
            language=code,
            template_key="custom",
            topic="viagem",
            quantity=3,
            deck_name=f"Teste {label}",
            front_components=["word"],
            back_components=["translation"],
            custom_content=["Saudações"],
        )
        assert f"Idioma-alvo: {label}" in prompt
        assert f'`language` deve ser exatamente "{code}"' in prompt


def test_prompt_audio_never_forces_example_and_kana_stays_kana() -> None:
    prompt = PromptService.build(
        language="ja",
        template_key="custom",
        topic="",
        quantity=5,
        deck_name="Kana",
        front_components=["image", "word"],
        back_components=["translation", "audio"],
        custom_content=["Hiragana"],
    )
    assert "não invente frase de exemplo para viabilizar áudio" in prompt
    assert "texto sintetizado será sempre o próprio `word`" in prompt
    assert "não o transforme em palavra" in prompt
    assert "あ → A" in prompt
    assert "não crie termos alternativos de busca de imagem" in prompt
