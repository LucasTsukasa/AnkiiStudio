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
        title = "File:Domestic cat.jpg" if term in {"domestic cat", "gato"} else "File:Cat.jpg"
        return [
            WikimediaMediaResult(
                title=title,
                file_url="https://example.invalid/cat.jpg",
                description_url="https://commons.wikimedia.org/wiki/File:Cat.jpg",
                license_name="CC0",
            )
        ]

    def download(self, url: str):
        self.downloads.append(url)
        return b"raw-image", "image/jpeg"


class FakeKanaWikimedia(FakeWikimedia):
    def search(self, term: str, *, kind: str, limit: int):
        self.searches.append(term)
        if self.succeed_on is not None and term != self.succeed_on:
            return []
        return [
            WikimediaMediaResult(
                title="File:Hiragana letter O.svg",
                file_url="https://example.invalid/o.svg",
                thumbnail_url="https://example.invalid/o.png",
                description_url="https://commons.wikimedia.org/wiki/File:Hiragana_letter_O.svg",
                mime="image/svg+xml",
                license_name="CC0",
            )
        ]


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


def test_best_image_tries_original_word_before_concrete_ai_search_terms(tmp_path: Path) -> None:
    wikimedia = FakeWikimedia(succeed_on="domestic cat")
    project, card, service = _saved_project_and_card(tmp_path, wikimedia)
    updated = service.apply_best_image(project, card)
    assert Path(updated.image_path).is_file()
    assert wikimedia.searches == ["猫", "domestic cat"]


def test_best_image_falls_back_from_original_and_visual_term_to_translation(tmp_path: Path) -> None:
    wikimedia = FakeWikimedia(succeed_on="gato")
    project, card, service = _saved_project_and_card(tmp_path, wikimedia)
    updated = service.apply_best_image(project, card)
    assert Path(updated.image_path).is_file()
    assert wikimedia.searches == ["猫", "domestic cat", "gato"]


def test_bulk_image_search_uses_exact_original_word_when_no_visual_terms(tmp_path: Path) -> None:
    database = Database(tmp_path / "kana.db")
    project = ProjectData(
        name="Hiragana",
        template_key="hiragana",
        front_components=["image", "word"],
        back_components=["translation"],
    )
    project_id = database.create_project(project)
    project = database.get_project(project_id)
    card_id = database.add_cards(
        project_id,
        [FlashcardData(word="お", translation="O", image_search_terms=[])],
    )[0]
    card = database.get_card(card_id)
    assert project is not None and card is not None

    wikimedia = FakeKanaWikimedia(succeed_on="お")
    service = CardImageService(database, wikimedia, FakeImageService(tmp_path / "images"))
    updated = service.apply_best_image(project, card)

    assert Path(updated.image_path).is_file()
    assert wikimedia.searches == ["お"]


def test_bulk_image_search_falls_back_to_translation_after_original_word(tmp_path: Path) -> None:
    database = Database(tmp_path / "kana-fallback.db")
    project = ProjectData(
        name="Hiragana",
        template_key="hiragana",
        front_components=["image", "word"],
        back_components=["translation"],
    )
    project_id = database.create_project(project)
    project = database.get_project(project_id)
    card_id = database.add_cards(
        project_id,
        [FlashcardData(word="お", translation="O", image_search_terms=[])],
    )[0]
    card = database.get_card(card_id)
    assert project is not None and card is not None

    wikimedia = FakeKanaWikimedia(succeed_on="O")
    service = CardImageService(database, wikimedia, FakeImageService(tmp_path / "images"))
    updated = service.apply_best_image(project, card)

    assert Path(updated.image_path).is_file()
    assert wikimedia.searches == ["お", "O"]



class FakeRelevanceWikimedia(FakeWikimedia):
    def search(self, term: str, *, kind: str, limit: int):
        self.searches.append(term)
        if term != "メロン":
            return []
        return [
            WikimediaMediaResult(
                title="File:Melon Stadium football match.jpg",
                file_url="https://example.invalid/stadium.jpg",
                description="Football players inside a stadium",
            ),
            WikimediaMediaResult(
                title="File:Fresh melon fruit.jpg",
                file_url="https://example.invalid/melon.jpg",
                description="Fresh melon fruit cut open",
            ),
        ]


