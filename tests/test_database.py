import sqlite3
from pathlib import Path

from ankiistudio.database import Database
from ankiistudio.models import DeckThemeSettings, FlashcardData, ProjectData


def test_project_and_card_roundtrip(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    project = ProjectData(
        name="Teste",
        template_key="hiragana",
        front_components=["word"],
        back_components=["translation"],
        audio_providers=["voicevox"],
    )
    project_id = db.create_project(project)
    db.add_cards(project_id, [FlashcardData(word="猫", translation="gato")])
    loaded = db.get_project(project_id)
    cards = db.list_cards(project_id)
    assert loaded is not None
    assert loaded.name == "Teste"
    assert cards[0].translation == "gato"


def test_custom_content_roundtrip(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    project = ProjectData(
        name="Personalizado",
        template_key="custom",
        custom_content=["Kanjis avançados", "Verbos N3"],
        topic="trabalho",
        front_components=["word"],
        back_components=["translation"],
    )
    project_id = db.create_project(project)
    loaded = db.get_project(project_id)
    assert loaded is not None
    assert loaded.custom_content == ["Kanjis avançados", "Verbos N3"]
    assert loaded.topic == "trabalho"


def test_existing_database_is_migrated_with_custom_content_column(tmp_path: Path) -> None:
    path = tmp_path / "legacy.db"
    connection = sqlite3.connect(path)
    connection.execute(
        '''
        CREATE TABLE projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            template_key TEXT NOT NULL,
            topic TEXT NOT NULL DEFAULT '',
            creation_mode TEXT NOT NULL,
            front_components TEXT NOT NULL,
            back_components TEXT NOT NULL,
            audio_mode TEXT NOT NULL,
            audio_providers TEXT NOT NULL,
            fixed_audio_provider TEXT NOT NULL,
            voice_variant TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        '''
    )
    connection.commit()
    connection.close()

    Database(path)
    connection = sqlite3.connect(path)
    columns = {row[1] for row in connection.execute("PRAGMA table_info(projects)")}
    connection.close()
    assert {"custom_content", "language"} <= columns


def test_sections_and_deck_theme_roundtrip(tmp_path: Path) -> None:
    db = Database(tmp_path / "theme.db")
    project = ProjectData(
        name="Estruturado",
        template_key="hiragana",
        front_components=["word"],
        back_components=["translation"],
        deck_sections=["Palavras", "Frases", "Alfabeto"],
        card_theme=DeckThemeSettings(
            background="#FFFFFF",
            card_background="#F5F5F5",
            primary="#19D978",
            text="#101510",
            secondary_text="#526057",
            border="#D5DDD8",
            word_size=50,
            translation_size=32,
        ),
    )
    project_id = db.create_project(project)
    card_id = db.add_cards(
        project_id,
        [FlashcardData(word="猫", translation="gato", section="Palavras")],
    )[0]
    loaded = db.get_project(project_id)
    card = db.get_card(card_id)
    assert loaded is not None and card is not None
    assert loaded.deck_sections == ["Palavras", "Frases", "Alfabeto"]
    assert loaded.card_theme.background == "#FFFFFF"
    assert loaded.card_theme.word_size == 50
    assert card.section == "Palavras"


def test_existing_database_is_migrated_with_0_4_columns(tmp_path: Path) -> None:
    path = tmp_path / "legacy04.db"
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, template_key TEXT NOT NULL, topic TEXT NOT NULL DEFAULT '',
            creation_mode TEXT NOT NULL, front_components TEXT NOT NULL, back_components TEXT NOT NULL,
            audio_mode TEXT NOT NULL, audio_providers TEXT NOT NULL, fixed_audio_provider TEXT NOT NULL,
            voice_variant TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL, word TEXT NOT NULL,
            reading TEXT NOT NULL DEFAULT '', romanization TEXT NOT NULL DEFAULT '', translation TEXT NOT NULL DEFAULT '',
            example TEXT NOT NULL DEFAULT '', example_reading TEXT NOT NULL DEFAULT '', example_translation TEXT NOT NULL DEFAULT '',
            explanation TEXT NOT NULL DEFAULT '', mnemonic TEXT NOT NULL DEFAULT '', part_of_speech TEXT NOT NULL DEFAULT '',
            level TEXT NOT NULL DEFAULT '', tags TEXT NOT NULL DEFAULT '[]', image_search_terms TEXT NOT NULL DEFAULT '[]',
            image_path TEXT NOT NULL DEFAULT '', word_audio_path TEXT NOT NULL DEFAULT '', sentence_audio_path TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )
        """
    )
    connection.commit()
    connection.close()

    Database(path)
    connection = sqlite3.connect(path)
    project_columns = {row[1] for row in connection.execute("PRAGMA table_info(projects)")}
    card_columns = {row[1] for row in connection.execute("PRAGMA table_info(cards)")}
    connection.close()
    assert {"language", "custom_content", "deck_sections", "card_theme"} <= project_columns
    assert "section" in card_columns


def test_project_language_roundtrip(tmp_path: Path) -> None:
    db = Database(tmp_path / "languages.db")
    project = ProjectData(
        name="English",
        language="en",
        template_key="custom",
        custom_content=["Basic phrases"],
        front_components=["word"],
        back_components=["translation"],
    )
    project_id = db.create_project(project)
    loaded = db.get_project(project_id)
    assert loaded is not None
    assert loaded.language == "en"


def test_project_accepts_catalog_languages_beyond_original_four(tmp_path: Path) -> None:
    db = Database(tmp_path / "many-languages.db")
    for code in ("fr", "de", "ar", "sw", "th", "uk"):
        project = ProjectData(
            name=f"Projeto {code}",
            language=code,
            template_key="custom",
            custom_content=["Vocabulário"],
            front_components=["word"],
            back_components=["translation"],
        )
        project_id = db.create_project(project)
        loaded = db.get_project(project_id)
        assert loaded is not None
        assert loaded.language == code


def test_voicevox_settings_roundtrip(tmp_path: Path) -> None:
    db = Database(tmp_path / "voicevox.db")
    project = ProjectData(
        name="VOICEVOX",
        language="ja",
        template_key="custom",
        front_components=["word"],
        back_components=["audio"],
        voicevox_style_id=7,
        voicevox_style_label="ずんだもん — ノーマル",
        voicevox_speed_scale=1.2,
        voicevox_pitch_scale=0.04,
        voicevox_intonation_scale=1.25,
        voicevox_volume_scale=0.85,
        voicevox_pause_length_scale=1.1,
    )
    project_id = db.create_project(project)
    loaded = db.get_project(project_id)
    assert loaded is not None
    assert loaded.voicevox_style_id == 7
    assert loaded.voicevox_style_label == "ずんだもん — ノーマル"
    assert loaded.voicevox_speed_scale == 1.2
    assert loaded.voicevox_pitch_scale == 0.04
    assert loaded.voicevox_intonation_scale == 1.25
    assert loaded.voicevox_volume_scale == 0.85
    assert loaded.voicevox_pause_length_scale == 1.1


def test_existing_database_is_migrated_with_voicevox_settings(tmp_path: Path) -> None:
    path = tmp_path / "legacy-voicevox.db"
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            template_key TEXT NOT NULL,
            topic TEXT NOT NULL DEFAULT '',
            creation_mode TEXT NOT NULL,
            front_components TEXT NOT NULL,
            back_components TEXT NOT NULL,
            audio_mode TEXT NOT NULL,
            audio_providers TEXT NOT NULL,
            fixed_audio_provider TEXT NOT NULL,
            voice_variant TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.commit()
    connection.close()
    Database(path)
    connection = sqlite3.connect(path)
    columns = {row[1] for row in connection.execute("PRAGMA table_info(projects)")}
    connection.close()
    assert {
        "voicevox_style_id",
        "voicevox_style_label",
        "voicevox_speed_scale",
        "voicevox_pitch_scale",
        "voicevox_intonation_scale",
        "voicevox_volume_scale",
        "voicevox_pause_length_scale",
    } <= columns


def test_existing_database_is_migrated_with_structure_variation_columns(tmp_path: Path) -> None:
    path = tmp_path / "legacy-structures.db"
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, template_key TEXT NOT NULL, topic TEXT NOT NULL DEFAULT '',
            creation_mode TEXT NOT NULL, front_components TEXT NOT NULL, back_components TEXT NOT NULL,
            audio_mode TEXT NOT NULL, audio_providers TEXT NOT NULL, fixed_audio_provider TEXT NOT NULL,
            voice_variant TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL, word TEXT NOT NULL,
            reading TEXT NOT NULL DEFAULT '', romanization TEXT NOT NULL DEFAULT '', translation TEXT NOT NULL DEFAULT '',
            example TEXT NOT NULL DEFAULT '', example_reading TEXT NOT NULL DEFAULT '', example_translation TEXT NOT NULL DEFAULT '',
            explanation TEXT NOT NULL DEFAULT '', mnemonic TEXT NOT NULL DEFAULT '', part_of_speech TEXT NOT NULL DEFAULT '',
            level TEXT NOT NULL DEFAULT '', tags TEXT NOT NULL DEFAULT '[]', image_search_terms TEXT NOT NULL DEFAULT '[]',
            image_path TEXT NOT NULL DEFAULT '', word_audio_path TEXT NOT NULL DEFAULT '', sentence_audio_path TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )
        """
    )
    connection.commit()
    connection.close()
    Database(path)
    connection = sqlite3.connect(path)
    project_columns = {row[1] for row in connection.execute("PRAGMA table_info(projects)")}
    card_columns = {row[1] for row in connection.execute("PRAGMA table_info(cards)")}
    connection.close()
    assert {"card_structures", "structure_distribution"} <= project_columns
    assert "structure_key" in card_columns


