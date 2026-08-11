from __future__ import annotations

from pathlib import Path

import sys
import types

if "keyring" not in sys.modules:
    keyring_stub = types.ModuleType("keyring")
    keyring_stub.errors = types.SimpleNamespace(KeyringError=RuntimeError, PasswordDeleteError=RuntimeError)
    keyring_stub.get_password = lambda *args, **kwargs: None
    keyring_stub.set_password = lambda *args, **kwargs: None
    keyring_stub.delete_password = lambda *args, **kwargs: None
    sys.modules["keyring"] = keyring_stub

from ankiistudio.config import AppPaths
from ankiistudio.database import Database
from ankiistudio.models import FlashcardData, MediaAsset, ProjectData
from ankiistudio.services.audio_service import ProjectAudioService


def test_remove_audio_clears_card_asset_and_local_file(tmp_path: Path) -> None:
    paths = AppPaths(tmp_path)
    paths.ensure()
    database = Database(paths.database_path)
    project = ProjectData(
        name="Áudio",
        template_key="custom",
        front_components=["audio"],
        back_components=["word"],
    )
    project_id = database.create_project(project)
    project = database.get_project(project_id)
    card_id = database.add_cards(project_id, [FlashcardData(word="猫")])[0]
    card = database.get_card(card_id)
    assert project is not None and card is not None

    audio_dir = paths.audio_dir / f"project_{project_id}"
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio = audio_dir / "cat.wav"
    audio.write_bytes(b"RIFFfake")
    card.word_audio_path = str(audio)
    database.update_card(card)
    database.add_media_asset(
        MediaAsset(
            project_id=project_id,
            card_id=card_id,
            kind="audio",
            provider="import",
            local_path=str(audio),
        )
    )

    service = ProjectAudioService(database, paths)
    removed = service.remove_audio(card)
    assert removed.audio_path == ""
    assert not audio.exists()
    with database.connection() as connection:
        total = connection.execute(
            "SELECT COUNT(*) AS total FROM media_assets WHERE card_id=? AND kind='audio'", (card_id,)
        ).fetchone()["total"]
    assert total == 0
