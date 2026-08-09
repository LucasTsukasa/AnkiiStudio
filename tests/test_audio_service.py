from pathlib import Path
from types import SimpleNamespace

import pytest

import sys
import types

# O ambiente de CI desta entrega não contém os SDKs externos opcionais.
# Estes stubs permitem testar a lógica de orquestração sem chamar serviços reais.
if "keyring" not in sys.modules:
    keyring_stub = types.ModuleType("keyring")
    keyring_stub.errors = types.SimpleNamespace(
        KeyringError=RuntimeError, PasswordDeleteError=RuntimeError
    )
    keyring_stub.get_password = lambda *args, **kwargs: None
    keyring_stub.set_password = lambda *args, **kwargs: None
    keyring_stub.delete_password = lambda *args, **kwargs: None
    sys.modules["keyring"] = keyring_stub

if "google.genai" not in sys.modules:
    genai_stub = types.ModuleType("google.genai")
    genai_stub.Client = object
    sys.modules["google.genai"] = genai_stub


from ankiistudio.database import Database
from ankiistudio.models import FlashcardData, ProjectData
from ankiistudio.services.audio.base import AudioGenerationResult
from ankiistudio.services.audio_service import ProjectAudioService


class FakeRouter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def generate(self, *, text, destination_stem, project, content_kind):
        self.calls.append((text, content_kind))
        path = destination_stem.with_suffix(".wav")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"RIFFfake-audio")
        return AudioGenerationResult(provider="fake", local_path=str(path))


def test_audio_regenerates_stale_path_and_only_required_type(tmp_path: Path, monkeypatch) -> None:
    database = Database(tmp_path / "db.sqlite")
    project = ProjectData(
        name="Audio",
        template_key="hiragana",
        front_components=["word"],
        back_components=["audio"],
        audio_providers=["fake"],
    )
    project_id = database.create_project(project)
    project = database.get_project(project_id)
    assert project is not None
    card_id = database.add_cards(
        project_id,
        [
            FlashcardData(
                word="猫",
                word_audio_path=str(tmp_path / "arquivo_que_sumiu.wav"),
                sentence_audio_path=str(tmp_path / "frase_que_sumiu.wav"),
            )
        ],
    )[0]
    card = database.get_card(card_id)
    assert card is not None

    paths = SimpleNamespace(audio_dir=tmp_path / "audio")
    service = ProjectAudioService(database, paths)
    router = FakeRouter()
    monkeypatch.setattr(service, "_build_router", lambda _project: router)

    updated = service.generate_for_card(project, card)
    assert Path(updated.word_audio_path).is_file()
    assert Path(updated.word_audio_path).stat().st_size > 0
    assert updated.sentence_audio_path == ""
    assert router.calls == [("猫", "content")]
    assert service.audio_status(project, updated) == (True, [])


def test_audio_requires_component_in_structure(tmp_path: Path) -> None:
    database = Database(tmp_path / "db.sqlite")
    project = ProjectData(
        name="Sem áudio",
        template_key="hiragana",
        front_components=["word"],
        back_components=["translation"],
    )
    project_id = database.create_project(project)
    project = database.get_project(project_id)
    card_id = database.add_cards(project_id, [FlashcardData(word="猫")])[0]
    card = database.get_card(card_id)
    assert project is not None and card is not None
    service = ProjectAudioService(database, SimpleNamespace(audio_dir=tmp_path / "audio"))
    with pytest.raises(ValueError, match="não utiliza Áudio"):
        service.generate_for_card(project, card)


def test_legacy_sentence_audio_file_is_reused_as_single_audio(tmp_path: Path, monkeypatch) -> None:
    database = Database(tmp_path / "db-legacy.sqlite")
    project = ProjectData(
        name="Áudio legado",
        template_key="hiragana",
        front_components=["word"],
        back_components=["audio"],
        audio_providers=["fake"],
    )
    project_id = database.create_project(project)
    project = database.get_project(project_id)
    legacy = tmp_path / "legacy.wav"
    legacy.write_bytes(b"RIFFlegacy-audio")
    card_id = database.add_cards(
        project_id,
        [FlashcardData(word="猫", sentence_audio_path=str(legacy))],
    )[0]
    card = database.get_card(card_id)
    assert project is not None and card is not None

    service = ProjectAudioService(database, SimpleNamespace(audio_dir=tmp_path / "audio"))
    monkeypatch.setattr(service, "_build_router", lambda _project: (_ for _ in ()).throw(AssertionError("router não deveria ser usado")))
    updated = service.generate_for_card(project, card)
    assert updated.word_audio_path == str(legacy)
    assert updated.sentence_audio_path == ""
