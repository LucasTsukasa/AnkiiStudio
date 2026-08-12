from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QEvent, QObject, Signal
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QComboBox,
    QGroupBox,
    QLabel,
    QLineEdit,
    QTabWidget,
    QTableWidget,
    QWidget,
)

DEFAULT_UI_LANGUAGE = "pt_BR"
LANGUAGES_DIR = Path(__file__).resolve().parent / "languages"
_CURRENT_UI_LANGUAGE = DEFAULT_UI_LANGUAGE


@lru_cache(maxsize=None)
def _catalog(language: str) -> dict:
    path = LANGUAGES_DIR / f"{language}.json"
    if not path.is_file():
        if language == DEFAULT_UI_LANGUAGE:
            return {"code": DEFAULT_UI_LANGUAGE, "name": "Português (Brasil)", "translations": {}, "fragments": []}
        return _catalog(DEFAULT_UI_LANGUAGE)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _catalog(DEFAULT_UI_LANGUAGE) if language != DEFAULT_UI_LANGUAGE else {
            "code": DEFAULT_UI_LANGUAGE,
            "name": "Português (Brasil)",
            "translations": {},
            "fragments": [],
        }
    if not isinstance(payload, dict):
        return _catalog(DEFAULT_UI_LANGUAGE)
    payload.setdefault("translations", {})
    payload.setdefault("fragments", [])
    return payload


def _discover_ui_languages() -> list[tuple[str, str]]:
    preferred = ["pt_BR", "en_US"]
    found: dict[str, str] = {}
    if LANGUAGES_DIR.is_dir():
        for path in LANGUAGES_DIR.glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            code = str(payload.get("code") or path.stem)
            name = str(payload.get("name") or code)
            found[code] = name
    order = [code for code in preferred if code in found]
    order.extend(sorted(code for code in found if code not in order))
    if not order:
        return [("Português (Brasil)", "pt_BR")]
    return [(found[code], code) for code in order]


UI_LANGUAGES = _discover_ui_languages()


def set_current_language(language: str) -> None:
    global _CURRENT_UI_LANGUAGE
    valid = {code for _, code in UI_LANGUAGES}
    _CURRENT_UI_LANGUAGE = language if language in valid else DEFAULT_UI_LANGUAGE


def current_language() -> str:
    return _CURRENT_UI_LANGUAGE


def tr(text: str, language: str | None = None) -> str:
    language = language or _CURRENT_UI_LANGUAGE
    if not text or language == DEFAULT_UI_LANGUAGE:
        return text
    catalog = _catalog(language)
    translations = catalog.get("translations") or {}
    if text in translations:
        return str(translations[text])
    translated = text
    for pair in catalog.get("fragments") or []:
        if not isinstance(pair, list) or len(pair) != 2:
            continue
        source, target = str(pair[0]), str(pair[1])
        if source in translated:
            translated = translated.replace(source, target)
    return translated


def _source_text(text: str, language: str) -> str:
    """Reconstrói a string-fonte pt-BR quando um widget já está traduzido."""
    if not text or language == DEFAULT_UI_LANGUAGE:
        return text
    catalog = _catalog(language)
    translations = catalog.get("translations") or {}
    reverse = {str(value): str(key) for key, value in translations.items()}
    if text in reverse:
        return reverse[text]
    source = text
    # Reverse longer fragments first to avoid partial replacements.
    pairs = []
    for pair in catalog.get("fragments") or []:
        if isinstance(pair, list) and len(pair) == 2:
            pairs.append((str(pair[0]), str(pair[1])))
    for original, translated in sorted(pairs, key=lambda item: len(item[1]), reverse=True):
        if translated and translated in source:
            source = source.replace(translated, original)
    return source


