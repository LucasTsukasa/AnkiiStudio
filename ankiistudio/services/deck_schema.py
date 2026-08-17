from __future__ import annotations

from typing import Iterable


_COMPONENT_FIELDS: dict[str, tuple[str, ...]] = {
    "word": ("word",),
    "reading": ("reading",),
    "romanization": ("romanization",),
    "translation": ("translation",),
    "example": ("example", "example_translation"),
    "explanation": ("explanation",),
    "mnemonic": ("mnemonic",),
    # Imagem é obtida posteriormente, mas a IA deve sempre devolver termos
    # visuais quando o componente faz parte da estrutura.
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


_GENERATED_CARD_PROPERTIES: dict[str, dict] = {
    "section": {
        "type": "string",
        "description": "Grupo ou subbaralho curto e consistente ao qual o cartão pertence.",
    },
    "word": {
        "type": "string",
        "description": "Conteúdo principal real estudado pelo cartão.",
    },
    "reading": {
        "type": "string",
        "description": "Leitura auxiliar do conteúdo principal, quando solicitada; caso contrário, string vazia.",
    },
    "romanization": {
        "type": "string",
        "description": "Romanização do conteúdo principal, quando solicitada; caso contrário, string vazia.",
    },
    "translation": {
        "type": "string",
        "description": "Tradução direta do conteúdo principal, quando solicitada; caso contrário, string vazia.",
    },
    "example": {
        "type": "string",
        "description": "Exemplo curto e natural relacionado ao conteúdo principal, quando solicitado.",
    },
    "example_reading": {
        "type": "string",
        "description": "Leitura auxiliar do exemplo, somente quando pedagogicamente necessária.",
    },
    "example_translation": {
        "type": "string",
        "description": "Tradução do exemplo, quando o componente Exemplo for solicitado.",
    },
    "explanation": {
        "type": "string",
        "description": "Explicação pedagógica objetiva, quando solicitada; caso contrário, string vazia.",
    },
    "mnemonic": {
        "type": "string",
        "description": "Mnemônico curto e útil, quando solicitado; caso contrário, string vazia.",
    },
    "image_search_terms": {
        "type": "array",
        "items": {"type": "string"},
        "description": "De uma a três buscas visuais concretas quando Imagem for solicitada; pode ser vazio para símbolos isolados.",
    },
}


def required_fields_for_components(components: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    for component in components:
        for field in _COMPONENT_FIELDS.get(str(component).strip(), ()):
            if field not in result:
                result.append(field)
    return tuple(result)


def build_generation_schema(
    _base_schema: dict | None = None,
    *,
    required_components: Iterable[str] = (),
    expected_cards: int | None = None,
    maximum_cards: int | None = None,
) -> dict:
    """Cria o schema enxuto enviado para a geração de conteúdo.

    O modelo persistente ``FlashcardData`` possui IDs, timestamps, caminhos de
    mídia, defaults e limites de validação que são úteis internamente, mas não
    pertencem à resposta da IA. A Interactions API aceita apenas um subconjunto
    de JSON Schema e também pode rejeitar schemas excessivamente complexos.
    Por isso, a geração usa deliberadamente um contrato pequeno e independente
    do schema de persistência. O ``_base_schema`` é mantido apenas por
    compatibilidade com chamadas antigas do serviço de prompt.
    """

    card_required = ["section", "word"]
    for field in required_fields_for_components(required_components):
        if field not in card_required:
            card_required.append(field)

    cards_schema: dict = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {key: dict(value) for key, value in _GENERATED_CARD_PROPERTIES.items()},
            "required": card_required,
            "additionalProperties": False,
        },
        "minItems": 1,
    }
    if expected_cards is not None:
        quantity = max(1, int(expected_cards))
        cards_schema["minItems"] = quantity
        cards_schema["maxItems"] = quantity
    elif maximum_cards is not None:
        cards_schema["maxItems"] = max(1, int(maximum_cards))

    return {
        "type": "object",
        "properties": {
            "format_version": {
                "type": "string",
                "description": "Versão do formato do BenkyouStudio; use exatamente 1.0.",
            },
            "language": {
                "type": "string",
                "description": "Código normalizado do idioma-alvo solicitado.",
            },
            "translation_language": {
                "type": "string",
                "description": "Código normalizado do idioma da tradução solicitado.",
            },
            "category": {
                "type": "string",
                "description": "Categoria interna/modelo solicitado para o baralho.",
            },
            "deck_name": {
                "type": "string",
                "description": "Nome do baralho solicitado.",
            },
            "cards": cards_schema,
        },
        "required": list(_TOP_LEVEL_REQUIRED),
        "additionalProperties": False,
    }


def build_generated_field_schema() -> dict:
    """Schema compacto para a geração individual de Exemplo/Explicação/Mnemônico."""

    return {
        "type": "object",
        "properties": {
            "value": {
                "type": "string",
                "description": "Conteúdo solicitado para o campo do cartão.",
            },
            "example_reading": {
                "type": "string",
                "description": "Leitura auxiliar do exemplo; use string vazia quando não se aplicar.",
            },
            "example_translation": {
                "type": "string",
                "description": "Tradução do exemplo; use string vazia quando não se aplicar.",
            },
        },
        "required": ["value", "example_reading", "example_translation"],
        "additionalProperties": False,
    }
