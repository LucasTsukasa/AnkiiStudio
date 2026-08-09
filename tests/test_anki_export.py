from pathlib import Path

import pytest

pytest.importorskip("genanki")

from ankiistudio.models import FlashcardData, ProjectData
from ankiistudio.services.anki_export_service import AnkiExportService


def test_export_apkg(tmp_path: Path) -> None:
    project = ProjectData(
        name="Baralho Teste",
        template_key="hiragana",
        front_components=["word"],
        back_components=["translation", "reading"],
        audio_providers=["voicevox"],
    )
    card = FlashcardData(word="猫", reading="ねこ", translation="gato")
    output = AnkiExportService().export(project, [card], tmp_path / "teste.apkg")
    assert output.is_file()
    assert output.stat().st_size > 0
