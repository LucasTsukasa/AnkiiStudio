from ankiistudio.services.import_service import DeckImportService


def test_import_valid_deck() -> None:
    deck = DeckImportService.from_text(
        '''{
          "format_version": "1.0",
          "language": "ja",
          "category": "basic_phrases",
          "deck_name": "Teste",
          "cards": [{
            "word": "猫",
            "reading": "ねこ",
            "translation": "gato",
            "tags": ["n5"]
          }]
        }'''
    )
    assert deck.language == "ja"
    assert deck.cards[0].word == "猫"


def test_import_repairs_common_unescaped_quotes_from_ai() -> None:
    text = '''{
      "format_version": "1.0",
      "language": "ja",
      "category": "basic_phrases",
      "deck_name": "Teste",
      "cards": [{
        "word": "いただきます",
        "translation": "Obrigado pela comida.",
        "example_translation": "Todos dizem "itadakimasu" antes de comer."
      }]
    }'''
    deck = DeckImportService.from_text(text)
    assert deck.cards[0].example_translation == 'Todos dizem "itadakimasu" antes de comer.'


def test_import_still_rejects_structurally_ambiguous_json() -> None:
    malformed = '''{
      "format_version": "1.0",
      "language": "ja",
      "category": "basic_phrases",
      "deck_name": "Teste"
      "cards": []
    }'''
    try:
        DeckImportService.from_text(malformed)
    except ValueError as exc:
        assert "JSON inválido" in str(exc)
    else:
        raise AssertionError("JSON estruturalmente inválido não deveria ser aceito.")


def test_import_accepts_json_inside_markdown_with_surrounding_text() -> None:
    text = '''Aqui está o conteúdo solicitado:\n```json\n{
      "format_version": "1.0",
      "language": "en",
      "translation_language": "pt",
      "category": "custom",
      "deck_name": "Teste",
      "cards": [{"word": "apple", "translation": "maçã"}]
    }\n```\nEspero que ajude.'''
    deck = DeckImportService.from_text(text)
    assert deck.cards[0].word == "apple"


def test_import_accepts_plain_preamble_and_epilogue_around_single_json_object() -> None:
    text = '''Resposta da IA:\n{
      "format_version": "1.0",
      "language": "en",
      "translation_language": "pt",
      "category": "custom",
      "deck_name": "Teste",
      "cards": [{"word": "orange", "translation": "laranja"}]
    }\nFim da resposta.'''
    deck = DeckImportService.from_text(text)
    assert deck.cards[0].word == "orange"


def test_import_repairs_simple_trailing_commas() -> None:
    text = '''{
      "format_version": "1.0",
      "language": "en",
      "translation_language": "pt",
      "category": "custom",
      "deck_name": "Teste",
      "cards": [{"word": "banana", "translation": "banana",},],
    }'''
    deck = DeckImportService.from_text(text)
    assert deck.cards[0].word == "banana"


def test_import_repairs_multiple_unescaped_quotes_like_copied_ai_response() -> None:
    text = '''{"format_version":"1.0","language":"en","translation_language":"pt","category":"custom","deck_name":"Basic English","cards":[{"section":"Frutas","word":"apple","translation":"maçã","example":"I bought three apples at the market.","example_translation":"Eu comprei três maçãs no mercado.","explanation":"Substantivo que significa "maçã". O plural regular é "apples".","mnemonic":"Mnemônico: imagine um app com o ícone de uma maçã para lembrar de "apple".","tags":[],"image_search_terms":[]}]}'''
    deck = DeckImportService.from_text(text)
    assert deck.cards[0].explanation == 'Substantivo que significa "maçã". O plural regular é "apples".'
    assert '"apple"' in deck.cards[0].mnemonic


def test_import_repairs_simple_doubled_string_delimiters() -> None:
    text = '''{
      "format_version": "1.0",
      "language": "en",
      "translation_language": "pt",
      "category": "custom",
      "deck_name": "Teste",
      "cards": [{"word": ""apple"", "translation": "maçã"}]
    }'''
    deck = DeckImportService.from_text(text)
    assert deck.cards[0].word == "apple"


def test_import_file_and_pasted_text_use_same_validation_path(tmp_path) -> None:
    text = '''\ufeff{
      "format_version": "1.0",
      "language": "en",
      "translation_language": "pt",
      "category": "custom",
      "deck_name": "Teste",
      "cards": [{"word": "apple", "translation": "maçã"}]
    }'''
    path = tmp_path / "deck.json"
    path.write_text(text, encoding="utf-8")
    from_file = DeckImportService.from_file(path)
    from_clipboard = DeckImportService.from_text(text)
    assert from_file.model_dump() == from_clipboard.model_dump()


def test_import_repairs_quoted_term_followed_by_natural_comma_inside_string() -> None:
    text = '''{
      "format_version": "1.0",
      "language": "en",
      "translation_language": "pt",
      "category": "custom",
      "deck_name": "Basic English",
      "cards": [{
        "word": "orange",
        "translation": "laranja",
        "explanation": "Como substantivo, "orange" significa "laranja", a fruta. A palavra também pode indicar a cor laranja."
      }]
    }'''
    deck = DeckImportService.from_text(text)
    assert deck.cards[0].explanation == (
        'Como substantivo, "orange" significa "laranja", a fruta. '
        'A palavra também pode indicar a cor laranja.'
    )
