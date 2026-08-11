from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QModelIndex, QSortFilterProxyModel, QTimer, QSize, Qt, Signal
from PySide6.QtGui import QIcon, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ankiistudio.constants import COMPONENT_LABELS
from ankiistudio.i18n import tr
from ankiistudio.services.search_rank import normalize_search_text, search_score


class _SearchRankingProxy(QSortFilterProxyModel):
    """Ordena por relevância sem remover nenhum item da lista."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._query = ""
        self.setDynamicSortFilter(True)

    def set_query(self, query: str) -> None:
        self._query = query
        self.invalidate()
        self.sort(0)

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:  # type: ignore[override]
        if not self._query.strip():
            return left.row() < right.row()
        model = self.sourceModel()
        left_label = str(model.data(left, Qt.ItemDataRole.DisplayRole) or "")
        right_label = str(model.data(right, Qt.ItemDataRole.DisplayRole) or "")
        left_score = search_score(left_label, self._query)[:2]
        right_score = search_score(right_label, self._query)[:2]
        if left_score != right_score:
            return left_score < right_score
        return left.row() < right.row()


class SearchableComboBox(QComboBox):
    """Seletor pesquisável com lista completa e ranking por relevância.

    O editor mantém o foco enquanto as sugestões ficam abertas. Clicar em qualquer
    parte do seletor mostra todas as opções; digitar apenas reordena os resultados,
    sem ocultar nenhuma opção.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setMaxVisibleItems(18)
        self._source_items: list[tuple[str, object]] = []
        self._query = ""
        self._source_model = QStandardItemModel(self)
        self._proxy_model = _SearchRankingProxy(self)
        self._proxy_model.setSourceModel(self._source_model)
        self.setModel(self._proxy_model)

        # QCompleter mantém o foco no QLineEdit, ao contrário do popup normal do
        # QComboBox. O modelo já vem ordenado por relevância e o modo Unfiltered
        # garante que os itens não correspondentes continuem visíveis abaixo.
        self._completer = QCompleter(self._proxy_model, self)
        self._completer.setCompletionMode(QCompleter.CompletionMode.UnfilteredPopupCompletion)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setMaxVisibleItems(18)
        self.setCompleter(self._completer)
        self._completer.activated.connect(self._completion_activated)

        editor = self.lineEdit()
        if editor is not None:
            editor.installEventFilter(self)
            editor.textEdited.connect(self._search_text_edited)
            editor.returnPressed.connect(self._accept_first_result)
        self.activated.connect(self._selection_activated)

    def set_items(
        self,
        items: list[tuple[str, object]],
        selected_data: object | None = None,
    ) -> None:
        self._source_items = [(str(label), data) for label, data in items]
        self._source_model.clear()
        for label, data in self._source_items:
            item = QStandardItem(label)
            item.setData(data, Qt.ItemDataRole.UserRole)
            self._source_model.appendRow(item)
        self._query = ""
        previous = self.blockSignals(True)
        self._proxy_model.set_query("")
        self._select_data_silently(selected_data)
        self.blockSignals(previous)
        self._refresh_completer("")

    def refresh_search_source(self) -> None:
        self._source_items = [
            (
                str(self._source_model.item(row).text()),
                self._source_model.item(row).data(Qt.ItemDataRole.UserRole),
            )
            for row in range(self._source_model.rowCount())
        ]

    def _select_data_silently(self, selected_data: object | None) -> None:
        previous = self.blockSignals(True)
        if selected_data is not None:
            index = self.findData(selected_data)
            if index < 0 and self.count():
                index = 0
        else:
            index = 0 if self.count() else -1
        self.setCurrentIndex(index)
        self.blockSignals(previous)

    def _refresh_completer(self, query: str) -> None:
        self._proxy_model.set_query(query)
        # O ranking já foi aplicado pelo proxy. Prefixo vazio impede um segundo
        # filtro do QCompleter e mantém todos os resultados visíveis.
        self._completer.setCompletionPrefix("")

    def _show_search_popup(self, *, select_text: bool = False) -> None:
        if not self.isEnabled() or not self.count():
            return
        editor = self.lineEdit()
        if editor is None:
            return
        self._refresh_completer(self._query)
        editor.setFocus(Qt.FocusReason.MouseFocusReason)
        if select_text and not self._query:
            editor.selectAll()
        self._completer.complete()

    def _search_text_edited(self, text: str) -> None:
        self._query = text
        editor = self.lineEdit()
        cursor_position = editor.cursorPosition() if editor is not None else len(text)

        # Não emita currentIndexChanged(-1) durante a digitação. Isso evita que
        # dependências como o idioma sejam recalculadas enquanto o usuário pesquisa.
        previous = self.blockSignals(True)
        self.setCurrentIndex(-1)
        self.blockSignals(previous)
        self._refresh_completer(text)
        if editor is not None:
            editor.setText(text)
            editor.setCursorPosition(min(cursor_position, len(text)))
            editor.setFocus(Qt.FocusReason.OtherFocusReason)
        self._completer.complete()

    def _data_for_completion(self, value: object) -> object | None:
        if isinstance(value, QModelIndex):
            label = str(value.data(Qt.ItemDataRole.DisplayRole) or "")
        else:
            label = str(value or "")
        for item_label, item_data in self._source_items:
            if item_label == label:
                return item_data
        return None

    def _completion_activated(self, value: object) -> None:
        selected_data = self._data_for_completion(value)
        if selected_data is None:
            # Pode existir uma opção intencionalmente associada a None; nesse caso
            # localize pelo texto exibido antes de desistir da seleção.
            label = str(value.data(Qt.ItemDataRole.DisplayRole) if isinstance(value, QModelIndex) else value or "")
            source_match = next(((item_label, data) for item_label, data in self._source_items if item_label == label), None)
            if source_match is None:
                return
            selected_data = source_match[1]

        self._query = ""
        previous = self.blockSignals(True)
        self._proxy_model.set_query("")
        index = self.findData(selected_data)
        if index < 0:
            label = next((label for label, data in self._source_items if data == selected_data), "")
            index = self.findText(label, Qt.MatchFlag.MatchExactly)
        self.blockSignals(previous)
        if index >= 0:
            # A emissão normal de currentIndexChanged é necessária para atualizar
            # Modelo/Idioma/VOICEVOX após a escolha feita no autocomplete.
            self.setCurrentIndex(index)
        self._completer.popup().hide()

    def _accept_first_result(self) -> None:
        if not normalize_search_text(self._query) or self.count() == 0:
            return
        proxy_index = self._proxy_model.index(0, 0)
        self._completion_activated(proxy_index)

    def _selection_activated(self, _index: int) -> None:
        selected_data = self.currentData()
        if selected_data is None and self.currentIndex() < 0:
            return
        self._query = ""
        previous = self.blockSignals(True)
        self._proxy_model.set_query("")
        self._select_data_silently(selected_data)
        self.blockSignals(previous)

    def showPopup(self) -> None:  # type: ignore[override]
        # Substitui o popup nativo do QComboBox pelo QCompleter. Assim a lista abre
        # ao clicar na seta, mas o QLineEdit continua recebendo o teclado.
        self._show_search_popup(select_text=True)

    def eventFilter(self, watched, event) -> bool:  # type: ignore[override]
        if watched is self.lineEdit() and event.type() == QEvent.Type.MouseButtonPress:
            # O evento original ainda posiciona o cursor. Depois dele, selecionamos
            # o texto atual e mostramos todas as opções sem roubar o foco do editor.
            QTimer.singleShot(0, lambda: self._show_search_popup(select_text=True))
        return super().eventFilter(watched, event)

    def reset_search_text(self) -> None:
        selected_data = self.currentData()
        self._query = ""
        previous = self.blockSignals(True)
        self._proxy_model.set_query("")
        self._select_data_silently(selected_data)
        self.blockSignals(previous)


