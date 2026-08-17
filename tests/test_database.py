import sqlite3

import pytest
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
            reading_size=23,
            romanization_size=16,
            translation_size=32,
            example_size=24,
            explanation_size=18,
            mnemonic_size=19,
            image_max_height=260,
            card_max_width=650,
            card_padding=15,
            component_spacing=7,
            layout_density="custom",
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
    assert loaded.card_theme.reading_size == 23
    assert loaded.card_theme.image_max_height == 260
    assert loaded.card_theme.card_max_width == 650
    assert loaded.card_theme.layout_density == "custom"
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
    assert "audio_profile_preferences" in columns


def test_partial_media_updates_preserve_concurrent_image_and_audio(tmp_path: Path) -> None:
    db = Database(tmp_path / "media-concurrency.db")
    project_id = db.create_project(
        ProjectData(
            name="Concorrência",
            template_key="custom",
            front_components=["word", "image"],
            back_components=["translation", "audio"],
            audio_providers=["voicevox"],
        )
    )
    card_id = db.add_cards(project_id, [FlashcardData(word="猫", translation="gato")])[0]

    # Simula dois workers que partiram do mesmo snapshot antigo do cartão.
    image_snapshot = db.get_card(card_id)
    audio_snapshot = db.get_card(card_id)
    assert image_snapshot is not None and audio_snapshot is not None

    db.update_card_media(
        card_id,
        project_id=project_id,
        image_path="images/cat.webp",
        update_image=True,
    )
    db.update_card_media(
        card_id,
        project_id=project_id,
        word_audio_path="audio/cat.wav",
        sentence_audio_path="",
        update_audio=True,
    )

    loaded = db.get_card(card_id)
    assert loaded is not None
    assert loaded.image_path == "images/cat.webp"
    assert loaded.word_audio_path == "audio/cat.wav"


def test_partial_media_updates_are_safe_from_two_threads(tmp_path: Path) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    db = Database(tmp_path / "media-real-concurrency.db")
    project_id = db.create_project(
        ProjectData(
            name="Concorrência real",
            template_key="custom",
            front_components=["word", "image"],
            back_components=["translation", "audio"],
            audio_providers=["voicevox"],
        )
    )
    card_id = db.add_cards(project_id, [FlashcardData(word="猫", translation="gato")])[0]
    barrier = Barrier(2)

    def write_image() -> None:
        barrier.wait()
        db.update_card_media(
            card_id, project_id=project_id, image_path="images/thread-cat.webp", update_image=True
        )

    def write_audio() -> None:
        barrier.wait()
        db.update_card_media(
            card_id, project_id=project_id, word_audio_path="audio/thread-cat.wav", update_audio=True
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda fn: fn(), [write_image, write_audio]))

    loaded = db.get_card(card_id)
    assert loaded is not None
    assert loaded.image_path == "images/thread-cat.webp"
    assert loaded.word_audio_path == "audio/thread-cat.wav"


def test_creation_presets_roundtrip(tmp_path: Path) -> None:
    from ankiistudio.models import CreationPreset

    db = Database(tmp_path / "presets.db")
    preset = CreationPreset(
        name="Japonês — Vocabulário",
        payload={"language": "ja", "quantity_mode": "automatic", "audio_mode": "intelligent"},
    )
    preset_id = db.save_creation_preset(preset)
    loaded = db.list_creation_presets()
    assert len(loaded) == 1
    assert loaded[0].id == preset_id
    assert loaded[0].payload["quantity_mode"] == "automatic"

    loaded[0].payload["language"] = "en"
    db.save_creation_preset(loaded[0])
    assert db.list_creation_presets()[0].payload["language"] == "en"

    db.delete_creation_preset(preset_id)
    assert db.list_creation_presets() == []


def test_audio_profile_preferences_roundtrip(tmp_path: Path) -> None:
    db = Database(tmp_path / "audio-preferences.db")
    project = ProjectData(
        name="Preferências de áudio",
        language="en",
        template_key="custom",
        creation_mode="manual",
        front_components=["word"],
        back_components=["audio"],
        audio_providers=["gemini", "elevenlabs"],
        audio_profile_preferences={"gemini": "gemini-profile", "elevenlabs": "eleven-profile"},
    )
    project_id = db.create_project(project)
    loaded = db.get_project(project_id)
    assert loaded is not None
    assert loaded.audio_profile_preferences == {
        "gemini": "gemini-profile",
        "elevenlabs": "eleven-profile",
    }


