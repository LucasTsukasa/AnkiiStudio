from __future__ import annotations

from pathlib import Path

from ankiistudio.ui.design_system.tokens import get_theme_tokens


def build_stylesheet(resource_dir: Path, theme: str = "dark") -> str:
    icons = resource_dir / "icons"
    check_name = "check_crimson.svg" if theme == "crimson" else "check.svg"
    radio_name = "radio_crimson.svg" if theme == "crimson" else "radio.svg"
    check_icon = (icons / check_name).as_posix()
    radio_icon = (icons / radio_name).as_posix()

    t = get_theme_tokens(theme)
    c = t.legacy_mapping()

    return f"""
* {{
    font-family: "Segoe UI", "Noto Sans", sans-serif;
    font-size: 13px;
    color: {c['text']};
}}
QMainWindow, QWidget {{ background: {c['bg']}; }}
QLabel {{ background: transparent; }}
QWidget#PageSurface, QScrollArea#PageScroll, QScrollArea#PageScroll > QWidget > QWidget {{ background: {c['bg']}; }}
QScrollArea#PageScroll {{ border: 0; }}
QFrame#Sidebar {{ background: {c['sidebar']}; border-right: 1px solid {c['border']}; }}
QFrame#BrandPanel {{ background: transparent; border: 0; }}
QLabel#Brand {{ font-size: 19px; font-weight: 800; color: {c['text']}; background: transparent; }}
QLabel#BrandMark {{ font-size: 22px; font-weight: 900; color: {c['primary']}; background: transparent; }}
QLabel#HeroName {{ font-size: 28px; font-weight: 850; color: {c['text']}; background: transparent; }}
QLabel#DeveloperName {{ font-size: 15px; font-weight: 750; color: {c['text']}; background: transparent; }}
QLabel#ImagePreview {{ background: {c['input']}; border: 1px solid {c['border']}; border-radius: 12px; padding: 6px; }}
QLabel#ImageMetadata {{ color: {c['text_soft']}; background: transparent; }}
QLabel#ImageSearchWarning {{
    background: {c['danger_bg']}; color: {c['danger_text']}; border: 1px solid {c['danger_border']};
    border-radius: 8px; padding: 7px 9px;
}}
QFrame#ImageSearchPanel {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 12px; }}
QFrame#ImageSuggestionRow {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 10px; }}
QFrame#ImageSearchDivider {{ color: {c['border']}; background: {c['border']}; border: 0; max-height: 1px; }}
QListWidget#ImageResultList, QListWidget#ImageSuggestionList {{
    background: transparent; border: 0; padding: 2px;
}}
QListWidget#ImageResultList::item, QListWidget#ImageSuggestionList::item {{
    background: {c['input']}; border: 1px solid {c['border']}; border-radius: 9px; padding: 6px;
}}
QListWidget#ImageResultList::item:hover, QListWidget#ImageSuggestionList::item:hover {{
    border-color: {c['border_hover']}; background: {c['card']};
}}
QListWidget#ImageResultList::item:selected, QListWidget#ImageSuggestionList::item:selected {{
    background: {c['selected']}; border: 1px solid {c['selected_border']}; color: {c['text']};
}}
QToolButton#ImageSourceFilterButton {{
    background: {c['input']}; border: 1px solid {c['border']}; border-radius: 9px; padding: 7px;
}}
QToolButton#ImageSourceFilterButton:hover {{ background: {c['card']}; border-color: {c['primary']}; }}
QToolButton#ImageSourceFilterButton::menu-indicator {{ image: none; width: 0px; }}
QToolButton#AiFieldButton {{
    background: transparent; border: 1px solid transparent; border-radius: 7px; padding: 1px;
    color: {c['primary']}; font-size: 14px; font-weight: 700;
}}
QToolButton#AiFieldButton:hover {{ background: {c['selected']}; border-color: {c['selected_border']}; }}
QToolButton#AiFieldButton:disabled {{ color: {c['muted']}; background: transparent; border-color: transparent; }}
QScrollArea#ImageSuggestionScroll {{ background: transparent; border: 0; }}
QPushButton#NavButton {{
    background: transparent; border: 0; border-radius: 9px; padding: 10px 12px;
    text-align: left; color: {c['muted']}; font-size: 13px; font-weight: 600;
}}
QPushButton#NavButton:hover {{ background: {c['input']}; color: {c['text']}; }}
QPushButton#NavButton:checked {{ background: {c['selected']}; color: {c['primary']}; font-weight: 700; }}
QPushButton#SidebarToggle {{ background: transparent; border: 0; border-radius: 9px; padding: 0; color: {c['muted']}; font-size: 18px; font-weight: 700; }}
QPushButton#SidebarToggle:hover {{ background: {c['input']}; color: {c['text']}; }}
QPushButton#CollapsibleHeader {{ background: transparent; border: 0; border-radius: 0; padding: 14px 18px 8px 18px; text-align: left; color: {c['text']}; font-size: 15px; font-weight: 750; }}
QPushButton#CollapsibleHeader:hover {{ background: {c['input']}; }}
QWidget#CollapsibleBody {{ background: transparent; }}
QFrame#TaskCenter {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 12px; }}
QFrame#TaskRow {{ background: {c['input']}; border: 1px solid {c['border']}; border-radius: 9px; }}
QLabel[taskError="true"] {{ color: {c['danger_text']}; }}
QFrame#ProjectCard {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 14px; }}
QFrame#ProjectCard:hover {{ border-color: {c['primary']}; background: {c['hero']}; }}
QPushButton#ProjectCardButton {{ background: transparent; border: 0; text-align: left; padding: 0; font-size: 16px; font-weight: 750; color: {c['text']}; }}
QPushButton#ProjectCardButton:hover {{ color: {c['primary']}; }}
QToolButton#ProjectCardMenuButton {{
    background: transparent; border: 1px solid transparent; border-radius: 7px;
    color: {c['muted']}; font-size: 16px; font-weight: 700; padding: 0;
}}
QToolButton#ProjectCardMenuButton:hover {{ background: {c['input']}; border-color: {c['border_hover']}; color: {c['text']}; }}
QLabel#ProjectTopic {{ color: {c['text_soft']}; font-size: 13px; font-weight: 600; background: transparent; }}
QFrame#CardPreviewStage {{ background: {c['input']}; border: 1px solid {c['border']}; border-radius: 12px; }}
QTextBrowser#CardPreviewBrowser {{ background: transparent; border: 0; border-radius: 10px; padding: 0; }}
QFrame#CreateActionBar {{ background: {c['bg']}; border-top: 1px solid {c['border']}; }}
QPushButton#SettingsCategory {{ background: transparent; border: 0; text-align: left; padding: 10px 12px; color: {c['muted']}; }}
QPushButton#SettingsCategory:checked {{ background: {c['selected']}; color: {c['primary']}; font-weight: 750; }}
QDialog#SettingsDialog, QDialog#UpdateDialog {{ background: {c['bg']}; }}
QLabel#PageTitle {{ font-size: 25px; font-weight: 800; color: {c['text']}; background: transparent; }}
QLabel#PageSubtitle {{ color: {c['muted']}; font-size: 13px; background: transparent; }}
QLabel#SectionTitle {{ font-size: 16px; font-weight: 750; color: {c['text']}; background: transparent; }}
QLabel#SectionSubtitle, QLabel#MutedLabel {{ color: {c['muted']}; background: transparent; }}
QLabel#FieldLabel {{ color: {c['text_soft']}; font-size: 12px; font-weight: 650; background: transparent; }}
QLabel#Badge {{
    background: {c['selected']}; color: {c['primary']}; border: 1px solid {c['selected_border']};
    border-radius: 9px; padding: 3px 8px; font-size: 11px; font-weight: 700;
}}
QFrame#RoadmapCard, QFrame#RoadmapCardCurrent {{
    background: {c['card']}; border: 1px solid {c['border']}; border-radius: 14px;
}}
QFrame#RoadmapCardCurrent {{ border: 1px solid {c['selected_border']}; background: {c['hero']}; }}
QFrame#RoadmapLine {{ background: {c['border_hover']}; border: 0; }}
QLabel#RoadmapTitle {{ font-size: 16px; font-weight: 780; color: {c['text']}; background: transparent; }}
QLabel#RoadmapDescription {{ color: {c['text_soft']}; background: transparent; }}
QLabel#RoadmapDetails {{ color: {c['muted']}; background: transparent; }}
QLabel#RoadmapStatusCompleted, QLabel#RoadmapStatusInProgress, QLabel#RoadmapStatusPlanned, QLabel#RoadmapCurrentBadge {{
    border-radius: 8px; padding: 3px 7px; font-size: 10px; font-weight: 750; background: transparent;
}}
QLabel#RoadmapStatusCompleted {{ color: {c['primary']}; border: 1px solid {c['selected_border']}; background: {c['selected']}; }}
QLabel#RoadmapStatusInProgress {{ color: {c['primary_text']}; border: 1px solid {c['primary']}; background: {c['primary']}; }}
QLabel#RoadmapStatusPlanned {{ color: {c['muted']}; border: 1px solid {c['border_hover']}; background: {c['input']}; }}
QLabel#RoadmapCurrentBadge {{ color: {c['primary']}; border: 0; padding-left: 0; }}
QLabel#RoadmapNodeCompleted {{ color: {c['primary']}; font-size: 20px; background: transparent; }}
QLabel#RoadmapNodeInProgress {{ color: {c['primary']}; font-size: 26px; font-weight: 900; background: transparent; }}
QLabel#RoadmapNodePlanned {{ color: {c['muted']}; font-size: 20px; background: transparent; }}
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
QPushButton:focus {{ border: 1px solid {c['primary']}; }}
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

/* AnkiiStudio Design System v1 ------------------------------------------------ */
QFrame#ASSidebar {{ background: {c['sidebar']}; border-right: 1px solid {c['border']}; }}
QPushButton#ASSidebarItem {{
    background: transparent; border: 0; border-radius: 9px; padding: 10px 12px;
    text-align: left; color: {c['muted']}; font-size: 13px; font-weight: 600;
}}
QPushButton#ASSidebarItem:hover {{ background: {c['input']}; color: {c['text']}; }}
QPushButton#ASSidebarItem:checked {{ background: {c['selected']}; color: {c['primary']}; font-weight: 700; }}
QPushButton#ASButton[asComponent="sidebar-item"] {{
    background: transparent; border: 0; border-radius: 9px; padding: 10px 12px;
    text-align: left; color: {c['muted']}; font-size: 13px; font-weight: 600;
}}
QPushButton#ASButton[asComponent="sidebar-item"]:hover {{ background: {c['input']}; color: {c['text']}; }}
QPushButton#ASButton {{ min-height: 18px; }}
QPushButton#ASButton[asVariant="primary"] {{ background: {c['primary']}; color: {c['primary_text']}; border-color: {c['primary']}; font-weight: 750; }}
QPushButton#ASButton[asVariant="primary"]:hover {{ background: {c['primary_hover']}; border-color: {c['primary_hover']}; }}
QPushButton#ASButton[asVariant="secondary"] {{ background: {c['card']}; color: {c['text']}; border-color: {c['border_hover']}; }}
QPushButton#ASButton[asVariant="ghost"] {{ background: transparent; border-color: transparent; color: {c['text_soft']}; }}
QPushButton#ASButton[asVariant="ghost"]:hover {{ background: {c['input']}; color: {c['text']}; }}
QPushButton#ASButton[asVariant="danger"] {{ background: {c['danger_bg']}; color: {c['danger_text']}; border-color: {c['danger_border']}; }}
QPushButton#ASButton[asVariant="icon"] {{ background: transparent; border-color: transparent; padding: 7px; }}
QFrame#ASCard, QFrame#ASSectionCard, QFrame#ASToast {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 14px; }}
QFrame#ASCard[asVariant="raised"] {{ background: {c['hero']}; border-color: {c['border_hover']}; }}
QFrame#ASCard[asVariant="interactive"]:hover {{ background: {c['hero']}; border-color: {c['primary']}; }}
QFrame#ASCard[asVariant="selected"] {{ background: {c['selected']}; border-color: {c['selected_border']}; }}
QFrame#ASCard[asVariant="danger"], QFrame#ASToast[asVariant="danger"] {{ background: {c['danger_bg']}; border-color: {c['danger_border']}; }}
QFrame#ASCard[asVariant="warning"], QFrame#ASToast[asVariant="warning"] {{ background: {t.warning_bg}; border-color: {c['border_hover']}; }}
QFrame#ASCard[asVariant="success"], QFrame#ASToast[asVariant="success"] {{ background: {t.success_bg}; border-color: {c['selected_border']}; }}
QFrame#Card[asVariant="danger"] {{ background: {c['danger_bg']}; border-color: {c['danger_border']}; }}
QFrame#Card[asVariant="success"] {{ background: {t.success_bg}; border-color: {c['selected_border']}; }}
QLineEdit#ASInput[asError="true"], QTextEdit#ASInput[asError="true"], QPlainTextEdit#ASInput[asError="true"] {{ border-color: {c['danger_text']}; }}
QComboBox#ASComboBox {{ min-height: 20px; }}
QDialog#ASDialog {{ background: {c['bg']}; }}
QTabWidget#ASTabs::pane {{ border: 0; border-top: 1px solid {c['border']}; background: transparent; }}
QTabBar::tab {{ background: transparent; color: {c['muted']}; border: 0; padding: 10px 14px; font-weight: 650; }}
QTabBar::tab:hover {{ color: {c['text']}; background: {c['input']}; }}
QTabBar::tab:selected {{ color: {c['primary']}; border-bottom: 2px solid {c['primary']}; }}
QMenu#ASContextMenu {{ background: {c['card']}; border: 1px solid {c['border']}; padding: 6px; }}
QMenu#ASContextMenu::item {{ padding: 7px 24px 7px 10px; border-radius: 6px; }}
QMenu#ASContextMenu::item:selected {{ background: {c['selected']}; color: {c['text']}; }}
QProgressBar#ASProgress {{ min-height: 8px; }}
QTableView#ASTable, QTableWidget#ASTable {{ background: {c['input']}; border: 1px solid {c['border']}; border-radius: 9px; gridline-color: transparent; }}
QTableView#ASTable::item, QTableWidget#ASTable::item {{ padding: 7px; border-bottom: 1px solid {c['border']}; }}
QTableView#ASTable::item:selected, QTableWidget#ASTable::item:selected {{ background: {c['selected']}; color: {c['text']}; }}
QLabel[asTextRole="title"] {{ font-size: 25px; font-weight: 800; color: {c['text']}; }}
QLabel[asTextRole="section"] {{ font-size: 16px; font-weight: 750; color: {c['text']}; }}
QLabel[asTextRole="muted"] {{ color: {c['muted']}; }}
QWidget#ASToastManager {{ background: transparent; }}
"""