def test_automatic_image_selection_ranks_relevant_candidate_instead_of_first_result(tmp_path: Path) -> None:
    database = Database(tmp_path / "relevance.db")
    project = ProjectData(
        name="Vocabulário",
        template_key="custom",
        front_components=["image", "word"],
        back_components=["translation"],
    )
    project_id = database.create_project(project)
    project = database.get_project(project_id)
    card_id = database.add_cards(
        project_id,
        [
            FlashcardData(
                word="メロン",
                translation="melão",
                image_search_terms=["melon fruit"],
            )
        ],
    )[0]
    card = database.get_card(card_id)
    assert project is not None and card is not None

    wikimedia = FakeRelevanceWikimedia()
    service = CardImageService(database, wikimedia, FakeImageService(tmp_path / "images"))
    updated = service.apply_best_image(project, card)

    assert Path(updated.image_path).is_file()
    assert wikimedia.searches == ["メロン"]
    assert wikimedia.downloads == ["https://example.invalid/melon.jpg"]


def test_automatic_image_selection_rejects_unrelated_candidates_when_visual_terms_exist() -> None:
    card = FlashcardData(
        word="メロン",
        translation="melão",
        image_search_terms=["melon fruit"],
    )
    stadium = WikimediaMediaResult(
        title="File:Melon Stadium football match.jpg",
        file_url="https://example.invalid/stadium.jpg",
        description="Football stadium at night",
    )
    fruit = WikimediaMediaResult(
        title="File:Fresh melon fruit.jpg",
        file_url="https://example.invalid/melon.jpg",
    )
    ranked = CardImageService._rank_relevant_results(card, "メロン", [stadium, fruit])
    assert [item.title for item in ranked] == ["File:Fresh melon fruit.jpg"]

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


def test_import_and_remove_image_for_card(tmp_path: Path) -> None:
    from PIL import Image
    from ankiistudio.services.image_service import ImageService

    database = Database(tmp_path / "import.db")
    project = ProjectData(
        name="Importar imagem",
        template_key="custom",
        front_components=["image", "word"],
        back_components=["translation"],
    )
    project_id = database.create_project(project)
    project = database.get_project(project_id)
    card_id = database.add_cards(project_id, [FlashcardData(word="gato")])[0]
    card = database.get_card(card_id)
    assert project is not None and card is not None

    source = tmp_path / "gato.png"
    Image.new("RGB", (64, 64), "white").save(source)
    service = CardImageService(database, FakeWikimedia(), ImageService(tmp_path / "images"))
    updated = service.import_image_file(project, card, source)
    imported = Path(updated.image_path)
    assert imported.is_file()
    assert imported.suffix == ".webp"
    with database.connection() as connection:
        asset = connection.execute(
            "SELECT provider FROM media_assets WHERE card_id=? AND kind='image'", (card_id,)
        ).fetchone()
    assert asset is not None and asset["provider"] == "user_import"

    removed = service.remove_image(updated)
    assert removed.image_path == ""
    assert not imported.exists()
    with database.connection() as connection:
        total = connection.execute(
            "SELECT COUNT(*) AS total FROM media_assets WHERE card_id=? AND kind='image'", (card_id,)
        ).fetchone()["total"]
    assert total == 0


def test_non_latin_wikimedia_result_must_contain_the_searched_term() -> None:
    irrelevant = WikimediaMediaResult(
        title="File:HEP building.jpg",
        file_url="https://example.invalid/building.jpg",
        description="A building and pedestrian bridge",
    )
    relevant = WikimediaMediaResult(
        title="File:怖い expression.jpg",
        file_url="https://example.invalid/scared.jpg",
    )
    assert CardImageService._wikimedia_result_matches_non_latin_term(irrelevant, "怖い") is False
    assert CardImageService._wikimedia_result_matches_non_latin_term(relevant, "怖い") is True


def test_kana_wikimedia_result_can_match_unicode_character_name() -> None:
    result = WikimediaMediaResult(
        title="File:Hiragana letter O.svg",
        file_url="https://example.invalid/o.svg",
    )
    assert CardImageService._wikimedia_result_matches_non_latin_term(result, "お") is True


def test_manual_image_search_uses_original_word_and_auxiliary_fields() -> None:
    card = FlashcardData(
        word="猫",
        translation="Gato",
        romanization="neko",
        reading="ねこ",
        image_search_terms=["Cat", "domestic cat", "Gato"],
    )
    primary, auxiliary = CardImageService.manual_search_terms(card)
    assert primary == "猫"
    assert auxiliary == ["Gato", "neko", "ねこ", "Cat", "domestic cat"]


def test_manual_image_search_for_kana_does_not_replace_original_with_translation() -> None:
    card = FlashcardData(word="あ", translation="A", romanization="a")
    primary, auxiliary = CardImageService.manual_search_terms(card)
    assert primary == "あ"
    assert auxiliary == ["A"]



