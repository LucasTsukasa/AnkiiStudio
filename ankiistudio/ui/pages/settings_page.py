from __future__ import annotations

from dataclasses import asdict
import json
import logging
from pathlib import Path
from time import perf_counter

from PySide6.QtCore import Qt, QThreadPool, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ankiistudio.config import AppPaths, SecretStore
from ankiistudio.constants import DEFAULT_GEMINI_TEXT_MODEL, DEFAULT_VOICEVOX_URL, language_label
from ankiistudio.database import Database
from ankiistudio.i18n import UI_LANGUAGES, tr
from ankiistudio.services.audio.elevenlabs import ElevenLabsProvider
from ankiistudio.services.audio.gemini_tts import GeminiTTSProvider
from ankiistudio.services.audio.voicevox import VoicevoxProvider
from ankiistudio.services.audio_preferences import (
    VOICEVOX_DEFAULTS_KEY, VoicevoxSettingsData, load_voicevox_defaults, preview_text, save_voicevox_defaults,
)
from ankiistudio.services.audio_profile_service import AudioProfileService, AudioVoiceProfile
from ankiistudio.services.gemini_tts_usage import GeminiTTSUsageTracker
from ankiistudio.services.theme_settings import DEFAULT_CARD_THEME_SETTING, load_default_card_theme
from ankiistudio.ui.design_system.components import ASButton, ASComboBox, ASLineEdit
from ankiistudio.ui.deck_theme_editor import DeckThemeEditor
from ankiistudio.ui.dialogs.audio_profile_dialog import AudioProfileDialog
from ankiistudio.ui.dialogs.voicevox_settings_dialog import VoicevoxSettingsDialog
from ankiistudio.ui.design_system.themes import apply_design_system
from ankiistudio.ui.widgets import PageScrollArea, SearchableComboBox, SectionCard, StatusBanner
from ankiistudio.ui.workers import Worker


logger = logging.getLogger(__name__)