def test_batch_update_and_delete_cards(tmp_path: Path) -> None:
    db = Database(tmp_path / "batch-cards.db")
    project_id = db.create_project(
        ProjectData(
            name="Edição em lote",
            template_key="custom",
            front_components=["word"],
            back_components=["translation"],
        )
    )
    card_ids = db.add_cards(
        project_id,
        [
            FlashcardData(word="猫", translation="gato"),
            FlashcardData(word="犬", translation="cachorro"),
            FlashcardData(word="鳥", translation="pássaro"),
        ],
    )
    first = db.get_card(card_ids[0])
    second = db.get_card(card_ids[1])
    assert first is not None and second is not None

    db.update_cards(
        [
            first.model_copy(update={"translation": "felino"}),
            second.model_copy(update={"translation": "cão"}),
        ]
    )
    assert db.get_card(card_ids[0]).translation == "felino"  # type: ignore[union-attr]
    assert db.get_card(card_ids[1]).translation == "cão"  # type: ignore[union-attr]

    db.delete_cards(card_ids[:2])
    assert db.get_card(card_ids[0]) is None
    assert db.get_card(card_ids[1]) is None
    assert db.get_card(card_ids[2]) is not None


def test_project_translation_language_roundtrip_and_legacy_default(tmp_path: Path) -> None:
    db = Database(tmp_path / "translation-language.db")
    project = ProjectData(
        name="Japanese for English speakers",
        language="ja",
        translation_language="en",
        template_key="custom",
        custom_content=["Vocabulary"],
        front_components=["word"],
        back_components=["translation"],
    )
    project_id = db.create_project(project)
    loaded = db.get_project(project_id)
    assert loaded is not None
    assert loaded.translation_language == "en"


def test_existing_database_is_migrated_with_translation_language(tmp_path: Path) -> None:
    path = tmp_path / "legacy-translation-language.db"
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, template_key TEXT NOT NULL, topic TEXT NOT NULL DEFAULT '',
            creation_mode TEXT NOT NULL, front_components TEXT NOT NULL, back_components TEXT NOT NULL,
            audio_mode TEXT NOT NULL, audio_providers TEXT NOT NULL, fixed_audio_provider TEXT NOT NULL,
            voice_variant TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )
        """
    )
    connection.commit()
    connection.close()
    Database(path)
    connection = sqlite3.connect(path)
    columns = {row[1] for row in connection.execute("PRAGMA table_info(projects)")}
    connection.close()
    assert "translation_language" in columns
