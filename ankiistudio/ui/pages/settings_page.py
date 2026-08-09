from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ankiistudio.config import SecretStore
from ankiistudio.constants import DEFAULT_GEMINI_TEXT_MODEL, DEFAULT_VOICEVOX_URL
from ankiistudio.database import Database
from ankiistudio.services.audio.voicevox import VoicevoxProvider
from ankiistudio.ui.theme import build_stylesheet
from ankiistudio.ui.widgets import PageHeader, PageScrollArea, SectionCard, StatusBanner
from ankiistudio.ui.workers import Worker


class SettingsPage(QWidget):
    RESPONSIVE_BREAKPOINT = 820

    def __init__(self, database: Database, resource_dir: Path) -> None:
        super().__init__()
        self.database = database
        self.resource_dir = resource_dir
        self.thread_pool = QThreadPool.globalInstance()
        self._voicevox_worker: Worker | None = None
        self._compact_layout = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)
        layout.addWidget(
            PageHeader(
                "Configurações",
                "Gerencie a aparência, credenciais e conexões utilizadas pelo AnkiiStudio.",
            )
        )
        self.status = StatusBanner()
        layout.addWidget(self.status)

        appearance = SectionCard("Aparência")
        self.appearance_combo = QComboBox()
        self.appearance_combo.addItem("Escuro", "dark")
        self.appearance_combo.addItem("Claro", "light")
        self._add_field(appearance, "Tema do aplicativo", self.appearance_combo)
        layout.addWidget(appearance)

        self.providers_grid = QGridLayout()
        self.providers_grid.setHorizontalSpacing(12)
        self.providers_grid.setVerticalSpacing(12)

        self.gemini_card = SectionCard(
            "Gemini",
            "A chave é usada para geração de conteúdo e pelos perfis Gemini TTS configurados na aba Áudios.",
        )
        self.gemini_key = QLineEdit()
        self.gemini_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.gemini_key.setPlaceholderText("Cole sua API key")
        self.gemini_text_model = QLineEdit()
        self._add_field(self.gemini_card, "API key", self.gemini_key)
        self._add_field(self.gemini_card, "Modelo de texto", self.gemini_text_model)

        self.eleven_card = SectionCard(
            "ElevenLabs",
            "A chave é utilizada pelos perfis de voz ElevenLabs configurados na aba Áudios.",
        )
        self.eleven_key = QLineEdit()
        self.eleven_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.eleven_key.setPlaceholderText("Cole sua API key")
        self._add_field(self.eleven_card, "API key", self.eleven_key)

        self.providers_grid.addWidget(self.gemini_card, 0, 0)
        self.providers_grid.addWidget(self.eleven_card, 0, 1)
        layout.addLayout(self.providers_grid)

        voicevox = SectionCard(
            "VOICEVOX",
            "Configure o endereço do engine local. Personagens e estilos são carregados diretamente na aba Áudios.",
        )
        self.voicevox_url = QLineEdit()
        self._add_field(voicevox, "URL local", self.voicevox_url)
        self.test_voicevox_button = QPushButton("Testar conexão")
        self.test_voicevox_button.setObjectName("SubtleButton")
        self.test_voicevox_button.clicked.connect(self.test_voicevox)
        voicevox.root.addWidget(self.test_voicevox_button)
        layout.addWidget(voicevox)

        actions = QHBoxLayout()
        actions.addStretch(1)
        save_button = QPushButton("Salvar configurações")
        save_button.setObjectName("PrimaryButton")
        save_button.clicked.connect(self.save)
        actions.addWidget(save_button)
        layout.addLayout(actions)
        layout.addStretch(1)
        root.addWidget(PageScrollArea(content))
        self.load()

    @staticmethod
    def _add_field(card: SectionCard, label: str, widget: QWidget) -> None:
        label_widget = QLabel(label)
        label_widget.setObjectName("FieldLabel")
        card.root.addWidget(label_widget)
        card.root.addWidget(widget)

    @staticmethod
    def _select_data(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        compact = self.width() < self.RESPONSIVE_BREAKPOINT
        if compact != self._compact_layout:
            self._compact_layout = compact
            self.providers_grid.removeWidget(self.gemini_card)
            self.providers_grid.removeWidget(self.eleven_card)
            if compact:
                self.providers_grid.addWidget(self.gemini_card, 0, 0)
                self.providers_grid.addWidget(self.eleven_card, 1, 0)
            else:
                self.providers_grid.addWidget(self.gemini_card, 0, 0)
                self.providers_grid.addWidget(self.eleven_card, 0, 1)
        super().resizeEvent(event)

    def load(self) -> None:
        self._select_data(self.appearance_combo, self.database.get_setting("appearance_theme", "dark"))
        self.gemini_key.setText(SecretStore.get("GEMINI_API_KEY"))
        self.eleven_key.setText(SecretStore.get("ELEVENLABS_API_KEY"))
        self.gemini_text_model.setText(
            self.database.get_setting("gemini_text_model", DEFAULT_GEMINI_TEXT_MODEL)
        )
        self.voicevox_url.setText(self.database.get_setting("voicevox_url", DEFAULT_VOICEVOX_URL))

    def save(self) -> None:
        try:
            SecretStore.set("GEMINI_API_KEY", self.gemini_key.text().strip())
            SecretStore.set("ELEVENLABS_API_KEY", self.eleven_key.text().strip())
            values = {
                "appearance_theme": str(self.appearance_combo.currentData()),
                "gemini_text_model": self.gemini_text_model.text().strip(),
                "voicevox_url": self.voicevox_url.text().strip(),
            }
            for key, value in values.items():
                self.database.set_setting(key, value)
            app = QApplication.instance()
            if app is not None:
                app.setStyleSheet(build_stylesheet(self.resource_dir, values["appearance_theme"]))
        except Exception as exc:
            QMessageBox.critical(self, "Falha ao salvar", str(exc))
            return
        self.status.show_message("Configurações salvas.")

    def test_voicevox(self) -> None:
        url = self.voicevox_url.text().strip().rstrip("/")
        if not url:
            QMessageBox.warning(self, "URL ausente", "Informe a URL local do VOICEVOX.")
            return
        if self._voicevox_worker is not None:
            return
        self.test_voicevox_button.setEnabled(False)
        self.status.show_message("Testando conexão com o VOICEVOX...")
        worker = Worker(VoicevoxProvider.get_version, url, 3.0)
        self._voicevox_worker = worker
        worker.signals.result.connect(
            lambda version: self.status.show_message(f"VOICEVOX disponível. Versão: {version}")
        )
        worker.signals.error.connect(lambda message: self.status.show_message(message, error=True))

        def finished() -> None:
            self.test_voicevox_button.setEnabled(True)
            self._voicevox_worker = None

        worker.signals.finished.connect(finished)
        self.thread_pool.start(worker)
