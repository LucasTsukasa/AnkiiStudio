from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

from ankiistudio.models import FlashcardData, ProjectData


class FakeModel:
    def __init__(self, model_id, name, fields, templates, css):
        self.model_id = model_id
        self.name = name
        self.fields = fields
        self.templates = templates
        self.css = css


class FakeNote:
    def __init__(self, *, model, fields, tags):
        self.model = model
        self.fields = fields
        self.tags = tags


class FakeDeck:
    def __init__(self, deck_id, name):
        self.deck_id = deck_id
        self.name = name
        self.notes = []

    def add_note(self, note):
        self.notes.append(note)


class FakePackage:
    last = None

    def __init__(self, decks):
        self.decks = decks if isinstance(decks, list) else [decks]
        self.media_files = []
        FakePackage.last = self

    def write_to_file(self, path: str):
        Path(path).write_bytes(b"fake-apkg")


def load_export_module(monkeypatch):
    fake = types.ModuleType("genanki")
    fake.Model = FakeModel
    fake.Note = FakeNote
    fake.Deck = FakeDeck
    fake.Package = FakePackage
    fake.guid_for = lambda value: f"guid:{value}"
    monkeypatch.setitem(sys.modules, "genanki", fake)

    source = Path(__file__).resolve().parents[1] / "ankiistudio" / "services" / "anki_export_service.py"
    spec = importlib.util.spec_from_file_location("anki_export_service_under_test", source)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_export_preserves_100_cards_with_duplicate_visible_content(tmp_path: Path, monkeypatch) -> None:
    module = load_export_module(monkeypatch)
    project = ProjectData(
        id=7,
        name="Japonês N5",
        template_key="hiragana",
        front_components=["word"],
        back_components=["translation"],
        deck_sections=["Palavras", "Frases"],
    )
    cards = [
        FlashcardData(id=index, project_id=7, section="Palavras" if index <= 50 else "Frases", word="同じ", translation="igual")
        for index in range(1, 101)
    ]
    output = module.AnkiExportService().export(project, cards, tmp_path / "deck.apkg")
    assert output.is_file()
    package = FakePackage.last
    assert package is not None
    assert [deck.name for deck in package.decks] == ["Japonês N5::Palavras", "Japonês N5::Frases"]
    notes = [note for deck in package.decks for note in deck.notes]
    assert len(notes) == 100
    assert len({note.guid for note in notes}) == 100


def test_export_packages_audio_using_basename(tmp_path: Path, monkeypatch) -> None:
    module = load_export_module(monkeypatch)
    audio = tmp_path / "audio" / "card.wav"
    audio.parent.mkdir()
    audio.write_bytes(b"RIFFaudio")
    project = ProjectData(
        id=3,
        name="Áudio",
        template_key="hiragana",
        front_components=["word"],
        back_components=["word_audio"],
    )
    card = FlashcardData(id=9, project_id=3, word="猫", word_audio_path=str(audio))
    module.AnkiExportService().export(project, [card], tmp_path / "audio.apkg")
    package = FakePackage.last
    note = package.decks[0].notes[0]
    assert note.fields[13] == "[sound:card.wav]"
    assert str(audio) in package.media_files


def test_export_warns_but_allows_missing_audio_when_front_has_content(tmp_path: Path, monkeypatch) -> None:
    module = load_export_module(monkeypatch)
    project = ProjectData(
        id=3,
        name="Áudio",
        template_key="hiragana",
        front_components=["word"],
        back_components=["word_audio"],
    )
    card = FlashcardData(id=9, project_id=3, word="猫", word_audio_path=str(tmp_path / "missing.wav"))
    errors, warnings = module.AnkiExportService.analyze_cards(project, [card])
    assert errors == []
    assert warnings
    output = module.AnkiExportService().export(project, [card], tmp_path / "audio.apkg")
    assert output.is_file()
    note = FakePackage.last.decks[0].notes[0]
    assert note.fields[13] == ""


def test_export_still_blocks_when_front_would_be_empty(tmp_path: Path, monkeypatch) -> None:
    module = load_export_module(monkeypatch)
    project = ProjectData(
        id=4,
        name="Imagem",
        template_key="hiragana",
        front_components=["image"],
        back_components=["translation"],
    )
    card = FlashcardData(id=10, project_id=4, word="猫", translation="gato")
    try:
        module.AnkiExportService().export(project, [card], tmp_path / "image.apkg")
    except ValueError as exc:
        assert "sem conteúdo na frente" in str(exc)
    else:
        raise AssertionError("A exportação deveria bloquear uma frente completamente vazia.")
