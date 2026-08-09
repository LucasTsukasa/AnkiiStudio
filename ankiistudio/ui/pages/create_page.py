from __future__ import annotations

from PySide6.QtCore import QThreadPool, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ankiistudio.config import SecretStore
from ankiistudio.constants import (
    DEFAULT_AUDIO_PROVIDERS,
    DEFAULT_GEMINI_TEXT_MODEL,
    LANGUAGE_LABELS,
    TEMPLATE_DEFAULT_STRUCTURES,
    TEMPLATE_LABELS,
    TEMPLATES_BY_LANGUAGE,
)
from ankiistudio.data.japanese_seed import builtin_card_count
from ankiistudio.database import Database
from ankiistudio.models import ProjectData
from ankiistudio.services.gemini_service import GeminiContentService
from ankiistudio.services.project_service import ProjectService
from ankiistudio.services.prompt_service import PromptService
from ankiistudio.ui.dialogs.import_dialog import ImportDeckDialog
from ankiistudio.ui.dialogs.prompt_dialog import PromptDialog
from ankiistudio.ui.widgets import (
    ComponentOrderEditor,
    PageHeader,
    PageScrollArea,
    SearchableComboBox,
    SectionCard,
    StatusBanner,
)
from ankiistudio.ui.workers import Worker


