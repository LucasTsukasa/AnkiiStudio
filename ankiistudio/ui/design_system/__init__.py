"""AnkiiStudio Design System.

Camada visual própria sobre Qt/PySide6. O módulo-base permanece importável sem
PySide6 para que tokens/contratos possam ser usados em ferramentas e testes.
Componentes Qt são carregados sob demanda.
"""
from __future__ import annotations

from .responsive import breakpoint_for_width, responsive_columns
from .tokens import Breakpoint, Breakpoints, ControlSize, Radius, Spacing, ThemeTokens, Typography, get_theme_tokens

DESIGN_SYSTEM_VERSION = "1.0"

_LAZY_EXPORTS = {
    "IconRegistry": ("ankiistudio.ui.design_system.icons", "IconRegistry"),
    "ThemeManager": ("ankiistudio.ui.design_system.themes", "ThemeManager"),
    "apply_design_system": ("ankiistudio.ui.design_system.themes", "apply_design_system"),
}


def __getattr__(name: str):
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attribute = target
    from importlib import import_module

    value = getattr(import_module(module_name), attribute)
    globals()[name] = value
    return value


__all__ = [
    "DESIGN_SYSTEM_VERSION", "IconRegistry", "ThemeManager", "apply_design_system", "breakpoint_for_width",
    "responsive_columns", "Breakpoint", "Breakpoints", "ControlSize", "Radius", "Spacing", "ThemeTokens",
    "Typography", "get_theme_tokens",
]
