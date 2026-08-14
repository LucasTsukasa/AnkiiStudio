from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QGridLayout, QLabel, QLineEdit, QSpinBox, QTextBrowser, QVBoxLayout, QWidget

from ankiistudio.models import DeckThemeSettings
from ankiistudio.services.card_template_service import render_preview_document
from ankiistudio.ui.design_system.components import ASComboBox, ASLineEdit
from ankiistudio.ui.widgets import SectionCard


DENSITY_PRESETS = {
    "compact": {"image_max_height": 240, "card_max_width": 640, "card_padding": 14, "component_spacing": 6},
    "normal": {"image_max_height": 320, "card_max_width": 720, "card_padding": 20, "component_spacing": 10},
    "spacious": {"image_max_height": 420, "card_max_width": 760, "card_padding": 28, "component_spacing": 14},
}


class DeckThemeEditor(QWidget):
    changed = Signal()

    def __init__(self, parent: QWidget | None = None, *, with_preview: bool = True) -> None:
        super().__init__(parent)
        self._loading = False
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        card = SectionCard("Tema padrão dos flashcards", "Novos projetos usam este tema como ponto de partida. Cada projeto continua podendo ser personalizado separadamente.")
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(9)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        self.density = ASComboBox()
        self.density.addItem("Compacto", "compact")
        self.density.addItem("Normal", "normal")
        self.density.addItem("Espaçoso", "spacious")
        self.density.addItem("Personalizado", "custom")
        self.background = ASLineEdit()
        self.card_background = ASLineEdit()
        self.primary = ASLineEdit()
        self.text = ASLineEdit()
        self.secondary = ASLineEdit()
        self.border = ASLineEdit()
        self.font = ASLineEdit()
        self.word_size = self._pixel_spin(18, 96)
        self.reading_size = self._pixel_spin(12, 72)
        self.romanization_size = self._pixel_spin(10, 48)
        self.translation_size = self._pixel_spin(14, 72)
        self.example_size = self._pixel_spin(12, 72)
        self.explanation_size = self._pixel_spin(12, 48)
        self.mnemonic_size = self._pixel_spin(12, 48)
        self.image_max_height = self._pixel_spin(120, 900)
        self.card_max_width = self._pixel_spin(360, 1200)
        self.card_padding = self._pixel_spin(8, 64)
        self.component_spacing = self._pixel_spin(0, 32)

        fields = (
            ("Densidade do layout", self.density),
            ("Fonte", self.font),
            ("Fundo", self.background),
            ("Fundo do cartão", self.card_background),
            ("Cor principal", self.primary),
            ("Texto", self.text),
            ("Texto secundário", self.secondary),
            ("Borda", self.border),
            ("Tamanho do conteúdo principal", self.word_size),
            ("Tamanho da leitura", self.reading_size),
            ("Tamanho da romanização", self.romanization_size),
            ("Tamanho da tradução", self.translation_size),
            ("Tamanho do exemplo", self.example_size),
            ("Tamanho da explicação", self.explanation_size),
            ("Tamanho do mnemônico", self.mnemonic_size),
            ("Altura máxima da imagem", self.image_max_height),
            ("Largura máxima do cartão", self.card_max_width),
            ("Espaçamento interno", self.card_padding),
            ("Espaço entre componentes", self.component_spacing),
        )
        for index, (label, widget) in enumerate(fields):
            cell = QWidget()
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            cell_layout.setSpacing(5)
            title = QLabel(label)
            title.setObjectName("FieldLabel")
            cell_layout.addWidget(title)
            cell_layout.addWidget(widget)
            grid.addWidget(cell, index // 2, index % 2)
        card.root.addLayout(grid)
        root.addWidget(card)

        self.preview: QTextBrowser | None = None
        if with_preview:
            preview_card = SectionCard("Pré-visualização", "Exemplo do tema padrão aplicado a um cartão.")
            self.preview = QTextBrowser()
            self.preview.setMinimumHeight(330)
            self.preview.setOpenExternalLinks(False)
            preview_card.root.addWidget(self.preview)
            root.addWidget(preview_card)

        for widget in (self.background, self.card_background, self.primary, self.text, self.secondary, self.border, self.font):
            widget.textChanged.connect(self._changed)
        for widget in self._numeric_widgets():
            widget.valueChanged.connect(self._numeric_changed)
            widget.valueChanged.connect(self._changed)
        self.density.currentIndexChanged.connect(self._density_changed)
        self.set_theme(DeckThemeSettings())

    @staticmethod
    def _pixel_spin(minimum: int, maximum: int) -> QSpinBox:
        widget = QSpinBox()
        widget.setRange(minimum, maximum)
        widget.setSuffix(" px")
        return widget

    def _numeric_widgets(self) -> tuple[QSpinBox, ...]:
        return (
            self.word_size, self.reading_size, self.romanization_size, self.translation_size,
            self.example_size, self.explanation_size, self.mnemonic_size,
            self.image_max_height, self.card_max_width, self.card_padding, self.component_spacing,
        )

    def _layout_values(self) -> dict[str, int]:
        return {
            "image_max_height": self.image_max_height.value(),
            "card_max_width": self.card_max_width.value(),
            "card_padding": self.card_padding.value(),
            "component_spacing": self.component_spacing.value(),
        }

    def _density_changed(self, *_args) -> None:
        if self._loading:
            return
        key = str(self.density.currentData() or "custom")
        preset = DENSITY_PRESETS.get(key)
        if preset:
            self._loading = True
            try:
                self.image_max_height.setValue(preset["image_max_height"])
                self.card_max_width.setValue(preset["card_max_width"])
                self.card_padding.setValue(preset["card_padding"])
                self.component_spacing.setValue(preset["component_spacing"])
            finally:
                self._loading = False
        self._changed()

    def _numeric_changed(self, *_args) -> None:
        if self._loading:
            return
        key = str(self.density.currentData() or "custom")
        preset = DENSITY_PRESETS.get(key)
        if preset is not None and self._layout_values() != preset:
            previous = self.density.blockSignals(True)
            index = self.density.findData("custom")
            self.density.setCurrentIndex(index)
            self.density.blockSignals(previous)

    def _changed(self, *_args) -> None:
        if self._loading:
            return
        self.update_preview()
        self.changed.emit()

    def set_theme(self, theme: DeckThemeSettings) -> None:
        self._loading = True
        try:
            self.background.setText(theme.background)
            self.card_background.setText(theme.card_background)
            self.primary.setText(theme.primary)
            self.text.setText(theme.text)
            self.secondary.setText(theme.secondary_text)
            self.border.setText(theme.border)
            self.font.setText(theme.font_family)
            self.word_size.setValue(theme.word_size)
            self.reading_size.setValue(theme.reading_size)
            self.romanization_size.setValue(theme.romanization_size)
            self.translation_size.setValue(theme.translation_size)
            self.example_size.setValue(theme.example_size)
            self.explanation_size.setValue(theme.explanation_size)
            self.mnemonic_size.setValue(theme.mnemonic_size)
            self.image_max_height.setValue(theme.image_max_height)
            self.card_max_width.setValue(theme.card_max_width)
            self.card_padding.setValue(theme.card_padding)
            self.component_spacing.setValue(theme.component_spacing)
            index = self.density.findData(theme.layout_density)
            self.density.setCurrentIndex(index if index >= 0 else self.density.findData("custom"))
        finally:
            self._loading = False
        self.update_preview()

    def theme(self) -> DeckThemeSettings:
        return DeckThemeSettings(
            background=self.background.text().strip(),
            card_background=self.card_background.text().strip(),
            primary=self.primary.text().strip(),
            text=self.text.text().strip(),
            secondary_text=self.secondary.text().strip(),
            border=self.border.text().strip(),
            font_family=self.font.text().strip(),
            word_size=self.word_size.value(),
            reading_size=self.reading_size.value(),
            romanization_size=self.romanization_size.value(),
            translation_size=self.translation_size.value(),
            example_size=self.example_size.value(),
            explanation_size=self.explanation_size.value(),
            mnemonic_size=self.mnemonic_size.value(),
            image_max_height=self.image_max_height.value(),
            card_max_width=self.card_max_width.value(),
            card_padding=self.card_padding.value(),
            component_spacing=self.component_spacing.value(),
            layout_density=str(self.density.currentData() or "custom"),
        )

    def update_preview(self) -> None:
        if self.preview is None:
            return
        try:
            theme = self.theme()
        except Exception:
            return
        self.preview.setHtml(render_preview_document(["word", "reading", "translation", "example", "explanation"], theme))
