from __future__ import annotations

from .tokens import Breakpoint, Breakpoints


def breakpoint_for_width(width: int) -> Breakpoint:
    return Breakpoints.for_width(width)


def responsive_columns(
    width: int,
    *,
    item_min_width: int = 260,
    maximum: int = 4,
    spacing: int = 0,
) -> int:
    """Retorna quantas colunas cabem sem comprimir itens abaixo do mínimo.

    O espaçamento entre colunas participa do cálculo; ignorá-lo cria pequenas
    faixas de largura em que a grade escolhe uma coluna a mais do que realmente
    cabe e força os cards a ficarem menores que o planejado.
    """
    safe_width = max(1, width)
    safe_item = max(1, item_min_width)
    safe_spacing = max(0, spacing)
    columns = (safe_width + safe_spacing) // (safe_item + safe_spacing)
    return max(1, min(maximum, columns))
