from pathlib import Path

import pytest

from ankiistudio.database import Database
from ankiistudio.models import FlashcardData, ImportedDeck, ProjectData
from ankiistudio.services.project_service import ProjectService


def _project(**overrides) -> ProjectData:
    data = {
        "name": "Teste",
        "template_key": "custom",
        "custom_content": ["Geral"],
        "topic": "",
        "front_components": ["word"],
        "back_components": ["translation"],
    }
    data.update(overrides)
    return ProjectData(**data)


def test_sanitize_cards_obeys_exact_structure() -> None:
    project = _project(
        front_components=["word"],
        back_components=["translation", "audio"],
    )
    card = FlashcardData(
        word="猫",
        reading="ねこ",
        romanization="neko",
        translation="gato",
        example="猫が好きです。",
        explanation="explicação",
        tags=["N5"],
        image_search_terms=["cat"],
        image_path="imagem.webp",
        sentence_audio_path="sentence.wav",
    )
    sanitized = ProjectService.sanitize_cards_for_structure(project, [card])[0]
    assert sanitized.word == "猫"
    assert sanitized.translation == "gato"
    assert sanitized.reading == ""
    assert sanitized.romanization == ""
    assert sanitized.example == ""
    assert sanitized.explanation == ""
    assert sanitized.tags == []
    assert sanitized.image_search_terms == []
    assert sanitized.image_path == ""
    assert sanitized.sentence_audio_path == ""



def test_sanitize_preserves_image_search_terms_when_image_is_selected() -> None:
    project = _project(
        front_components=["image", "word"],
        back_components=["translation"],
    )
    card = FlashcardData(
        word="メロン",
        translation="melão",
        image_search_terms=["melon fruit", "fresh melon"],
    )
    sanitized = ProjectService.sanitize_cards_for_structure(project, [card])[0]
    assert sanitized.image_search_terms == ["melon fruit", "fresh melon"]



def test_create_from_import_keeps_visual_search_terms_for_image_cards(tmp_path: Path) -> None:
    database = Database(tmp_path / "visual-terms.db")
    service = ProjectService(database)
    project = _project(
        language="ja",
        translation_language="pt",
        front_components=["image", "word"],
        back_components=["translation"],
    )
    imported = ImportedDeck(
        language="ja",
        translation_language="pt",
        category="custom",
        deck_name="Teste",
        cards=[
            FlashcardData(
                word="メロン",
                translation="melão",
                image_search_terms=["melon fruit"],
            )
        ],
    )

    project_id = service.create_from_import(project, imported)
    cards = database.list_cards(project_id)
    assert cards[0].image_search_terms == ["melon fruit"]


def test_audio_does_not_keep_or_require_example() -> None:
    project = _project(
        front_components=["word"],
        back_components=["audio"],
    )
    card = FlashcardData(word="猫", example="猫がいます。", example_translation="Há um gato.")
    sanitized = ProjectService.sanitize_cards_for_structure(project, [card])[0]
    assert sanitized.example == ""
    assert sanitized.example_reading == ""
    assert sanitized.example_translation == ""


def test_single_topic_is_context_not_a_forced_subdeck() -> None:
    project = _project(template_key="basic_phrases", topic="Restaurante")
    assert ProjectService.requested_groups(project) == []
    card = ProjectService.sanitize_cards_for_structure(
        project, [FlashcardData(word="お願いします", translation="Por favor")]
    )[0]
    assert card.section == "Frases Básicas"


def test_comma_separated_topic_items_are_mandatory_subdecks() -> None:
    project = _project(template_key="hiragana", custom_content=[], topic="Katakana, letras, palavra")
    assert ProjectService.requested_groups(project) == ["Katakana", "letras", "palavra"]
    cards = [
        FlashcardData(word="ア", section="Katakana"),
        FlashcardData(word="カ", section="letras"),
        FlashcardData(word="テレビ", section="palavra"),
    ]
    ProjectService.validate_requested_group_coverage(project, cards)


def test_missing_requested_topic_group_is_rejected() -> None:
    project = _project(template_key="hiragana", custom_content=[], topic="Katakana, letras, palavra")
    cards = [
        FlashcardData(word="ア", section="Katakana"),
        FlashcardData(word="テレビ", section="palavra"),
    ]
    with pytest.raises(ValueError, match="letras"):
        ProjectService.validate_requested_group_coverage(project, cards)