class PageHeader(QWidget):
    def __init__(self, title: str, subtitle: str = "") -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 10)
        layout.setSpacing(4)
        title_label = QLabel(title)
        title_label.setObjectName("PageTitle")
        layout.addWidget(title_label)
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("PageSubtitle")
            subtitle_label.setWordWrap(True)
            layout.addWidget(subtitle_label)


class PageScrollArea(QScrollArea):
    def __init__(self, content: QWidget) -> None:
        super().__init__()
        self.setObjectName("PageScroll")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content.setObjectName("PageSurface")
        self.setWidget(content)


class SectionCard(QFrame):
    def __init__(self, title: str = "", subtitle: str = "") -> None:
        super().__init__()
        self.setObjectName("SectionCard")
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(18, 16, 18, 16)
        self.root.setSpacing(12)
        if title:
            title_label = QLabel(title)
            title_label.setObjectName("SectionTitle")
            self.root.addWidget(title_label)
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("SectionSubtitle")
            subtitle_label.setWordWrap(True)
            self.root.addWidget(subtitle_label)


class ActionCard(QFrame):
    clicked = Signal()

    def __init__(
        self,
        title: str,
        description: str,
        button_text: str,
        icon_path: Path | None = None,
    ) -> None:
        super().__init__()
        self.setObjectName("Card")
        self.setMinimumHeight(148)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        heading = QHBoxLayout()
        if icon_path and icon_path.is_file():
            icon_label = QLabel()
            icon_label.setPixmap(QIcon(str(icon_path)).pixmap(QSize(22, 22)))
            icon_label.setFixedSize(24, 24)
            heading.addWidget(icon_label)
        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        heading.addWidget(title_label)
        heading.addStretch(1)
        layout.addLayout(heading)

        description_label = QLabel(description)
        description_label.setWordWrap(True)
        description_label.setObjectName("SectionSubtitle")
        layout.addWidget(description_label, 1)

        button = QPushButton(button_text)
        button.setObjectName("PrimaryButton")
        button.clicked.connect(self.clicked.emit)
        layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignLeft)


