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
    assert "caminhos de mídia" in prompt
    assert "word_audio_path" not in prompt
    assert "sentence_audio_path" not in prompt


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
    assert "1 a 3 buscas visuais concretas" in prompt


def test_prompt_respects_independent_translation_language() -> None:
    prompt = PromptService.build(
        language="ja",
        translation_language="en",
        template_key="custom",
        topic="",
        quantity=4,
        deck_name="Japanese in English",
        front_components=["word"],
        back_components=["translation", "explanation"],
        custom_content=["Basic vocabulary"],
    )
    assert "Idioma-alvo: Japonês" in prompt
    assert "Idioma da tradução: Inglês" in prompt
    assert 'translation_language` deve ser exatamente "en"' in prompt
    assert "Escreva `translation` em Inglês (en)" in prompt
    assert "Escreva `explanation` em Inglês (en)" in prompt


def test_prompt_supports_chinese_as_translation_language() -> None:
    prompt = PromptService.build(
        language="ja",
        translation_language="zh",
        template_key="custom",
        topic="",
        quantity=3,
        deck_name="Japanese to Chinese",
        front_components=["word"],
        back_components=["translation", "explanation"],
        custom_content=["Basic vocabulary"],
    )
    assert "Idioma-alvo: Japonês" in prompt
    assert "Idioma da tradução: Chinês" in prompt
    assert 'translation_language` deve ser exatamente "zh"' in prompt
    assert "Escreva `translation` em Chinês (zh)" in prompt
    assert "Escreva `explanation` em Chinês (zh)" in prompt


def test_prompt_supports_automatic_ai_quantity_with_safe_limit() -> None:
    prompt = PromptService.build(
        language="ja",
        translation_language="pt",
        template_key="custom",
        topic="animais",
        quantity=None,
        max_auto_quantity=200,
        deck_name="Vocabulário",
        front_components=["word"],
        back_components=["translation"],
        custom_content=["Animais"],
    )
    assert "Quantidade: Automática (máximo 200)" in prompt
    assert "Determine uma quantidade adequada" in prompt
    assert "Gere no máximo 200 cartões" in prompt
    assert "Crie exatamente None" not in prompt
    assert "não excede 200" in prompt


def test_prompt_requires_strict_json_escaping_and_dynamic_selected_fields() -> None:
    import json

    prompt = PromptService.build(
        language="en",
        translation_language="pt",
        template_key="custom",
        topic="frutas",
        quantity=3,
        deck_name="Basic English",
        front_components=["image", "word"],
        back_components=["translation", "example", "explanation", "mnemonic"],
        custom_content=["Frutas"],
    )
    assert "JSON estritamente válido" in prompt
    assert "aspas internas" in prompt
    assert "Não use vírgula final" in prompt
    assert "sem Markdown" in prompt
    schema_text = prompt.split("JSON SCHEMA OBRIGATÓRIO\n", 1)[1]
    schema = json.loads(schema_text)
    card_schema = schema["properties"]["cards"]["items"]
    required = set(card_schema["required"])
    assert {"word", "translation", "example", "example_translation", "explanation", "mnemonic", "image_search_terms"} <= required
    assert schema["properties"]["cards"]["minItems"] == 3
    assert schema["properties"]["cards"]["maxItems"] == 3


def test_prompt_can_omit_schema_for_native_gemini_structured_output() -> None:
    prompt = PromptService.build(
        language="en",
        translation_language="pt",
        template_key="custom",
        topic="frutas",
        quantity=3,
        deck_name="Basic English",
        front_components=["word"],
        back_components=["translation"],
        custom_content=["Frutas"],
        include_schema=False,
    )
    assert "JSON SCHEMA OBRIGATÓRIO" not in prompt
    assert "Crie exatamente 3 cartões" in prompt
    assert 'O campo `language` deve ser exatamente "en"' in prompt