class SettingsPage(QWidget):
    """Conteúdo categorizado das configurações, pensado para uso dentro de QDialog."""

    check_updates_requested = Signal()
    ui_language_changed = Signal(str)

    CATEGORIES = (
        ("Geral", "general"),
        ("Aparência", "appearance"),
        ("IA e APIs", "ai"),
        ("Imagens", "images"),
        ("Áudio", "audio"),
        ("Atualizações", "updates"),
    )

    def __init__(self, database: Database, paths: AppPaths, resource_dir: Path) -> None:
        super().__init__()
        self.database = database
        self.paths = paths
        self.resource_dir = resource_dir
        self.thread_pool = QThreadPool.globalInstance()
        self._voicevox_worker: Worker | None = None
        self._workers: list[Worker] = []
        self._voicevox_defaults = load_voicevox_defaults(database)
        self.preview_audio_output = QAudioOutput(self)
        self.preview_audio_output.setVolume(0.9)
        self.preview_player = QMediaPlayer(self)
        self.preview_player.setAudioOutput(self.preview_audio_output)
        self._loading_settings = True
        self.profile_service = AudioProfileService(database)
        self.gemini_usage = GeminiTTSUsageTracker(database)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        navigation = QWidget()
        navigation.setFixedWidth(190)
        nav = QVBoxLayout(navigation)
        nav.setContentsMargins(14, 16, 12, 16)
        nav.setSpacing(5)
        title = QLabel("Configurações")
        title.setObjectName("PageTitle")
        nav.addWidget(title)
        nav.addSpacing(8)

        self.category_group = QButtonGroup(self)
        self.category_group.setExclusive(True)
        self.category_buttons: list[QPushButton] = []
        self.stack = QStackedWidget()
        for index, (label, key) in enumerate(self.CATEGORIES):
            button = ASButton(label)
            button.setObjectName("SettingsCategory")
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, target=index: self.stack.setCurrentIndex(target))
            self.category_group.addButton(button, index)
            self.category_buttons.append(button)
            nav.addWidget(button)
            self.stack.addWidget(self._build_category(key))
        nav.addStretch(1)
        self.status = StatusBanner()
        nav.addWidget(self.status)
        self.save_button = ASButton("Salvar configurações")
        self.save_button.setObjectName("PrimaryButton")
        self.save_button.clicked.connect(self.save)
        nav.addWidget(self.save_button)

        root.addWidget(navigation)
        root.addWidget(self.stack, 1)
        self.category_buttons[0].setChecked(True)
        self.stack.setCurrentIndex(0)
        self.load()
        self._refresh_profiles()
        self._loading_settings = False

    def _page(self, title: str, subtitle: str = "") -> tuple[QWidget, QVBoxLayout]:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)
        heading = QLabel(title)
        heading.setObjectName("PageTitle")
        layout.addWidget(heading)
        if subtitle:
            description = QLabel(subtitle)
            description.setObjectName("PageSubtitle")
            description.setWordWrap(True)
            layout.addWidget(description)
        return content, layout

    def _build_category(self, key: str) -> QWidget:
        if key == "general":
            content, layout = self._page("Geral", "Preferências básicas de funcionamento do BenkyouStudio.")
            card = SectionCard("Idioma")
            self.ui_language_combo = ASComboBox()
            for label, code in UI_LANGUAGES:
                self.ui_language_combo.addItem(label, code)
            self.ui_language_combo._i18n_skip_items = True
            self.ui_language_combo.currentIndexChanged.connect(self._ui_language_selected)
            self._add_field(card, "Idioma da interface", self.ui_language_combo)
            layout.addWidget(card)
        elif key == "appearance":
            content, layout = self._page("Aparência", "Personalize a aparência geral do aplicativo.")
            card = SectionCard("Tema do aplicativo")
            self.appearance_combo = ASComboBox()
            self.appearance_combo.addItem("Escuro", "dark")
            self.appearance_combo.addItem("Claro", "light")
            self.appearance_combo.addItem("Carmesim", "crimson")
            self._add_field(card, "Tema", self.appearance_combo)
            layout.addWidget(card)
            self.default_card_theme_editor = DeckThemeEditor(with_preview=True)
            layout.addWidget(self.default_card_theme_editor)
        elif key == "ai":
            content, layout = self._page("IA e APIs", "Credenciais usadas por recursos de IA e provedores externos.")
            gemini = SectionCard("Gemini", "Usada na geração de conteúdo, IA por campo e Gemini TTS.")
            self.gemini_key = ASLineEdit()
            self.gemini_key.setEchoMode(QLineEdit.EchoMode.Password)
            self.gemini_key.setPlaceholderText("Cole sua API key")
            self.gemini_text_model = ASLineEdit()
            self._add_field(gemini, "API key", self.gemini_key)
            self._add_field(gemini, "Modelo de texto", self.gemini_text_model)
            layout.addWidget(gemini)
            eleven = SectionCard("ElevenLabs", "A chave é usada pelos perfis ElevenLabs configurados em Áudio.")
            self.eleven_key = ASLineEdit()
            self.eleven_key.setEchoMode(QLineEdit.EchoMode.Password)
            self.eleven_key.setPlaceholderText("Cole sua API key")
            self._add_field(eleven, "API key", self.eleven_key)
            layout.addWidget(eleven)
        elif key == "images":
            content, layout = self._page("Imagens", "Configure as fontes disponíveis para pesquisas de imagem.")
            card = SectionCard("Fontes de imagem")
            self.wikimedia_images = QCheckBox("Wikimedia Commons")
            self.pixabay_images = QCheckBox("Pixabay")
            self.pexels_images = QCheckBox("Pexels")
            row = QHBoxLayout()
            row.addWidget(self.wikimedia_images)
            row.addWidget(self.pixabay_images)
            row.addWidget(self.pexels_images)
            row.addStretch(1)
            card.root.addLayout(row)
            self.pixabay_key = ASLineEdit()
            self.pixabay_key.setEchoMode(QLineEdit.EchoMode.Password)
            self.pexels_key = ASLineEdit()
            self.pexels_key.setEchoMode(QLineEdit.EchoMode.Password)
            self._add_field(card, "Pixabay API key", self.pixabay_key)
            self._add_field(card, "Pexels API key", self.pexels_key)
            layout.addWidget(card)
        elif key == "audio":
            content, layout = self._page(
                "Áudio",
                "Configurações globais e perfis de voz. A estratégia usada em cada projeto fica dentro do próprio projeto.",
            )
            voicevox = SectionCard("VOICEVOX", "Configure o engine local e a voz padrão usada por novos projetos em Japonês.")
            self.voicevox_url = ASLineEdit()
            self._add_field(voicevox, "URL local", self.voicevox_url)
            self.voicevox_default_combo = SearchableComboBox()
            self.voicevox_default_combo.lineEdit().setPlaceholderText("Carregue ou pesquise um personagem/estilo")
            self._add_field(voicevox, "Voz padrão", self.voicevox_default_combo)
            vv_actions = QGridLayout()
            vv_actions.setHorizontalSpacing(8)
            vv_actions.setVerticalSpacing(8)
            self.test_voicevox_button = ASButton("Testar conexão")
            self.voicevox_load_button = ASButton("Carregar vozes")
            self.voicevox_adjust_button = ASButton("Ajustar voz")
            self.voicevox_preview_button = ASButton("▶ Ouvir exemplo")
            for button in (self.test_voicevox_button, self.voicevox_load_button, self.voicevox_adjust_button, self.voicevox_preview_button):
                button.setObjectName("SubtleButton")
            self.test_voicevox_button.clicked.connect(self.test_voicevox)
            self.voicevox_load_button.clicked.connect(self.load_voicevox_styles)
            self.voicevox_adjust_button.clicked.connect(self.adjust_voicevox_defaults)
            self.voicevox_preview_button.clicked.connect(self.preview_voicevox_default)
            vv_actions.addWidget(self.test_voicevox_button, 0, 0)
            vv_actions.addWidget(self.voicevox_load_button, 0, 1)
            vv_actions.addWidget(self.voicevox_adjust_button, 1, 0)
            vv_actions.addWidget(self.voicevox_preview_button, 1, 1)
            vv_actions.setColumnStretch(0, 1)
            vv_actions.setColumnStretch(1, 1)
            voicevox.root.addLayout(vv_actions)
            layout.addWidget(voicevox)
            self.profile_lists: dict[str, QListWidget] = {}
            for provider, title in (("gemini", "Perfis Gemini TTS"), ("elevenlabs", "Perfis ElevenLabs")):
                card = SectionCard(title, "Perfis globais reutilizáveis pelos projetos.")
                profile_list = QListWidget()
                profile_list.setMinimumHeight(110)
                self.profile_lists[provider] = profile_list
                card.root.addWidget(profile_list)
                actions = QGridLayout()
                actions.setHorizontalSpacing(8)
                actions.setVerticalSpacing(8)
                add_button = ASButton("Adicionar")
                edit_button = ASButton("Editar")
                remove_button = ASButton("Remover")
                for button in (add_button, edit_button, remove_button):
                    button.setObjectName("SubtleButton")
                add_button.clicked.connect(lambda _=False, p=provider: self._add_profile(p))
                edit_button.clicked.connect(lambda _=False, p=provider: self._edit_profile(p))
                remove_button.clicked.connect(lambda _=False, p=provider: self._delete_profile(p))
                actions.addWidget(add_button, 0, 0)
                actions.addWidget(edit_button, 0, 1)
                preview_button = ASButton("▶ Ouvir selecionada")
                preview_button.setObjectName("SubtleButton")
                preview_button.clicked.connect(lambda _=False, p=provider: self.preview_selected_profile(p))
                actions.addWidget(remove_button, 1, 0)
                actions.addWidget(preview_button, 1, 1)
                actions.setColumnStretch(0, 1)
                actions.setColumnStretch(1, 1)
                card.root.addLayout(actions)
                if provider == "gemini":
                    self.gemini_usage_label = QLabel()
                    self.gemini_usage_label.setObjectName("MutedLabel")
                    self.gemini_usage_label.setWordWrap(True)
                    card.root.addWidget(self.gemini_usage_label)
                layout.addWidget(card)
        else:
            content, layout = self._page("Atualizações", "Controle como novas versões do BenkyouStudio são verificadas.")
            updates = SectionCard("Atualizações")
            self.check_updates = QCheckBox("Procurar atualizações automaticamente")
            self.check_updates_now_button = ASButton("Procurar atualizações agora")
            self.check_updates_now_button.setObjectName("SubtleButton")
            self.check_updates_now_button.clicked.connect(lambda: self.check_updates_requested.emit())
            updates.root.addWidget(self.check_updates)
            updates.root.addWidget(self.check_updates_now_button)
            layout.addWidget(updates)
        layout.addStretch(1)
        return PageScrollArea(content)

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

    def load(self) -> None:
        appearance_theme = self.database.get_setting("appearance_theme", "dark")
        self._loaded_appearance_theme = appearance_theme
        self._select_data(self.appearance_combo, appearance_theme)
        self._select_data(self.ui_language_combo, self.database.get_setting("ui_language", "pt_BR"))
        self._loaded_secret_values = {
            "GEMINI_API_KEY": SecretStore.get("GEMINI_API_KEY"),
            "ELEVENLABS_API_KEY": SecretStore.get("ELEVENLABS_API_KEY"),
            "PIXABAY_API_KEY": SecretStore.get("PIXABAY_API_KEY"),
            "PEXELS_API_KEY": SecretStore.get("PEXELS_API_KEY"),
        }
        self.gemini_key.setText(self._loaded_secret_values["GEMINI_API_KEY"])
        self.eleven_key.setText(self._loaded_secret_values["ELEVENLABS_API_KEY"])
        self.pixabay_key.setText(self._loaded_secret_values["PIXABAY_API_KEY"])
        self.pexels_key.setText(self._loaded_secret_values["PEXELS_API_KEY"])
        self.wikimedia_images.setChecked(self.database.get_setting("image_source_wikimedia", "1") == "1")
        self.pixabay_images.setChecked(self.database.get_setting("image_source_pixabay", "0") == "1")
        self.pexels_images.setChecked(self.database.get_setting("image_source_pexels", "0") == "1")
        self.check_updates.setChecked(self.database.get_setting("check_updates", "1") == "1")
        self.gemini_text_model.setText(self.database.get_setting("gemini_text_model", DEFAULT_GEMINI_TEXT_MODEL))
        self.voicevox_url.setText(self.database.get_setting("voicevox_url", DEFAULT_VOICEVOX_URL))
        if hasattr(self, "default_card_theme_editor"):
            self.default_card_theme_editor.set_theme(load_default_card_theme(self.database))
        if hasattr(self, "voicevox_default_combo"):
            label = self._voicevox_defaults.style_label or f"Estilo ID {self._voicevox_defaults.style_id} — carregue para atualizar"
            self.voicevox_default_combo.set_items([(label, self._voicevox_defaults.style_id)], self._voicevox_defaults.style_id)

    def save(self) -> None:
        total_started = perf_counter()
        timings: dict[str, float] = {}
        changed_secret_count = 0
        theme_changed = False
        try:
            phase_started = perf_counter()
            pixabay_key = self.pixabay_key.text().strip()
            pexels_key = self.pexels_key.text().strip()
            if not any((self.wikimedia_images.isChecked(), self.pixabay_images.isChecked(), self.pexels_images.isChecked())):
                raise ValueError("Habilite ao menos uma fonte de imagem.")
            if self.pixabay_images.isChecked() and not pixabay_key:
                raise ValueError("Informe a API key do Pixabay antes de habilitar essa fonte.")
            if self.pexels_images.isChecked() and not pexels_key:
                raise ValueError("Informe a API key do Pexels antes de habilitar essa fonte.")

            secret_values = {
                "GEMINI_API_KEY": self.gemini_key.text().strip(),
                "ELEVENLABS_API_KEY": self.eleven_key.text().strip(),
                "PIXABAY_API_KEY": pixabay_key,
                "PEXELS_API_KEY": pexels_key,
            }
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
            if hasattr(self, "default_card_theme_editor"):
                values[DEFAULT_CARD_THEME_SETTING] = self.default_card_theme_editor.theme().model_dump_json()
            if hasattr(self, "voicevox_default_combo") and self.voicevox_default_combo.currentData() is not None:
                self._voicevox_defaults.style_id = int(self.voicevox_default_combo.currentData())
                self._voicevox_defaults.style_label = self.voicevox_default_combo.currentText().strip()
                values[VOICEVOX_DEFAULTS_KEY] = json.dumps(asdict(self._voicevox_defaults), ensure_ascii=False)
            theme_changed = values["appearance_theme"] != getattr(self, "_loaded_appearance_theme", "dark")
            timings["validation_ms"] = (perf_counter() - phase_started) * 1000

            phase_started = perf_counter()
            loaded_secret_values = getattr(self, "_loaded_secret_values", {})
            changed_secrets = {
                key: value
                for key, value in secret_values.items()
                if value != loaded_secret_values.get(key, "")
            }
            for key, value in changed_secrets.items():
                SecretStore.set(key, value)
                loaded_secret_values[key] = value
            changed_secret_count = len(changed_secrets)
            timings["keyring_ms"] = (perf_counter() - phase_started) * 1000

            phase_started = perf_counter()
            self.database.set_settings(values)
            timings["sqlite_ms"] = (perf_counter() - phase_started) * 1000

            phase_started = perf_counter()
            app = QApplication.instance()
            if app is not None and theme_changed:
                apply_design_system(app, self.resource_dir, values["appearance_theme"])
            timings["design_system_ms"] = (perf_counter() - phase_started) * 1000

            self._loaded_secret_values = secret_values.copy()
            self._loaded_appearance_theme = values["appearance_theme"]
        except Exception as exc:
            logger.exception(
                "Falha ao salvar configurações após %.2f ms",
                (perf_counter() - total_started) * 1000,
            )
            QMessageBox.critical(self, "Falha ao salvar", str(exc))
            return

        timings["total_ms"] = (perf_counter() - total_started) * 1000
        logger.info(
            "Settings Save: validation=%.2fms keyring=%.2fms sqlite=%.2fms design_system=%.2fms total=%.2fms keyring_updates=%d theme_changed=%s",
            timings["validation_ms"],
            timings["keyring_ms"],
            timings["sqlite_ms"],
            timings["design_system_ms"],
            timings["total_ms"],
            changed_secret_count,
            theme_changed,
        )
        self.status.show_message(tr("Configurações salvas."))

    def _ui_language_selected(self, _index: int) -> None:
        if self._loading_settings:
            return
        language = str(self.ui_language_combo.currentData() or "pt_BR")
        self.database.set_setting("ui_language", language)
        self.ui_language_changed.emit(language)
        self.status.show_message(tr("Idioma da interface atualizado."))

    def _refresh_profiles(self) -> None:
        profiles = self.profile_service.load()
        for provider, widget in getattr(self, "profile_lists", {}).items():
            widget.clear()
            for profile in profiles:
                if profile.provider != provider:
                    continue
                item = QListWidgetItem(profile.display_name + ("" if profile.enabled else " · desativado"))
                item.setData(Qt.ItemDataRole.UserRole, profile.id)
                widget.addItem(item)
        self._refresh_gemini_usage()

    def _refresh_gemini_usage(self) -> None:
        label = getattr(self, "gemini_usage_label", None)
        if label is None:
            return
        profiles = [p for p in self.profile_service.load() if p.provider == "gemini" and p.enabled]
        models: list[str] = []
        for profile in profiles:
            if profile.model and profile.model not in models:
                models.append(profile.model)
        if not models:
            label.setText(tr("Adicione um perfil Gemini para acompanhar o uso observado por modelo."))
            return
        lines: list[str] = []
        for model in models:
            status = self.gemini_usage.status(model)
            retry = status["retry_remaining_seconds"]
            limit = status["detected_limit"]
            remaining = status["estimated_remaining"]
            if retry:
                info = f"nova tentativa estimada em {retry}s"
            elif limit is not None and remaining is not None:
                info = f"~{remaining} de {limit} restantes"
            elif limit is not None:
                info = f"último limite detectado: {limit}"
            else:
                info = "limite ainda não observado"
            lines.append(f"{model}: {info}; {status['successes_24h']} sucesso(s) nas últimas 24h")
        label.setText(tr("Uso observado:\n" + "\n".join(lines)))

    def _selected_profile(self, provider: str) -> AudioVoiceProfile | None:
        widget = self.profile_lists.get(provider)
        if widget is None or widget.currentItem() is None:
            return None
        return self.profile_service.get(str(widget.currentItem().data(Qt.ItemDataRole.UserRole) or ""))

    def _add_profile(self, provider: str) -> None:
        dialog = AudioProfileDialog(provider, parent=self)
        if not dialog.exec():
            return
        try:
            self.profile_service.upsert(dialog.value())
        except Exception as exc:
            QMessageBox.warning(self, "Perfil inválido", str(exc))
            return
        self._refresh_profiles()

    def _edit_profile(self, provider: str) -> None:
        profile = self._selected_profile(provider)
        if profile is None:
            return
        dialog = AudioProfileDialog(provider, profile, self)
        if not dialog.exec():
            return
        try:
            self.profile_service.upsert(dialog.value())
        except Exception as exc:
            QMessageBox.warning(self, "Perfil inválido", str(exc))
            return
        self._refresh_profiles()

    def _delete_profile(self, provider: str) -> None:
        profile = self._selected_profile(provider)
        if profile is None:
            return
        if QMessageBox.question(self, "Remover perfil", f"Remover o perfil “{profile.name}”? ") != QMessageBox.StandardButton.Yes:
            return
        self.profile_service.delete(profile.id)
        self._refresh_profiles()

    def _keep_worker(self, worker: Worker) -> None:
        self._workers.append(worker)
        worker.signals.finished.connect(lambda: self._workers.remove(worker) if worker in self._workers else None)
        self.thread_pool.start(worker)

    def _play_preview_result(self, result: object, success_message: str) -> None:
        local_path = getattr(result, "local_path", "")
        path = Path(str(local_path))
        if not path.is_file() or path.stat().st_size <= 0:
            self.status.show_message("O provedor não retornou um arquivo de áudio válido.", error=True)
            return
        self.preview_player.stop()
        self.preview_player.setSource(QUrl.fromLocalFile(str(path)))
        self.preview_player.play()
        self.status.show_message(success_message)

    def load_voicevox_styles(self) -> None:
        url = self.voicevox_url.text().strip().rstrip("/") or DEFAULT_VOICEVOX_URL
        self.voicevox_load_button.setEnabled(False)
        self.status.show_message("Carregando vozes do VOICEVOX...")
        worker = Worker(VoicevoxProvider.list_speaker_styles, url, 8.0)

        def loaded(result: object) -> None:
            items = [(str(item["label"]), int(item["id"])) for item in list(result)]
            self.voicevox_default_combo.set_items(items, self._voicevox_defaults.style_id)
            self.status.show_message(f"{len(items)} estilos do VOICEVOX carregados.")

        worker.signals.result.connect(loaded)
        worker.signals.error.connect(lambda message: self.status.show_message(message, error=True))
        worker.signals.finished.connect(lambda: self.voicevox_load_button.setEnabled(True))
        self._keep_worker(worker)

    def adjust_voicevox_defaults(self) -> None:
        if self.voicevox_default_combo.currentData() is not None:
            self._voicevox_defaults.style_id = int(self.voicevox_default_combo.currentData())
            self._voicevox_defaults.style_label = self.voicevox_default_combo.currentText().strip()
        dialog = VoicevoxSettingsDialog(self._voicevox_defaults, self)
        if dialog.exec():
            dialog.apply_to(self._voicevox_defaults)
            save_voicevox_defaults(self.database, self._voicevox_defaults)
            self.status.show_message("Ajustes padrão do VOICEVOX salvos.")

    def preview_voicevox_default(self) -> None:
        style_id = self.voicevox_default_combo.currentData()
        if style_id is None:
            QMessageBox.information(self, "Voz não carregada", "Carregue as vozes do VOICEVOX antes de testar.")
            return
        url = self.voicevox_url.text().strip().rstrip("/") or DEFAULT_VOICEVOX_URL
        provider = VoicevoxProvider(
            url, int(style_id),
            speed_scale=self._voicevox_defaults.speed_scale,
            pitch_scale=self._voicevox_defaults.pitch_scale,
            intonation_scale=self._voicevox_defaults.intonation_scale,
            volume_scale=self._voicevox_defaults.volume_scale,
            pause_length_scale=self._voicevox_defaults.pause_length_scale,
        )
        target = self.paths.audio_dir / "voice_preview" / "voicevox_default"
        self.voicevox_preview_button.setEnabled(False)
        worker = Worker(provider.generate, preview_text("ja"), target)
        worker.signals.result.connect(lambda result: self._play_preview_result(result, "Reproduzindo a voz padrão do VOICEVOX."))
        worker.signals.error.connect(lambda message: self.status.show_message(message, error=True))
        worker.signals.finished.connect(lambda: self.voicevox_preview_button.setEnabled(True))
        self._keep_worker(worker)

    def preview_selected_profile(self, provider: str) -> None:
        profile = self._selected_profile(provider)
        if profile is None:
            QMessageBox.information(self, "Selecione uma voz", "Selecione um perfil para ouvir o exemplo.")
            return
        if provider == "gemini":
            engine = GeminiTTSProvider(
                SecretStore.get("GEMINI_API_KEY"), profile.model, profile.voice,
                GeminiTTSUsageTracker(self.database), language_label(profile.language),
            )
        else:
            engine = ElevenLabsProvider(
                SecretStore.get("ELEVENLABS_API_KEY"), profile.voice, profile.model,
                language=profile.language, stability=profile.stability,
                similarity_boost=profile.similarity_boost, style=profile.style,
                speed=profile.speed, speaker_boost=profile.speaker_boost,
            )
        target = self.paths.audio_dir / "voice_preview" / f"{provider}_{profile.id}"
        self.status.show_message(f"Gerando exemplo de {profile.name}...")
        worker = Worker(engine.generate, preview_text(profile.language), target)
        worker.signals.result.connect(lambda result: self._play_preview_result(result, f"Reproduzindo {profile.name}."))
        worker.signals.error.connect(lambda message: self.status.show_message(message, error=True))
        self._keep_worker(worker)

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
        worker.signals.result.connect(lambda version: self.status.show_message(tr(f"VOICEVOX disponível. Versão: {version}")))
        worker.signals.error.connect(lambda message: self.status.show_message(message, error=True))

        def finished() -> None:
            self.test_voicevox_button.setEnabled(True)
            self._voicevox_worker = None

        worker.signals.finished.connect(finished)
        self.thread_pool.start(worker)
