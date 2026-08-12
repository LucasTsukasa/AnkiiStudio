from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThreadPool, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
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
from ankiistudio.i18n import UI_LANGUAGES, tr
from ankiistudio.services.audio.voicevox import VoicevoxProvider
from ankiistudio.ui.theme import build_stylesheet
from ankiistudio.ui.widgets import PageHeader, PageScrollArea, SectionCard, StatusBanner
from ankiistudio.ui.workers import Worker


class SettingsPage(QWidget):
    check_updates_requested = Signal()
    ui_language_changed = Signal(str)
    RESPONSIVE_BREAKPOINT = 820

    def __init__(self, database: Database, resource_dir: Path) -> None:
        super().__init__()
        self.database = database
        self.resource_dir = resource_dir
        self.thread_pool = QThreadPool.globalInstance()
        self._voicevox_worker: Worker | None = None
        self._compact_layout = False
        self._loading_settings = True

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
        self.ui_language_combo = QComboBox()
        for label, code in UI_LANGUAGES:
            self.ui_language_combo.addItem(label, code)
        self.ui_language_combo._i18n_skip_items = True
        self.ui_language_combo.currentIndexChanged.connect(self._ui_language_selected)
        self._add_field(appearance, "Idioma da interface", self.ui_language_combo)
        layout.addWidget(appearance)

        self.providers_grid = QGridLayout()
        self.providers_grid.setHorizontalSpacing(12)
        self.providers_grid.setVerticalSpacing(12)

        self.gemini_card = SectionCard(
            "Gemini",
            "A chave é usada para geração de conteúdo, IA por campo e pelos perfis Gemini TTS configurados na aba Áudios.",
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

        image_sources = SectionCard(
            "Fontes de imagem",
            "O Wikimedia Commons fica habilitado por padrão. Ative fontes adicionais somente quando quiser ampliar os resultados da busca.",
        )
        self.wikimedia_images = QCheckBox("Wikimedia Commons")
        self.pixabay_images = QCheckBox("Pixabay")
        self.pexels_images = QCheckBox("Pexels")
        image_source_row = QHBoxLayout()
        image_source_row.addWidget(self.wikimedia_images)
        image_source_row.addWidget(self.pixabay_images)
        image_source_row.addWidget(self.pexels_images)
        image_source_row.addStretch(1)
        image_sources.root.addLayout(image_source_row)
        self.pixabay_key = QLineEdit()
        self.pixabay_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.pixabay_key.setPlaceholderText("API key do Pixabay")
        self.pexels_key = QLineEdit()
        self.pexels_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.pexels_key.setPlaceholderText("API key do Pexels")
        self._add_field(image_sources, "Pixabay API key", self.pixabay_key)
        self._add_field(image_sources, "Pexels API key", self.pexels_key)
        layout.addWidget(image_sources)

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

        updates = SectionCard(
            "Atualizações",
            "Quando habilitado, o AnkiiStudio procura novas versões publicadas no GitHub ao iniciar.",
        )
        self.check_updates = QCheckBox("Procurar atualizações automaticamente")
        self.check_updates_now_button = QPushButton("Procurar atualizações agora")
        self.check_updates_now_button.setObjectName("SubtleButton")
        self.check_updates_now_button.clicked.connect(lambda: self.check_updates_requested.emit())
        updates.root.addWidget(self.check_updates)
        updates.root.addWidget(self.check_updates_now_button)
        layout.addWidget(updates)

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
        self._loading_settings = False

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
        self._select_data(self.ui_language_combo, self.database.get_setting("ui_language", "pt_BR"))
        self.gemini_key.setText(SecretStore.get("GEMINI_API_KEY"))
        self.eleven_key.setText(SecretStore.get("ELEVENLABS_API_KEY"))
        self.pixabay_key.setText(SecretStore.get("PIXABAY_API_KEY"))
        self.pexels_key.setText(SecretStore.get("PEXELS_API_KEY"))
        self.wikimedia_images.setChecked(self.database.get_setting("image_source_wikimedia", "1") == "1")
        self.pixabay_images.setChecked(self.database.get_setting("image_source_pixabay", "0") == "1")
        self.pexels_images.setChecked(self.database.get_setting("image_source_pexels", "0") == "1")
        self.check_updates.setChecked(self.database.get_setting("check_updates", "1") == "1")
        self.gemini_text_model.setText(
            self.database.get_setting("gemini_text_model", DEFAULT_GEMINI_TEXT_MODEL)
        )
        self.voicevox_url.setText(self.database.get_setting("voicevox_url", DEFAULT_VOICEVOX_URL))

    def save(self) -> None:
        try:
            pixabay_key = self.pixabay_key.text().strip()
            pexels_key = self.pexels_key.text().strip()
            if not any((
                self.wikimedia_images.isChecked(),
                self.pixabay_images.isChecked(),
                self.pexels_images.isChecked(),
            )):
                raise ValueError("Habilite ao menos uma fonte de imagem.")
            if self.pixabay_images.isChecked() and not pixabay_key:
                raise ValueError("Informe a API key do Pixabay antes de habilitar essa fonte.")
            if self.pexels_images.isChecked() and not pexels_key:
                raise ValueError("Informe a API key do Pexels antes de habilitar essa fonte.")
            SecretStore.set("GEMINI_API_KEY", self.gemini_key.text().strip())
            SecretStore.set("ELEVENLABS_API_KEY", self.eleven_key.text().strip())
            SecretStore.set("PIXABAY_API_KEY", pixabay_key)
            SecretStore.set("PEXELS_API_KEY", pexels_key)
            selected_ui_language = str(self.ui_language_combo.currentData() or "pt_BR")
            values = {
                "appearance_theme": str(self.appearance_combo.currentData()),
                "ui_language": selected_ui_language,
                "gemini_text_model": self.gemini_text_model.text().strip(),
                "voicevox_url": self.voicevox_url.text().strip(),
                "image_source_wikimedia": "1" if self.wikimedia_images.isChecked() else "0",
                "image_source_pixabay": "1" if self.pixabay_images.isChecked() else "0",
                "image_source_pexels": "1" if self.pexels_images.isChecked() else "0",
                "check_updates": "1" if self.check_updates.isChecked() else "0",
            }
            for key, value in values.items():
                self.database.set_setting(key, value)
            app = QApplication.instance()
            if app is not None:
                app.setStyleSheet(build_stylesheet(self.resource_dir, values["appearance_theme"]))
        except Exception as exc:
            QMessageBox.critical(self, "Falha ao salvar", str(exc))
            return
        self.status.show_message(tr("Configurações salvas."))


    def _ui_language_selected(self, _index: int) -> None:
        if self._loading_settings:
            return
        language = str(self.ui_language_combo.currentData() or "pt_BR")
        self.database.set_setting("ui_language", language)
        self.ui_language_changed.emit(language)
        self.status.show_message(tr("Idioma da interface atualizado."))

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
            lambda version: self.status.show_message(tr(f"VOICEVOX disponível. Versão: {version}"))
        )
        worker.signals.error.connect(lambda message: self.status.show_message(message, error=True))

        def finished() -> None:
            self.test_voicevox_button.setEnabled(True)
            self._voicevox_worker = None

        worker.signals.finished.connect(finished)
        self.thread_pool.start(worker)