class UiLanguageManager(QObject):
    """Gerencia os pacotes de idioma e aplica mudanças sem reiniciar a aplicação."""

    languageChanged = Signal(str)

    def __init__(self, language: str) -> None:
        super().__init__()
        valid = {code for _, code in UI_LANGUAGES}
        self.language = language if language in valid else DEFAULT_UI_LANGUAGE
        set_current_language(self.language)

    def set_language(self, language: str) -> None:
        valid = {code for _, code in UI_LANGUAGES}
        target = language if language in valid else DEFAULT_UI_LANGUAGE
        previous = self.language
        if target == previous:
            return
        self.language = target
        set_current_language(target)
        app = QApplication.instance()
        if app is not None:
            for root in app.topLevelWidgets():
                self.translate_widget_tree(root, source_language=previous)
        self.languageChanged.emit(target)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # type: ignore[override]
        if event.type() == QEvent.Type.Show and isinstance(watched, QWidget):
            self.translate_widget_tree(watched, source_language=DEFAULT_UI_LANGUAGE)
        return False

    def translate_widget_tree(self, root: QWidget, *, source_language: str | None = None) -> None:
        source_language = source_language or self.language
        widgets: Iterable[QWidget] = [root, *root.findChildren(QWidget)]
        for widget in widgets:
            self._translate_widget(widget, source_language)

    def _translated_value(self, widget: QWidget, cache_name: str, current: str, source_language: str) -> str:
        source = getattr(widget, cache_name, None)
        if source is None:
            source = _source_text(current, source_language)
        else:
            expected = tr(str(source), source_language)
            if current != expected:
                source = _source_text(current, source_language)
        setattr(widget, cache_name, source)
        return tr(str(source), self.language)

    def _translate_widget(self, widget: QWidget, source_language: str) -> None:
        if bool(getattr(widget, "_i18n_skip", False)):
            return
        if widget.windowTitle():
            widget.setWindowTitle(self._translated_value(widget, "_i18n_source_window_title", widget.windowTitle(), source_language))
        if widget.toolTip():
            widget.setToolTip(self._translated_value(widget, "_i18n_source_tooltip", widget.toolTip(), source_language))

        if isinstance(widget, QLabel):
            widget.setText(self._translated_value(widget, "_i18n_source_text", widget.text(), source_language))
        elif isinstance(widget, QAbstractButton):
            widget.setText(self._translated_value(widget, "_i18n_source_text", widget.text(), source_language))
        elif isinstance(widget, QGroupBox):
            widget.setTitle(self._translated_value(widget, "_i18n_source_title", widget.title(), source_language))
        elif isinstance(widget, QLineEdit):
            widget.setPlaceholderText(
                self._translated_value(widget, "_i18n_source_placeholder", widget.placeholderText(), source_language)
            )
        elif isinstance(widget, QComboBox):
            if not bool(getattr(widget, "_i18n_skip_items", False)):
                current_data = widget.currentData()
                current_items = [widget.itemText(index) for index in range(widget.count())]
                sources = getattr(widget, "_i18n_source_items", None)
                if not isinstance(sources, list) or len(sources) != len(current_items):
                    sources = [_source_text(value, source_language) for value in current_items]
                else:
                    for index, value in enumerate(current_items):
                        if value != tr(str(sources[index]), source_language):
                            sources[index] = _source_text(value, source_language)
                widget._i18n_source_items = sources
                for index, source in enumerate(sources):
                    widget.setItemText(index, tr(str(source), self.language))
                refresh = getattr(widget, "refresh_search_source", None)
                if callable(refresh):
                    refresh()
                if current_data is not None:
                    idx = widget.findData(current_data)
                    if idx >= 0:
                        widget.setCurrentIndex(idx)
        elif isinstance(widget, QTableWidget):
            sources = getattr(widget, "_i18n_source_headers", {})
            if not isinstance(sources, dict):
                sources = {}
            for column in range(widget.columnCount()):
                item = widget.horizontalHeaderItem(column)
                if item is None:
                    continue
                current = item.text()
                source = sources.get(column)
                if source is None or current != tr(str(source), source_language):
                    source = _source_text(current, source_language)
                sources[column] = source
                item.setText(tr(str(source), self.language))
            widget._i18n_source_headers = sources
        elif isinstance(widget, QTabWidget):
            sources = getattr(widget, "_i18n_source_tabs", [])
            current_tabs = [widget.tabText(index) for index in range(widget.count())]
            if not isinstance(sources, list) or len(sources) != len(current_tabs):
                sources = [_source_text(value, source_language) for value in current_tabs]
            else:
                for index, value in enumerate(current_tabs):
                    if value != tr(str(sources[index]), source_language):
                        sources[index] = _source_text(value, source_language)
            widget._i18n_source_tabs = sources
            for index, source in enumerate(sources):
                widget.setTabText(index, tr(str(source), self.language))


def ui_language_to_translation_code(ui_language: str) -> str:
    return "en" if ui_language == "en_US" else "pt"


def language_display_name(code: str, ui_language: str | None = None) -> str:
    from ankiistudio.constants import LANGUAGE_LABELS, LANGUAGE_LABELS_EN, normalize_language_code

    normalized = normalize_language_code(code)
    language = ui_language or _CURRENT_UI_LANGUAGE
    if language == "en_US":
        return LANGUAGE_LABELS_EN.get(normalized, LANGUAGE_LABELS.get(normalized, normalized))
    return LANGUAGE_LABELS.get(normalized, normalized)


def language_items(ui_language: str | None = None) -> list[tuple[str, str]]:
    from ankiistudio.constants import LANGUAGE_LABELS

    return [(language_display_name(code, ui_language), code) for code in LANGUAGE_LABELS]
