from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt, QThreadPool
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ankiistudio.models import WikimediaMediaResult
from ankiistudio.services.wikimedia_service import WikimediaService
from ankiistudio.ui.workers import Worker


class ImageSearchDialog(QDialog):
    def __init__(self, initial_term: str, service: WikimediaService, parent=None) -> None:
        super().__init__(parent)
        self.service = service
        self.thread_pool = QThreadPool.globalInstance()
        self.results: list[WikimediaMediaResult] = []
        self.selected_result: WikimediaMediaResult | None = None
        self.setWindowTitle("Pesquisar imagem no Wikimedia Commons")
        self.resize(980, 680)

        root = QVBoxLayout(self)
        search_row = QHBoxLayout()
        self.search_input = QLineEdit(initial_term)
        self.search_button = QPushButton("Pesquisar")
        self.search_button.setObjectName("PrimaryButton")
        self.search_button.clicked.connect(self.search)
        search_row.addWidget(self.search_input, 1)
        search_row.addWidget(self.search_button)
        root.addLayout(search_row)

        splitter = QSplitter()
        self.list_widget = QListWidget()
        self.list_widget.currentRowChanged.connect(self.show_selected)
        splitter.addWidget(self.list_widget)

        details = QWidget()
        details_layout = QVBoxLayout(details)
        self.preview = QLabel("Selecione um resultado")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(420, 320)
        self.preview.setObjectName("ImagePreview")
        self.metadata = QLabel()
        self.metadata.setWordWrap(True)
        details_layout.addWidget(self.preview, 1)
        details_layout.addWidget(self.metadata)
        splitter.addWidget(details)
        splitter.setSizes([360, 600])
        root.addWidget(splitter, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel_button = QPushButton("Cancelar")
        use_button = QPushButton("Usar imagem selecionada")
        use_button.setObjectName("PrimaryButton")
        cancel_button.clicked.connect(self.reject)
        use_button.clicked.connect(self.accept_selected)
        buttons.addWidget(cancel_button)
        buttons.addWidget(use_button)
        root.addLayout(buttons)

        if initial_term.strip():
            self.search()

    def search(self) -> None:
        term = self.search_input.text().strip()
        if not term:
            QMessageBox.warning(self, "Pesquisa vazia", "Informe um termo para pesquisar.")
            return
        self.search_button.setEnabled(False)
        self.list_widget.clear()
        self.preview.setText("Pesquisando...")
        worker = Worker(self.service.search, term, kind="image", limit=12)
        worker.signals.result.connect(self.populate)
        worker.signals.error.connect(lambda message: QMessageBox.critical(self, "Erro na pesquisa", message))
        worker.signals.finished.connect(lambda: self.search_button.setEnabled(True))
        self.thread_pool.start(worker)

    def populate(self, results: object) -> None:
        self.results = list(results)
        self.list_widget.clear()
        for result in self.results:
            license_text = result.license_name or "licença não identificada"
            item = QListWidgetItem(f"{result.title}\n{license_text}")
            self.list_widget.addItem(item)
        if self.results:
            self.list_widget.setCurrentRow(0)
        else:
            self.preview.setText("Nenhuma imagem encontrada.")

    def show_selected(self, index: int) -> None:
        if index < 0 or index >= len(self.results):
            return
        result = self.results[index]
        self.selected_result = result
        self.metadata.setText(
            f"<b>{result.title}</b><br>Autor: {result.author or 'não informado'}<br>"
            f"Licença: {result.license_name or 'não identificada'}<br>"
            f"Dimensões: {result.width or '?'} × {result.height or '?'}"
        )
        url = result.thumbnail_url or result.file_url
        worker = Worker(self.service.download, url)
        worker.signals.result.connect(self.set_preview)
        worker.signals.error.connect(lambda _: self.preview.setText("Não foi possível carregar a miniatura."))
        self.thread_pool.start(worker)

    def set_preview(self, payload: object) -> None:
        raw, _ = payload
        pixmap = QPixmap()
        pixmap.loadFromData(QByteArray(raw))
        if pixmap.isNull():
            self.preview.setText("Formato de imagem não suportado na prévia.")
            return
        self.preview.setPixmap(
            pixmap.scaled(
                self.preview.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def accept_selected(self) -> None:
        if self.selected_result is None:
            QMessageBox.warning(self, "Nenhuma imagem", "Selecione uma imagem.")
            return
        self.accept()