class StatusBanner(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("Card")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        self.label = QLabel()
        self.label.setWordWrap(True)
        layout.addWidget(self.label)
        self.hide()

    def show_message(self, text: str, error: bool = False) -> None:
        self.label.setText(tr(text))
        border = "#B84A55" if error else "#19D978"
        self.setStyleSheet(f"QFrame#Card {{ border:1px solid {border}; border-radius:10px; }}")
        self.show()


class AdaptiveSplitter(QSplitter):
    """Alterna entre painéis lado a lado e empilhados conforme a largura disponível."""

    def __init__(self, breakpoint: int = 900, parent: QWidget | None = None) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.breakpoint = breakpoint
        self.setChildrenCollapsible(False)
        self.setHandleWidth(8)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        orientation = (
            Qt.Orientation.Vertical
            if self.width() < self.breakpoint
            else Qt.Orientation.Horizontal
        )
        if orientation != self.orientation():
            self.setOrientation(orientation)
            if self.count() >= 2:
                self.setStretchFactor(0, 3 if orientation == Qt.Orientation.Horizontal else 0)
                self.setStretchFactor(1, 2 if orientation == Qt.Orientation.Horizontal else 0)
        super().resizeEvent(event)


class ComponentOrderEditor(QFrame):
    changed = Signal()

    def __init__(self, title: str, components: list[str]) -> None:
        super().__init__()
        self.setObjectName("SectionCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        heading_row = QHBoxLayout()
        heading = QLabel(title)
        heading.setObjectName("SectionTitle")
        count_label = QLabel("ordem automática")
        count_label.setObjectName("Badge")
        heading_row.addWidget(heading)
        heading_row.addStretch(1)
        heading_row.addWidget(count_label)
        layout.addLayout(heading_row)

        self.list_widget = QListWidget()
        self.list_widget.setMinimumHeight(180)
        self.list_widget.currentRowChanged.connect(lambda *_: self._update_controls())
        layout.addWidget(self.list_widget, 1)

        add_row = QHBoxLayout()
        self.component_combo = QComboBox()
        for key, label in COMPONENT_LABELS.items():
            self.component_combo.addItem(tr(label), key)
        add_button = QPushButton("Adicionar")
        add_button.setObjectName("SubtleButton")
        add_button.clicked.connect(self.add_component)
        add_row.addWidget(self.component_combo, 1)
        add_row.addWidget(add_button)
        layout.addLayout(add_row)

        controls = QHBoxLayout()
        self.up_button = QPushButton("↑")
        self.down_button = QPushButton("↓")
        self.remove_button = QPushButton("Remover")
        for button in (self.up_button, self.down_button, self.remove_button):
            button.setObjectName("SubtleButton")
        self.up_button.setFixedWidth(42)
        self.down_button.setFixedWidth(42)
        self.up_button.setToolTip("Mover para cima")
        self.down_button.setToolTip("Mover para baixo")
        self.up_button.clicked.connect(lambda: self.move(-1))
        self.down_button.clicked.connect(lambda: self.move(1))
        self.remove_button.clicked.connect(self.remove_component)
        controls.addWidget(self.up_button)
        controls.addWidget(self.down_button)
        controls.addStretch(1)
        controls.addWidget(self.remove_button)
        layout.addLayout(controls)
        self.set_components(components)

    def set_components(self, components: list[str]) -> None:
        self.list_widget.clear()
        for key in components:
            self._append(key)
        if self.list_widget.count():
            self.list_widget.setCurrentRow(0)
        self._update_controls()
        self.changed.emit()

    def _append(self, key: str) -> None:
        label = tr(COMPONENT_LABELS.get(key, key))
        self.list_widget.addItem(label)
        item = self.list_widget.item(self.list_widget.count() - 1)
        item.setData(Qt.ItemDataRole.UserRole, key)
        item.setToolTip(label)

    def components(self) -> list[str]:
        return [
            str(self.list_widget.item(index).data(Qt.ItemDataRole.UserRole))
            for index in range(self.list_widget.count())
        ]

    def add_component(self) -> None:
        key = str(self.component_combo.currentData())
        if key in self.components():
            return
        self._append(key)
        self.list_widget.setCurrentRow(self.list_widget.count() - 1)
        self._update_controls()
        self.changed.emit()

    def remove_component(self) -> None:
        row = self.list_widget.currentRow()
        if row < 0:
            return
        self.list_widget.takeItem(row)
        if self.list_widget.count():
            self.list_widget.setCurrentRow(min(row, self.list_widget.count() - 1))
        self._update_controls()
        self.changed.emit()

    def move(self, direction: int) -> None:
        row = self.list_widget.currentRow()
        target = row + direction
        if row < 0 or target < 0 or target >= self.list_widget.count():
            return
        item = self.list_widget.takeItem(row)
        self.list_widget.insertItem(target, item)
        self.list_widget.setCurrentRow(target)
        self._update_controls()
        self.changed.emit()

    def _update_controls(self) -> None:
        row = self.list_widget.currentRow()
        count = self.list_widget.count()
        self.up_button.setEnabled(row > 0)
        self.down_button.setEnabled(row >= 0 and row < count - 1)
        self.remove_button.setEnabled(row >= 0)