def test_set_settings_persists_multiple_values_with_one_connection(tmp_path: Path) -> None:
    from contextlib import contextmanager

    db = Database(tmp_path / "settings-batch.db")
    original_connection = db.connection
    calls = 0

    @contextmanager
    def counted_connection():
        nonlocal calls
        calls += 1
        with original_connection() as connection:
            yield connection

    db.connection = counted_connection  # type: ignore[method-assign]
    db.set_settings({"one": "1", "two": "2", "three": "3"})

    assert calls == 1
    assert db.get_setting("one") == "1"
    assert db.get_setting("two") == "2"
    assert db.get_setting("three") == "3"


def test_add_media_assets_inserts_batch_with_one_connection(tmp_path: Path) -> None:
    from contextlib import contextmanager
    from ankiistudio.models import MediaAsset

    db = Database(tmp_path / "media-batch.db")
    project_id = db.create_project(
        ProjectData(
            name="Batch",
            template_key="custom",
            front_components=["word"],
            back_components=["translation"],
        )
    )
    card_ids = db.add_cards(project_id, [FlashcardData(word="a"), FlashcardData(word="b")])
    assets = [
        MediaAsset(project_id=project_id, card_id=card_ids[0], kind="image", provider="test", local_path="a.webp"),
        MediaAsset(project_id=project_id, card_id=card_ids[1], kind="audio", provider="test", local_path="b.mp3"),
    ]
    original_connection = db.connection
    calls = 0

    @contextmanager
    def counted_connection():
        nonlocal calls
        calls += 1
        with original_connection() as connection:
            yield connection

    db.connection = counted_connection  # type: ignore[method-assign]
    ids = db.add_media_assets(assets)

    assert calls == 1
    assert len(ids) == 2
    assert len(db.list_media_assets_for_project(project_id)) == 2



def test_lightweight_project_summaries_and_choices(tmp_path: Path) -> None:
    db = Database(tmp_path / "summaries.db")
    project_ids: list[int] = []
    for index in range(12):
        project_ids.append(
            db.create_project(
                ProjectData(
                    name=f"Projeto {index}",
                    language="ja" if index % 2 == 0 else "en",
                    template_key="custom",
                    topic=f"Tópico {index}",
                    custom_content=["conteúdo detalhado"],
                    front_components=["word"],
                    back_components=["translation"],
                )
            )
        )
    db.add_cards(
        project_ids[-1],
        [
            FlashcardData(word="a"),
            FlashcardData(word="b"),
            FlashcardData(word="c"),
        ],
    )

    summaries = db.list_project_summaries(limit=10)
    assert len(summaries) == 10
    assert summaries[0].id == project_ids[-1]
    assert summaries[0].card_count == 3
    assert summaries[0].name == "Projeto 11"
    assert not hasattr(summaries[0], "front_components")

    choices = db.list_project_choices()
    assert len(choices) == 12
    assert choices[0].id == project_ids[-1]
    assert choices[0].name == "Projeto 11"
    assert not hasattr(choices[0], "topic")


def test_card_summaries_only_load_table_fields(tmp_path: Path) -> None:
    db = Database(tmp_path / "card-summaries.db")
    project_id = db.create_project(
        ProjectData(
            name="Resumos",
            template_key="custom",
            front_components=["word", "image"],
            back_components=["translation", "audio"],
        )
    )
    card_id = db.add_cards(
        project_id,
        [
            FlashcardData(
                word="猫",
                translation="gato",
                explanation="explicação grande",
                mnemonic="mnemônico grande",
                tags=["animal", "n5"],
                image_search_terms=["domestic cat"],
                image_path="images/cat.webp",
                word_audio_path="audio/cat.mp3",
                structure_key="default",
            )
        ],
    )[0]

    summaries = db.list_card_summaries(project_id)
    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.id == card_id
    assert summary.word == "猫"
    assert summary.translation == "gato"
    assert summary.audio_path == "audio/cat.mp3"
    assert not hasattr(summary, "explanation")
    assert not hasattr(summary, "tags")

    by_id = db.get_card_summary(card_id)
    assert by_id == summary
    assert db.list_card_summaries_by_ids(project_id, [card_id]) == [summary]


def test_media_card_kind_index_exists(tmp_path: Path) -> None:
    path = tmp_path / "media-index.db"
    Database(path)
    connection = sqlite3.connect(path)
    try:
        columns = [
            row[2]
            for row in connection.execute("PRAGMA index_info(idx_media_card_kind)").fetchall()
        ]
    finally:
        connection.close()
    assert columns == ["card_id", "kind"]


