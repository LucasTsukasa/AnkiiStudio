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
