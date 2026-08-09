from __future__ import annotations

import unicodedata
from typing import Iterable, TypeVar

T = TypeVar("T")


def normalize_search_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).casefold().strip()


def search_score(label: str, query: str) -> tuple[int, int, str]:
    """Menor tupla = maior relevância; itens não correspondentes continuam na lista."""
    text = normalize_search_text(label)
    wanted = normalize_search_text(query)
    if not wanted:
        return (3, 0, text)
    if text == wanted:
        return (0, 0, text)
    if text.startswith(wanted):
        return (1, len(text) - len(wanted), text)
    position = text.find(wanted)
    if position >= 0:
        return (2, position, text)
    return (3, 0, text)


def rank_labels(items: Iterable[T], query: str, label_getter=lambda item: str(item)) -> list[T]:
    source = list(items)
    if not normalize_search_text(query):
        return source
    indexed = list(enumerate(source))
    return [
        item
        for _index, item in sorted(
            indexed,
            key=lambda pair: (*search_score(label_getter(pair[1]), query), pair[0]),
        )
    ]
