from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThreadPool, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QInputDialog,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ankiistudio.config import AppPaths, SecretStore
from ankiistudio.constants import (
    AUDIO_PROVIDER_LABELS,
    DEFAULT_AUDIO_PROVIDERS,
    DEFAULT_GEMINI_TEXT_MODEL,
    DEFAULT_VOICEVOX_URL,
    LANGUAGE_LABELS,
    TEMPLATE_DEFAULT_STRUCTURES,
    TEMPLATE_LABELS,
    TEMPLATES_BY_LANGUAGE,
    language_label,
)
from ankiistudio.data.japanese_seed import builtin_card_count
from ankiistudio.database import Database
from ankiistudio.i18n import current_language, language_items, tr, ui_language_to_translation_code
from ankiistudio.models import CardStructureVariation, CreationPreset, DeckThemeSettings, ProjectData
from ankiistudio.services.audio.elevenlabs import ElevenLabsProvider
from ankiistudio.services.audio.gemini_tts import GeminiTTSProvider
from ankiistudio.services.audio.voicevox import VoicevoxProvider
from ankiistudio.services.audio_preferences import (
    VoicevoxSettingsData, load_voicevox_defaults, preview_text,
)
from ankiistudio.services.audio_profile_service import AudioProfileService
from ankiistudio.services.gemini_service import GeminiContentService
from ankiistudio.services.gemini_tts_usage import GeminiTTSUsageTracker
from ankiistudio.services.project_service import ProjectService
from ankiistudio.services.theme_settings import load_default_card_theme
from ankiistudio.services.prompt_service import PromptService
from ankiistudio.ui.design_system.components import ASButton, ASComboBox, ASLineEdit
from ankiistudio.ui.dialogs.import_dialog import ImportDeckDialog
from ankiistudio.ui.dialogs.prompt_dialog import PromptDialog
from ankiistudio.ui.dialogs.voicevox_settings_dialog import VoicevoxSettingsDialog
from ankiistudio.ui.widgets import (
    ComponentOrderEditor,
    PageHeader,
    PageScrollArea,
    SearchableComboBox,
    CollapsibleSection,
    SectionCard,
    StatusBanner,
)
from ankiistudio.ui.workers import Worker


