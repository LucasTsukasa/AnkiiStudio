from pathlib import Path

import pytest

from ankiistudio.database import Database
from ankiistudio.models import FlashcardData, ProjectData, WikimediaMediaResult
from ankiistudio.services.media_service import CardImageService


class FakeWikimedia:
    def __init__(self, *, succeed_on: str | None = None) -> None:
        self.searches: list[str] = []
        self.downloads: list[str] = []
        self.succeed_on = succeed_on

    def search(self, term: str, *, kind: str, limit: int):
        self.searches.append(term)
        if self.succeed_on is not None and term != self.succeed_on:
            return []
        return [
            WikimediaMediaResult(
                title="File:Cat.jpg",
                file_url="https://example.invalid/cat.jpg",
                description_url="https://commons.wikimedia.org/wiki/File:Cat.jpg",
                license_name="CC0",
            )
        ]

    def download(self, url: str):
        self.downloads.append(url)
        return b"raw-image", "image/jpeg"


class FakeImageService:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def optimize(self, raw: bytes, title: str, *, flatten_transparency: bool = False) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / "cat.webp"
        path.write_bytes(b"webp-image")
        self.flatten_transparency = flatten_transparency
        return path


def _saved_project_and_card(tmp_path: Path, wikimedia: FakeWikimedia):
    database = Database(tmp_path / "db.sqlite")
    project = ProjectData(
        name="Imagens",
        template_key="hiragana",
        front_components=["image", "word"],
        back_components=["translation"],
    )
    project_id = database.create_project(project)
    project = database.get_project(project_id)
    card_id = database.add_cards(
        project_id,
        [
            FlashcardData(
                word="猫",
                translation="gato",
                image_search_terms=["domestic cat"],
                image_path=str(tmp_path / "missing.webp"),
            )
        ],
    )[0]
    card = database.get_card(card_id)
    assert project is not None and card is not None
    service = CardImageService(database, wikimedia, FakeImageService(tmp_path / "images"))
    return project, card, service


def test_best_wikimedia_image_uses_original_content_before_ai_terms(tmp_path: Path) -> None:
    wikimedia = FakeWikimedia(succeed_on="猫")
    project, card, service = _saved_project_and_card(tmp_path, wikimedia)
    updated = service.apply_best_wikimedia_image(project, card)
    assert Path(updated.image_path).is_file()
    assert wikimedia.searches == ["猫"]
    assert "domestic cat" not in wikimedia.searches


def test_best_wikimedia_image_falls_back_to_translation_only_after_original(tmp_path: Path) -> None:
    wikimedia = FakeWikimedia(succeed_on="gato")
    project, card, service = _saved_project_and_card(tmp_path, wikimedia)
    updated = service.apply_best_wikimedia_image(project, card)
    assert Path(updated.image_path).is_file()
    assert wikimedia.searches == ["猫", "gato"]
    assert "domestic cat" not in wikimedia.searches


def test_image_generation_is_rejected_when_image_not_in_structure(tmp_path: Path) -> None:
    database = Database(tmp_path / "db.sqlite")
    project = ProjectData(
        name="Sem imagem",
        template_key="hiragana",
        front_components=["word"],
        back_components=["translation"],
    )
    card = FlashcardData(id=1, project_id=1, word="猫")
    service = CardImageService(database, FakeWikimedia(), FakeImageService(tmp_path / "images"))
    with pytest.raises(ValueError, match="não utiliza imagens"):
        service.apply_best_wikimedia_image(project, card)


def test_svg_from_wikimedia_uses_rasterized_thumbnail(tmp_path: Path) -> None:
    database = Database(tmp_path / "svg.db")
    project = ProjectData(
        name="Kana SVG",
        template_key="hiragana",
        front_components=["image", "word"],
        back_components=["translation"],
    )
    project_id = database.create_project(project)
    project = database.get_project(project_id)
    card_id = database.add_cards(project_id, [FlashcardData(word="を", translation="O")])[0]
    card = database.get_card(card_id)
    assert project is not None and card is not None
    wikimedia = FakeWikimedia()
    service = CardImageService(database, wikimedia, FakeImageService(tmp_path / "images"))
    result = WikimediaMediaResult(
        title="File:Japanese Hiragana wo.svg",
        file_url="https://upload.wikimedia.org/original.svg",
        thumbnail_url="https://upload.wikimedia.org/900px-original.svg.png",
        description_url="https://commons.wikimedia.org/wiki/File:Japanese_Hiragana_wo.svg",
        mime="image/svg+xml",
        license_name="CC BY-SA",
    )
    updated = service.apply_wikimedia_image(project, card, result)
    assert Path(updated.image_path).is_file()
    assert wikimedia.downloads == ["https://upload.wikimedia.org/900px-original.svg.png"]
    assert service.image_service.flatten_transparency is True
    with database.connection() as connection:
        row = connection.execute(
            "SELECT modifications FROM media_assets WHERE project_id=? ORDER BY id DESC LIMIT 1",
            (project_id,),
        ).fetchone()
    assert row is not None
    assert "SVG rasterizado pelo Wikimedia" in row["modifications"]