def test_replacing_managed_image_removes_previous_orphan(tmp_path: Path) -> None:
    from PIL import Image
    from ankiistudio.services.image_service import ImageService

    database = Database(tmp_path / "replace-image.db")
    project_id = database.create_project(
        ProjectData(
            name="Lifecycle",
            template_key="custom",
            front_components=["image", "word"],
            back_components=["translation"],
        )
    )
    project = database.get_project(project_id)
    card_id = database.add_cards(project_id, [FlashcardData(word="gato")])[0]
    card = database.get_card(card_id)
    assert project is not None and card is not None

    first_source = tmp_path / "first.png"
    second_source = tmp_path / "second.png"
    Image.new("RGB", (32, 32), "white").save(first_source)
    Image.new("RGB", (32, 32), "black").save(second_source)

    service = CardImageService(database, FakeWikimedia(), ImageService(tmp_path / "images"))
    card = service.import_image_file(project, card, first_source)
    first_managed = Path(card.image_path)
    assert first_managed.is_file()

    card = service.import_image_file(project, card, second_source)
    second_managed = Path(card.image_path)
    assert second_managed.is_file()
    assert second_managed != first_managed
    assert not first_managed.exists()


def test_replacing_shared_managed_image_preserves_file_still_in_use(tmp_path: Path) -> None:
    from PIL import Image
    from ankiistudio.services.image_service import ImageService

    database = Database(tmp_path / "shared-image.db")
    project_id = database.create_project(
        ProjectData(
            name="Compartilhada",
            template_key="custom",
            front_components=["image", "word"],
            back_components=["translation"],
        )
    )
    project = database.get_project(project_id)
    card_ids = database.add_cards(
        project_id,
        [FlashcardData(word="gato"), FlashcardData(word="felino")],
    )
    first_card = database.get_card(card_ids[0])
    second_card = database.get_card(card_ids[1])
    assert project is not None and first_card is not None and second_card is not None

    shared_source = tmp_path / "shared.png"
    replacement_source = tmp_path / "replacement.png"
    Image.new("RGB", (32, 32), "white").save(shared_source)
    Image.new("RGB", (32, 32), "black").save(replacement_source)

    service = CardImageService(database, FakeWikimedia(), ImageService(tmp_path / "images"))
    first_card = service.import_image_file(project, first_card, shared_source)
    second_card = service.import_image_file(project, second_card, shared_source)
    shared_managed = Path(first_card.image_path)
    assert second_card.image_path == first_card.image_path

    service.import_image_file(project, first_card, replacement_source)
    assert shared_managed.exists()


def test_cleanup_after_card_deletion_only_removes_unreferenced_managed_image(tmp_path: Path) -> None:
    from PIL import Image
    from ankiistudio.services.image_service import ImageService

    database = Database(tmp_path / "delete-lifecycle.db")
    project_id = database.create_project(
        ProjectData(
            name="Excluir",
            template_key="custom",
            front_components=["image", "word"],
            back_components=["translation"],
        )
    )
    project = database.get_project(project_id)
    card_id = database.add_cards(project_id, [FlashcardData(word="imagem")])[0]
    card = database.get_card(card_id)
    assert project is not None and card is not None

    source = tmp_path / "managed.png"
    Image.new("RGB", (32, 32), "white").save(source)
    service = CardImageService(database, FakeWikimedia(), ImageService(tmp_path / "images"))
    card = service.import_image_file(project, card, source)
    managed = Path(card.image_path)

    paths = database.image_paths_for_cards([card_id])
    database.delete_cards([card_id])
    service.cleanup_unreferenced_paths(paths)

    assert not managed.exists()

def test_image_cleanup_never_deletes_external_user_file(tmp_path: Path) -> None:
    from PIL import Image
    from ankiistudio.services.image_service import ImageService

    database = Database(tmp_path / "external-image.db")
    project_id = database.create_project(
        ProjectData(
            name="Imagem externa",
            template_key="custom",
            front_components=["word", "image"],
            back_components=["translation"],
        )
    )
    external_dir = tmp_path / "user-photos"
    external_dir.mkdir()
    external = external_dir / "original.png"
    Image.new("RGB", (32, 32), "white").save(external)
    card_id = database.add_cards(
        project_id,
        [FlashcardData(word="externa", image_path=str(external))],
    )[0]
    service = CardImageService(
        database,
        FakeWikimedia(),
        ImageService(tmp_path / "managed-images"),
    )

    paths = database.image_paths_for_cards([card_id])
    database.delete_cards([card_id])
    service.cleanup_unreferenced_paths(paths)

    assert external.exists()

