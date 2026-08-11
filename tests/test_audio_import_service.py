from pathlib import Path
from types import SimpleNamespace

import sys
import types

if "keyring" not in sys.modules:
    keyring_stub = types.ModuleType("keyring")
    keyring_stub.errors = types.SimpleNamespace(KeyringError=RuntimeError, PasswordDeleteError=RuntimeError)
    keyring_stub.get_password = lambda *args, **kwargs: None
    keyring_stub.set_password = lambda *args, **kwargs: None
    keyring_stub.delete_password = lambda *args, **kwargs: None
    sys.modules["keyring"] = keyring_stub

if "google.genai" not in sys.modules:
    genai_stub = types.ModuleType("google.genai")
    genai_stub.Client = object
    sys.modules["google.genai"] = genai_stub

from ankiistudio.database import Database
from ankiistudio.models import CardStructureVariation, FlashcardData, ProjectData
from ankiistudio.services.audio_import_service import AudioImportService, normalize_match_text
from ankiistudio.services.audio_service import ProjectAudioService


def _setup(tmp_path: Path):
    db = Database(tmp_path / "audio-import.sqlite")
    project = ProjectData(
        name="Áudio importado",
        language="ja",
        template_key="custom",
        custom_content=["Kana"],
        front_components=["word"],
        back_components=["audio"],
        card_structures=[
            CardStructureVariation(key="audio", name="Áudio", front_components=["word"], back_components=["audio"]),
            CardStructureVariation(key="no-audio", name="Sem áudio", front_components=["word"], back_components=["translation"]),
        ],
    )
    project_id = db.create_project(project)
    ids = db.add_cards(
        project_id,
        [
            FlashcardData(word="あ", reading="あ", romanization="a", translation="A", structure_key="audio"),
            FlashcardData(word="い", reading="い", romanization="i", translation="I", structure_key="audio"),
            FlashcardData(word="う", reading="う", romanization="u", translation="U", structure_key="no-audio"),
        ],
    )
    loaded = db.get_project(project_id)
    assert loaded is not None
    audio_service = ProjectAudioService(db, SimpleNamespace(audio_dir=tmp_path / "media" / "audio"))
    return db, loaded, [db.get_card(i) for i in ids], AudioImportService(audio_service)


def test_filename_matches_primary_content_and_ignores_cards_without_audio(tmp_path: Path) -> None:
    _db, project, cards, service = _setup(tmp_path)
    f1 = tmp_path / "あ.wav"; f1.write_bytes(b"RIFF-a")
    f2 = tmp_path / "う.wav"; f2.write_bytes(b"RIFF-u")
    matches = service.preview(project, [card for card in cards if card], [f1, f2], "word")
    assert matches[0].matched and matches[0].card_word == "あ"
    assert matches[1].status == "unmatched"


def test_matching_can_use_romanization(tmp_path: Path) -> None:
    _db, project, cards, service = _setup(tmp_path)
    source = tmp_path / "A.WAV"; source.write_bytes(b"RIFF-a")
    match = service.preview(project, [card for card in cards if card], [source], "romanization")[0]
    assert match.matched
    assert match.card_word == "あ"


def test_unicode_and_whitespace_are_normalized_for_matching() -> None:
    assert normalize_match_text("  Ａ  ") == normalize_match_text("a")
    assert normalize_match_text("ガ") == normalize_match_text("ガ")


def test_batch_apply_copies_audio_and_respects_skip_policy(tmp_path: Path) -> None:
    db, project, cards, service = _setup(tmp_path)
    source = tmp_path / "あ.wav"; source.write_bytes(b"RIFF-imported")
    matches = service.preview(project, [card for card in cards if card], [source], "word")
    first = service.apply(project, matches, conflict_policy="replace")
    assert first.imported == 1
    card = db.get_card(int(matches[0].card_id))
    assert card is not None and Path(card.audio_path).is_file()

    matches_again = service.preview(project, [db.get_card(int(matches[0].card_id))], [source], "word")
    second = service.apply(project, matches_again, conflict_policy="skip")
    assert second.imported == 0
    assert second.skipped_existing == 1


def test_duplicate_files_for_same_card_are_marked_ambiguous(tmp_path: Path) -> None:
    _db, project, cards, service = _setup(tmp_path)
    a = tmp_path / "x" / "あ.wav"; a.parent.mkdir(); a.write_bytes(b"a")
    b = tmp_path / "y" / "あ.mp3"; b.parent.mkdir(); b.write_bytes(b"b")
    matches = service.preview(project, [card for card in cards if card], [a, b], "word")
    assert [item.status for item in matches] == ["ambiguous", "ambiguous"]
