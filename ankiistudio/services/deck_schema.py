from __future__ import annotations

from copy import deepcopy
from typing import Iterable


_COMPONENT_FIELDS: dict[str, tuple[str, ...]] = {
    "word": ("word",),
    "reading": ("reading",),
    "romanization": ("romanization",),
    "translation": ("translation",),
    "example": ("example", "example_translation"),
    "explanation": ("explanation",),
    "mnemonic": ("mnemonic",),
    # Imagem é obtida posteriormente, mas a IA deve sempre devolver o campo de
    # termos visuais quando o componente faz parte da estrutura. Ele pode ser []
    # para kana/símbolos isolados, conforme as regras do prompt.
    "image": ("image_search_terms",),
}


_TOP_LEVEL_REQUIRED = (
    "format_version",
    "language",
    "translation_language",
    "category",
    "deck_name",
    "cards",
)


def required_fields_for_components(components: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    for component in components:
        for field in _COMPONENT_FIELDS.get(str(component).strip(), ()):
            if field not in result:
                result.append(field)
    return tuple(result)


def build_generation_schema(
    base_schema: dict,
    *,
    required_components: Iterable[str] = (),
    expected_cards: int | None = None,
    maximum_cards: int | None = None,
) -> dict:
    """Torna o schema de baralho coerente com a estrutura pedida pelo usuário.

    O modelo persistente continua permissivo para manter compatibilidade com
    edição manual e importações antigas. Somente os schemas usados para pedir
    conteúdo a uma IA são endurecidos dinamicamente.
    """

    schema = deepcopy(base_schema)
    top_required = list(schema.get("required", []))
    for field in _TOP_LEVEL_REQUIRED:
        if field not in top_required:
            top_required.append(field)
    schema["required"] = top_required

    cards_schema = schema.get("properties", {}).get("cards", {})
    if expected_cards is not None:
        cards_schema["minItems"] = int(expected_cards)
        cards_schema["maxItems"] = int(expected_cards)
    else:
        cards_schema["minItems"] = 1
        if maximum_cards is not None:
            cards_schema["maxItems"] = int(maximum_cards)

    card_schema = schema.get("$defs", {}).get("FlashcardData")
    if not isinstance(card_schema, dict):
        return schema

    required = list(card_schema.get("required", []))
    properties = card_schema.get("properties", {})
    for field in required_fields_for_components(required_components):
        if field not in required:
            required.append(field)
        if isinstance(properties.get(field), dict):
            current = str(properties[field].get("description") or "").strip()
            note = "Obrigatório nesta geração; forneça o conteúdo correspondente em vez de omitir o campo."
            properties[field]["description"] = f"{current} {note}".strip()
    card_schema["required"] = required
    return schema
