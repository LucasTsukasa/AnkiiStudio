from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
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
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
    QComboBox,
)

from ankiistudio.constants import COMPONENT_LABELS
from ankiistudio.database import Database
from ankiistudio.i18n import tr
from ankiistudio.models import DeckThemeSettings, FlashcardData, ProjectData
from ankiistudio.services.theme_settings import load_default_card_theme
from ankiistudio.services.card_template_service import render_preview_document
from ankiistudio.ui.design_system.components import ASButton, ASComboBox, ASLineEdit
from ankiistudio.ui.widgets import AdaptiveSplitter, ComponentOrderEditor, PageHeader, PageScrollArea, SectionCard


DENSITY_PRESETS = {
    "compact": {"image_max_height": 240, "card_max_width": 640, "card_padding": 14, "component_spacing": 6},
    "normal": {"image_max_height": 320, "card_max_width": 720, "card_padding": 20, "component_spacing": 10},
    "spacious": {"image_max_height": 420, "card_max_width": 760, "card_padding": 28, "component_spacing": 14},
}


class CardPreviewStage(QFrame):
    """Área de apresentação do cartão, sem alterar o HTML/CSS exportado.

    O QTextBrowser possui um sizeHint relativamente estreito. Quando ele era
    centralizado diretamente no SectionCard, o preview desktop acabava parecendo
    uma tela de celular e podia exibir uma barra horizontal. Este container dá ao
    renderer uma viewport previsível e responsiva, preservando o documento usado
    pela exportação.
    """

    DESKTOP_MAX_WIDTH = 760
    DESKTOP_HEIGHT = 400
    MOBILE_MAX_WIDTH = 390
    MOBILE_HEIGHT = 520

    def __init__(self, browser: QTextBrowser, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.browser = browser
        self._device = "desktop"
        self.setObjectName("CardPreviewStage")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(22, 22, 22, 22)
        self._layout.setSpacing(0)

        # O browser pode crescer até a largura simulada do dispositivo, mas nunca
        # força o container/página a ultrapassar o viewport disponível. Os stretches
        # laterais apenas centralizam o preview quando há espaço sobrando.
        self._preview_row = QHBoxLayout()
        self._preview_row.setContentsMargins(0, 0, 0, 0)
        self._preview_row.setSpacing(0)
        self._preview_row.addStretch(1)
        self._preview_row.addWidget(self.browser, 1000)
        self._preview_row.addStretch(1)
        self._layout.addLayout(self._preview_row)
        self.set_device("desktop")

    def set_device(self, device: str) -> None:
        self._device = "mobile" if device == "mobile" else "desktop"
        if self._device == "mobile":
            max_width = self.MOBILE_MAX_WIDTH
            target_height = self.MOBILE_HEIGHT
            minimum_height = 564
        else:
            max_width = self.DESKTOP_MAX_WIDTH
            target_height = self.DESKTOP_HEIGHT
            minimum_height = 444

        self.setMinimumHeight(minimum_height)
        self.browser.setMinimumWidth(0)
        self.browser.setMaximumWidth(max_width)
        self.browser.setFixedHeight(target_height)
        self.browser.updateGeometry()


class ModelsPage(QWidget):
    def __init__(self, database: Database, *, embedded: bool = False) -> None:
        super().__init__()
        self.database = database
        self.embedded = embedded
        self.current_project: ProjectData | None = None
        self._preview_showing_answer = False
        self._preview_sample_project_id: int | None = None
        self._preview_sample: FlashcardData | None = None
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(90)
        self._preview_timer.timeout.connect(self.update_preview)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(12)
        if not embedded:
            layout.addWidget(PageHeader("Modelos de cartão", "Edite a estrutura, os subbaralhos e o tema visual de cada projeto."))

        selector_card = SectionCard()
        selector = QHBoxLayout()
        label = QLabel("Projeto")
        label.setObjectName("FieldLabel")
        self.project_combo = ASComboBox()
        self.project_combo.currentIndexChanged.connect(self.load_project)
        self.save_button = ASButton("Salvar modelo")
        self.save_button.setObjectName("PrimaryButton")
        self.save_button.clicked.connect(self.save_model)
        selector.addWidget(label)
        selector.addWidget(self.project_combo, 1)
        selector.addWidget(self.save_button)
        selector_card.root.addLayout(selector)
        layout.addWidget(selector_card)
        selector_card.setVisible(not embedded)

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
        self.add_section_button = ASButton("Adicionar")
        self.rename_section_button = ASButton("Renomear")
        self.delete_section_button = ASButton("Excluir")
        self.section_up_button = ASButton("↑")
        self.section_down_button = ASButton("↓")
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

        theme_card = SectionCard(
            "Tema do baralho",
            "A aparência é salva por projeto e aplicada ao arquivo .apkg.",
        )
        theme_grid = QGridLayout()
        theme_grid.setHorizontalSpacing(12)
        theme_grid.setVerticalSpacing(9)
        theme_grid.setColumnStretch(0, 1)
        theme_grid.setColumnStretch(1, 1)

        self.theme_density = ASComboBox()
        self.theme_density.addItem("Compacto", "compact")
        self.theme_density.addItem("Normal", "normal")
        self.theme_density.addItem("Espaçoso", "spacious")
        self.theme_density.addItem("Personalizado", "custom")
        self.theme_background = ASLineEdit()
        self.theme_card_background = ASLineEdit()
        self.theme_primary = ASLineEdit()
        self.theme_text = ASLineEdit()
        self.theme_secondary = ASLineEdit()
        self.theme_border = ASLineEdit()
        self.theme_font = ASLineEdit()

        self.theme_word_size = self._pixel_spin(18, 96)
        self.theme_reading_size = self._pixel_spin(12, 72)
        self.theme_romanization_size = self._pixel_spin(10, 48)
        self.theme_translation_size = self._pixel_spin(14, 72)
        self.theme_example_size = self._pixel_spin(12, 72)
        self.theme_explanation_size = self._pixel_spin(12, 48)
        self.theme_mnemonic_size = self._pixel_spin(12, 48)
        self.theme_image_max_height = self._pixel_spin(120, 900)
        self.theme_card_max_width = self._pixel_spin(360, 1200)
        self.theme_card_padding = self._pixel_spin(8, 64)
        self.theme_component_spacing = self._pixel_spin(0, 32)

        fields = [
            ("Densidade do layout", self.theme_density),
            ("Fonte", self.theme_font),
            ("Fundo", self.theme_background),
            ("Fundo do cartão", self.theme_card_background),
            ("Cor principal", self.theme_primary),
            ("Texto", self.theme_text),
            ("Texto secundário", self.theme_secondary),
            ("Borda", self.theme_border),
            ("Tamanho do conteúdo principal", self.theme_word_size),
            ("Tamanho da leitura", self.theme_reading_size),
            ("Tamanho da romanização", self.theme_romanization_size),
            ("Tamanho da tradução", self.theme_translation_size),
            ("Tamanho do exemplo", self.theme_example_size),
            ("Tamanho da explicação", self.theme_explanation_size),
            ("Tamanho do mnemônico", self.theme_mnemonic_size),
            ("Altura máxima da imagem", self.theme_image_max_height),
            ("Largura máxima do cartão", self.theme_card_max_width),
            ("Espaçamento interno", self.theme_card_padding),
            ("Espaço entre componentes", self.theme_component_spacing),
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
            theme_grid.addWidget(cell, index // 2, index % 2)
        theme_card.root.addLayout(theme_grid)
        theme_actions = QHBoxLayout()
        self.apply_global_theme_button = ASButton("Aplicar tema padrão global")
        self.apply_global_theme_button.setObjectName("SubtleButton")
        self.apply_global_theme_button.setToolTip(
            "Carrega o tema padrão definido em Configurações. A alteração só é gravada neste projeto ao clicar em Salvar modelo."
        )
        self.apply_global_theme_button.clicked.connect(self.apply_global_theme)
        theme_actions.addWidget(self.apply_global_theme_button)
        theme_actions.addStretch(1)
        theme_card.root.addLayout(theme_actions)
        layout.addWidget(theme_card)

        preview_card = SectionCard(
            "Pré-visualização no Anki",
            "Visualize frente e resposta com o mesmo HTML/CSS usado na exportação.",
        )
        preview_controls = QHBoxLayout()
        preview_controls.setSpacing(8)
        preview_label = QLabel("Visualização")
        preview_label.setObjectName("FieldLabel")
        self.preview_device = ASComboBox()
        self.preview_device.addItem("Desktop", "desktop")
        self.preview_device.addItem("Celular", "mobile")
        self.preview_device.setMinimumWidth(130)
        self.preview_device.currentIndexChanged.connect(self._apply_preview_device)
        self.preview_toggle = ASButton("Mostrar resposta")
        self.preview_toggle.setObjectName("PrimaryButton")
        self.preview_toggle.clicked.connect(self._toggle_preview_side)
        preview_controls.addWidget(preview_label)
        preview_controls.addWidget(self.preview_device)
        preview_controls.addStretch(1)
        preview_controls.addWidget(self.preview_toggle)
        preview_card.root.addLayout(preview_controls)
        self.front_preview = QTextBrowser()
        self.front_preview.setObjectName("CardPreviewBrowser")
        self.back_preview = QTextBrowser()  # buffer compatível com integrações antigas
        self.back_preview.hide()
        self.preview = self.front_preview
        self.front_preview.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.front_preview.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.front_preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.front_preview.setOpenExternalLinks(False)
        self.preview_stage = CardPreviewStage(self.front_preview)
        preview_card.root.addWidget(self.preview_stage)
        layout.addWidget(preview_card)

        self.front_editor.changed.connect(self._schedule_preview_update)
        self.back_editor.changed.connect(self._schedule_preview_update)
        for widget in (
            self.theme_background,
            self.theme_card_background,
            self.theme_primary,
            self.theme_text,
            self.theme_secondary,
            self.theme_border,
            self.theme_font,
        ):
            widget.textChanged.connect(self._schedule_preview_update)
        self.theme_density.currentIndexChanged.connect(self._apply_density_preset)
        for widget in self._theme_numeric_widgets():
            widget.valueChanged.connect(self._theme_numeric_changed)
            widget.valueChanged.connect(self._schedule_preview_update)

        layout.addStretch(1)
        root.addWidget(PageScrollArea(content))
        self.refresh()

    def _schedule_preview_update(self, *_args) -> None:
        self._preview_timer.start()

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
            self._preview_sample_project_id = None
            self._preview_sample = None
            self.save_button.setEnabled(False)
            return
        self.current_project = self.database.get_project(int(project_id))
        self._preview_sample_project_id = None
        self._preview_sample = None
        self.save_button.setEnabled(self.current_project is not None)
        if not self.current_project:
            return
        self.front_editor.set_components(self.current_project.front_components)
        self.back_editor.set_components(self.current_project.back_components)
        sections = list(self.current_project.deck_sections)
        if not sections and self.current_project.id is not None:
            sections = self.database.list_card_sections(self.current_project.id)
        self._set_sections(sections)
        self._load_theme(self.current_project.card_theme)
        self.update_preview()

    def _set_sections(self, sections: list[str]) -> None:
        self.section_list.clear()
        counts: dict[str, int] = {}
        if self.current_project and self.current_project.id is not None:
            counts = self.database.project_section_counts(self.current_project.id)
        for section in sections:
            item = QListWidgetItem(tr(f"{section}   ·   {counts.get(section, 0)} cartões"))
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
        item = QListWidgetItem(tr(f"{name}   ·   0 cartões"))
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

    @staticmethod
    def _pixel_spin(minimum: int, maximum: int) -> QSpinBox:
        widget = QSpinBox()
        widget.setRange(minimum, maximum)
        widget.setSuffix(" px")
        return widget

    def _theme_numeric_widgets(self) -> tuple[QSpinBox, ...]:
        return (
            self.theme_word_size,
            self.theme_reading_size,
            self.theme_romanization_size,
            self.theme_translation_size,
            self.theme_example_size,
            self.theme_explanation_size,
            self.theme_mnemonic_size,
            self.theme_image_max_height,
            self.theme_card_max_width,
            self.theme_card_padding,
            self.theme_component_spacing,
        )

    def _layout_numeric_widgets(self) -> tuple[QSpinBox, ...]:
        return (
            self.theme_image_max_height,
            self.theme_card_max_width,
            self.theme_card_padding,
            self.theme_component_spacing,
        )

    def _load_theme(self, theme: DeckThemeSettings) -> None:
        self.theme_background.setText(theme.background)
        self.theme_card_background.setText(theme.card_background)
        self.theme_primary.setText(theme.primary)
        self.theme_text.setText(theme.text)
        self.theme_secondary.setText(theme.secondary_text)
        self.theme_border.setText(theme.border)
        self.theme_font.setText(theme.font_family)
        self.theme_word_size.setValue(theme.word_size)
        self.theme_reading_size.setValue(theme.reading_size)
        self.theme_romanization_size.setValue(theme.romanization_size)
        self.theme_translation_size.setValue(theme.translation_size)
        self.theme_example_size.setValue(theme.example_size)
        self.theme_explanation_size.setValue(theme.explanation_size)
        self.theme_mnemonic_size.setValue(theme.mnemonic_size)
        self.theme_image_max_height.setValue(theme.image_max_height)
        self.theme_card_max_width.setValue(theme.card_max_width)
        self.theme_card_padding.setValue(theme.card_padding)
        self.theme_component_spacing.setValue(theme.component_spacing)
        previous = self.theme_density.blockSignals(True)
        index = self.theme_density.findData(theme.layout_density)
        self.theme_density.setCurrentIndex(index if index >= 0 else self.theme_density.findData("custom"))
        self.theme_density.blockSignals(previous)

    def apply_global_theme(self) -> None:
        self._load_theme(load_default_card_theme(self.database))
        self.update_preview()

    def _apply_density_preset(self, *_args) -> None:
        key = str(self.theme_density.currentData() or "custom")
        preset = DENSITY_PRESETS.get(key)
        if preset is None:
            self.update_preview()
            return
        mapping = {
            "image_max_height": self.theme_image_max_height,
            "card_max_width": self.theme_card_max_width,
            "card_padding": self.theme_card_padding,
            "component_spacing": self.theme_component_spacing,
        }
        for name, widget in mapping.items():
            previous = widget.blockSignals(True)
            widget.setValue(int(preset[name]))
            widget.blockSignals(previous)
        self.update_preview()

    def _theme_numeric_changed(self, *_args) -> None:
        key = str(self.theme_density.currentData() or "custom")
        preset = DENSITY_PRESETS.get(key)
        if preset is None:
            return
        current = {
            "image_max_height": self.theme_image_max_height.value(),
            "card_max_width": self.theme_card_max_width.value(),
            "card_padding": self.theme_card_padding.value(),
            "component_spacing": self.theme_component_spacing.value(),
        }
        if current != preset:
            previous = self.theme_density.blockSignals(True)
            custom_index = self.theme_density.findData("custom")
            self.theme_density.setCurrentIndex(custom_index)
            self.theme_density.blockSignals(previous)

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
            reading_size=self.theme_reading_size.value(),
            romanization_size=self.theme_romanization_size.value(),
            translation_size=self.theme_translation_size.value(),
            example_size=self.theme_example_size.value(),
            explanation_size=self.theme_explanation_size.value(),
            mnemonic_size=self.theme_mnemonic_size.value(),
            image_max_height=self.theme_image_max_height.value(),
            card_max_width=self.theme_card_max_width.value(),
            card_padding=self.theme_card_padding.value(),
            component_spacing=self.theme_component_spacing.value(),
            layout_density=str(self.theme_density.currentData() or "custom"),
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
        if self.current_project.card_structures:
            primary = self.current_project.card_structures[0]
            self.current_project.card_structures[0] = primary.model_copy(
                update={"front_components": front, "back_components": back}
            )
        self.current_project.deck_sections = self.sections()
        self.current_project.card_theme = theme
        self.database.update_project(self.current_project)
        QMessageBox.information(self, "Modelo salvo", "Estrutura, ordem dos subbaralhos e tema foram atualizados.")
        self.update_preview()

    def set_project(self, project_id: int) -> None:
        index = self.project_combo.findData(project_id)
        if index < 0:
            self.refresh()
            index = self.project_combo.findData(project_id)
        if index >= 0:
            self.project_combo.setCurrentIndex(index)
            self.load_project()

    def _toggle_preview_side(self) -> None:
        self._preview_showing_answer = not self._preview_showing_answer
        self.preview_toggle.setText("Mostrar frente" if self._preview_showing_answer else "Mostrar resposta")
        self.update_preview()

    def _apply_preview_device(self, *_args) -> None:
        device = str(self.preview_device.currentData() or "desktop")
        self.preview_stage.set_device(device)
        self.update_preview()

    def update_preview(self, *_args) -> None:
        self._preview_timer.stop()
        try:
            theme = self._collect_theme()
        except Exception:
            theme = self.current_project.card_theme if self.current_project else DeckThemeSettings()

        sample: FlashcardData | None = None
        if self.current_project is not None and self.current_project.id is not None:
            project_id = int(self.current_project.id)
            if self._preview_sample_project_id != project_id:
                self._preview_sample = self.database.get_first_card(project_id)
                self._preview_sample_project_id = project_id
            sample = self._preview_sample

        front_html = render_preview_document(self.front_editor.components(), theme, sample)
        back_html = render_preview_document(self.back_editor.components(), theme, sample)
        self.back_preview.setHtml(back_html)
        self.front_preview.setHtml(back_html if self._preview_showing_answer else front_html)
        self.front_preview.horizontalScrollBar().setValue(0)
