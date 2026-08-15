from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from ankiistudio.models import (
    DeckThemeSettings,
    FlashcardData,
    MediaAsset,
    ProjectData,
    CreationPreset,
    utc_now_iso,
)


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connection() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    language TEXT NOT NULL DEFAULT 'ja',
                    translation_language TEXT NOT NULL DEFAULT 'pt',
                    template_key TEXT NOT NULL,
                    topic TEXT NOT NULL DEFAULT '',
                    custom_content TEXT NOT NULL DEFAULT '[]',
                    creation_mode TEXT NOT NULL,
                    front_components TEXT NOT NULL,
                    back_components TEXT NOT NULL,
                    card_structures TEXT NOT NULL DEFAULT '[]',
                    structure_distribution TEXT NOT NULL DEFAULT 'balanced_random',
                    deck_sections TEXT NOT NULL DEFAULT '[]',
                    card_theme TEXT NOT NULL DEFAULT '{}',
                    audio_mode TEXT NOT NULL,
                    audio_providers TEXT NOT NULL,
                    fixed_audio_provider TEXT NOT NULL,
                    fixed_audio_profile_id TEXT NOT NULL DEFAULT '',
                    audio_profile_preferences TEXT NOT NULL DEFAULT '{}',
                    voicevox_style_id INTEGER NOT NULL DEFAULT 0,
                    voicevox_style_label TEXT NOT NULL DEFAULT '',
                    voicevox_speed_scale REAL NOT NULL DEFAULT 1.0,
                    voicevox_pitch_scale REAL NOT NULL DEFAULT 0.0,
                    voicevox_intonation_scale REAL NOT NULL DEFAULT 1.0,
                    voicevox_volume_scale REAL NOT NULL DEFAULT 1.0,
                    voicevox_pause_length_scale REAL NOT NULL DEFAULT 1.0,
                    voice_variant TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS cards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    section TEXT NOT NULL DEFAULT '',
                    word TEXT NOT NULL,
                    reading TEXT NOT NULL DEFAULT '',
                    romanization TEXT NOT NULL DEFAULT '',
                    translation TEXT NOT NULL DEFAULT '',
                    example TEXT NOT NULL DEFAULT '',
                    example_reading TEXT NOT NULL DEFAULT '',
                    example_translation TEXT NOT NULL DEFAULT '',
                    explanation TEXT NOT NULL DEFAULT '',
                    mnemonic TEXT NOT NULL DEFAULT '',
                    part_of_speech TEXT NOT NULL DEFAULT '',
                    level TEXT NOT NULL DEFAULT '',
                    tags TEXT NOT NULL DEFAULT '[]',
                    image_search_terms TEXT NOT NULL DEFAULT '[]',
                    image_path TEXT NOT NULL DEFAULT '',
                    word_audio_path TEXT NOT NULL DEFAULT '',
                    sentence_audio_path TEXT NOT NULL DEFAULT '',
                    structure_key TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS media_assets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    card_id INTEGER,
                    kind TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    local_path TEXT NOT NULL,
                    source_title TEXT NOT NULL DEFAULT '',
                    source_url TEXT NOT NULL DEFAULT '',
                    author TEXT NOT NULL DEFAULT '',
                    license_name TEXT NOT NULL DEFAULT '',
                    license_url TEXT NOT NULL DEFAULT '',
                    modifications TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
                    FOREIGN KEY(card_id) REFERENCES cards(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS creation_presets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    payload TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_cards_project_id ON cards(project_id);
                CREATE INDEX IF NOT EXISTS idx_media_project_id ON media_assets(project_id);
                """
            )
            self._migrate(connection)

    @staticmethod
    def _migrate(connection: sqlite3.Connection) -> None:
        project_columns = {
            str(row["name"]) for row in connection.execute("PRAGMA table_info(projects)").fetchall()
        }
        project_migrations = {
            "language": "ALTER TABLE projects ADD COLUMN language TEXT NOT NULL DEFAULT 'ja'",
            "translation_language": "ALTER TABLE projects ADD COLUMN translation_language TEXT NOT NULL DEFAULT 'pt'",
            "custom_content": "ALTER TABLE projects ADD COLUMN custom_content TEXT NOT NULL DEFAULT '[]'",
            "card_structures": "ALTER TABLE projects ADD COLUMN card_structures TEXT NOT NULL DEFAULT '[]'",
            "structure_distribution": "ALTER TABLE projects ADD COLUMN structure_distribution TEXT NOT NULL DEFAULT 'balanced_random'",
            "deck_sections": "ALTER TABLE projects ADD COLUMN deck_sections TEXT NOT NULL DEFAULT '[]'",
            "card_theme": "ALTER TABLE projects ADD COLUMN card_theme TEXT NOT NULL DEFAULT '{}'",
            "fixed_audio_profile_id": "ALTER TABLE projects ADD COLUMN fixed_audio_profile_id TEXT NOT NULL DEFAULT ''",
            "audio_profile_preferences": "ALTER TABLE projects ADD COLUMN audio_profile_preferences TEXT NOT NULL DEFAULT '{}'",
            "voicevox_style_id": "ALTER TABLE projects ADD COLUMN voicevox_style_id INTEGER NOT NULL DEFAULT 0",
            "voicevox_style_label": "ALTER TABLE projects ADD COLUMN voicevox_style_label TEXT NOT NULL DEFAULT ''",
            "voicevox_speed_scale": "ALTER TABLE projects ADD COLUMN voicevox_speed_scale REAL NOT NULL DEFAULT 1.0",
            "voicevox_pitch_scale": "ALTER TABLE projects ADD COLUMN voicevox_pitch_scale REAL NOT NULL DEFAULT 0.0",
            "voicevox_intonation_scale": "ALTER TABLE projects ADD COLUMN voicevox_intonation_scale REAL NOT NULL DEFAULT 1.0",
            "voicevox_volume_scale": "ALTER TABLE projects ADD COLUMN voicevox_volume_scale REAL NOT NULL DEFAULT 1.0",
            "voicevox_pause_length_scale": "ALTER TABLE projects ADD COLUMN voicevox_pause_length_scale REAL NOT NULL DEFAULT 1.0",
        }
        for column, sql in project_migrations.items():
            if column not in project_columns:
                connection.execute(sql)

        card_columns = {
            str(row["name"]) for row in connection.execute("PRAGMA table_info(cards)").fetchall()
        }
        if "section" not in card_columns:
            connection.execute("ALTER TABLE cards ADD COLUMN section TEXT NOT NULL DEFAULT ''")
        if "structure_key" not in card_columns:
            connection.execute("ALTER TABLE cards ADD COLUMN structure_key TEXT NOT NULL DEFAULT ''")
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_cards_project_section ON cards(project_id, section)"
        )

    def create_project(self, project: ProjectData) -> int:
        with self.connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO projects (
                    name, language, translation_language, template_key, topic, custom_content, creation_mode,
                    front_components, back_components, card_structures, structure_distribution, deck_sections, card_theme,
                    audio_mode, audio_providers, fixed_audio_provider, fixed_audio_profile_id, audio_profile_preferences,
                    voicevox_style_id, voicevox_style_label, voicevox_speed_scale, voicevox_pitch_scale,
                    voicevox_intonation_scale, voicevox_volume_scale, voicevox_pause_length_scale,
                    voice_variant, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project.name,
                    project.language,
                    project.translation_language,
                    project.template_key,
                    project.topic,
                    json.dumps(project.custom_content, ensure_ascii=False),
                    project.creation_mode,
                    json.dumps(project.front_components, ensure_ascii=False),
                    json.dumps(project.back_components, ensure_ascii=False),
                    json.dumps([item.model_dump() for item in project.card_structures], ensure_ascii=False),
                    project.structure_distribution,
                    json.dumps(project.deck_sections, ensure_ascii=False),
                    project.card_theme.model_dump_json(),
                    project.audio_mode,
                    json.dumps(project.audio_providers, ensure_ascii=False),
                    project.fixed_audio_provider,
                    project.fixed_audio_profile_id,
                    json.dumps(project.audio_profile_preferences, ensure_ascii=False),
                    project.voicevox_style_id,
                    project.voicevox_style_label,
                    project.voicevox_speed_scale,
                    project.voicevox_pitch_scale,
                    project.voicevox_intonation_scale,
                    project.voicevox_volume_scale,
                    project.voicevox_pause_length_scale,
                    project.voice_variant,
                    project.created_at,
                    project.updated_at,
                ),
            )
            return int(cursor.lastrowid)

    def update_project(self, project: ProjectData) -> None:
        if project.id is None:
            raise ValueError("Projeto sem identificador.")
        project.updated_at = utc_now_iso()
        with self.connection() as connection:
            connection.execute(
                """
                UPDATE projects SET
                    name=?, language=?, translation_language=?, template_key=?, topic=?, custom_content=?, creation_mode=?,
                    front_components=?, back_components=?, card_structures=?, structure_distribution=?, deck_sections=?, card_theme=?,
                    audio_mode=?, audio_providers=?, fixed_audio_provider=?, fixed_audio_profile_id=?, audio_profile_preferences=?, voicevox_style_id=?, voicevox_style_label=?,
                    voicevox_speed_scale=?, voicevox_pitch_scale=?, voicevox_intonation_scale=?, voicevox_volume_scale=?, voicevox_pause_length_scale=?,
                    voice_variant=?, updated_at=?
                WHERE id=?
                """,
                (
                    project.name,
                    project.language,
                    project.translation_language,
                    project.template_key,
                    project.topic,
                    json.dumps(project.custom_content, ensure_ascii=False),
                    project.creation_mode,
                    json.dumps(project.front_components, ensure_ascii=False),
                    json.dumps(project.back_components, ensure_ascii=False),
                    json.dumps([item.model_dump() for item in project.card_structures], ensure_ascii=False),
                    project.structure_distribution,
                    json.dumps(project.deck_sections, ensure_ascii=False),
                    project.card_theme.model_dump_json(),
                    project.audio_mode,
                    json.dumps(project.audio_providers, ensure_ascii=False),
                    project.fixed_audio_provider,
                    project.fixed_audio_profile_id,
                    json.dumps(project.audio_profile_preferences, ensure_ascii=False),
                    project.voicevox_style_id,
                    project.voicevox_style_label,
                    project.voicevox_speed_scale,
                    project.voicevox_pitch_scale,
                    project.voicevox_intonation_scale,
                    project.voicevox_volume_scale,
                    project.voicevox_pause_length_scale,
                    project.voice_variant,
                    project.updated_at,
                    project.id,
                ),
            )

    def list_projects(self) -> list[ProjectData]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM projects ORDER BY updated_at DESC, id DESC"
            ).fetchall()
        return [self._row_to_project(row) for row in rows]

    def get_project(self, project_id: int) -> ProjectData | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM projects WHERE id=?", (project_id,)
            ).fetchone()
        return self._row_to_project(row) if row else None

    def delete_project(self, project_id: int) -> None:
        with self.connection() as connection:
            connection.execute("DELETE FROM projects WHERE id=?", (project_id,))

    def add_cards(self, project_id: int, cards: list[FlashcardData]) -> list[int]:
        ids: list[int] = []
        with self.connection() as connection:
            for card in cards:
                card.project_id = project_id
                cursor = connection.execute(
                    """
                    INSERT INTO cards (
                        project_id, section, word, reading, romanization, translation,
                        example, example_reading, example_translation, explanation,
                        mnemonic, part_of_speech, level, tags, image_search_terms,
                        image_path, word_audio_path, sentence_audio_path, structure_key, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        card.section,
                        card.word,
                        card.reading,
                        card.romanization,
                        card.translation,
                        card.example,
                        card.example_reading,
                        card.example_translation,
                        card.explanation,
                        card.mnemonic,
                        card.part_of_speech,
                        card.level,
                        json.dumps(card.tags, ensure_ascii=False),
                        json.dumps(card.image_search_terms, ensure_ascii=False),
                        card.image_path,
                        card.word_audio_path,
                        card.sentence_audio_path,
                        card.structure_key,
                        card.created_at,
                        card.updated_at,
                    ),
                )
                ids.append(int(cursor.lastrowid))
            connection.execute(
                "UPDATE projects SET updated_at=? WHERE id=?", (utc_now_iso(), project_id)
            )
        return ids

    def list_cards(self, project_id: int) -> list[FlashcardData]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM cards WHERE project_id=? ORDER BY id", (project_id,)
            ).fetchall()
        return [self._row_to_card(row) for row in rows]

    def get_first_card(self, project_id: int) -> FlashcardData | None:
        """Retorna somente o primeiro cartão do projeto.

        É usado por previews que precisam de uma única amostra e evita carregar e
        desserializar todos os cartões apenas para acessar ``cards[0]``.
        """
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM cards WHERE project_id=? ORDER BY id LIMIT 1",
                (project_id,),
            ).fetchone()
        return self._row_to_card(row) if row else None

    def list_cards_by_ids(self, project_id: int, card_ids: list[int]) -> list[FlashcardData]:
        if not card_ids:
            return []
        placeholders = ",".join("?" for _ in card_ids)
        values: list[object] = [project_id, *card_ids]
        with self.connection() as connection:
            rows = connection.execute(
                f"SELECT * FROM cards WHERE project_id=? AND id IN ({placeholders}) ORDER BY id",
                values,
            ).fetchall()
        return [self._row_to_card(row) for row in rows]

    def get_card(self, card_id: int) -> FlashcardData | None:
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM cards WHERE id=?", (card_id,)).fetchone()
        return self._row_to_card(row) if row else None

    def update_card(self, card: FlashcardData) -> None:
        if card.id is None:
            raise ValueError("Cartão sem identificador.")
        card.updated_at = utc_now_iso()
        with self.connection() as connection:
            connection.execute(
                """
                UPDATE cards SET
                    section=?, word=?, reading=?, romanization=?, translation=?, example=?,
                    example_reading=?, example_translation=?, explanation=?, mnemonic=?,
                    part_of_speech=?, level=?, tags=?, image_search_terms=?, image_path=?,
                    word_audio_path=?, sentence_audio_path=?, structure_key=?, updated_at=?
                WHERE id=?
                """,
                (
                    card.section,
                    card.word,
                    card.reading,
                    card.romanization,
                    card.translation,
                    card.example,
                    card.example_reading,
                    card.example_translation,
                    card.explanation,
                    card.mnemonic,
                    card.part_of_speech,
                    card.level,
                    json.dumps(card.tags, ensure_ascii=False),
                    json.dumps(card.image_search_terms, ensure_ascii=False),
                    card.image_path,
                    card.word_audio_path,
                    card.sentence_audio_path,
                    card.structure_key,
                    card.updated_at,
                    card.id,
                ),
            )
            connection.execute(
                "UPDATE projects SET updated_at=? WHERE id=?",
                (card.updated_at, card.project_id),
            )

    def update_card_media(
        self,
        card_id: int,
        *,
        project_id: int | None = None,
        image_path: str | None = None,
        word_audio_path: str | None = None,
        sentence_audio_path: str | None = None,
        update_image: bool = False,
        update_audio: bool = False,
    ) -> None:
        """Atualiza somente mídia, evitando lost updates entre workers concorrentes."""
        assignments: list[str] = []
        values: list[object] = []
        if update_image:
            assignments.append("image_path=?")
            values.append(image_path or "")
        if update_audio:
            assignments.extend(["word_audio_path=?", "sentence_audio_path=?"])
            values.extend([word_audio_path or "", sentence_audio_path or ""])
        if not assignments:
            return
        now = utc_now_iso()
        assignments.append("updated_at=?")
        values.append(now)
        values.append(int(card_id))
        with self.connection() as connection:
            connection.execute(
                f"UPDATE cards SET {', '.join(assignments)} WHERE id=?",
                values,
            )
            if project_id is None:
                row = connection.execute("SELECT project_id FROM cards WHERE id=?", (card_id,)).fetchone()
                project_id = int(row["project_id"]) if row and row["project_id"] is not None else None
            if project_id is not None:
                connection.execute("UPDATE projects SET updated_at=? WHERE id=?", (now, project_id))

    def replace_card_media_asset(
        self,
        card_id: int,
        asset: MediaAsset,
        *,
        project_id: int | None = None,
        image_path: str | None = None,
        word_audio_path: str | None = None,
        sentence_audio_path: str | None = None,
        update_image: bool = False,
        update_audio: bool = False,
    ) -> int:
        """Atualiza a mídia do cartão e substitui seu asset em uma única transação."""
        if not update_image and not update_audio:
            raise ValueError("Informe o tipo de mídia que deve ser atualizado.")
        if asset.card_id is not None and int(asset.card_id) != int(card_id):
            raise ValueError("O asset de mídia não pertence ao cartão informado.")

        assignments: list[str] = []
        values: list[object] = []
        if update_image:
            assignments.append("image_path=?")
            values.append(image_path or "")
        if update_audio:
            assignments.extend(["word_audio_path=?", "sentence_audio_path=?"])
            values.extend([word_audio_path or "", sentence_audio_path or ""])
        now = utc_now_iso()
        assignments.append("updated_at=?")
        values.extend([now, int(card_id)])

        with self.connection() as connection:
            connection.execute(
                f"UPDATE cards SET {', '.join(assignments)} WHERE id=?",
                values,
            )
            resolved_project_id = project_id or asset.project_id
            if resolved_project_id is None:
                row = connection.execute(
                    "SELECT project_id FROM cards WHERE id=?", (card_id,)
                ).fetchone()
                resolved_project_id = int(row["project_id"]) if row else None
            if resolved_project_id is not None:
                connection.execute(
                    "UPDATE projects SET updated_at=? WHERE id=?",
                    (now, int(resolved_project_id)),
                )
            connection.execute(
                "DELETE FROM media_assets WHERE card_id=? AND kind=?",
                (card_id, asset.kind),
            )
            cursor = self._insert_media_asset(connection, asset)
            return int(cursor.lastrowid)

    def clear_card_media_asset(
        self,
        card_id: int,
        kind: str,
        *,
        project_id: int | None = None,
        image_path: str | None = None,
        word_audio_path: str | None = None,
        sentence_audio_path: str | None = None,
        update_image: bool = False,
        update_audio: bool = False,
    ) -> None:
        """Limpa a mídia e o asset correspondente de forma atômica."""
        assignments: list[str] = []
        values: list[object] = []
        if update_image:
            assignments.append("image_path=?")
            values.append(image_path or "")
        if update_audio:
            assignments.extend(["word_audio_path=?", "sentence_audio_path=?"])
            values.extend([word_audio_path or "", sentence_audio_path or ""])
        if not assignments:
            raise ValueError("Informe o tipo de mídia que deve ser atualizado.")
        now = utc_now_iso()
        assignments.append("updated_at=?")
        values.extend([now, int(card_id)])
        with self.connection() as connection:
            connection.execute(
                f"UPDATE cards SET {', '.join(assignments)} WHERE id=?",
                values,
            )
            if project_id is None:
                row = connection.execute(
                    "SELECT project_id FROM cards WHERE id=?", (card_id,)
                ).fetchone()
                project_id = int(row["project_id"]) if row else None
            if project_id is not None:
                connection.execute(
                    "UPDATE projects SET updated_at=? WHERE id=?", (now, int(project_id))
                )
            connection.execute(
                "DELETE FROM media_assets WHERE card_id=? AND kind=?",
                (card_id, kind),
            )

    def count_cards(self, project_id: int) -> int:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS total FROM cards WHERE project_id=?", (project_id,)
            ).fetchone()
        return int(row["total"] if row else 0)

    def project_card_counts(self) -> dict[int, int]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT project_id, COUNT(*) AS total FROM cards GROUP BY project_id"
            ).fetchall()
        return {int(row["project_id"]): int(row["total"]) for row in rows}

    def project_section_counts(self, project_id: int) -> dict[str, int]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT section, COUNT(*) AS total
                FROM cards
                WHERE project_id=?
                GROUP BY section
                """,
                (project_id,),
            ).fetchall()
        return {str(row["section"]): int(row["total"]) for row in rows}

    def list_card_sections(self, project_id: int) -> list[str]:
        """Lista seções na ordem em que aparecem pela primeira vez no projeto."""
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT section, MIN(id) AS first_id
                FROM cards
                WHERE project_id=? AND TRIM(section) <> ''
                GROUP BY section
                ORDER BY first_id
                """,
                (project_id,),
            ).fetchall()

        result: list[str] = []
        seen: set[str] = set()
        for row in rows:
            section = str(row["section"]).strip()
            key = section.casefold()
            if not section or key in seen:
                continue
            seen.add(key)
            result.append(section)
        return result

    def list_creation_presets(self) -> list[CreationPreset]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM creation_presets ORDER BY name COLLATE NOCASE"
            ).fetchall()
        return [
            CreationPreset(
                id=row["id"], name=row["name"], payload=json.loads(row["payload"] or "{}"),
                created_at=row["created_at"], updated_at=row["updated_at"]
            ) for row in rows
        ]

    def save_creation_preset(self, preset: CreationPreset) -> int:
        now = utc_now_iso()
        with self.connection() as connection:
            if preset.id is None:
                cursor = connection.execute(
                    """INSERT INTO creation_presets(name, payload, created_at, updated_at)
                       VALUES (?, ?, ?, ?)""",
                    (preset.name.strip(), json.dumps(preset.payload, ensure_ascii=False), now, now),
                )
                preset.id = int(cursor.lastrowid)
                preset.created_at = now
            else:
                connection.execute(
                    "UPDATE creation_presets SET name=?, payload=?, updated_at=? WHERE id=?",
                    (preset.name.strip(), json.dumps(preset.payload, ensure_ascii=False), now, preset.id),
                )
            preset.updated_at = now
        return int(preset.id)

    def delete_creation_preset(self, preset_id: int) -> None:
        with self.connection() as connection:
            connection.execute("DELETE FROM creation_presets WHERE id=?", (preset_id,))

    def rename_card_section(self, project_id: int, old_name: str, new_name: str) -> None:
        with self.connection() as connection:
            connection.execute(
                "UPDATE cards SET section=?, updated_at=? WHERE project_id=? AND section=?",
                (new_name, utc_now_iso(), project_id, old_name),
            )

    def clear_card_section(self, project_id: int, section: str) -> None:
        with self.connection() as connection:
            connection.execute(
                "UPDATE cards SET section='', updated_at=? WHERE project_id=? AND section=?",
                (utc_now_iso(), project_id, section),
            )

    def delete_card(self, card_id: int) -> None:
        self.delete_cards([card_id])

    def delete_cards(self, card_ids: list[int]) -> None:
        ids = sorted({int(card_id) for card_id in card_ids if int(card_id) > 0})
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        with self.connection() as connection:
            connection.execute(f"DELETE FROM cards WHERE id IN ({placeholders})", ids)

    def update_cards(self, cards: list[FlashcardData]) -> None:
        if not cards:
            return
        project_ids: set[int] = set()
        with self.connection() as connection:
            for card in cards:
                if card.id is None:
                    raise ValueError("Cartão sem identificador.")
                card.updated_at = utc_now_iso()
                connection.execute(
                    """
                    UPDATE cards SET
                        section=?, word=?, reading=?, romanization=?, translation=?, example=?,
                        example_reading=?, example_translation=?, explanation=?, mnemonic=?,
                        part_of_speech=?, level=?, tags=?, image_search_terms=?, image_path=?,
                        word_audio_path=?, sentence_audio_path=?, structure_key=?, updated_at=?
                    WHERE id=?
                    """,
                    (
                        card.section, card.word, card.reading, card.romanization, card.translation,
                        card.example, card.example_reading, card.example_translation, card.explanation,
                        card.mnemonic, card.part_of_speech, card.level,
                        json.dumps(card.tags, ensure_ascii=False),
                        json.dumps(card.image_search_terms, ensure_ascii=False),
                        card.image_path, card.word_audio_path, card.sentence_audio_path,
                        card.structure_key, card.updated_at, card.id,
                    ),
                )
                if card.project_id is not None:
                    project_ids.add(int(card.project_id))
            now = utc_now_iso()
            for project_id in project_ids:
                connection.execute("UPDATE projects SET updated_at=? WHERE id=?", (now, project_id))

    def delete_media_assets_for_card(self, card_id: int, kind: str | None = None) -> None:
        with self.connection() as connection:
            if kind:
                connection.execute(
                    "DELETE FROM media_assets WHERE card_id=? AND kind=?", (card_id, kind)
                )
            else:
                connection.execute("DELETE FROM media_assets WHERE card_id=?", (card_id,))

    def count_card_media_path_references(self, path: str, kind: str) -> int:
        if not path:
            return 0
        with self.connection() as connection:
            if kind == "image":
                row = connection.execute(
                    "SELECT COUNT(*) AS total FROM cards WHERE image_path=?", (path,)
                ).fetchone()
            elif kind == "audio":
                row = connection.execute(
                    "SELECT COUNT(*) AS total FROM cards WHERE word_audio_path=? OR sentence_audio_path=?",
                    (path, path),
                ).fetchone()
            else:
                raise ValueError("Tipo de mídia inválido.")
        return int(row["total"] if row else 0)

    def add_media_asset(self, asset: MediaAsset) -> int:
        with self.connection() as connection:
            cursor = self._insert_media_asset(connection, asset)
            return int(cursor.lastrowid)

    def add_media_assets(self, assets: list[MediaAsset]) -> list[int]:
        """Insere vários assets em uma única transação SQLite."""
        if not assets:
            return []
        ids: list[int] = []
        with self.connection() as connection:
            for asset in assets:
                cursor = self._insert_media_asset(connection, asset)
                ids.append(int(cursor.lastrowid))
        return ids

    @staticmethod
    def _insert_media_asset(connection: sqlite3.Connection, asset: MediaAsset) -> sqlite3.Cursor:
        return connection.execute(
            """
            INSERT INTO media_assets (
                project_id, card_id, kind, provider, local_path,
                source_title, source_url, author, license_name,
                license_url, modifications, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                asset.project_id,
                asset.card_id,
                asset.kind,
                asset.provider,
                asset.local_path,
                asset.source_title,
                asset.source_url,
                asset.author,
                asset.license_name,
                asset.license_url,
                asset.modifications,
                asset.metadata_json,
                asset.created_at,
            ),
        )

    def list_media_assets_for_project(self, project_id: int) -> list[MediaAsset]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM media_assets WHERE project_id=? ORDER BY id", (project_id,)
            ).fetchall()
        return [MediaAsset(**dict(row)) for row in rows]

    def count_media_assets(self) -> int:
        with self.connection() as connection:
            row = connection.execute("SELECT COUNT(*) AS total FROM media_assets").fetchone()
        return int(row["total"] if row else 0)

    def get_setting(self, key: str, default: str = "") -> str:
        with self.connection() as connection:
            row = connection.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return str(row["value"]) if row else default

    def set_setting(self, key: str, value: str) -> None:
        self.set_settings({key: value})

    def set_settings(self, values: dict[str, str]) -> None:
        """Persiste um conjunto de configurações em uma única transação."""
        if not values:
            return
        with self.connection() as connection:
            connection.executemany(
                """
                INSERT INTO settings(key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                list(values.items()),
            )

    @staticmethod
    def _row_to_project(row: sqlite3.Row) -> ProjectData:
        theme_raw = row["card_theme"] if "card_theme" in row.keys() else "{}"
        try:
            theme = DeckThemeSettings.model_validate_json(theme_raw or "{}")
        except Exception:
            theme = DeckThemeSettings()
        return ProjectData(
            id=row["id"],
            name=row["name"],
            language=row["language"] if "language" in row.keys() else "ja",
            translation_language=row["translation_language"] if "translation_language" in row.keys() else "pt",
            template_key=row["template_key"],
            topic=row["topic"],
            custom_content=json.loads(row["custom_content"]) if "custom_content" in row.keys() else [],
            creation_mode=row["creation_mode"],
            front_components=json.loads(row["front_components"]),
            back_components=json.loads(row["back_components"]),
            card_structures=json.loads(row["card_structures"]) if "card_structures" in row.keys() else [],
            structure_distribution=row["structure_distribution"] if "structure_distribution" in row.keys() else "balanced_random",
            deck_sections=json.loads(row["deck_sections"]) if "deck_sections" in row.keys() else [],
            card_theme=theme,
            audio_mode=row["audio_mode"],
            audio_providers=json.loads(row["audio_providers"]),
            fixed_audio_provider=row["fixed_audio_provider"],
            fixed_audio_profile_id=row["fixed_audio_profile_id"] if "fixed_audio_profile_id" in row.keys() else "",
            audio_profile_preferences=json.loads(row["audio_profile_preferences"] or "{}") if "audio_profile_preferences" in row.keys() else {},
            voicevox_style_id=int(row["voicevox_style_id"]) if "voicevox_style_id" in row.keys() else 0,
            voicevox_style_label=row["voicevox_style_label"] if "voicevox_style_label" in row.keys() else "",
            voicevox_speed_scale=float(row["voicevox_speed_scale"]) if "voicevox_speed_scale" in row.keys() else 1.0,
            voicevox_pitch_scale=float(row["voicevox_pitch_scale"]) if "voicevox_pitch_scale" in row.keys() else 0.0,
            voicevox_intonation_scale=float(row["voicevox_intonation_scale"]) if "voicevox_intonation_scale" in row.keys() else 1.0,
            voicevox_volume_scale=float(row["voicevox_volume_scale"]) if "voicevox_volume_scale" in row.keys() else 1.0,
            voicevox_pause_length_scale=float(row["voicevox_pause_length_scale"]) if "voicevox_pause_length_scale" in row.keys() else 1.0,
            voice_variant=row["voice_variant"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_card(row: sqlite3.Row) -> FlashcardData:
        return FlashcardData(
            id=row["id"],
            project_id=row["project_id"],
            section=row["section"] if "section" in row.keys() else "",
            word=row["word"],
            reading=row["reading"],
            romanization=row["romanization"],
            translation=row["translation"],
            example=row["example"],
            example_reading=row["example_reading"],
            example_translation=row["example_translation"],
            explanation=row["explanation"],
            mnemonic=row["mnemonic"],
            part_of_speech=row["part_of_speech"],
            level=row["level"],
            tags=json.loads(row["tags"]),
            image_search_terms=json.loads(row["image_search_terms"]),
            image_path=row["image_path"],
            word_audio_path=row["word_audio_path"],
            sentence_audio_path=row["sentence_audio_path"],
            structure_key=row["structure_key"] if "structure_key" in row.keys() else "",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