class CreatePage(QWidget):
    project_created = Signal(int)
    AUTO_CARD_LIMIT = 200
    RESPONSIVE_BREAKPOINT = 820

    MODES = {
        "builtin": (
            "Conteúdo padrão",
            "Usa a base revisada incluída no AnkiiStudio.",
        ),
        "gemini": (
            "Gemini API",
            "Gera o conteúdo diretamente pela API configurada.",
        ),
        "import": (
            "Importar de uma IA",
            "Gera um prompt estruturado e importa o JSON ou TXT resultante.",
        ),
        "manual": (
            "Projeto vazio",
            "Cria somente a estrutura para preenchimento manual.",
        ),
    }

    def __init__(self, database: Database, paths: AppPaths) -> None:
        super().__init__()
        self.database = database
        self.paths = paths
        self.project_service = ProjectService(database)
        self.audio_profile_service = AudioProfileService(database)
        self.thread_pool = QThreadPool.globalInstance()
        self.creation_mode = "import"
        self._workers: list[Worker] = []
        self._updating_templates = False
        self._compact_layout = False
        self._structure_variations: list[CardStructureVariation] = []
        self._loading_structure = False
        self._preset_card_theme: dict[str, object] | None = None
        defaults = load_voicevox_defaults(database)
        self._create_voicevox_settings = VoicevoxSettingsData(**defaults.__dict__)
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
        self.content_layout = layout
        layout.addWidget(
            PageHeader(
                "Criar projeto",
                "Configure o conteúdo e defina exatamente o que aparecerá na frente e no verso dos cartões.",
            )
        )
        self.status = StatusBanner()
        layout.addWidget(self.status)

        self.preset_card = SectionCard("Preset de criação")
        preset_card = self.preset_card
        preset_card.root.setContentsMargins(18, 13, 18, 13)
        preset_card.root.setSpacing(8)
        self.preset_grid = QGridLayout()
        self.preset_grid.setHorizontalSpacing(8)
        self.preset_grid.setVerticalSpacing(8)
        self.preset_combo = ASComboBox()
        self.preset_combo.addItem("Nenhum preset", None)
        self.preset_combo.setToolTip(
            "Reutilize configurações de criação sem salvar credenciais ou chaves de API."
        )
        self.preset_combo.currentIndexChanged.connect(self._preset_selected)
        self.save_preset_button = ASButton("Salvar como preset")
        self.delete_preset_button = ASButton("Excluir preset")
        self.save_preset_button.setObjectName("SubtleButton")
        self.delete_preset_button.setObjectName("DangerButton")
        self.save_preset_button.clicked.connect(self.save_creation_preset)
        self.delete_preset_button.clicked.connect(self.delete_creation_preset)
        for widget in (self.preset_combo, self.save_preset_button, self.delete_preset_button):
            self.preset_grid.addWidget(widget, 0, 0)
        preset_card.root.addLayout(self.preset_grid)
        layout.addWidget(preset_card)

        content_card = CollapsibleSection(
            "1. Conteúdo",
            "Defina o projeto, os idiomas, o modelo e o conteúdo que será usado.",
        )
        self.content_grid = QGridLayout()
        self.content_grid.setHorizontalSpacing(14)
        self.content_grid.setVerticalSpacing(8)

        self.name_input = ASLineEdit()
        self.name_input.setPlaceholderText("Ex.: Frases para viagem")
        self.language_combo = SearchableComboBox()
        self.language_combo._i18n_skip_items = True
        self.language_combo.set_items(language_items(), "ja")
        self.language_combo.lineEdit().setPlaceholderText("Selecione ou pesquise um idioma")
        self.translation_language_combo = SearchableComboBox()
        self.translation_language_combo._i18n_skip_items = True
        default_translation_language = ui_language_to_translation_code(current_language())
        self.translation_language_combo.set_items(language_items(), default_translation_language)
        self.translation_language_combo.lineEdit().setPlaceholderText("Selecione ou pesquise o idioma da tradução")
        self.template_combo = SearchableComboBox()
        self.template_combo.lineEdit().setPlaceholderText("Selecione ou pesquise um modelo")

        self.custom_content_input = ASLineEdit()
        self.custom_content_input.setPlaceholderText(
            "Ex.: Kanjis avançados, verbos formais, expressões de viagem"
        )
        self.topic_input = ASLineEdit()
        self.topic_input.setPlaceholderText("Ex.: Restaurante, trabalho, situações cotidianas")
        self.quantity_spin = QSpinBox()
        self.quantity_spin.setRange(1, 5000)
        self.quantity_spin.setValue(30)
        self.quantity_mode_combo = ASComboBox()
        self.quantity_mode_combo.addItem("Definida", "fixed")
        self.quantity_mode_combo.addItem("Automática — a IA decide", "automatic")
        self.quantity_mode_combo.currentIndexChanged.connect(self._quantity_mode_changed)
        quantity_widget = QWidget()
        quantity_layout = QHBoxLayout(quantity_widget)
        quantity_layout.setContentsMargins(0, 0, 0, 0)
        quantity_layout.setSpacing(8)
        quantity_layout.addWidget(self.quantity_mode_combo, 1)
        quantity_layout.addWidget(self.quantity_spin)

        self.name_cell = self._field_cell("Nome do projeto", self.name_input)
        self.language_cell = self._field_cell("Idioma", self.language_combo)
        self.translation_language_cell = self._field_cell("Idioma da tradução", self.translation_language_combo)
        self.template_cell = self._field_cell("Modelo", self.template_combo)
        self.custom_content_cell = self._field_cell(
            "Conteúdos personalizados",
            self.custom_content_input,
            "Separe conteúdos diferentes por vírgulas; cada item será tratado como requisito de estudo.",
        )
        self.topic_cell = self._field_cell(
            "Tema / contexto (opcional)",
            self.topic_input,
            "Refina o assunto ou a situação usada na geração do modelo Personalizado.",
        )
        self.quantity_cell = self._field_cell("Quantidade de cartões", quantity_widget, "No modo Automática, a IA escolhe uma quantidade adequada, limitada a 200 cartões.")
        for cell in (
            self.name_cell,
            self.language_cell,
            self.translation_language_cell,
            self.template_cell,
            self.custom_content_cell,
            self.topic_cell,
            self.quantity_cell,
        ):
            self.content_grid.addWidget(cell, 0, 0)
        content_card.root.addLayout(self.content_grid)
        layout.addWidget(content_card)

        mode_card = CollapsibleSection(
            "2. Como criar",
            "Escolha de onde virá o conteúdo do projeto.",
        )
        self.mode_grid = QGridLayout()
        self.mode_grid.setSpacing(10)
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.mode_buttons: dict[str, QPushButton] = {}
        for key, (title, description) in self.MODES.items():
            button = ASButton(f"{title}\n{description}")
            button.setObjectName("ModeButton")
            button.setCheckable(True)
            button.clicked.connect(
                lambda checked=False, value=key: self.set_creation_mode(value)
            )
            self.mode_group.addButton(button)
            self.mode_buttons[key] = button
            self.mode_grid.addWidget(button, 0, 0)
        mode_card.root.addLayout(self.mode_grid)
        layout.addWidget(mode_card)

        media_card = CollapsibleSection(
            "3. Mídias e áudio",
            "Defina como o áudio será gerado. Perfis e credenciais continuam em Configurações.",
            expanded=False,
        )
        audio_grid = QGridLayout()
        audio_grid.setHorizontalSpacing(10)
        audio_grid.setVerticalSpacing(8)
        self.audio_mode_combo = ASComboBox()
        self.audio_mode_combo.addItem("Seleção inteligente — recomendada", "intelligent")
        self.audio_mode_combo.addItem("Somente um provedor fixo", "fixed")
        self.audio_mode_combo.addItem("Alternância aleatória", "random")
        self.audio_mode_combo.currentIndexChanged.connect(self._update_audio_creation_controls)
        self.fixed_audio_provider_combo = ASComboBox()
        for key, label in AUDIO_PROVIDER_LABELS.items():
            self.fixed_audio_provider_combo.addItem(label, key)
        self.fixed_audio_provider_combo.currentIndexChanged.connect(self._refresh_creation_audio_profiles)
        self.fixed_audio_profile_combo = ASComboBox()
        audio_grid.addWidget(QLabel("Modo"), 0, 0)
        audio_grid.addWidget(self.audio_mode_combo, 0, 1)
        audio_grid.addWidget(QLabel("Provedor fixo"), 1, 0)
        audio_grid.addWidget(self.fixed_audio_provider_combo, 1, 1)
        audio_grid.addWidget(QLabel("Voz fixa"), 2, 0)
        audio_grid.addWidget(self.fixed_audio_profile_combo, 2, 1)
        media_card.root.addLayout(audio_grid)
        providers_label = QLabel("Provedores permitidos")
        providers_label.setObjectName("FieldLabel")
        media_card.root.addWidget(providers_label)
        self.audio_provider_checks: dict[str, QCheckBox] = {}
        provider_row = QGridLayout()
        for index, (key, label) in enumerate(AUDIO_PROVIDER_LABELS.items()):
            check = QCheckBox(label)
            check.setChecked(key in DEFAULT_AUDIO_PROVIDERS)
            self.audio_provider_checks[key] = check
            provider_row.addWidget(check, index // 2, index % 2)
        media_card.root.addLayout(provider_row)

        self.audio_advanced_section = CollapsibleSection(
            "Avançado",
            "Escolha vozes específicas, ouça exemplos e ajuste o VOICEVOX. Essas preferências podem ser salvas em presets.",
            expanded=False,
        )
        self.create_voicevox_card = SectionCard("VOICEVOX", "Voz e ajustes usados neste novo projeto.")
        self.create_voicevox_combo = SearchableComboBox()
        self.create_voicevox_combo.lineEdit().setPlaceholderText("Carregue ou pesquise personagem/estilo")
        self.create_voicevox_card.root.addWidget(self.create_voicevox_combo)
        vv_actions = QHBoxLayout()
        self.create_voicevox_load_button = ASButton("Carregar vozes")
        self.create_voicevox_adjust_button = ASButton("Ajustar voz")
        self.create_voicevox_preview_button = ASButton("▶ Ouvir exemplo")
        for button in (self.create_voicevox_load_button, self.create_voicevox_adjust_button, self.create_voicevox_preview_button):
            button.setObjectName("SubtleButton")
        self.create_voicevox_load_button.clicked.connect(self._load_create_voicevox_styles)
        self.create_voicevox_adjust_button.clicked.connect(self._adjust_create_voicevox)
        self.create_voicevox_preview_button.clicked.connect(self._preview_create_voicevox)
        vv_actions.addWidget(self.create_voicevox_load_button)
        vv_actions.addWidget(self.create_voicevox_adjust_button)
        vv_actions.addWidget(self.create_voicevox_preview_button)
        vv_actions.addStretch(1)
        self.create_voicevox_card.root.addLayout(vv_actions)
        self.audio_advanced_section.root.addWidget(self.create_voicevox_card)

        self.preferred_profile_combos: dict[str, QComboBox] = {}
        self.preferred_profile_preview_buttons: dict[str, QPushButton] = {}
        for provider, title in (("gemini", "Gemini TTS"), ("elevenlabs", "ElevenLabs")):
            profile_card = SectionCard(title, "Opcional: escolha uma voz preferida para este provedor. Sem seleção, o AnkiiStudio usa os perfis habilitados do idioma.")
            combo = ASComboBox()
            preview_button = ASButton("▶ Ouvir selecionada")
            preview_button.setObjectName("SubtleButton")
            preview_button.clicked.connect(lambda _=False, p=provider: self._preview_create_profile(p))
            profile_card.root.addWidget(combo)
            profile_card.root.addWidget(preview_button)
            self.preferred_profile_combos[provider] = combo
            self.preferred_profile_preview_buttons[provider] = preview_button
            self.audio_advanced_section.root.addWidget(profile_card)

        media_card.root.addWidget(self.audio_advanced_section)
        layout.addWidget(media_card)

        structure_card = CollapsibleSection(
            "4. Estrutura do cartão",
            "Defina frente e verso e, se necessário, crie variações de estrutura.",
        )
        self.structure_controls = QGridLayout()
        self.structure_controls.setHorizontalSpacing(8)
        self.structure_controls.setVerticalSpacing(6)
        self.structure_selector = ASComboBox()
        self.structure_name_input = ASLineEdit()
        self.structure_name_input.setPlaceholderText("Nome da variação")
        self.add_structure_button = ASButton("+ Adicionar variação")
        self.remove_structure_button = ASButton("Remover variação")
        self.add_structure_button.setObjectName("SubtleButton")
        self.remove_structure_button.setObjectName("SubtleButton")
        self.structure_variation_label = QLabel("Variação")
        self.structure_name_label = QLabel("Nome")
        for label in (self.structure_variation_label, self.structure_name_label):
            label.setObjectName("FieldLabel")
        for widget in (
            self.structure_variation_label, self.structure_selector, self.add_structure_button,
            self.structure_name_label, self.structure_name_input, self.remove_structure_button,
        ):
            self.structure_controls.addWidget(widget, 0, 0)
        structure_card.root.addLayout(self.structure_controls)

        structure_hint = QLabel(
            "Com duas ou mais variações, os cartões são distribuídos aleatoriamente de forma equilibrada entre as estruturas."
        )
        structure_hint.setObjectName("MutedLabel")
        structure_hint.setWordWrap(True)
        structure_card.root.addWidget(structure_hint)

        self.structure_grid = QGridLayout()
        self.structure_grid.setHorizontalSpacing(12)
        self.structure_grid.setVerticalSpacing(12)
        self.front_editor = ComponentOrderEditor("Frente", [])
        self.back_editor = ComponentOrderEditor("Verso", [])
        self.structure_grid.addWidget(self.front_editor, 0, 0)
        self.structure_grid.addWidget(self.back_editor, 0, 1)
        structure_card.root.addLayout(self.structure_grid)
        layout.addWidget(structure_card)

        self.structure_selector.currentIndexChanged.connect(self._structure_selected)
        self.structure_name_input.editingFinished.connect(self._save_current_structure)
        self.front_editor.changed.connect(self._save_current_structure)
        self.back_editor.changed.connect(self._save_current_structure)
        self.add_structure_button.clicked.connect(self._add_structure_variation)
        self.remove_structure_button.clicked.connect(self._remove_structure_variation)

        actions = QHBoxLayout()
        actions.setContentsMargins(24, 10, 24, 10)
        actions.setSpacing(8)
        self.prompt_button = ASButton("Gerar prompt para a IA")
        self.prompt_button.setObjectName("SubtleButton")
        self.create_button = ASButton("Criar projeto")
        self.create_button.setObjectName("PrimaryButton")
        self.prompt_button.clicked.connect(self.show_prompt)
        self.create_button.clicked.connect(self.create_project)
        actions.addWidget(self.prompt_button)
        actions.addStretch(1)
        actions.addWidget(self.create_button)
        self.page_scroll = PageScrollArea(content)
        self.page_scroll.viewport_resized.connect(lambda _width: self._apply_responsive_layout())
        root.addWidget(self.page_scroll, 1)

        self.action_bar = QFrame()
        self.action_bar.setObjectName("CreateActionBar")
        self.action_bar.setLayout(actions)
        root.addWidget(self.action_bar)

        self.language_combo.currentIndexChanged.connect(self._language_changed)
        self.template_combo.currentIndexChanged.connect(self._template_changed)
        self._language_changed()
        self._refresh_presets()
        self._quantity_mode_changed()
        self._refresh_creation_audio_profiles()
        self._refresh_advanced_audio_profiles()
        self._prepare_create_voicevox_default()
        self._update_audio_creation_controls()
        self._apply_responsive_layout(force=True)

    @staticmethod
    def _field_cell(label: str, widget: QWidget, help_text: str = "") -> QWidget:
        cell = QWidget()
        cell_layout = QVBoxLayout(cell)
        cell_layout.setContentsMargins(0, 0, 0, 0)
        cell_layout.setSpacing(5)
        label_widget = QLabel(label)
        label_widget.setObjectName("FieldLabel")
        cell_layout.addWidget(label_widget)
        cell_layout.addWidget(widget)
        if help_text:
            helper = QLabel(help_text)
            helper.setObjectName("MutedLabel")
            helper.setWordWrap(True)
            cell_layout.addWidget(helper)
        return cell

    @staticmethod
    def _parse_custom_content(value: str) -> list[str]:
        items: list[str] = []
        seen: set[str] = set()
        for raw_item in value.split(","):
            item = raw_item.strip()
            if not item:
                continue
            normalized = item.casefold()
            if normalized in seen:
                continue
            seen.add(normalized)
            items.append(item)
        return items

    def _refresh_structure_selector(self, current_index: int = 0) -> None:
        self.structure_selector.blockSignals(True)
        self.structure_selector.clear()
        for index, variation in enumerate(self._structure_variations, start=1):
            self.structure_selector.addItem(f"{index}. {variation.name}", variation.key)
        if self._structure_variations:
            self.structure_selector.setCurrentIndex(max(0, min(current_index, len(self._structure_variations) - 1)))
        self.structure_selector.blockSignals(False)
        self.remove_structure_button.setEnabled(len(self._structure_variations) > 1)

    def _reset_structure_variations(self, front: list[str], back: list[str]) -> None:
        self._loading_structure = True
        self._structure_variations = [
            CardStructureVariation(name="Variação 1", front_components=front, back_components=back)
        ]
        self._refresh_structure_selector(0)
        self.structure_name_input.setText(self._structure_variations[0].name)
        self.front_editor.set_components(front)
        self.back_editor.set_components(back)
        self._loading_structure = False

    def _save_current_structure(self) -> None:
        if self._loading_structure or not self._structure_variations:
            return
        index = self.structure_selector.currentIndex()
        if index < 0 or index >= len(self._structure_variations):
            return
        name = self.structure_name_input.text().strip() or f"Variação {index + 1}"
        self._structure_variations[index] = self._structure_variations[index].model_copy(
            update={
                "name": name,
                "front_components": self.front_editor.components(),
                "back_components": self.back_editor.components(),
            }
        )
        self.structure_selector.setItemText(index, f"{index + 1}. {name}")

    def _structure_selected(self, index: int) -> None:
        if self._loading_structure or index < 0 or index >= len(self._structure_variations):
            return
        self._loading_structure = True
        variation = self._structure_variations[index]
        self.structure_name_input.setText(variation.name)
        self.front_editor.set_components(list(variation.front_components))
        self.back_editor.set_components(list(variation.back_components))
        self._loading_structure = False

    def _add_structure_variation(self) -> None:
        self._save_current_structure()
        if self._structure_variations:
            base = self._structure_variations[max(0, self.structure_selector.currentIndex())]
            variation = CardStructureVariation(
                name=f"Variação {len(self._structure_variations) + 1}",
                front_components=list(base.front_components),
                back_components=list(base.back_components),
            )
        else:
            variation = CardStructureVariation(
                name="Variação 1", front_components=["word"], back_components=["translation"]
            )
        self._structure_variations.append(variation)
        index = len(self._structure_variations) - 1
        self._refresh_structure_selector(index)
        self._structure_selected(index)

    def _remove_structure_variation(self) -> None:
        if len(self._structure_variations) <= 1:
            return
        index = self.structure_selector.currentIndex()
        if index < 0:
            return
        self._structure_variations.pop(index)
        target = min(index, len(self._structure_variations) - 1)
        self._refresh_structure_selector(target)
        self._structure_selected(target)

    def _responsive_content_width(self) -> int:
        """Largura realmente utilizável dentro dos cards principais.

        O breakpoint é aplicado sobre o viewport do scroll, descontando as
        margens externas da página e o padding horizontal dos SectionCard.
        Isso evita a faixa em que a página parecia larga o suficiente, mas os
        controles ainda eram cortados na lateral direita.
        """
        viewport_width = self.page_scroll.viewport().width()
        if viewport_width <= 0:
            viewport_width = self.width()
        margins = self.content_layout.contentsMargins()
        card_margins = self.preset_card.root.contentsMargins()
        return max(
            0,
            viewport_width
            - margins.left()
            - margins.right()
            - card_margins.left()
            - card_margins.right(),
        )

    def _apply_responsive_layout(self, force: bool = False) -> None:
        compact = self._responsive_content_width() < self.RESPONSIVE_BREAKPOINT
        if not force and compact == self._compact_layout:
            return
        self._compact_layout = compact

        for widget in (self.preset_combo, self.save_preset_button, self.delete_preset_button):
            self.preset_grid.removeWidget(widget)
        if compact:
            self.preset_grid.addWidget(self.preset_combo, 0, 0, 1, 2)
            self.preset_grid.addWidget(self.save_preset_button, 1, 0)
            self.preset_grid.addWidget(self.delete_preset_button, 1, 1)
        else:
            self.preset_grid.addWidget(self.preset_combo, 0, 0)
            self.preset_grid.addWidget(self.save_preset_button, 0, 1)
            self.preset_grid.addWidget(self.delete_preset_button, 0, 2)
            self.preset_grid.setColumnStretch(0, 1)

        for widget in (
            self.structure_variation_label, self.structure_selector, self.add_structure_button,
            self.structure_name_label, self.structure_name_input, self.remove_structure_button,
        ):
            self.structure_controls.removeWidget(widget)
        if compact:
            self.structure_controls.addWidget(self.structure_variation_label, 0, 0, 1, 2)
            self.structure_controls.addWidget(self.structure_selector, 1, 0, 1, 2)
            self.structure_controls.addWidget(self.structure_name_label, 2, 0, 1, 2)
            self.structure_controls.addWidget(self.structure_name_input, 3, 0, 1, 2)
            self.structure_controls.addWidget(self.add_structure_button, 4, 0)
            self.structure_controls.addWidget(self.remove_structure_button, 4, 1)
        else:
            self.structure_controls.addWidget(self.structure_variation_label, 0, 0)
            self.structure_controls.addWidget(self.structure_selector, 0, 1)
            self.structure_controls.addWidget(self.add_structure_button, 0, 2)
            self.structure_controls.addWidget(self.structure_name_label, 1, 0)
            self.structure_controls.addWidget(self.structure_name_input, 1, 1)
            self.structure_controls.addWidget(self.remove_structure_button, 1, 2)
            self.structure_controls.setColumnStretch(1, 1)

        for cell in (
            self.name_cell,
            self.language_cell,
            self.translation_language_cell,
            self.template_cell,
            self.custom_content_cell,
            self.topic_cell,
            self.quantity_cell,
        ):
            self.content_grid.removeWidget(cell)

        if compact:
            self.content_grid.addWidget(self.name_cell, 0, 0)
            self.content_grid.addWidget(self.language_cell, 1, 0)
            self.content_grid.addWidget(self.translation_language_cell, 2, 0)
            self.content_grid.addWidget(self.template_cell, 3, 0)
            self.content_grid.addWidget(self.custom_content_cell, 4, 0)
            self.content_grid.addWidget(self.topic_cell, 5, 0)
            self.content_grid.addWidget(self.quantity_cell, 6, 0)
        else:
            self.content_grid.addWidget(self.name_cell, 0, 0, 1, 2)
            self.content_grid.addWidget(self.language_cell, 1, 0)
            self.content_grid.addWidget(self.translation_language_cell, 1, 1)
            self.content_grid.addWidget(self.template_cell, 2, 0, 1, 2)
            self.content_grid.addWidget(self.custom_content_cell, 3, 0, 1, 2)
            self.content_grid.addWidget(self.topic_cell, 4, 0)
            self.content_grid.addWidget(self.quantity_cell, 4, 1)

        for button in self.mode_buttons.values():
            self.mode_grid.removeWidget(button)
        for index, key in enumerate(self.MODES):
            if compact:
                self.mode_grid.addWidget(self.mode_buttons[key], index, 0)
            else:
                self.mode_grid.addWidget(self.mode_buttons[key], index // 2, index % 2)

        self.structure_grid.removeWidget(self.front_editor)
        self.structure_grid.removeWidget(self.back_editor)
        if compact:
            self.structure_grid.addWidget(self.front_editor, 0, 0)
            self.structure_grid.addWidget(self.back_editor, 1, 0)
        else:
            self.structure_grid.addWidget(self.front_editor, 0, 0)
            self.structure_grid.addWidget(self.back_editor, 0, 1)

    def retranslate_ui(self) -> None:
        selected_language = str(self.language_combo.currentData() or "ja")
        selected_translation = str(self.translation_language_combo.currentData() or "pt")

        self.language_combo.blockSignals(True)
        self.translation_language_combo.blockSignals(True)
        try:
            self.language_combo.set_items(language_items(), selected_language)
            self.translation_language_combo.set_items(language_items(), selected_translation)
        finally:
            self.language_combo.blockSignals(False)
            self.translation_language_combo.blockSignals(False)

        for index in range(self.template_combo.count()):
            key = str(self.template_combo.itemData(index) or "")
            if key in TEMPLATE_LABELS:
                self.template_combo.setItemText(index, tr(TEMPLATE_LABELS[key]))
        refresh = getattr(self.template_combo, "refresh_search_source", None)
        if callable(refresh):
            refresh()

    def _language_changed(self, _index: int | None = None) -> None:
        language_data = self.language_combo.currentData()
        if language_data is None:
            return
        language = str(language_data)
        self._updating_templates = True
        items = [
            (tr(TEMPLATE_LABELS[key]), key)
            for key in TEMPLATES_BY_LANGUAGE.get(language, ["custom"])
        ]
        self.template_combo.blockSignals(True)
        self.template_combo.set_items(items, "custom")
        self.template_combo.blockSignals(False)
        self._updating_templates = False
        self._template_changed()
        self._refresh_creation_audio_profiles()
        self._refresh_advanced_audio_profiles()
        self._prepare_create_voicevox_default()

    def _template_changed(self, _index: int | None = None) -> None:
        if self._updating_templates:
            return
        template_key = str(self.template_combo.currentData() or "custom")
        is_custom = template_key == "custom"
        is_standard = not is_custom and str(self.language_combo.currentData()) == "ja"
        self.custom_content_cell.setVisible(is_custom)

        front, back = TEMPLATE_DEFAULT_STRUCTURES.get(
            template_key, TEMPLATE_DEFAULT_STRUCTURES["custom"]
        )
        self._reset_structure_variations(list(front), list(back))

        self.topic_input.setEnabled(is_custom)
        self.quantity_mode_combo.setEnabled(is_custom)
        self.quantity_spin.setEnabled(is_custom and str(self.quantity_mode_combo.currentData() or "fixed") == "fixed")
        if is_standard:
            self.quantity_mode_combo.setCurrentIndex(self.quantity_mode_combo.findData("fixed"))
            self.topic_input.clear()
            self.quantity_spin.setValue(max(1, builtin_card_count(template_key)))
            self.set_creation_mode("builtin")
        elif self.creation_mode == "builtin":
            self.set_creation_mode("import")
        else:
            self.set_creation_mode(self.creation_mode)

        for key, button in self.mode_buttons.items():
            if is_standard:
                button.setEnabled(key == "builtin")
            else:
                button.setEnabled(key != "builtin")
        self.mode_buttons["builtin"].setToolTip(
            "" if is_standard else "Conteúdo padrão está disponível apenas nos modelos padrão de Japonês."
        )

    def set_creation_mode(self, mode: str) -> None:
        template_key = str(self.template_combo.currentData() or "custom")
        is_standard = (
            str(self.language_combo.currentData() or "ja") == "ja"
            and template_key != "custom"
        )
        if is_standard:
            mode = "builtin"
        elif mode == "builtin" or mode not in self.MODES:
            mode = "import"
        self.creation_mode = mode
        for key, button in self.mode_buttons.items():
            button.setChecked(key == mode)
        self.prompt_button.setVisible(mode == "import")
        self.create_button.setText(
            tr("Importar e criar projeto") if mode == "import" else tr("Criar projeto")
        )
        self._quantity_mode_changed()

    def _update_audio_creation_controls(self, *_args) -> None:
        fixed = str(self.audio_mode_combo.currentData() or "") == "fixed"
        self.fixed_audio_provider_combo.setEnabled(fixed)
        provider = str(self.fixed_audio_provider_combo.currentData() or "")
        self.fixed_audio_profile_combo.setEnabled(fixed and provider in {"gemini", "elevenlabs"})

    def _refresh_creation_audio_profiles(self, *_args) -> None:
        if not hasattr(self, "fixed_audio_profile_combo"):
            return
        previous = self.fixed_audio_profile_combo.currentData()
        self.fixed_audio_profile_combo.clear()
        provider = str(self.fixed_audio_provider_combo.currentData() or "")
        language = str(self.language_combo.currentData() or "ja")
        voicevox_check = self.audio_provider_checks.get("voicevox")
        if voicevox_check is not None:
            voicevox_check.setEnabled(language == "ja")
            if language != "ja":
                voicevox_check.setChecked(False)
        if provider in {"gemini", "elevenlabs"}:
            for profile in self.audio_profile_service.list_for(provider, language):
                self.fixed_audio_profile_combo.addItem(profile.display_name, profile.id)
            preferred_combo = getattr(self, "preferred_profile_combos", {}).get(provider)
            preferred = preferred_combo.currentData() if preferred_combo is not None else None
            target = previous or preferred
            if target:
                idx = self.fixed_audio_profile_combo.findData(target)
                if idx >= 0:
                    self.fixed_audio_profile_combo.setCurrentIndex(idx)
        self._update_audio_creation_controls()

    def _refresh_advanced_audio_profiles(self) -> None:
        if not hasattr(self, "preferred_profile_combos"):
            return
        language = str(self.language_combo.currentData() or "ja")
        for provider, combo in self.preferred_profile_combos.items():
            previous = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("Automática — usar perfis habilitados", "")
            for profile in self.audio_profile_service.list_for(provider, language):
                combo.addItem(profile.display_name, profile.id)
            if previous:
                index = combo.findData(previous)
                if index >= 0:
                    combo.setCurrentIndex(index)
            combo.blockSignals(False)
        if hasattr(self, "create_voicevox_card"):
            self.create_voicevox_card.setVisible(language == "ja")

    def _prepare_create_voicevox_default(self) -> None:
        if not hasattr(self, "create_voicevox_combo"):
            return
        language = str(self.language_combo.currentData() or "ja")
        enabled = language == "ja"
        self.create_voicevox_card.setVisible(enabled)
        if not enabled:
            return
        label = self._create_voicevox_settings.style_label or f"Estilo ID {self._create_voicevox_settings.style_id} — carregue para atualizar"
        self.create_voicevox_combo.set_items([(label, self._create_voicevox_settings.style_id)], self._create_voicevox_settings.style_id)

    def refresh_audio_options(self) -> None:
        if self.preset_combo.currentData() is None:
            defaults = load_voicevox_defaults(self.database)
            self._create_voicevox_settings = VoicevoxSettingsData(**defaults.__dict__)
        self._refresh_creation_audio_profiles()
        self._refresh_advanced_audio_profiles()
        self._prepare_create_voicevox_default()

    def _play_audio_preview(self, result: object, message: str) -> None:
        local_path = getattr(result, "local_path", "")
        path = Path(str(local_path))
        if not path.is_file() or path.stat().st_size <= 0:
            self.status.show_message("O provedor não retornou um arquivo de áudio válido.", error=True)
            return
        self.preview_player.stop()
        self.preview_player.setSource(QUrl.fromLocalFile(str(path)))
        self.preview_player.play()
        self.status.show_message(message)

    def _load_create_voicevox_styles(self) -> None:
        if str(self.language_combo.currentData() or "ja") != "ja":
            return
        url = self.database.get_setting("voicevox_url", DEFAULT_VOICEVOX_URL)
        self.create_voicevox_load_button.setEnabled(False)
        self.status.show_message("Carregando vozes do VOICEVOX...")
        worker = Worker(VoicevoxProvider.list_speaker_styles, url, 8.0)

        def loaded(result: object) -> None:
            items = [(str(item["label"]), int(item["id"])) for item in list(result)]
            self.create_voicevox_combo.set_items(items, self._create_voicevox_settings.style_id)
            self.status.show_message(f"{len(items)} estilos do VOICEVOX carregados.")

        worker.signals.result.connect(loaded)
        worker.signals.error.connect(lambda message: self.status.show_message(message, error=True))
        worker.signals.finished.connect(lambda: self.create_voicevox_load_button.setEnabled(True))
        self._keep_worker(worker)

    def _adjust_create_voicevox(self) -> None:
        if self.create_voicevox_combo.currentData() is not None:
            self._create_voicevox_settings.style_id = int(self.create_voicevox_combo.currentData())
            self._create_voicevox_settings.style_label = self.create_voicevox_combo.currentText().strip()
        dialog = VoicevoxSettingsDialog(self._create_voicevox_settings, self)
        if dialog.exec():
            dialog.apply_to(self._create_voicevox_settings)
            self.status.show_message("Ajustes do VOICEVOX aplicados a esta criação.")

    def _preview_create_voicevox(self) -> None:
        style_id = self.create_voicevox_combo.currentData()
        if style_id is None:
            QMessageBox.information(self, "Voz não carregada", "Carregue as vozes do VOICEVOX antes de testar.")
            return
        url = self.database.get_setting("voicevox_url", DEFAULT_VOICEVOX_URL)
        provider = VoicevoxProvider(
            url, int(style_id),
            speed_scale=self._create_voicevox_settings.speed_scale,
            pitch_scale=self._create_voicevox_settings.pitch_scale,
            intonation_scale=self._create_voicevox_settings.intonation_scale,
            volume_scale=self._create_voicevox_settings.volume_scale,
            pause_length_scale=self._create_voicevox_settings.pause_length_scale,
        )
        target = self.paths.audio_dir / "voice_preview" / "create_voicevox"
        self.create_voicevox_preview_button.setEnabled(False)
        worker = Worker(provider.generate, preview_text("ja"), target)
        worker.signals.result.connect(lambda result: self._play_audio_preview(result, "Reproduzindo exemplo do VOICEVOX."))
        worker.signals.error.connect(lambda message: self.status.show_message(message, error=True))
        worker.signals.finished.connect(lambda: self.create_voicevox_preview_button.setEnabled(True))
        self._keep_worker(worker)

    def _preview_create_profile(self, provider: str) -> None:
        combo = self.preferred_profile_combos.get(provider)
        profile_id = str(combo.currentData() or "") if combo is not None else ""
        if not profile_id:
            QMessageBox.information(self, "Selecione uma voz", "Selecione uma voz específica antes de ouvir o exemplo.")
            return
        profile = self.audio_profile_service.get(profile_id)
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
                SecretStore.get("ELEVENLABS_API_KEY"), profile.voice, profile.model,
                language=profile.language, stability=profile.stability, similarity_boost=profile.similarity_boost,
                style=profile.style, speed=profile.speed, speaker_boost=profile.speaker_boost,
            )
        target = self.paths.audio_dir / "voice_preview" / f"create_{provider}_{profile.id}"
        button = self.preferred_profile_preview_buttons[provider]
        button.setEnabled(False)
        worker = Worker(engine.generate, preview_text(profile.language), target)
        worker.signals.result.connect(lambda result: self._play_audio_preview(result, f"Reproduzindo {profile.name}."))
        worker.signals.error.connect(lambda message: self.status.show_message(message, error=True))
        worker.signals.finished.connect(lambda: button.setEnabled(True))
        self._keep_worker(worker)

    def _requested_quantity(self) -> int | None:
        template_key = str(self.template_combo.currentData() or "custom")
        if template_key != "custom":
            return self.quantity_spin.value()
        mode = str(self.quantity_mode_combo.currentData() or "fixed")
        if mode == "automatic" and self.creation_mode in {"gemini", "import"}:
            return None
        return self.quantity_spin.value()

    def _quantity_mode_changed(self, *_args) -> None:
        template_key = str(self.template_combo.currentData() or "custom")
        automatic = str(self.quantity_mode_combo.currentData() or "fixed") == "automatic"
        supported = template_key == "custom" and self.creation_mode in {"gemini", "import"}
        self.quantity_spin.setVisible(not (automatic and supported))
        self.quantity_spin.setEnabled(template_key == "custom" and not automatic)
        self.quantity_mode_combo.setToolTip(
            "A IA decide a quantidade com limite de 200 cartões." if supported else
            "Quantidade automática está disponível para geração/importação por IA no modelo Personalizado."
        )

    def _refresh_presets(self, selected_id: int | None = None) -> None:
        previous = self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        self.preset_combo.addItem("Nenhum preset", None)
        for preset in self.database.list_creation_presets():
            self.preset_combo.addItem(preset.name, preset.id)
        if selected_id is not None:
            index = self.preset_combo.findData(selected_id)
            if index >= 0:
                self.preset_combo.setCurrentIndex(index)
        self.preset_combo.blockSignals(previous)
        self.delete_preset_button.setEnabled(self.preset_combo.currentData() is not None)

    def _preset_payload(self) -> dict[str, object]:
        self._save_current_structure()
        return {
            "language": self.language_combo.currentData(),
            "translation_language": self.translation_language_combo.currentData(),
            "template_key": self.template_combo.currentData(),
            "custom_content": self.custom_content_input.text(),
            "topic": self.topic_input.text(),
            "quantity_mode": self.quantity_mode_combo.currentData(),
            "quantity": self.quantity_spin.value(),
            "creation_mode": self.creation_mode,
            "audio_mode": self.audio_mode_combo.currentData(),
            "audio_providers": [key for key, check in self.audio_provider_checks.items() if check.isChecked()],
            "fixed_audio_provider": self.fixed_audio_provider_combo.currentData(),
            "fixed_audio_profile_id": self.fixed_audio_profile_combo.currentData() or "",
            "audio_profile_preferences": {provider: str(combo.currentData() or "") for provider, combo in self.preferred_profile_combos.items() if combo.currentData()},
            "voicevox_style_id": int(self.create_voicevox_combo.currentData() if self.create_voicevox_combo.currentData() is not None else self._create_voicevox_settings.style_id),
            "voicevox_style_label": self.create_voicevox_combo.currentText().strip() or self._create_voicevox_settings.style_label,
            "voicevox_speed_scale": self._create_voicevox_settings.speed_scale,
            "voicevox_pitch_scale": self._create_voicevox_settings.pitch_scale,
            "voicevox_intonation_scale": self._create_voicevox_settings.intonation_scale,
            "voicevox_volume_scale": self._create_voicevox_settings.volume_scale,
            "voicevox_pause_length_scale": self._create_voicevox_settings.pause_length_scale,
            "card_theme": (
                DeckThemeSettings.model_validate(self._preset_card_theme)
                if self._preset_card_theme is not None
                else load_default_card_theme(self.database)
            ).model_dump(),
            "card_structures": [item.model_dump() for item in self._structure_variations],
        }

    def save_creation_preset(self) -> None:
        name, ok = QInputDialog.getText(self, "Salvar preset", "Nome do preset")
        name = name.strip()
        if not ok or not name:
            return
        try:
            preset = CreationPreset(name=name, payload=self._preset_payload())
            preset_id = self.database.save_creation_preset(preset)
        except Exception as exc:
            QMessageBox.warning(self, "Não foi possível salvar o preset", str(exc))
            return
        self._refresh_presets(preset_id)
        self.status.show_message("Preset salvo.")

    def delete_creation_preset(self) -> None:
        preset_id = self.preset_combo.currentData()
        if preset_id is None:
            self._preset_card_theme = None
            return
        if QMessageBox.question(self, "Excluir preset", "Excluir o preset selecionado?") != QMessageBox.StandardButton.Yes:
            return
        self.database.delete_creation_preset(int(preset_id))
        self._preset_card_theme = None
        self._refresh_presets()
        defaults = load_voicevox_defaults(self.database)
        self._create_voicevox_settings = VoicevoxSettingsData(**defaults.__dict__)
        self.refresh_audio_options()
        self.status.show_message("Preset excluído.")

    def _preset_selected(self, *_args) -> None:
        preset_id = self.preset_combo.currentData()
        self.delete_preset_button.setEnabled(preset_id is not None)
        if preset_id is None:
            self._preset_card_theme = None
            defaults = load_voicevox_defaults(self.database)
            self._create_voicevox_settings = VoicevoxSettingsData(**defaults.__dict__)
            self._refresh_advanced_audio_profiles()
            self._prepare_create_voicevox_default()
            return
        preset = next((item for item in self.database.list_creation_presets() if item.id == int(preset_id)), None)
        if preset is None:
            return
        data = preset.payload
        language = str(data.get("language") or "ja")
        translation = str(data.get("translation_language") or "pt")
        self.language_combo.setCurrentIndex(max(0, self.language_combo.findData(language)))
        self._language_changed()
        template_key = str(data.get("template_key") or "custom")
        template_index = self.template_combo.findData(template_key)
        if template_index >= 0:
            self.template_combo.setCurrentIndex(template_index)
        self._template_changed()
        self.translation_language_combo.setCurrentIndex(max(0, self.translation_language_combo.findData(translation)))
        self.custom_content_input.setText(str(data.get("custom_content") or ""))
        self.topic_input.setText(str(data.get("topic") or ""))
        self.quantity_spin.setValue(int(data.get("quantity") or 30))
        quantity_index = self.quantity_mode_combo.findData(str(data.get("quantity_mode") or "fixed"))
        if quantity_index >= 0:
            self.quantity_mode_combo.setCurrentIndex(quantity_index)
        raw_structures = data.get("card_structures")
        if isinstance(raw_structures, list) and raw_structures:
            try:
                self._structure_variations = [CardStructureVariation.model_validate(item) for item in raw_structures]
                self._refresh_structure_selector(0)
                self._structure_selected(0)
            except Exception:
                pass
        audio_mode_idx = self.audio_mode_combo.findData(str(data.get("audio_mode") or "intelligent"))
        if audio_mode_idx >= 0:
            self.audio_mode_combo.setCurrentIndex(audio_mode_idx)
        providers = data.get("audio_providers")
        if isinstance(providers, list):
            selected = {str(item) for item in providers}
            for key, check in self.audio_provider_checks.items():
                check.setChecked(key in selected)
        fixed_provider_idx = self.fixed_audio_provider_combo.findData(str(data.get("fixed_audio_provider") or "voicevox"))
        if fixed_provider_idx >= 0:
            self.fixed_audio_provider_combo.setCurrentIndex(fixed_provider_idx)
        self._refresh_creation_audio_profiles()
        fixed_profile_idx = self.fixed_audio_profile_combo.findData(str(data.get("fixed_audio_profile_id") or ""))
        if fixed_profile_idx >= 0:
            self.fixed_audio_profile_combo.setCurrentIndex(fixed_profile_idx)
        self._refresh_advanced_audio_profiles()
        preferences = data.get("audio_profile_preferences")
        if isinstance(preferences, dict):
            for provider, combo in self.preferred_profile_combos.items():
                index = combo.findData(str(preferences.get(provider) or ""))
                if index >= 0:
                    combo.setCurrentIndex(index)
        self._create_voicevox_settings = VoicevoxSettingsData(
            style_id=int(data.get("voicevox_style_id") or 0),
            style_label=str(data.get("voicevox_style_label") or ""),
            speed_scale=float(data.get("voicevox_speed_scale", 1.0)),
            pitch_scale=float(data.get("voicevox_pitch_scale", 0.0)),
            intonation_scale=float(data.get("voicevox_intonation_scale", 1.0)),
            volume_scale=float(data.get("voicevox_volume_scale", 1.0)),
            pause_length_scale=float(data.get("voicevox_pause_length_scale", 1.0)),
        )
        self._prepare_create_voicevox_default()
        raw_theme = data.get("card_theme")
        self._preset_card_theme = raw_theme if isinstance(raw_theme, dict) else None
        self.set_creation_mode(str(data.get("creation_mode") or "import"))
        self._quantity_mode_changed()
        self._update_audio_creation_controls()
        self.status.show_message("Preset aplicado.")

    def _build_project(self) -> ProjectData:
        name = self.name_input.text().strip()
        if not name:
            raise ValueError("Informe um nome para o projeto.")
        self._save_current_structure()
        if not self._structure_variations:
            raise ValueError("Adicione ao menos uma variação de estrutura.")
        for variation in self._structure_variations:
            if not variation.front_components or not variation.back_components:
                raise ValueError(
                    f"A variação “{variation.name}” precisa ter ao menos um componente na frente e no verso."
                )
        front = list(self._structure_variations[0].front_components)
        back = list(self._structure_variations[0].back_components)

        language_data = self.language_combo.currentData()
        if language_data is None:
            raise ValueError("Selecione um idioma da lista.")
        language = str(language_data)
        translation_language_data = self.translation_language_combo.currentData()
        if translation_language_data is None:
            raise ValueError("Selecione o idioma da tradução.")
        translation_language = str(translation_language_data)
        template_key = str(self.template_combo.currentData() or "custom")
        is_standard = language == "ja" and template_key != "custom"
        custom_content = self._parse_custom_content(self.custom_content_input.text())
        if template_key == "custom" and not custom_content:
            raise ValueError(
                "No modelo Personalizado, informe ao menos um conteúdo separado por vírgulas."
            )
        selected_audio_providers = [
            key for key, check in self.audio_provider_checks.items() if check.isEnabled() and check.isChecked()
        ]
        uses_audio = any(
            "audio" in (variation.front_components + variation.back_components)
            for variation in self._structure_variations
        )
        audio_mode = str(self.audio_mode_combo.currentData() or "intelligent")
        fixed_audio_provider = str(self.fixed_audio_provider_combo.currentData() or "voicevox")
        audio_profile_preferences = {
            provider: str(combo.currentData() or "")
            for provider, combo in self.preferred_profile_combos.items()
            if combo.currentData()
        }
        fixed_audio_profile_id = str(self.fixed_audio_profile_combo.currentData() or "")
        if uses_audio and audio_mode == "fixed" and fixed_audio_provider in audio_profile_preferences and not fixed_audio_profile_id:
            fixed_audio_profile_id = audio_profile_preferences[fixed_audio_provider]
        if uses_audio and not selected_audio_providers:
            raise ValueError("Selecione ao menos um provedor de áudio para este projeto.")
        if uses_audio and audio_mode == "fixed":
            if fixed_audio_provider not in selected_audio_providers:
                selected_audio_providers.append(fixed_audio_provider)
            if fixed_audio_provider in {"gemini", "elevenlabs"} and not fixed_audio_profile_id:
                raise ValueError("Selecione uma voz fixa cadastrada em Configurações para o provedor escolhido.")

        return ProjectData(
            name=name,
            language=language,
            translation_language=translation_language,
            template_key=template_key,
            topic="" if is_standard else self.topic_input.text().strip(),
            custom_content=custom_content if template_key == "custom" else [],
            creation_mode="builtin" if is_standard else self.creation_mode,
            front_components=front,
            back_components=back,
            card_structures=[item.model_copy(deep=True) for item in self._structure_variations],
            structure_distribution="balanced_random",
            audio_mode=audio_mode,
            audio_providers=selected_audio_providers,
            fixed_audio_provider=fixed_audio_provider,
            fixed_audio_profile_id=fixed_audio_profile_id,
            audio_profile_preferences=audio_profile_preferences,
            voicevox_style_id=int(self.create_voicevox_combo.currentData() if language == "ja" and self.create_voicevox_combo.currentData() is not None else self._create_voicevox_settings.style_id),
            voicevox_style_label=self.create_voicevox_combo.currentText().strip() if language == "ja" else "",
            voicevox_speed_scale=self._create_voicevox_settings.speed_scale,
            voicevox_pitch_scale=self._create_voicevox_settings.pitch_scale,
            voicevox_intonation_scale=self._create_voicevox_settings.intonation_scale,
            voicevox_volume_scale=self._create_voicevox_settings.volume_scale,
            voicevox_pause_length_scale=self._create_voicevox_settings.pause_length_scale,
            card_theme=(
                load_default_card_theme(self.database)
                if self._preset_card_theme is None
                else DeckThemeSettings.model_validate(self._preset_card_theme)
            ),
        )

    def _build_prompt(self, project: ProjectData) -> str:
        return PromptService.build(
            language=project.language,
            translation_language=project.translation_language,
            ui_language=current_language(),
            template_key=project.template_key,
            topic=project.topic,
            quantity=self._requested_quantity(),
            max_auto_quantity=self.AUTO_CARD_LIMIT,
            deck_name=project.name,
            front_components=project.prompt_front_components(),
            back_components=project.prompt_back_components(),
            custom_content=project.custom_content,
        )

    def show_prompt(self) -> None:
        try:
            project = self._build_project()
            prompt = self._build_prompt(project)
        except Exception as exc:
            QMessageBox.warning(self, "Configuração incompleta", str(exc))
            return
        PromptDialog(prompt, self).exec()

    def create_project(self) -> None:
        try:
            project = self._build_project()
        except Exception as exc:
            QMessageBox.warning(self, "Configuração incompleta", str(exc))
            return
        mode = project.creation_mode
        if mode == "builtin":
            try:
                project_id = self.project_service.create_builtin(project, self.quantity_spin.value())
            except Exception as exc:
                QMessageBox.critical(self, "Não foi possível criar", str(exc))
                return
            self._finish(project_id)
        elif mode == "manual":
            project_id = self.database.create_project(project)
            self._finish(project_id)
        elif mode == "import":
            dialog = ImportDeckDialog(self)
            if dialog.exec() and dialog.imported_deck:
                try:
                    project_id = self.project_service.create_from_import(project, dialog.imported_deck)
                except Exception as exc:
                    QMessageBox.critical(self, "Não foi possível importar", str(exc))
                    return
                self._finish(project_id)
        elif mode == "gemini":
            self._create_with_gemini(project)

    def _keep_worker(self, worker: Worker) -> None:
        self._workers.append(worker)
        worker.signals.finished.connect(
            lambda: self._workers.remove(worker) if worker in self._workers else None
        )
        self.thread_pool.start(worker)

    def _create_with_gemini(self, project: ProjectData) -> None:
        api_key = SecretStore.get("GEMINI_API_KEY")
        model = self.database.get_setting("gemini_text_model", DEFAULT_GEMINI_TEXT_MODEL)
        try:
            service = GeminiContentService(api_key, model)
        except Exception as exc:
            QMessageBox.warning(self, "Gemini não configurada", str(exc))
            return
        self.create_button.setEnabled(False)
        self.status.show_message("Gerando conteúdo com a Gemini API...")
        prompt = self._build_prompt(project)
        requested_quantity = self._requested_quantity()
        worker = Worker(
            service.generate_deck,
            prompt,
            maximum_cards=self.AUTO_CARD_LIMIT if requested_quantity is None else None,
            expected_cards=requested_quantity,
            expected_language=project.language,
            expected_translation_language=project.translation_language,
        )

        def save(imported_deck: object) -> None:
            try:
                project_id = self.project_service.create_from_import(project, imported_deck)
            except Exception as exc:
                QMessageBox.critical(self, "Erro ao salvar", str(exc))
                return
            self._finish(project_id)

        worker.signals.result.connect(save)
        worker.signals.error.connect(lambda message: self.status.show_message(message, error=True))
        worker.signals.finished.connect(lambda: self.create_button.setEnabled(True))
        self._keep_worker(worker)

    def _finish(self, project_id: int) -> None:
        self.status.show_message("Projeto criado com sucesso.")
        self.project_created.emit(project_id)
        QMessageBox.information(
            self,
            "Projeto criado",
            "O projeto foi criado e está pronto para revisão.",
        )
