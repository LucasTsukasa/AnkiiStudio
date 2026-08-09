from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QThreadPool, QUrl, Qt
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ankiistudio.config import AppPaths, SecretStore
from ankiistudio.constants import AUDIO_PROVIDER_LABELS, DEFAULT_VOICEVOX_URL, language_label
from ankiistudio.database import Database
from ankiistudio.models import ProjectData
from ankiistudio.services.audio.voicevox import VoicevoxProvider
from ankiistudio.services.audio_profile_service import AudioProfileService, AudioVoiceProfile
from ankiistudio.services.audio_service import ProjectAudioService
from ankiistudio.services.gemini_tts_usage import GeminiTTSUsageTracker
from ankiistudio.ui.dialogs.audio_profile_dialog import AudioProfileDialog
from ankiistudio.ui.dialogs.voicevox_settings_dialog import VoicevoxSettingsDialog
from ankiistudio.ui.widgets import PageHeader, PageScrollArea, SearchableComboBox, SectionCard, StatusBanner
from ankiistudio.ui.workers import Worker


_PROVIDER_DESCRIPTIONS = {
    "voicevox": "Síntese local para japonês. Selecione o personagem e o estilo diretamente a partir do VOICEVOX Engine.",
    "wikimedia": "Usa gravações humanas quando houver conteúdo compatível no Wikimedia Commons.",
    "gemini": "Usa os perfis Gemini TTS habilitados para o idioma do projeto, respeitando modelo e voz de cada perfil.",
    "elevenlabs": "Usa os perfis ElevenLabs habilitados para o idioma do projeto, com Voice ID e modelo próprios.",
}


