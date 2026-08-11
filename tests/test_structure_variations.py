from collections import Counter
from pathlib import Path

from ankiistudio.database import Database
from ankiistudio.models import CardStructureVariation, FlashcardData, ProjectData
from ankiistudio.services.project_service import ProjectService


def _project() -> ProjectData:
    variations = [
        CardStructureVariation(key="recognition", name="Reconhecimento", front_components=["word"], back_components=["translation"]),
        CardStructureVariation(key="listening", name="Audição", front_components=["audio"], back_components=["word", "translation"]),
        CardStructureVariation(key="production", name="Produção", front_components=["translation"], back_components=["word", "audio"]),
    ]
    return ProjectData(
        name="Variações",
        language="ja",
        template_key="custom",
        custom_content=["Vocabulário"],
        creation_mode="manual",
        front_components=["word"],
        back_components=["translation"],
        card_structures=variations,
    )


def test_balanced_distribution_differs_by_at_most_one() -> None:
    project = _project()
    cards = [FlashcardData(word=f"item {i}", translation=f"tradução {i}") for i in range(100)]
    assigned = ProjectService.assign_structure_variations(project, cards, shuffle=False)
    counts = Counter(card.structure_key for card in assigned)
    assert counts == {"recognition": 34, "listening": 33, "production": 33}
    assert max(counts.values()) - min(counts.values()) <= 1


def test_sanitization_uses_each_cards_assigned_variation() -> None:
    project = _project()
    cards = [
        FlashcardData(word="猫", translation="gato", reading="ねこ", structure_key="recognition"),
        FlashcardData(word="犬", translation="cachorro", reading="いぬ", structure_key="listening"),
    ]
    sanitized = ProjectService.sanitize_cards_for_structure(project, cards)
    assert sanitized[0].translation == "gato"
    assert sanitized[0].reading == ""
    assert sanitized[1].translation == "cachorro"
    assert sanitized[1].reading == ""
    assert project.card_uses_component(sanitized[0], "audio") is False
    assert project.card_uses_component(sanitized[1], "audio") is True


def test_structure_variations_and_card_key_roundtrip(tmp_path: Path) -> None:
    db = Database(tmp_path / "variations.sqlite")
    project = _project()
    project_id = db.create_project(project)
    card_id = db.add_cards(
        project_id,
        [FlashcardData(word="猫", translation="gato", structure_key="listening")],
    )[0]
    loaded = db.get_project(project_id)
    card = db.get_card(card_id)
    assert loaded is not None and card is not None
    assert [item.key for item in loaded.card_structures] == ["recognition", "listening", "production"]
    assert card.structure_key == "listening"
    assert loaded.structure_for_card(card).name == "Audição"


def test_next_structure_key_prefers_least_used_variation() -> None:
    project = _project()
    existing = [
        FlashcardData(word="1", structure_key="recognition"),
        FlashcardData(word="2", structure_key="recognition"),
        FlashcardData(word="3", structure_key="listening"),
    ]
    assert ProjectService.next_structure_key(project, existing) == "production"
