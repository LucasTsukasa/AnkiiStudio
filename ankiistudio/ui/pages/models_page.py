from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
    QComboBox,
)

from ankiistudio.constants import COMPONENT_LABELS
from ankiistudio.database import Database
from ankiistudio.models import DeckThemeSettings, FlashcardData, ProjectData
from ankiistudio.services.project_service import ProjectService
from ankiistudio.services.card_template_service import render_preview_document
from ankiistudio.ui.widgets import AdaptiveSplitter, ComponentOrderEditor, PageHeader, PageScrollArea, SectionCard


class ModelsPage(QWidget):
    def __init__(self, database: Database) -> None:
        super().__init__()
        self.database = database
        self.current_project: ProjectData | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(12)
        layout.addWidget(PageHeader("Modelos de cartão", "Edite a estrutura, os subbaralhos e o tema visual de cada projeto."))

        selector_card = SectionCard()
        selector = QHBoxLayout()
        label = QLabel("Projeto")
        label.setObjectName("FieldLabel")
        self.project_combo = QComboBox()
        self.project_combo.currentIndexChanged.connect(self.load_project)
        self.save_button = QPushButton("Salvar modelo")
        self.save_button.setObjectName("PrimaryButton")
        self.save_button.clicked.connect(self.save_model)
        selector.addWidget(label)
        selector.addWidget(self.project_combo, 1)
        selector.addWidget(self.save_button)
        selector_card.root.addLayout(selector)
        layout.addWidget(selector_card)

        editors_card = SectionCard("Frente e verso", "Somente os componentes escolhidos serão exibidos nos cartões exportados.")
        editors = AdaptiveSplitter(breakpoint=800)
        self.front_editor = ComponentOrderEditor("Frente", [])
        self.back_editor = ComponentOrderEditor("Verso", [])
        editors.addWidget(self.front_editor)
        editors.addWidget(self.back_editor)
        editors.setStretchFactor(0, 1)
        editors.setStretchFactor(1, 1)
        editors_card.root.addWidget(editors)
        layout.addWidget(editors_card)

        structure_card = SectionCard(
            "Estrutura do baralho",
            "Organize os cartões em subbaralhos. A ordem abaixo fica salva no projeto.",
        )
        self.section_list = QListWidget()
        self.section_list.setMinimumHeight(150)
        structure_card.root.addWidget(self.section_list)
        section_actions = QHBoxLayout()
        self.add_section_button = QPushButton("Adicionar")
        self.rename_section_button = QPushButton("Renomear")
        self.delete_section_button = QPushButton("Excluir")
        self.section_up_button = QPushButton("↑")
        self.section_down_button = QPushButton("↓")
        for button in (
            self.add_section_button,
            self.rename_section_button,
            self.delete_section_button,
            self.section_up_button,
            self.section_down_button,
        ):
            button.setObjectName("SubtleButton")
        self.add_section_button.clicked.connect(self.add_section)
        self.rename_section_button.clicked.connect(self.rename_section)
        self.delete_section_button.clicked.connect(self.delete_section)
        self.section_up_button.clicked.connect(lambda: self.move_section(-1))
        self.section_down_button.clicked.connect(lambda: self.move_section(1))
        section_actions.addWidget(self.add_section_button)
        section_actions.addWidget(self.rename_section_button)
        section_actions.addWidget(self.delete_section_button)
        section_actions.addStretch(1)
        section_actions.addWidget(self.section_up_button)
        section_actions.addWidget(self.section_down_button)
        structure_card.root.addLayout(section_actions)
        layout.addWidget(structure_card)

        theme_card = SectionCard("Tema do baralho", "A aparência é salva por projeto e aplicada ao arquivo .apkg.")
        theme_grid = QGridLayout()
        theme_grid.setHorizontalSpacing(12)
        theme_grid.setVerticalSpacing(8)
        self.theme_background = QLineEdit()
        self.theme_card_background = QLineEdit()
        self.theme_primary = QLineEdit()
        self.theme_text = QLineEdit()
        self.theme_secondary = QLineEdit()
        self.theme_border = QLineEdit()
        self.theme_font = QLineEdit()
        self.theme_word_size = QSpinBox()
        self.theme_word_size.setRange(18, 96)
        self.theme_translation_size = QSpinBox()
        self.theme_translation_size.setRange(14, 72)
        fields = [
            ("Fundo", self.theme_background),
            ("Fundo do cartão", self.theme_card_background),
            ("Cor principal", self.theme_primary),
            ("Texto", self.theme_text),
            ("Texto secundário", self.theme_secondary),
            ("Borda", self.theme_border),
            ("Fonte", self.theme_font),
            ("Tamanho da palavra", self.theme_word_size),
            ("Tamanho da tradução", self.theme_translation_size),
        ]
        for index, (field_label, widget) in enumerate(fields):
            cell = QWidget()
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            cell_layout.setSpacing(4)
            title = QLabel(field_label)
            title.setObjectName("FieldLabel")
            cell_layout.addWidget(title)
            cell_layout.addWidget(widget)
            theme_grid.addWidget(cell, index, 0)
        theme_card.root.addLayout(theme_grid)
        layout.addWidget(theme_card)

        preview_card = SectionCard(
            "Pré-visualização real",
            "Usa o mesmo estilo dos cartões exportados para o Anki. Quando possível, exibe dados reais do primeiro cartão do projeto.",
        )
        preview_splitter = AdaptiveSplitter(breakpoint=800)
        self.front_preview = QTextBrowser()
        self.back_preview = QTextBrowser()
        self.preview = self.front_preview  # compatibilidade com integrações anteriores
        for title_text, browser in (("Frente", self.front_preview), ("Verso", self.back_preview)):
            pane = QWidget()
            pane_layout = QVBoxLayout(pane)
            pane_layout.setContentsMargins(0, 0, 0, 0)
            pane_layout.setSpacing(5)
            pane_label = QLabel(title_text)
            pane_label.setObjectName("FieldLabel")
            browser.setMinimumHeight(320)
            browser.setOpenExternalLinks(False)
            pane_layout.addWidget(pane_label)
            pane_layout.addWidget(browser)
            preview_splitter.addWidget(pane)
        preview_splitter.setStretchFactor(0, 1)
        preview_splitter.setStretchFactor(1, 1)
        preview_card.root.addWidget(preview_splitter)
        layout.addWidget(preview_card)

        self.front_editor.changed.connect(self.update_preview)
        self.back_editor.changed.connect(self.update_preview)
        for widget in (
            self.theme_background,
            self.theme_card_background,
            self.theme_primary,
            self.theme_text,
            self.theme_secondary,
            self.theme_border,
            self.theme_font,
        ):
            widget.textChanged.connect(self.update_preview)
        self.theme_word_size.valueChanged.connect(self.update_preview)
        self.theme_translation_size.valueChanged.connect(self.update_preview)

        layout.addStretch(1)
        root.addWidget(PageScrollArea(content))
        self.refresh()

    def refresh(self) -> None:
        current_id = self.current_project.id if self.current_project else None
        self.project_combo.blockSignals(True)
        self.project_combo.clear()
        for project in self.database.list_projects():
            self.project_combo.addItem(project.name, project.id)
        self.project_combo.blockSignals(False)
        has_projects = self.project_combo.count() > 0
        self.save_button.setEnabled(has_projects)
        if not has_projects:
            self.current_project = None
            self.front_editor.set_components([])
            self.back_editor.set_components([])
            self.section_list.clear()
            self._load_theme(DeckThemeSettings())
            self.update_preview()
            return
        index = 0
        if current_id is not None:
            for i in range(self.project_combo.count()):
                if self.project_combo.itemData(i) == current_id:
                    index = i
                    break
        self.project_combo.setCurrentIndex(index)
        self.load_project()

    def load_project(self) -> None:
        project_id = self.project_combo.currentData()
        if project_id is None:
            self.current_project = None
            self.save_button.setEnabled(False)
            return
        self.current_project = self.database.get_project(int(project_id))
        self.save_button.setEnabled(self.current_project is not None)
        if not self.current_project:
            return
        self.front_editor.set_components(self.current_project.front_components)
        self.back_editor.set_components(self.current_project.back_components)
        sections = list(self.current_project.deck_sections)
        if not sections and self.current_project.id is not None:
            sections = ProjectService.derive_sections(self.database.list_cards(self.current_project.id))
        self._set_sections(sections)
        self._load_theme(self.current_project.card_theme)
        self.update_preview()

    def _set_sections(self, sections: list[str]) -> None:
        self.section_list.clear()
        counts: dict[str, int] = {}
        if self.current_project and self.current_project.id is not None:
            for card in self.database.list_cards(self.current_project.id):
                counts[card.section] = counts.get(card.section, 0) + 1
        for section in sections:
            item = QListWidgetItem(f"{section}   ·   {counts.get(section, 0)} cartões")
            item.setData(Qt.ItemDataRole.UserRole, section)
            self.section_list.addItem(item)
        if self.section_list.count():
            self.section_list.setCurrentRow(0)

    def sections(self) -> list[str]:
        return [
            str(self.section_list.item(index).data(Qt.ItemDataRole.UserRole))
            for index in range(self.section_list.count())
        ]

    def add_section(self) -> None:
        name, ok = QInputDialog.getText(self, "Adicionar subbaralho", "Nome")
        name = name.strip()
        if not ok or not name:
            return
        if name.casefold() in {section.casefold() for section in self.sections()}:
            QMessageBox.warning(self, "Nome repetido", "Já existe um subbaralho com esse nome.")
            return
        item = QListWidgetItem(f"{name}   ·   0 cartões")
        item.setData(Qt.ItemDataRole.UserRole, name)
        self.section_list.addItem(item)
        self.section_list.setCurrentItem(item)

    def rename_section(self) -> None:
        item = self.section_list.currentItem()
        if item is None or self.current_project is None or self.current_project.id is None:
            return
        old = str(item.data(Qt.ItemDataRole.UserRole))
        name, ok = QInputDialog.getText(self, "Renomear subbaralho", "Novo nome", text=old)
        name = name.strip()
        if not ok or not name or name == old:
            return
        if name.casefold() in {section.casefold() for section in self.sections() if section != old}:
            QMessageBox.warning(self, "Nome repetido", "Já existe um subbaralho com esse nome.")
            return
        self.database.rename_card_section(self.current_project.id, old, name)
        item.setData(Qt.ItemDataRole.UserRole, name)
        self._set_sections([name if section == old else section for section in self.sections()])

    def delete_section(self) -> None:
        item = self.section_list.currentItem()
        if item is None or self.current_project is None or self.current_project.id is None:
            return
        name = str(item.data(Qt.ItemDataRole.UserRole))
        if QMessageBox.question(
            self,
            "Excluir subbaralho",
            f"Excluir “{name}”? Os cartões desse grupo voltarão para o baralho principal.",
        ) != QMessageBox.StandardButton.Yes:
            return
        self.database.clear_card_section(self.current_project.id, name)
        self.section_list.takeItem(self.section_list.row(item))

    def move_section(self, direction: int) -> None:
        row = self.section_list.currentRow()
        target = row + direction
        if row < 0 or target < 0 or target >= self.section_list.count():
            return
        item = self.section_list.takeItem(row)
        self.section_list.insertItem(target, item)
        self.section_list.setCurrentRow(target)

    def _load_theme(self, theme: DeckThemeSettings) -> None:
        self.theme_background.setText(theme.background)
        self.theme_card_background.setText(theme.card_background)
        self.theme_primary.setText(theme.primary)
        self.theme_text.setText(theme.text)
        self.theme_secondary.setText(theme.secondary_text)
        self.theme_border.setText(theme.border)
        self.theme_font.setText(theme.font_family)
        self.theme_word_size.setValue(theme.word_size)
        self.theme_translation_size.setValue(theme.translation_size)

    def _collect_theme(self) -> DeckThemeSettings:
        return DeckThemeSettings(
            background=self.theme_background.text().strip(),
            card_background=self.theme_card_background.text().strip(),
            primary=self.theme_primary.text().strip(),
            text=self.theme_text.text().strip(),
            secondary_text=self.theme_secondary.text().strip(),
            border=self.theme_border.text().strip(),
            font_family=self.theme_font.text().strip(),
            word_size=self.theme_word_size.value(),
            translation_size=self.theme_translation_size.value(),
        )

    def save_model(self) -> None:
        if self.current_project is None:
            QMessageBox.warning(self, "Sem projeto", "Selecione ou crie um projeto antes de salvar um modelo.")
            return
        front = self.front_editor.components()
        back = self.back_editor.components()
        if not front or not back:
            QMessageBox.warning(self, "Modelo inválido", "Frente e verso precisam ter conteúdo.")
            return
        try:
            theme = self._collect_theme()
        except Exception as exc:
            QMessageBox.warning(self, "Tema inválido", str(exc))
            return
        self.current_project.front_components = front
        self.current_project.back_components = back
        self.current_project.deck_sections = self.sections()
        self.current_project.card_theme = theme
        self.database.update_project(self.current_project)
        QMessageBox.information(self, "Modelo salvo", "Estrutura, ordem dos subbaralhos e tema foram atualizados.")
        self.update_preview()

    def update_preview(self, *_args) -> None:
        try:
            theme = self._collect_theme()
        except Exception:
            theme = self.current_project.card_theme if self.current_project else DeckThemeSettings()

        sample: FlashcardData | None = None
        if self.current_project is not None and self.current_project.id is not None:
            cards = self.database.list_cards(self.current_project.id)
            if cards:
                sample = cards[0]

        self.front_preview.setHtml(
            render_preview_document(self.front_editor.components(), theme, sample)
        )
        self.back_preview.setHtml(
            render_preview_document(self.back_editor.components(), theme, sample)
        )
