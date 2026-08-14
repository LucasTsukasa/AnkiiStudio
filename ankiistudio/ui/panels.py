from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThreadPool, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ankiistudio.config import AppPaths, SecretStore
from ankiistudio.constants import AUDIO_PROVIDER_LABELS, DEFAULT_VOICEVOX_URL, language_label
from ankiistudio.database import Database
from ankiistudio.models import ProjectData
from ankiistudio.services.audio.elevenlabs import ElevenLabsProvider
from ankiistudio.services.audio.gemini_tts import GeminiTTSProvider
from ankiistudio.services.audio.voicevox import VoicevoxProvider
from ankiistudio.services.audio_preferences import preview_text
from ankiistudio.services.audio_profile_service import AudioProfileService
from ankiistudio.services.gemini_tts_usage import GeminiTTSUsageTracker
from ankiistudio.ui.design_system.components import ASButton, ASComboBox
from ankiistudio.ui.dialogs.voicevox_settings_dialog import VoicevoxSettingsDialog
from ankiistudio.ui.widgets import PageScrollArea, SearchableComboBox, SectionCard, StatusBanner
from ankiistudio.ui.workers import Worker


class ProjectAudioSettingsPanel(QWidget):
    """Somente opções de áudio pertencentes ao projeto; perfis globais ficam em Configurações."""

    def __init__(self, database: Database, paths: AppPaths) -> None:
        super().__init__()
        self.database = database
        self.paths = paths
        self.profile_service = AudioProfileService(database)
        self.current_project: ProjectData | None = None
        self.thread_pool = QThreadPool.globalInstance()
        self._workers: list[Worker] = []
        self.preview_audio_output = QAudioOutput(self)
        self.preview_audio_output.setVolume(0.9)
        self.preview_player = QMediaPlayer(self)
        self.preview_player.setAudioOutput(self.preview_audio_output)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(12)
        self.status = StatusBanner()
        layout.addWidget(self.status)

        strategy = SectionCard(
            "Áudio do projeto",
            "Escolha como os provedores globais configurados serão usados neste projeto.",
        )
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        self.mode_combo = ASComboBox()
        self.mode_combo.addItem("Seleção inteligente — recomendada", "intelligent")
        self.mode_combo.addItem("Somente um provedor fixo", "fixed")
        self.mode_combo.addItem("Alternância aleatória", "random")
        self.fixed_combo = ASComboBox()
        for key, label in AUDIO_PROVIDER_LABELS.items():
            self.fixed_combo.addItem(label, key)
        self.fixed_profile_combo = ASComboBox()
        self.mode_combo.currentIndexChanged.connect(self._update_mode)
        self.fixed_combo.currentIndexChanged.connect(self._refresh_fixed_profiles)
        self._add_grid_field(grid, 0, "Modo", self.mode_combo)
        self._add_grid_field(grid, 1, "Provedor fixo", self.fixed_combo)
        self._add_grid_field(grid, 2, "Voz fixa", self.fixed_profile_combo)
        strategy.root.addLayout(grid)
        layout.addWidget(strategy)

        providers = SectionCard("Provedores permitidos")
        self.provider_checks: dict[str, QCheckBox] = {}
        for key, label in AUDIO_PROVIDER_LABELS.items():
            check = QCheckBox(label)
            self.provider_checks[key] = check
            providers.root.addWidget(check)
        layout.addWidget(providers)

        preferred = SectionCard(
            "Vozes preferidas",
            "Opcional. Nos modos inteligente e aleatório, fixe uma voz preferida por provedor; sem seleção, todos os perfis habilitados do idioma podem ser usados.",
        )
        self.preferred_profile_combos: dict[str, QComboBox] = {}
        self.preferred_profile_preview_buttons: dict[str, QPushButton] = {}
        preferred_grid = QGridLayout()
        preferred_grid.setHorizontalSpacing(10)
        preferred_grid.setVerticalSpacing(8)
        for row, (provider, label) in enumerate((("gemini", "Gemini TTS"), ("elevenlabs", "ElevenLabs"))):
            combo = ASComboBox()
            preview_button = ASButton("▶ Ouvir")
            preview_button.setObjectName("SubtleButton")
            preview_button.clicked.connect(lambda _=False, p=provider: self.preview_preferred_profile(p))
            preferred_grid.addWidget(QLabel(label), row, 0)
            preferred_grid.addWidget(combo, row, 1)
            preferred_grid.addWidget(preview_button, row, 2)
            self.preferred_profile_combos[provider] = combo
            self.preferred_profile_preview_buttons[provider] = preview_button
        preferred_grid.setColumnStretch(1, 1)
        preferred.root.addLayout(preferred_grid)
        layout.addWidget(preferred)

        self.voicevox_card = SectionCard(
            "VOICEVOX do projeto",
            "Personagem, estilo e ajustes são específicos deste projeto.",
        )
        voicevox_label = QLabel("Personagem / estilo")
        voicevox_label.setObjectName("FieldLabel")
        self.voicevox_card.root.addWidget(voicevox_label)
        self.voicevox_combo = SearchableComboBox()
        self.voicevox_combo.lineEdit().setPlaceholderText("Carregue ou pesquise um personagem/estilo")
        self.voicevox_load_button = ASButton("Carregar vozes")
        self.voicevox_adjust_button = ASButton("Ajustar voz")
        self.voicevox_test_button = ASButton("▶ Ouvir exemplo")
        for button in (self.voicevox_load_button, self.voicevox_adjust_button, self.voicevox_test_button):
            button.setObjectName("SubtleButton")
        self.voicevox_load_button.clicked.connect(self.load_voicevox_styles)
        self.voicevox_adjust_button.clicked.connect(self.adjust_voicevox)
        self.voicevox_test_button.clicked.connect(self.test_voicevox)
        self.voicevox_card.root.addWidget(self.voicevox_combo)
        actions = QHBoxLayout()
        actions.addWidget(self.voicevox_load_button)
        actions.addWidget(self.voicevox_adjust_button)
        actions.addWidget(self.voicevox_test_button)
        actions.addStretch(1)
        self.voicevox_card.root.addLayout(actions)
        layout.addWidget(self.voicevox_card)

        save = ASButton("Salvar áudio do projeto")
        save.setObjectName("PrimaryButton")
        save.clicked.connect(self.save_project)
        layout.addWidget(save)
        layout.addStretch(1)
        root.addWidget(PageScrollArea(content))

    @staticmethod
    def _add_grid_field(grid: QGridLayout, row: int, label: str, widget: QWidget) -> None:
        text = QLabel(label)
        text.setObjectName("FieldLabel")
        grid.addWidget(text, row, 0)
        grid.addWidget(widget, row, 1)

    @staticmethod
    def _select_data(combo: QComboBox, value: str) -> None:
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def set_project(self, project_id: int) -> None:
        self.current_project = self.database.get_project(project_id)
        project = self.current_project
        if project is None:
            return
        self._select_data(self.mode_combo, project.audio_mode)
        self._select_data(self.fixed_combo, project.fixed_audio_provider)
        for key, check in self.provider_checks.items():
            allowed = not (key == "voicevox" and project.language != "ja")
            check.setEnabled(allowed)
            check.setChecked(allowed and key in project.audio_providers)
        self.voicevox_card.setVisible(project.language == "ja")
        if project.language == "ja":
            label = project.voicevox_style_label or f"Estilo ID {project.voicevox_style_id} — carregue para atualizar"
            self.voicevox_combo.set_items([(label, project.voicevox_style_id)], project.voicevox_style_id)
        self._refresh_preferred_profiles()
        self._refresh_fixed_profiles()
        self._update_mode()

    def _refresh_preferred_profiles(self) -> None:
        project = self.current_project
        if project is None:
            return
        for provider, combo in self.preferred_profile_combos.items():
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("Automática — usar perfis habilitados", "")
            for profile in self.profile_service.list_for(provider, project.language):
                combo.addItem(profile.display_name, profile.id)
            target = project.audio_profile_preferences.get(provider, "")
            index = combo.findData(target) if target else 0
            combo.setCurrentIndex(index if index >= 0 else 0)
            combo.blockSignals(False)

    def _update_mode(self, *_args) -> None:
        fixed = str(self.mode_combo.currentData() or "") == "fixed"
        self.fixed_combo.setEnabled(fixed)
        self.fixed_profile_combo.setEnabled(fixed and str(self.fixed_combo.currentData() or "") in {"gemini", "elevenlabs"})

    def _refresh_fixed_profiles(self, *_args) -> None:
        self.fixed_profile_combo.clear()
        project = self.current_project
        provider = str(self.fixed_combo.currentData() or "")
        if project is None or provider not in {"gemini", "elevenlabs"}:
            self._update_mode()
            return
        for profile in self.profile_service.list_for(provider, project.language):
            self.fixed_profile_combo.addItem(profile.display_name, profile.id)
        self._select_data(self.fixed_profile_combo, project.fixed_audio_profile_id)
        self._update_mode()

    def _play_preview_result(self, result: object, message: str) -> None:
        local_path = getattr(result, "local_path", "")
        path = Path(str(local_path))
        if not path.is_file() or path.stat().st_size <= 0:
            self.status.show_message("O provedor não retornou um arquivo de áudio válido.", error=True)
            return
        self.preview_player.stop()
        self.preview_player.setSource(QUrl.fromLocalFile(str(path)))
        self.preview_player.play()
        self.status.show_message(message)

    def preview_preferred_profile(self, provider: str) -> None:
        project = self.current_project
        combo = self.preferred_profile_combos.get(provider)
        profile_id = str(combo.currentData() or "") if combo is not None else ""
        if project is None or not profile_id:
            QMessageBox.information(self, "Selecione uma voz", "Selecione uma voz específica para ouvir o exemplo.")
            return
        profile = self.profile_service.get(profile_id)
        if profile is None:
            return
        if provider == "gemini":
            engine = GeminiTTSProvider(
                SecretStore.get("GEMINI_API_KEY"),
                profile.model,
                profile.voice,
                GeminiTTSUsageTracker(self.database),
                language_label(profile.language),
            )
        else:
            engine = ElevenLabsProvider(
                SecretStore.get("ELEVENLABS_API_KEY"),
                profile.voice,
                profile.model,
                language=profile.language,
                stability=profile.stability,
                similarity_boost=profile.similarity_boost,
                style=profile.style,
                speed=profile.speed,
                speaker_boost=profile.speaker_boost,
            )
        target = self.paths.audio_dir / "voice_preview" / f"project_{provider}_{profile.id}"
        button = self.preferred_profile_preview_buttons[provider]
        button.setEnabled(False)
        self.status.show_message(f"Gerando exemplo de {profile.name}...")
        worker = Worker(engine.generate, preview_text(profile.language), target)
        worker.signals.result.connect(lambda result: self._play_preview_result(result, f"Reproduzindo {profile.name}."))
        worker.signals.error.connect(lambda message: self.status.show_message(message, error=True))
        worker.signals.finished.connect(lambda: button.setEnabled(True))
        self._keep_worker(worker)

    def load_voicevox_styles(self) -> None:
        project = self.current_project
        if project is None or project.language != "ja":
            return
        url = self.database.get_setting("voicevox_url", DEFAULT_VOICEVOX_URL)
        self.voicevox_load_button.setEnabled(False)
        self.status.show_message("Carregando vozes do VOICEVOX...")
        worker = Worker(VoicevoxProvider.list_speaker_styles, url, 8.0)
        worker.signals.result.connect(self._voicevox_loaded)
        worker.signals.error.connect(lambda msg: self.status.show_message(msg, error=True))
        worker.signals.finished.connect(lambda: self.voicevox_load_button.setEnabled(True))
        self._keep_worker(worker)

    def _voicevox_loaded(self, result: object) -> None:
        project = self.current_project
        if project is None:
            return
        styles = list(result)
        items = [(str(item["label"]), int(item["id"])) for item in styles]
        self.voicevox_combo.set_items(items, project.voicevox_style_id)
        self.status.show_message(f"{len(items)} estilos carregados.")

    def test_voicevox(self) -> None:
        project = self.current_project
        if project is None or project.language != "ja":
            return
        style_id = self.voicevox_combo.currentData()
        if style_id is None:
            QMessageBox.information(self, "Voz não carregada", "Carregue as vozes do VOICEVOX antes de testar.")
            return
        url = self.database.get_setting("voicevox_url", DEFAULT_VOICEVOX_URL)
        provider = VoicevoxProvider(
            url,
            int(style_id),
            speed_scale=project.voicevox_speed_scale,
            pitch_scale=project.voicevox_pitch_scale,
            intonation_scale=project.voicevox_intonation_scale,
            volume_scale=project.voicevox_volume_scale,
            pause_length_scale=project.voicevox_pause_length_scale,
        )
        target = self.paths.audio_dir / "voicevox_preview" / "preview"
        self.voicevox_test_button.setEnabled(False)
        worker = Worker(provider.generate, preview_text("ja"), target)

        def open_audio(result: object) -> None:
            local_path = getattr(result, "local_path", "")
            path = Path(str(local_path))
            if not path.is_file():
                raise RuntimeError("O VOICEVOX não retornou um arquivo de áudio válido.")
            self.preview_player.stop()
            self.preview_player.setSource(QUrl.fromLocalFile(str(path)))
            self.preview_player.play()
            self.status.show_message("Reproduzindo o exemplo do VOICEVOX dentro do AnkiiStudio.")

        worker.signals.result.connect(open_audio)
        worker.signals.error.connect(lambda message: self.status.show_message(message, error=True))
        worker.signals.finished.connect(lambda: self.voicevox_test_button.setEnabled(True))
        self._keep_worker(worker)

    def adjust_voicevox(self) -> None:
        project = self.current_project
        if project is None or project.language != "ja":
            return
        style_id = self.voicevox_combo.currentData()
        if style_id is not None:
            project.voicevox_style_id = int(style_id)
            project.voicevox_style_label = self.voicevox_combo.currentText().strip()
        dialog = VoicevoxSettingsDialog(project, self)
        if dialog.exec():
            dialog.apply_to(project)
            self.database.update_project(project)
            self.status.show_message("Ajustes do VOICEVOX salvos.")

    def save_project(self) -> bool:
        project = self.current_project
        if project is None:
            return False
        providers = [key for key, check in self.provider_checks.items() if check.isEnabled() and check.isChecked()]
        mode = str(self.mode_combo.currentData() or "intelligent")
        fixed = str(self.fixed_combo.currentData() or "voicevox")
        if mode == "fixed" and fixed not in providers:
            providers.append(fixed)
        if not providers:
            QMessageBox.warning(self, "Sem provedores", "Selecione ao menos um provedor de áudio.")
            return False
        if mode == "fixed" and fixed in {"gemini", "elevenlabs"} and self.fixed_profile_combo.currentData() is None:
            QMessageBox.warning(self, "Voz ausente", "Cadastre uma voz nas Configurações e selecione-a aqui.")
            return False
        project.audio_mode = mode
        project.audio_providers = providers
        project.fixed_audio_provider = fixed
        project.fixed_audio_profile_id = str(self.fixed_profile_combo.currentData() or "") if fixed in {"gemini", "elevenlabs"} else ""
        project.audio_profile_preferences = {
            provider: str(combo.currentData() or "")
            for provider, combo in self.preferred_profile_combos.items()
            if combo.currentData()
        }
        if project.language == "ja" and self.voicevox_combo.currentData() is not None:
            project.voicevox_style_id = int(self.voicevox_combo.currentData())
            project.voicevox_style_label = self.voicevox_combo.currentText().strip()
        self.database.update_project(project)
        self.status.show_message("Configuração de áudio do projeto salva.")
        return True

    def _keep_worker(self, worker: Worker) -> None:
        self._workers.append(worker)
        worker.signals.finished.connect(lambda: self._workers.remove(worker) if worker in self._workers else None)
        self.thread_pool.start(worker)