def test_custom_content_groups_are_separate_from_single_topic_context() -> None:
    project = _project(
        template_key="custom",
        custom_content=["Kanjis avançados", "Verbos N3"],
        topic="Ambiente de trabalho",
    )
    assert ProjectService.requested_groups(project) == ["Kanjis avançados", "Verbos N3"]


def test_import_creates_subdeck_structure(tmp_path: Path) -> None:
    database = Database(tmp_path / "db.sqlite")
    service = ProjectService(database)
    project = _project(custom_content=["Palavras", "Frases", "Alfabeto"], topic="")
    imported = ImportedDeck(
        category="custom",
        deck_name="Teste",
        cards=[
            FlashcardData(word="猫", translation="gato", section="Palavras"),
            FlashcardData(word="こんにちは", translation="olá", section="Frases"),
            FlashcardData(word="あ", translation="a", section="Alfabeto"),
        ],
    )
    project_id = service.create_from_import(project, imported)
    loaded = database.get_project(project_id)
    assert loaded is not None
    assert loaded.deck_sections == ["Palavras", "Frases", "Alfabeto"]


def test_standard_hiragana_can_keep_only_romaji(tmp_path: Path) -> None:
    database = Database(tmp_path / "romaji-only.sqlite")
    service = ProjectService(database)
    project = ProjectData(
        name="Hiragana Romaji",
        language="ja",
        template_key="hiragana",
        creation_mode="builtin",
        front_components=["word"],
        back_components=["romanization"],
    )
    project_id = service.create_builtin(project, 5)
    cards = database.list_cards(project_id)
    assert len(cards) == 168
    assert cards[0].romanization == "a"
    assert any(card.romanization for card in cards)
    assert all(card.translation == "" for card in cards)
    assert all(card.explanation == "" for card in cards)
    assert cards[0].word == "あ"
    assert cards[0].romanization == "a"


def test_standard_models_are_rejected_for_non_japanese_builtin(tmp_path: Path) -> None:
    database = Database(tmp_path / "english-standard.sqlite")
    service = ProjectService(database)
    project = ProjectData(
        name="English",
        language="en",
        template_key="hiragana",
        creation_mode="builtin",
        front_components=["word"],
        back_components=["romanization"],
    )
    with pytest.raises(ValueError, match="somente para Japonês"):
        service.create_builtin(project, 5)


def test_legacy_components_normalize_to_simplified_structure() -> None:
    project = _project(
        front_components=["image", "word"],
        back_components=[
            "word_audio",
            "sentence_audio",
            "example_reading",
            "example_translation",
            "part_of_speech",
            "level",
            "tags",
        ],
    )
    assert project.front_components == ["image", "word"]
    assert project.back_components == ["audio", "example"]


def test_legacy_sentence_audio_path_is_migrated_to_single_audio_component() -> None:
    project = _project(front_components=["word"], back_components=["audio"])
    card = FlashcardData(word="猫", sentence_audio_path="legacy.wav")
    sanitized = ProjectService.sanitize_cards_for_structure(project, [card])[0]
    assert sanitized.word_audio_path == "legacy.wav"
    assert sanitized.sentence_audio_path == ""


def test_duplicate_project_copies_cards_and_media_metadata(tmp_path: Path) -> None:
    from ankiistudio.models import MediaAsset

    database = Database(tmp_path / "duplicate.db")
    service = ProjectService(database)
    source_id = database.create_project(
        _project(name="Original", front_components=["image", "word"], back_components=["translation", "audio"])
    )
    card_id = database.add_cards(
        source_id,
        [FlashcardData(word="猫", translation="gato", image_path="images/cat.webp", word_audio_path="audio/cat.wav")],
    )[0]
    database.add_media_asset(
        MediaAsset(
            project_id=source_id,
            card_id=card_id,
            kind="image",
            provider="wikimedia",
            local_path="images/cat.webp",
            source_title="Cat",
        )
    )

    copy_id = service.duplicate_project(source_id)
    copied_project = database.get_project(copy_id)
    copied_cards = database.list_cards(copy_id)
    copied_assets = database.list_media_assets_for_project(copy_id)

    assert copied_project is not None
    assert copied_project.name == "Original — Cópia"
    assert len(copied_cards) == 1
    assert copied_cards[0].id != card_id
    assert copied_cards[0].word == "猫"
    assert copied_cards[0].image_path == "images/cat.webp"
    assert copied_cards[0].word_audio_path == "audio/cat.wav"
    assert len(copied_assets) == 1
    assert copied_assets[0].card_id == copied_cards[0].id
    assert copied_assets[0].provider == "wikimedia"
