from __future__ import annotations

from pathlib import Path


def build_stylesheet(resource_dir: Path, theme: str = "dark") -> str:
    icons = resource_dir / "icons"
    check_icon = (icons / "check.svg").as_posix()
    radio_icon = (icons / "radio.svg").as_posix()

    if theme == "light":
        c = {
            "bg": "#F4F7F5",
            "sidebar": "#FFFFFF",
            "card": "#FFFFFF",
            "hero": "#F4FBF7",
            "input": "#F8FAF9",
            "input_disabled": "#EDF1EF",
            "text": "#17211B",
            "text_soft": "#44534B",
            "muted": "#66756D",
            "border": "#D7E0DA",
            "border_hover": "#B7C8BE",
            "primary": "#18C96F",
            "primary_hover": "#12B863",
            "primary_text": "#FFFFFF",
            "selected": "#DDF6E8",
            "selected_border": "#8AD8AE",
            "danger_bg": "#FFF1F2",
            "danger_border": "#E8B9BE",
            "danger_text": "#A5323E",
            "scroll": "#C8D3CD",
            "tooltip": "#FFFFFF",
        }
    else:
        c = {
            "bg": "#080B0A",
            "sidebar": "#0A0F0C",
            "card": "#0E1411",
            "hero": "#0D1712",
            "input": "#0A100D",
            "input_disabled": "#090D0B",
            "text": "#F3F7F4",
            "text_soft": "#B9C7BF",
            "muted": "#84968C",
            "border": "#24332B",
            "border_hover": "#3A5144",
            "primary": "#19D978",
            "primary_hover": "#2BE88A",
            "primary_text": "#031109",
            "selected": "#123121",
            "selected_border": "#1FAF64",
            "danger_bg": "#241214",
            "danger_border": "#4A252B",
            "danger_text": "#F5A6AD",
            "scroll": "#293A31",
            "tooltip": "#101813",
        }

    return f"""
* {{
    font-family: "Segoe UI", "Noto Sans", sans-serif;
    font-size: 13px;
    color: {c['text']};
}}
QMainWindow, QWidget {{ background: {c['bg']}; }}
QWidget#PageSurface, QScrollArea#PageScroll, QScrollArea#PageScroll > QWidget > QWidget {{ background: {c['bg']}; }}
QScrollArea#PageScroll {{ border: 0; }}
QFrame#Sidebar {{ background: {c['sidebar']}; border-right: 1px solid {c['border']}; }}
QFrame#BrandPanel {{ background: transparent; border: 0; }}
QLabel#Brand {{ font-size: 19px; font-weight: 800; color: {c['text']}; background: transparent; }}
QLabel#BrandMark {{ font-size: 22px; font-weight: 900; color: {c['primary']}; background: transparent; }}
QLabel#HeroName {{ font-size: 28px; font-weight: 850; color: {c['text']}; background: transparent; }}
QLabel#DeveloperName {{ font-size: 15px; font-weight: 750; color: {c['text']}; background: transparent; }}
QLabel#ImagePreview {{ background: {c['input']}; border: 1px solid {c['border']}; border-radius: 12px; }}
QPushButton#NavButton {{
    background: transparent; border: 0; border-radius: 9px; padding: 10px 12px;
    text-align: left; color: {c['muted']}; font-size: 13px; font-weight: 600;
}}
QPushButton#NavButton:hover {{ background: {c['input']}; color: {c['text']}; }}
QPushButton#NavButton:checked {{ background: {c['selected']}; color: {c['primary']}; font-weight: 700; }}
QLabel#PageTitle {{ font-size: 25px; font-weight: 800; color: {c['text']}; background: transparent; }}
QLabel#PageSubtitle {{ color: {c['muted']}; font-size: 13px; background: transparent; }}
QLabel#SectionTitle {{ font-size: 16px; font-weight: 750; color: {c['text']}; background: transparent; }}
QLabel#SectionSubtitle, QLabel#MutedLabel {{ color: {c['muted']}; background: transparent; }}
QLabel#FieldLabel {{ color: {c['text_soft']}; font-size: 12px; font-weight: 650; background: transparent; }}
QLabel#Badge {{
    background: {c['selected']}; color: {c['primary']}; border: 1px solid {c['selected_border']};
    border-radius: 9px; padding: 3px 8px; font-size: 11px; font-weight: 700;
}}
QFrame#Card, QFrame#SectionCard, QFrame#HeroCard, QFrame#ProviderCard {{
    background: {c['card']}; border: 1px solid {c['border']}; border-radius: 14px;
}}
QFrame#HeroCard {{ background: {c['hero']}; }}
QFrame#ProviderCard:disabled {{ background: {c['input_disabled']}; border-color: {c['border']}; }}
QWidget#ProviderOption {{ background: transparent; border: 0; }}
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QListWidget, QTableWidget, QTextBrowser {{
    background: {c['input']}; border: 1px solid {c['border']}; border-radius: 9px;
    padding: 8px 10px; selection-background-color: {c['primary']}; selection-color: {c['primary_text']};
}}
QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover, QComboBox:hover, QSpinBox:hover,
QListWidget:hover, QTableWidget:hover {{ border-color: {c['border_hover']}; }}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus,
QListWidget:focus, QTableWidget:focus {{ border: 1px solid {c['primary']}; }}
QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled, QComboBox:disabled, QSpinBox:disabled {{
    color: {c['muted']}; background: {c['input_disabled']}; border-color: {c['border']};
}}
QComboBox {{ min-height: 20px; }}
QComboBox::drop-down {{ border: 0; width: 28px; }}
QComboBox QAbstractItemView {{ background: {c['card']}; border: 1px solid {c['border']}; selection-background-color: {c['selected']}; outline: 0; }}
QPushButton {{
    background: {c['input']}; border: 1px solid {c['border']}; border-radius: 9px;
    padding: 9px 14px; font-weight: 650; color: {c['text_soft']};
}}
QPushButton:hover {{ background: {c['card']}; border-color: {c['border_hover']}; color: {c['text']}; }}
QPushButton:pressed {{ background: {c['selected']}; }}
QPushButton:disabled {{ background: {c['input_disabled']}; border-color: {c['border']}; color: {c['muted']}; }}
QPushButton#PrimaryButton {{ background: {c['primary']}; color: {c['primary_text']}; border: 1px solid {c['primary']}; font-weight: 750; }}
QPushButton#PrimaryButton:hover {{ background: {c['primary_hover']}; border-color: {c['primary_hover']}; }}
QPushButton#SubtleButton {{ background: transparent; border: 1px solid {c['border']}; color: {c['text_soft']}; }}
QPushButton#SubtleButton:hover {{ background: {c['input']}; border-color: {c['border_hover']}; color: {c['text']}; }}
QPushButton#DangerButton {{ background: {c['danger_bg']}; color: {c['danger_text']}; border: 1px solid {c['danger_border']}; }}
QPushButton#ModeButton {{
    text-align: left; min-height: 66px; padding: 12px 14px; background: {c['input']};
    border: 1px solid {c['border']}; border-radius: 11px; color: {c['text_soft']}; font-weight: 650;
}}
QPushButton#ModeButton:hover {{ background: {c['card']}; border-color: {c['border_hover']}; }}
QPushButton#ModeButton:checked {{ background: {c['selected']}; border: 1px solid {c['selected_border']}; color: {c['text']}; }}
QCheckBox, QRadioButton {{ spacing: 9px; color: {c['text_soft']}; background: transparent; }}
QCheckBox::indicator, QRadioButton::indicator {{ width: 18px; height: 18px; }}
QCheckBox::indicator:unchecked {{ background: {c['input']}; border: 1px solid {c['border_hover']}; border-radius: 5px; }}
QCheckBox::indicator:unchecked:hover {{ border-color: {c['primary']}; }}
QCheckBox::indicator:checked {{ image: url("{check_icon}"); border: 0; }}
QCheckBox::indicator:disabled {{ background: {c['input_disabled']}; border-color: {c['border']}; }}
QRadioButton::indicator:unchecked {{ background: {c['input']}; border: 1px solid {c['border_hover']}; border-radius: 9px; }}
QRadioButton::indicator:checked {{ image: url("{radio_icon}"); border: 0; }}
QHeaderView::section {{
    background: {c['input']}; color: {c['text_soft']}; padding: 8px; border: 0;
    border-bottom: 1px solid {c['border']}; font-weight: 650;
}}
QTableWidget {{ gridline-color: {c['border']}; }}
QTableWidget::item {{ padding: 6px; }}
QTableWidget::item:selected, QListWidget::item:selected {{ background: {c['selected']}; color: {c['text']}; }}
QListWidget::item {{ padding: 8px; border-radius: 7px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {c['scroll']}; border-radius: 5px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: {c['border_hover']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ height: 0; background: transparent; }}
QProgressBar {{ border: 1px solid {c['border']}; border-radius: 7px; text-align: center; background: {c['input']}; }}
QProgressBar::chunk {{ background: {c['primary']}; border-radius: 6px; }}
QToolTip {{ background: {c['tooltip']}; color: {c['text']}; border: 1px solid {c['border_hover']}; padding: 6px; }}
QSplitter::handle {{ background: transparent; width: 8px; }}
QMessageBox {{ background: {c['card']}; }}
"""
