from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from .tokens import ThemeTokens, get_theme_tokens
from .style import BenkyouStudioProxyStyle


class ThemeManager:
    """Aplica tema, paleta e stylesheet a partir dos tokens do design system."""

    def __init__(self, resource_dir: Path) -> None:
        self.resource_dir = resource_dir
        self.current_theme = "dark"

    def apply(self, app: QApplication, theme: str) -> ThemeTokens:
        # Import tardio mantém ui.theme como ponte de compatibilidade para plugins/código antigo.
        from ankiistudio.ui.theme import build_stylesheet

        tokens = get_theme_tokens(theme)
        self.current_theme = tokens.name
        if not isinstance(app.style(), BenkyouStudioProxyStyle):
            app.setStyle(BenkyouStudioProxyStyle(app.style()))
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(tokens.background))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(tokens.text))
        palette.setColor(QPalette.ColorRole.Base, QColor(tokens.input))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(tokens.surface))
        palette.setColor(QPalette.ColorRole.Text, QColor(tokens.text))
        palette.setColor(QPalette.ColorRole.Button, QColor(tokens.surface))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(tokens.text))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(tokens.primary))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(tokens.primary_text))
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(tokens.muted))
        app.setPalette(palette)
        app.setStyleSheet(build_stylesheet(self.resource_dir, tokens.name))
        app.setProperty("ankiistudioTheme", tokens.name)
        app._ankiistudio_theme_manager = self  # type: ignore[attr-defined]
        return tokens


def apply_design_system(app: QApplication, resource_dir: Path, theme: str) -> ThemeTokens:
    manager = getattr(app, "_ankiistudio_theme_manager", None)
    if not isinstance(manager, ThemeManager):
        manager = ThemeManager(resource_dir)
    return manager.apply(app, theme)