class CreatePage(QWidget):
    project_created = Signal(int)
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

    def __init__(self, database: Database) -> None:
        super().__init__()
        self.database = database
        self.project_service = ProjectService(database)
        self.thread_pool = QThreadPool.globalInstance()
        self.creation_mode = "import"
        self._workers: list[Worker] = []
        self._updating_templates = False
        self._compact_layout = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)
        layout.addWidget(
            PageHeader(
                "Criar projeto",
                "Configure o conteúdo e defina exatamente o que aparecerá na frente e no verso dos cartões.",
            )
        )
        self.status = StatusBanner()
        layout.addWidget(self.status)

        content_card = SectionCard(
            "1. Conteúdo",
            "Selecione o idioma e o modelo. Modelos padrão usam a base revisada; Personalizado permite definir o conteúdo livremente.",
        )
        self.content_grid = QGridLayout()
        self.content_grid.setHorizontalSpacing(14)
        self.content_grid.setVerticalSpacing(8)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Ex.: Frases para viagem")
        self.language_combo = SearchableComboBox()
        self.language_combo.set_items([(label, code) for code, label in LANGUAGE_LABELS.items()], "ja")
        self.language_combo.lineEdit().setPlaceholderText("Selecione ou pesquise um idioma")
        self.template_combo = SearchableComboBox()
        self.template_combo.lineEdit().setPlaceholderText("Selecione ou pesquise um modelo")

        self.custom_content_input = QLineEdit()
        self.custom_content_input.setPlaceholderText(
            "Ex.: Kanjis avançados, verbos formais, expressões de viagem"
        )
        self.topic_input = QLineEdit()
        self.topic_input.setPlaceholderText("Ex.: Restaurante, trabalho, situações cotidianas")
        self.quantity_spin = QSpinBox()
        self.quantity_spin.setRange(1, 5000)
        self.quantity_spin.setValue(30)

        self.name_cell = self._field_cell("Nome do projeto", self.name_input)
        self.language_cell = self._field_cell("Idioma", self.language_combo)
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
        self.quantity_cell = self._field_cell("Quantidade de cartões", self.quantity_spin)
        for cell in (
            self.name_cell,
            self.language_cell,
            self.template_cell,
            self.custom_content_cell,
            self.topic_cell,
            self.quantity_cell,
        ):
            self.content_grid.addWidget(cell, 0, 0)
        content_card.root.addLayout(self.content_grid)
        layout.addWidget(content_card)

        mode_card = SectionCard(
            "2. Como criar",
            "Modelos padrão usam sempre o Conteúdo padrão. No modelo Personalizado, escolha a origem do conteúdo.",
        )
        self.mode_grid = QGridLayout()
        self.mode_grid.setSpacing(10)
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.mode_buttons: dict[str, QPushButton] = {}
        for key, (title, description) in self.MODES.items():
            button = QPushButton(f"{title}\n{description}")
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

        structure_card = SectionCard(
            "3. Estrutura automática",
            "Modelos padrão carregam a estrutura recomendada. Você pode adicionar, remover e reorganizar componentes antes de criar o projeto.",
        )
        self.structure_grid = QGridLayout()
        self.structure_grid.setHorizontalSpacing(12)
        self.structure_grid.setVerticalSpacing(12)
        self.front_editor = ComponentOrderEditor("Frente", [])
        self.back_editor = ComponentOrderEditor("Verso", [])
        self.structure_grid.addWidget(self.front_editor, 0, 0)
        self.structure_grid.addWidget(self.back_editor, 0, 1)
        structure_card.root.addLayout(self.structure_grid)
        layout.addWidget(structure_card)

        actions = QHBoxLayout()
        self.prompt_button = QPushButton("Gerar prompt para a IA")
        self.prompt_button.setObjectName("SubtleButton")
        self.create_button = QPushButton("Criar projeto")
        self.create_button.setObjectName("PrimaryButton")
        self.prompt_button.clicked.connect(self.show_prompt)
        self.create_button.clicked.connect(self.create_project)
        actions.addWidget(self.prompt_button)
        actions.addStretch(1)
        actions.addWidget(self.create_button)
        layout.addLayout(actions)
        layout.addStretch(1)
        root.addWidget(PageScrollArea(content))

        self.language_combo.currentIndexChanged.connect(self._language_changed)
        self.template_combo.currentIndexChanged.connect(self._template_changed)
        self._language_changed()
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

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        self._apply_responsive_layout()
        super().resizeEvent(event)

    def _apply_responsive_layout(self, force: bool = False) -> None:
        compact = self.width() < self.RESPONSIVE_BREAKPOINT
        if not force and compact == self._compact_layout:
            return
        self._compact_layout = compact

        for cell in (
            self.name_cell,
            self.language_cell,
            self.template_cell,
            self.custom_content_cell,
            self.topic_cell,
            self.quantity_cell,
        ):
            self.content_grid.removeWidget(cell)

        if compact:
            self.content_grid.addWidget(self.name_cell, 0, 0)
            self.content_grid.addWidget(self.language_cell, 1, 0)
            self.content_grid.addWidget(self.template_cell, 2, 0)
            self.content_grid.addWidget(self.custom_content_cell, 3, 0)
            self.content_grid.addWidget(self.topic_cell, 4, 0)
            self.content_grid.addWidget(self.quantity_cell, 5, 0)
        else:
            self.content_grid.addWidget(self.name_cell, 0, 0, 1, 2)
            self.content_grid.addWidget(self.language_cell, 1, 0)
            self.content_grid.addWidget(self.template_cell, 1, 1)
            self.content_grid.addWidget(self.custom_content_cell, 2, 0, 1, 2)
            self.content_grid.addWidget(self.topic_cell, 3, 0)
            self.content_grid.addWidget(self.quantity_cell, 3, 1)

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

    def _language_changed(self, _index: int | None = None) -> None:
        language_data = self.language_combo.currentData()
        if language_data is None:
            return
        language = str(language_data)
        self._updating_templates = True
        items = [
            (TEMPLATE_LABELS[key], key)
            for key in TEMPLATES_BY_LANGUAGE.get(language, ["custom"])
        ]
        self.template_combo.blockSignals(True)
        self.template_combo.set_items(items, "custom")
        self.template_combo.blockSignals(False)
        self._updating_templates = False
        self._template_changed()

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
        self.front_editor.set_components(list(front))
        self.back_editor.set_components(list(back))

        self.topic_input.setEnabled(is_custom)
        self.quantity_spin.setEnabled(is_custom)
        if is_standard:
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
            "Importar e criar projeto" if mode == "import" else "Criar projeto"
        )

    def _build_project(self) -> ProjectData:
        name = self.name_input.text().strip()
        if not name:
            raise ValueError("Informe um nome para o projeto.")
        front = self.front_editor.components()
        back = self.back_editor.components()
        if not front or not back:
            raise ValueError("A frente e o verso precisam ter ao menos um componente.")

        language_data = self.language_combo.currentData()
        if language_data is None:
            raise ValueError("Selecione um idioma da lista.")
        language = str(language_data)
        template_key = str(self.template_combo.currentData() or "custom")
        is_standard = language == "ja" and template_key != "custom"
        custom_content = self._parse_custom_content(self.custom_content_input.text())
        if template_key == "custom" and not custom_content:
            raise ValueError(
                "No modelo Personalizado, informe ao menos um conteúdo separado por vírgulas."
            )

        return ProjectData(
            name=name,
            language=language,
            template_key=template_key,
            topic="" if is_standard else self.topic_input.text().strip(),
            custom_content=custom_content if template_key == "custom" else [],
            creation_mode="builtin" if is_standard else self.creation_mode,
            front_components=front,
            back_components=back,
            audio_providers=list(DEFAULT_AUDIO_PROVIDERS),
        )

    def _build_prompt(self, project: ProjectData) -> str:
        return PromptService.build(
            language=project.language,
            template_key=project.template_key,
            topic=project.topic,
            quantity=self.quantity_spin.value(),
            deck_name=project.name,
            front_components=project.front_components,
            back_components=project.back_components,
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
        worker = Worker(service.generate_deck, prompt)

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
