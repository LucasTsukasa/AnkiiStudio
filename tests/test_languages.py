from ankiistudio.constants import LANGUAGE_LABELS, language_label, normalize_language_code
from ankiistudio.models import ImportedDeck


def test_language_catalog_is_broad() -> None:
    assert len(LANGUAGE_LABELS) >= 180
    for code in ("ja", "en", "es", "ko", "pt", "fr", "de", "ar", "zh", "sw", "th", "uk"):
        assert code in LANGUAGE_LABELS


def test_language_names_and_codes_are_normalized() -> None:
    assert normalize_language_code("Japonês") == "ja"
    assert normalize_language_code("francês") == "fr"
    assert normalize_language_code("PT_br") == "pt-br"
    assert language_label("de") == "Alemão"


def test_imported_deck_accepts_catalog_language_name() -> None:
    deck = ImportedDeck(category="custom", deck_name="Francês", language="Francês", cards=[])
    assert deck.language == "fr"