class AudioPage(QWidget):
    RESPONSIVE_BREAKPOINT = 1180

    def __init__(self, database: Database, paths: AppPaths) -> None:
        super().__init__()
        self.database = database
        self.paths = paths
        self.service = ProjectAudioService(database, paths)
        self.profile_service = AudioProfileService(database)
        self.gemini_usage = GeminiTTSUsageTracker(database)
        self.thread_pool = QThreadPool.globalInstance()
        self.current_project: ProjectData | None = None
        self._workers: list[Worker] = []
        self._compact_layout = False
        self._voicevox_styles: list[dict[str, object]] = []
        self.preview_audio_output = QAudioOutput(self)
        self.preview_audio_output.setVolume(0.9)
        self.preview_player = QMediaPlayer(self)
        self.preview_player.setAudioOutput(self.preview_audio_output)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)
        layout.addWidget(
            PageHeader(
                "Áudios",
                "Configure a estratégia de geração e as vozes disponíveis para cada idioma.",
            )
        )
        self.status = StatusBanner()
        layout.addWidget(self.status)

        project_card = SectionCard(
            "Projeto e modo",
            "A configuração é salva por projeto; arquivos válidos já existentes são preservados.",
        )
        self.project_grid = QGridLayout()
        self.project_grid.setHorizontalSpacing(12)
        self.project_grid.setVerticalSpacing(8)
        self.project_combo = QComboBox()
        self.project_combo.currentIndexChanged.connect(self.load_project)
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Seleção inteligente — recomendada", "intelligent")
        self.mode_combo.addItem("Somente um provedor fixo", "fixed")
        self.mode_combo.addItem("Alternância aleatória", "random")
        self.mode_combo.currentIndexChanged.connect(self._update_mode_controls)
        self.fixed_combo = QComboBox()
        for key, label in AUDIO_PROVIDER_LABELS.items():
            self.fixed_combo.addItem(label, key)
        self.fixed_combo.currentIndexChanged.connect(self._refresh_fixed_profile_combo)
        self.fixed_profile_combo = QComboBox()

        self.project_cell = self._field_cell("Projeto", self.project_combo)
        self.mode_cell = self._field_cell("Modo", self.mode_combo)
        self.fixed_cell = self._field_cell("Provedor fixo", self.fixed_combo)
        self.fixed_profile_cell = self._field_cell("Voz fixa", self.fixed_profile_combo)
        for cell in (self.project_cell, self.mode_cell, self.fixed_cell, self.fixed_profile_cell):
            self.project_grid.addWidget(cell, 0, 0)
        project_card.root.addLayout(self.project_grid)
        layout.addWidget(project_card)

        providers = SectionCard(
            "Provedores permitidos",
            "Ative as fontes que podem participar da geração. Perfis de voz são organizados por idioma.",
        )
        self.provider_grid = QGridLayout()
        self.provider_grid.setHorizontalSpacing(12)
        self.provider_grid.setVerticalSpacing(12)
        self.provider_checks: dict[str, QCheckBox] = {}
        self.provider_status: dict[str, QLabel] = {}
        self.provider_cards: dict[str, SectionCard] = {}
        self.profile_lists: dict[str, QListWidget] = {}

        for key in ("gemini", "voicevox", "wikimedia", "elevenlabs"):
            card = SectionCard()
            card.setObjectName("ProviderCard")
            header = QHBoxLayout()
            check = QCheckBox(AUDIO_PROVIDER_LABELS[key])
            check.setObjectName("ProviderCheck")
            status = QLabel()
            status.setObjectName("Badge")
            header.addWidget(check, 1)
            header.addWidget(status)
            card.root.addLayout(header)
            description = QLabel(_PROVIDER_DESCRIPTIONS[key])
            description.setObjectName("MutedLabel")
            description.setWordWrap(True)
            card.root.addWidget(description)
            self.provider_checks[key] = check
            self.provider_status[key] = status
            self.provider_cards[key] = card

            if key in ("gemini", "elevenlabs"):
                profile_list = QListWidget()
                profile_list.setMinimumHeight(104)
                self.profile_lists[key] = profile_list
                card.root.addWidget(profile_list)
                buttons = QHBoxLayout()
                add_button = QPushButton("Adicionar voz")
                edit_button = QPushButton("Editar")
                delete_button = QPushButton("Remover")
                for button in (add_button, edit_button, delete_button):
                    button.setObjectName("SubtleButton")
                add_button.clicked.connect(lambda _=False, provider=key: self._add_profile(provider))
                edit_button.clicked.connect(lambda _=False, provider=key: self._edit_profile(provider))
                delete_button.clicked.connect(lambda _=False, provider=key: self._delete_profile(provider))
                buttons.addWidget(add_button)
                buttons.addWidget(edit_button)
                buttons.addWidget(delete_button)
                buttons.addStretch(1)
                card.root.addLayout(buttons)
                if key == "gemini":
                    self.gemini_usage_label = QLabel()
                    self.gemini_usage_label.setObjectName("MutedLabel")
                    self.gemini_usage_label.setWordWrap(True)
                    card.root.addWidget(self.gemini_usage_label)

            elif key == "voicevox":
                self.voicevox_combo = SearchableComboBox()
                self.voicevox_combo.lineEdit().setPlaceholderText("Selecione ou pesquise personagem/estilo")
                self.voicevox_combo.currentIndexChanged.connect(self._voicevox_selected)
                self._add_field(card, "Personagem / estilo", self.voicevox_combo)
                voice_actions = QHBoxLayout()
                self.voicevox_load_button = QPushButton("Carregar vozes")
                self.voicevox_adjust_button = QPushButton("Ajustar voz")
                self.voicevox_test_button = QPushButton("▶ Ouvir exemplo")
                for button in (self.voicevox_load_button, self.voicevox_adjust_button, self.voicevox_test_button):
                    button.setObjectName("SubtleButton")
                self.voicevox_load_button.clicked.connect(self.load_voicevox_styles)
                self.voicevox_adjust_button.clicked.connect(self.adjust_voicevox_voice)
                self.voicevox_test_button.clicked.connect(self.test_voicevox_voice)
                voice_actions.addWidget(self.voicevox_load_button)
                voice_actions.addWidget(self.voicevox_adjust_button)
                voice_actions.addWidget(self.voicevox_test_button)
                voice_actions.addStretch(1)
                card.root.addLayout(voice_actions)

            self.provider_grid.addWidget(card, 0, 0)

        providers.root.addLayout(self.provider_grid)
        layout.addWidget(providers)

        generation_card = SectionCard(
            "Geração",
            "Processa somente os áudios ausentes exigidos pela estrutura do projeto.",
        )
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.hide()
        generation_card.root.addWidget(self.progress)
        actions = QHBoxLayout()
        self.save_button = QPushButton("Salvar configuração")
        self.save_button.setObjectName("SubtleButton")
        self.generate_button = QPushButton("Gerar áudios ausentes")
        self.generate_button.setObjectName("PrimaryButton")
        self.save_button.clicked.connect(self.save_project)
        self.generate_button.clicked.connect(self.generate_all)
        actions.addStretch(1)
        actions.addWidget(self.save_button)
        actions.addWidget(self.generate_button)
        generation_card.root.addLayout(actions)
        layout.addWidget(generation_card)
        layout.addStretch(1)
        root.addWidget(PageScrollArea(content))

        self._apply_responsive_layout(force=True)
        self.refresh()

    @staticmethod
    def _field_cell(label: str, widget: QWidget) -> QWidget:
        cell = QWidget()
        layout = QVBoxLayout(cell)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        title = QLabel(label)
        title.setObjectName("FieldLabel")
        layout.addWidget(title)
        layout.addWidget(widget)
        return cell

    @classmethod
    def _add_field(cls, card: SectionCard, label: str, widget: QWidget) -> None:
        card.root.addWidget(cls._field_cell(label, widget))

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        self._apply_responsive_layout()
        super().resizeEvent(event)

    def _apply_responsive_layout(self, force: bool = False) -> None:
        compact = self.width() < self.RESPONSIVE_BREAKPOINT
        if not force and compact == self._compact_layout:
            return
        self._compact_layout = compact

        for cell in (self.project_cell, self.mode_cell, self.fixed_cell, self.fixed_profile_cell):
            self.project_grid.removeWidget(cell)
        if compact:
            self.project_grid.addWidget(self.project_cell, 0, 0)
            self.project_grid.addWidget(self.mode_cell, 1, 0)
            self.project_grid.addWidget(self.fixed_cell, 2, 0)
            self.project_grid.addWidget(self.fixed_profile_cell, 3, 0)
        else:
            self.project_grid.addWidget(self.project_cell, 0, 0, 1, 2)
            self.project_grid.addWidget(self.mode_cell, 1, 0)
            self.project_grid.addWidget(self.fixed_cell, 1, 1)
            self.project_grid.addWidget(self.fixed_profile_cell, 2, 0, 1, 2)

        for card in self.provider_cards.values():
            self.provider_grid.removeWidget(card)
        for index, key in enumerate(("gemini", "voicevox", "wikimedia", "elevenlabs")):
            if compact:
                self.provider_grid.addWidget(self.provider_cards[key], index, 0)
            else:
                self.provider_grid.addWidget(self.provider_cards[key], index // 2, index % 2)

    def refresh(self) -> None:
        current_id = self.current_project.id if self.current_project else None
        self.project_combo.blockSignals(True)
        self.project_combo.clear()
        for project in self.database.list_projects():
            language = language_label(project.language)
            self.project_combo.addItem(f"{project.name} · {language}", project.id)
        self.project_combo.blockSignals(False)
        self._refresh_profile_lists()
        has_projects = self.project_combo.count() > 0
        self.save_button.setEnabled(has_projects)
        self.generate_button.setEnabled(False)
        if not has_projects:
            self.current_project = None
            self._refresh_provider_statuses()
            return
        index = 0
        if current_id:
            for i in range(self.project_combo.count()):
                if self.project_combo.itemData(i) == current_id:
                    index = i
                    break
        self.project_combo.setCurrentIndex(index)
        self.load_project()

    def _refresh_profile_lists(self) -> None:
        profiles = self.profile_service.load()
        for provider in ("gemini", "elevenlabs"):
            widget = self.profile_lists[provider]
            selected_id = widget.currentItem().data(Qt.ItemDataRole.UserRole) if widget.currentItem() else None
            widget.clear()
            for profile in profiles:
                if profile.provider != provider:
                    continue
                prefix = "✓" if profile.enabled else "○"
                widget.addItem(f"{prefix} {profile.display_name}")
                item = widget.item(widget.count() - 1)
                item.setData(Qt.ItemDataRole.UserRole, profile.id)
                if profile.id == selected_id:
                    widget.setCurrentItem(item)
        self.refresh_gemini_usage()
        self._refresh_provider_statuses()
        self._refresh_fixed_profile_combo()

    def _selected_profile(self, provider: str) -> AudioVoiceProfile | None:
        item = self.profile_lists[provider].currentItem()
        if item is None:
            return None
        return self.profile_service.get(str(item.data(Qt.ItemDataRole.UserRole)))

    def _add_profile(self, provider: str) -> None:
        dialog = AudioProfileDialog(provider, parent=self)
        if not dialog.exec():
            return
        try:
            self.profile_service.upsert(dialog.value())
        except Exception as exc:
            QMessageBox.warning(self, "Perfil inválido", str(exc))
            return
        self.service.reset_provider_failures()
        self._refresh_profile_lists()
        self.status.show_message("Perfil de voz adicionado.")

    def _edit_profile(self, provider: str) -> None:
        profile = self._selected_profile(provider)
        if profile is None:
            QMessageBox.information(self, "Selecione uma voz", "Selecione um perfil para editar.")
            return
        dialog = AudioProfileDialog(provider, profile, self)
        if not dialog.exec():
            return
        try:
            self.profile_service.upsert(dialog.value())
        except Exception as exc:
            QMessageBox.warning(self, "Perfil inválido", str(exc))
            return
        self.service.reset_provider_failures()
        self._refresh_profile_lists()
        self.status.show_message("Perfil de voz atualizado.")

    def _delete_profile(self, provider: str) -> None:
        profile = self._selected_profile(provider)
        if profile is None:
            QMessageBox.information(self, "Selecione uma voz", "Selecione um perfil para remover.")
            return
        if QMessageBox.question(self, "Remover voz", f"Remover o perfil “{profile.name}”?" ) != QMessageBox.StandardButton.Yes:
            return
        self.profile_service.delete(profile.id)
        self.service.reset_provider_failures()
        self._refresh_profile_lists()
        self.status.show_message("Perfil de voz removido.")

    def _refresh_provider_statuses(self) -> None:
        project = self.current_project
        language = project.language if project else "ja"
        language_name = language_label(language)
        gemini_key = bool(SecretStore.get("GEMINI_API_KEY"))
        eleven_key = bool(SecretStore.get("ELEVENLABS_API_KEY"))
        gemini_profiles = self.profile_service.list_for("gemini", language)
        eleven_profiles = self.profile_service.list_for("elevenlabs", language)
        self.provider_status["gemini"].setText(
            f"● {len(gemini_profiles)} voz(es)" if gemini_key and gemini_profiles else ("○ Sem API key" if not gemini_key else f"○ Sem voz para {language_name}")
        )
        self.provider_status["elevenlabs"].setText(
            f"● {len(eleven_profiles)} voz(es)" if eleven_key and eleven_profiles else ("○ Sem API key" if not eleven_key else f"○ Sem voz para {language_name}")
        )
        self.provider_status["wikimedia"].setText("● Disponível")
        self.provider_status["voicevox"].setText("○ Local" if language == "ja" else "○ Somente japonês")

    def refresh_gemini_usage(self, *_args) -> None:
        profiles = self.profile_service.load()
        models = []
        seen: set[str] = set()
        for profile in profiles:
            if profile.provider != "gemini" or not profile.enabled:
                continue
            if profile.model not in seen:
                seen.add(profile.model)
                models.append(profile.model)
        if not models:
            self.gemini_usage_label.setText("Adicione um perfil Gemini para acompanhar o uso observado por modelo.")
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
        self.gemini_usage_label.setText("Uso observado:\n" + "\n".join(lines))

    def load_project(self) -> None:
        project_id = self.project_combo.currentData()
        if project_id is None:
            self.current_project = None
            return
        self.current_project = self.database.get_project(int(project_id))
        if not self.current_project:
            return
        self._select_data(self.mode_combo, self.current_project.audio_mode)
        self._select_data(self.fixed_combo, self.current_project.fixed_audio_provider)
        if self.current_project.language != "ja" and str(self.fixed_combo.currentData()) == "voicevox":
            fallback = self.fixed_combo.findData("gemini")
            if fallback >= 0:
                self.fixed_combo.setCurrentIndex(fallback)
        for key, check in self.provider_checks.items():
            allowed = not (key == "voicevox" and self.current_project.language != "ja")
            check.setEnabled(allowed)
            check.setChecked(allowed and key in self.current_project.audio_providers)
        self._prepare_voicevox_combo()
        self._update_mode_controls()
        self._refresh_fixed_profile_combo()
        self._update_generation_state()
        self._refresh_provider_statuses()
        self.refresh_gemini_usage()

    @staticmethod
    def _select_data(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _prepare_voicevox_combo(self) -> None:
        if not self.current_project or self.current_project.language != "ja":
            self.voicevox_combo.set_items([("VOICEVOX disponível somente para Japonês", None)], None)
            self.voicevox_combo.setEnabled(False)
            self.voicevox_load_button.setEnabled(False)
            self.voicevox_test_button.setEnabled(False)
            self.voicevox_adjust_button.setEnabled(False)
            return
        self.voicevox_combo.setEnabled(True)
        self.voicevox_load_button.setEnabled(True)
        style_id = self.current_project.voicevox_style_id
        saved_label = self.current_project.voicevox_style_label.strip()
        label = saved_label or f"Estilo ID {style_id} — clique em Carregar vozes"
        self.voicevox_combo.set_items([(label, style_id)], style_id)
        self.voicevox_test_button.setEnabled(True)
        self.voicevox_adjust_button.setEnabled(True)

    def load_voicevox_styles(self) -> None:
        if not self.current_project or self.current_project.language != "ja":
            return
        url = self.database.get_setting("voicevox_url", DEFAULT_VOICEVOX_URL)
        self.voicevox_load_button.setEnabled(False)
        self.status.show_message("Carregando personagens e estilos do VOICEVOX...")
        worker = Worker(VoicevoxProvider.list_speaker_styles, url, 8.0)

        def loaded(result: object) -> None:
            self._voicevox_styles = list(result)
            if not self._voicevox_styles:
                self.status.show_message("O VOICEVOX respondeu, mas não retornou personagens/estilos.", error=True)
                return
            selected = self.current_project.voicevox_style_id if self.current_project else 0
            items = [(str(style["label"]), int(style["id"])) for style in self._voicevox_styles]
            self.voicevox_combo.set_items(items, selected)
            self._voicevox_selected(self.voicevox_combo.currentIndex())
            self.status.show_message(
                f"{len(self._voicevox_styles)} estilos do VOICEVOX carregados. "
                "Clique em qualquer parte da caixa ou digite para priorizar uma voz sem ocultar as demais."
            )

        worker.signals.result.connect(loaded)
        worker.signals.error.connect(lambda message: self.status.show_message(message, error=True))
        worker.signals.finished.connect(lambda: self.voicevox_load_button.setEnabled(True))
        self._keep_worker(worker)

    def _voicevox_selected(self, _index: int | None = None) -> None:
        if not self.current_project or self.current_project.language != "ja":
            return
        style_id = self.voicevox_combo.currentData()
        if style_id is None:
            return
        self.current_project.voicevox_style_id = int(style_id)
        text = self.voicevox_combo.currentText().strip()
        if text and not text.startswith("Estilo ID "):
            self.current_project.voicevox_style_label = text

    def test_voicevox_voice(self) -> None:
        if not self.current_project or self.current_project.language != "ja":
            return
        style_id = self.voicevox_combo.currentData()
        if style_id is None:
            QMessageBox.information(self, "Voz não carregada", "Carregue as vozes do VOICEVOX antes de testar.")
            return
        url = self.database.get_setting("voicevox_url", DEFAULT_VOICEVOX_URL)
        provider = VoicevoxProvider(
            url,
            int(style_id),
            speed_scale=self.current_project.voicevox_speed_scale,
            pitch_scale=self.current_project.voicevox_pitch_scale,
            intonation_scale=self.current_project.voicevox_intonation_scale,
            volume_scale=self.current_project.voicevox_volume_scale,
            pause_length_scale=self.current_project.voicevox_pause_length_scale,
        )
        target = self.paths.audio_dir / "voicevox_preview" / "preview"
        self.voicevox_test_button.setEnabled(False)
        worker = Worker(provider.generate, "こんにちは。音声テストです。", target)

        def open_audio(result: object) -> None:
            path = Path(result.local_path)
            self.preview_player.stop()
            self.preview_player.setSource(QUrl.fromLocalFile(str(path)))
            self.preview_player.play()
            self.status.show_message("Reproduzindo o exemplo do VOICEVOX dentro do AnkiiStudio.")

        worker.signals.result.connect(open_audio)
        worker.signals.error.connect(lambda message: self.status.show_message(message, error=True))
        worker.signals.finished.connect(lambda: self.voicevox_test_button.setEnabled(True))
        self._keep_worker(worker)

    def adjust_voicevox_voice(self) -> None:
        if not self.current_project or self.current_project.language != "ja":
            return
        dialog = VoicevoxSettingsDialog(self.current_project, self)
        if not dialog.exec():
            return
        dialog.apply_to(self.current_project)
        self._voicevox_selected(self.voicevox_combo.currentIndex())
        self.database.update_project(self.current_project)
        self.service.reset_provider_failures()
        self.status.show_message("Ajustes do VOICEVOX salvos. Use Ouvir exemplo para comparar imediatamente.")

    def _update_mode_controls(self) -> None:
        fixed = str(self.mode_combo.currentData()) == "fixed"
        self.fixed_cell.setVisible(fixed)
        self.fixed_profile_cell.setVisible(fixed and str(self.fixed_combo.currentData()) in ("gemini", "elevenlabs"))
        self._refresh_fixed_profile_combo()

    def _refresh_fixed_profile_combo(self, *_args) -> None:
        if not hasattr(self, "fixed_profile_combo"):
            return
        provider = str(self.fixed_combo.currentData() or "")
        project = self.current_project
        self.fixed_profile_combo.clear()
        if not project or provider not in ("gemini", "elevenlabs"):
            self.fixed_profile_cell.setVisible(False)
            return
        profiles = self.profile_service.list_for(provider, project.language)
        for profile in profiles:
            self.fixed_profile_combo.addItem(profile.display_name, profile.id)
        self.fixed_profile_cell.setVisible(str(self.mode_combo.currentData()) == "fixed")
        self._select_data(self.fixed_profile_combo, project.fixed_audio_profile_id)

    def _update_generation_state(self) -> None:
        enabled = bool(self.current_project and self.current_project.uses_audio)
        self.generate_button.setEnabled(enabled)
        self.generate_button.setToolTip("" if enabled else "A estrutura do projeto não utiliza Áudio.")

    def _keep_worker(self, worker: Worker) -> None:
        self._workers.append(worker)
        worker.signals.finished.connect(lambda: self._workers.remove(worker) if worker in self._workers else None)
        self.thread_pool.start(worker)

    def save_project(self) -> bool:
        if self.current_project is None:
            QMessageBox.warning(self, "Sem projeto", "Selecione um projeto para configurar áudio.")
            return False
        providers = [key for key, check in self.provider_checks.items() if check.isEnabled() and check.isChecked()]
        mode = str(self.mode_combo.currentData())
        fixed = str(self.fixed_combo.currentData())
        if mode == "fixed":
            if fixed == "voicevox" and self.current_project.language != "ja":
                QMessageBox.warning(self, "Provedor indisponível", "VOICEVOX está disponível somente para projetos em japonês.")
                return False
            if fixed not in providers:
                providers.append(fixed)
                self.provider_checks[fixed].setChecked(True)
            if fixed in ("gemini", "elevenlabs") and self.fixed_profile_combo.currentData() is None:
                QMessageBox.warning(self, "Voz ausente", "Cadastre e selecione uma voz para o provedor fixo.")
                return False
        if not providers:
            QMessageBox.warning(self, "Sem provedores", "Selecione ao menos um provedor.")
            return False

        self.current_project.audio_mode = mode
        self.current_project.fixed_audio_provider = fixed
        self.current_project.fixed_audio_profile_id = str(self.fixed_profile_combo.currentData() or "") if fixed in ("gemini", "elevenlabs") else ""
        if self.current_project.language == "ja":
            if "voicevox" in providers and self.voicevox_combo.currentData() is None:
                QMessageBox.warning(
                    self,
                    "Voz do VOICEVOX ausente",
                    "Carregue e selecione um personagem/estilo do VOICEVOX antes de salvar.",
                )
                return False
            self._voicevox_selected(self.voicevox_combo.currentIndex())
        self.current_project.audio_providers = providers
        self.database.update_project(self.current_project)
        self.status.show_message("Configuração de áudio salva.")
        self._refresh_provider_statuses()
        return True

    def generate_all(self) -> None:
        if self.current_project is None or self.current_project.id is None:
            QMessageBox.warning(self, "Sem projeto", "Selecione um projeto antes de gerar áudios.")
            return
        if not self.current_project.uses_audio:
            QMessageBox.information(self, "Áudio não utilizado", "A estrutura deste projeto não utiliza Áudio.")
            return
        if not self.save_project():
            return
        # Cada novo lote começa limpo; falhas permanentes passam a ser bloqueadas
        # somente durante a execução atual para evitar dezenas de requisições 400 idênticas.
        self.service.reset_provider_failures()
        cards = self.database.list_cards(self.current_project.id)
        if not cards:
            QMessageBox.warning(self, "Sem cartões", "Este projeto não possui cartões.")
            return
        if QMessageBox.question(
            self,
            "Gerar áudios",
            f"Gerar os áudios ausentes de {len(cards)} cartões? Serviços por API podem consumir cota.",
        ) != QMessageBox.StandardButton.Yes:
            return
        self.generate_button.setEnabled(False)
        self.progress.setValue(0)
        self.progress.show()
        self.status.show_message("Gerando áudios ausentes...")

        def run_all() -> tuple[int, int, list[str]]:
            completed = 0
            existing = 0
            errors: list[str] = []
            total = len(cards)
            for index, card in enumerate(cards, start=1):
                before_ok, _ = self.service.audio_status(self.current_project, card)
                if before_ok:
                    existing += 1
                    state = "existing"
                else:
                    try:
                        updated = self.service.generate_for_card(self.current_project, card)
                        ok, missing = self.service.audio_status(self.current_project, updated)
                        if not ok:
                            raise RuntimeError("faltam " + ", ".join(missing))
                        completed += 1
                        state = "done"
                    except Exception as exc:
                        errors.append(f"{card.word}: {exc}")
                        state = "error"
                worker.signals.progress.emit(
                    int(index * 100 / total),
                    json.dumps({"word": card.word, "state": state, "index": index, "total": total}, ensure_ascii=False),
                )
            return completed, existing, errors

        worker = Worker(run_all)
        worker.signals.progress.connect(self._generation_progress)
        worker.signals.result.connect(self.finished_generation)
        worker.signals.error.connect(lambda message: self.status.show_message(message, error=True))
        worker.signals.finished.connect(self._generation_worker_finished)
        self._keep_worker(worker)

    def _generation_progress(self, percent: int, payload: str) -> None:
        self.progress.setValue(percent)
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return
        state = data.get("state")
        state_label = {"done": "gerado", "existing": "já existente", "error": "falhou"}.get(state, state)
        self.status.show_message(
            f"Áudios: {data.get('index')}/{data.get('total')} · {data.get('word')} · {state_label}",
            error=state == "error",
        )
        self.refresh_gemini_usage()

    def _generation_worker_finished(self) -> None:
        self._update_generation_state()
        self.refresh_gemini_usage()

    def finished_generation(self, result: object) -> None:
        completed, existing, errors = result
        self.progress.setValue(100)
        if errors:
            self.status.show_message(
                f"Concluído: {completed} gerados, {existing} já existentes e {len(errors)} falharam. Primeira falha: {errors[0]}",
                error=True,
            )
        else:
            self.status.show_message(f"Concluído: {completed} gerados e {existing} já existentes.")
        self.refresh_gemini_usage()
