from ankiistudio.services.search_rank import normalize_search_text, rank_labels


def test_empty_search_preserves_original_order() -> None:
    items = ["Personalizado", "Hiragana", "Katakana", "Frases Básicas"]
    assert rank_labels(items, "") == items
    assert rank_labels(items, "   ") == items


def test_search_ranks_matches_first_without_hiding_items() -> None:
    items = ["Personalizado", "Katakana", "Frases Básicas", "Hiragana"]
    ranked = rank_labels(items, "hira")
    assert ranked[0] == "Hiragana"
    assert set(ranked) == set(items)
    assert len(ranked) == len(items)


def test_search_is_case_and_accent_insensitive() -> None:
    items = ["Inglês", "Espanhol", "Coreano", "Japonês"]
    ranked = rank_labels(items, "JAPONES")
    assert ranked[0] == "Japonês"
    assert set(ranked) == set(items)
    assert normalize_search_text("Japonês") == "japones"


def test_exact_prefix_and_contains_are_ranked_in_that_order() -> None:
    items = ["Meu Hiragana", "Hiragana Avançado", "Hiragana", "Katakana"]
    ranked = rank_labels(items, "hiragana")
    assert ranked[:3] == ["Hiragana", "Hiragana Avançado", "Meu Hiragana"]
    assert ranked[-1] == "Katakana"