def test_settings_prefix_listing_and_batch_delete(tmp_path: Path) -> None:
    db = Database(tmp_path / "settings-prefix.db")
    db.set_settings(
        {
            "image_api_cache_pixabay_a": "a",
            "image_api_cache_pixabay_b": "b",
            "image_source_pixabay": "1",
        }
    )
    cached = db.list_settings_with_prefix("image_api_cache_pixabay_")
    assert cached == {
        "image_api_cache_pixabay_a": "a",
        "image_api_cache_pixabay_b": "b",
    }
    db.delete_settings(list(cached))
    assert db.list_settings_with_prefix("image_api_cache_pixabay_") == {}
    assert db.get_setting("image_source_pixabay") == "1"


def test_save_project_changes_is_atomic_for_theme_audio_cards_and_sections(tmp_path: Path) -> None:
    db = Database(tmp_path / "project-save.db")
    project_id = db.create_project(
        ProjectData(
            name="Projeto",
            template_key="custom",
            front_components=["word"],
            back_components=["translation"],
            deck_sections=["Antiga", "Remover"],
            audio_mode="intelligent",
            audio_providers=["voicevox"],
        )
    )
    card_ids = db.add_cards(
        project_id,
        [
            FlashcardData(word="猫", translation="gato", section="Antiga"),
            FlashcardData(word="犬", translation="cachorro", section="Remover"),
        ],
    )
    project = db.get_project(project_id)
    first = db.get_card(card_ids[0])
    assert project is not None and first is not None

    project.card_theme = DeckThemeSettings(
        background="#112233",
        card_background="#223344",
        primary="#33AA66",
        text="#FFFFFF",
        secondary_text="#CCCCCC",
        border="#445566",
        word_size=54,
        layout_density="custom",
    )
    project.deck_sections = ["Nova"]
    project.audio_mode = "random"
    project.audio_providers = ["gemini", "voicevox"]
    first = first.model_copy(update={"translation": "felino"})

    db.save_project_changes(
        project,
        [first],
        section_renames=[("Antiga", "Nova")],
        cleared_sections=["Remover"],
    )

    loaded = db.get_project(project_id)
    cards = db.list_cards(project_id)
    assert loaded is not None
    assert loaded.card_theme.background == "#112233"
    assert loaded.card_theme.word_size == 54
    assert loaded.audio_mode == "random"
    assert loaded.audio_providers == ["gemini", "voicevox"]
    assert loaded.deck_sections == ["Nova"]
    by_word = {card.word: card for card in cards}
    assert by_word["猫"].translation == "felino"
    assert by_word["猫"].section == "Nova"
    assert by_word["犬"].section == ""



def test_save_project_changes_applies_section_rename_chains_simultaneously(tmp_path: Path) -> None:
    db = Database(tmp_path / "project-save-section-chain.db")
    project_id = db.create_project(
        ProjectData(
            name="Projeto",
            template_key="custom",
            front_components=["word"],
            back_components=["translation"],
            deck_sections=["A", "B"],
        )
    )
    db.add_cards(
        project_id,
        [
            FlashcardData(word="um", translation="1", section="A"),
            FlashcardData(word="dois", translation="2", section="B"),
        ],
    )
    project = db.get_project(project_id)
    assert project is not None
    project.deck_sections = ["B", "C"]

    db.save_project_changes(
        project,
        section_renames=[("A", "B"), ("B", "C")],
    )

    by_word = {card.word: card for card in db.list_cards(project_id)}
    assert by_word["um"].section == "B"
    assert by_word["dois"].section == "C"

def test_save_project_changes_rolls_back_everything_on_failure(tmp_path: Path) -> None:
    db = Database(tmp_path / "project-save-rollback.db")
    project_id = db.create_project(
        ProjectData(
            name="Original",
            template_key="custom",
            front_components=["word"],
            back_components=["translation"],
        )
    )
    card_id = db.add_cards(project_id, [FlashcardData(word="猫", translation="gato")])[0]
    project = db.get_project(project_id)
    card = db.get_card(card_id)
    assert project is not None and card is not None

    project.name = "Alterado"
    card.translation = "não deve persistir"
    with db.connection() as connection:
        connection.execute(
            """
            CREATE TRIGGER fail_card_update
            BEFORE UPDATE ON cards
            BEGIN
                SELECT RAISE(ABORT, 'falha simulada');
            END
            """
        )

    with pytest.raises(sqlite3.DatabaseError, match="falha simulada"):
        db.save_project_changes(project, [card])

    assert db.get_project(project_id).name == "Original"  # type: ignore[union-attr]
    assert db.get_card(card_id).translation == "gato"  # type: ignore[union-attr]
