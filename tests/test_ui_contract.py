from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "ankiistudio" / "ui"
ICONS = ROOT / "ankiistudio" / "resources" / "icons"


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_main_window_is_compact_and_images_tab_is_removed() -> None:
    source = read("ankiistudio/ui/main_window.py")
    assert "self.resize(1120, 720)" in source
    assert "self.setMinimumSize(960, 620)" in source
    assert 'sidebar.setFixedWidth(196)' in source
    assert '("Imagens"' not in source
    assert "ImagesPage" not in source


def test_new_logo_is_used_and_packaged() -> None:
    main = read("ankiistudio/ui/main_window.py")
    about = read("ankiistudio/ui/pages/about_page.py")
    spec = read("AnkiiStudio.spec")
    assert (ICONS / "app.png").is_file()
    assert (ICONS / "app.ico").is_file()
    assert 'icons" / "app.png"' in main
    assert 'icons" / "app.png"' in about
    assert '".png"' in spec


def test_sidebar_icons_are_packaged() -> None:
    for name in ("home", "create", "projects", "models", "audio", "settings", "about"):
        assert (ICONS / f"{name}_idle.svg").is_file()
        assert (ICONS / f"{name}_active.svg").is_file()


def test_home_import_button_opens_import_creation_mode() -> None:
    home = read("ankiistudio/ui/pages/home_page.py")
    main = read("ankiistudio/ui/main_window.py")
    create = read("ankiistudio/ui/pages/create_page.py")
    assert "import_requested = Signal()" in home
    assert "self.home_page.import_requested.connect(self.open_import)" in main
    assert 'self.create_page.set_creation_mode("import")' in main
    assert "def set_creation_mode" in create


def test_compact_pages_use_scrollable_layouts() -> None:
    for filename in (
        "create_page.py",
        "projects_page.py",
        "audio_page.py",
        "settings_page.py",
        "about_page.py",
    ):
        source = read(f"ankiistudio/ui/pages/{filename}")
        assert "PageScrollArea" in source
        assert "QGroupBox" not in source


def test_adaptive_splitters_are_used_for_dense_pages() -> None:
    widgets = read("ankiistudio/ui/widgets.py")
    projects = read("ankiistudio/ui/pages/projects_page.py")
    models = read("ankiistudio/ui/pages/models_page.py")
    assert "class AdaptiveSplitter(QSplitter)" in widgets
    assert "Qt.Orientation.Vertical" in widgets
    assert "AdaptiveSplitter(breakpoint=900)" in projects
    assert "AdaptiveSplitter(breakpoint=800)" in models


def test_projects_card_table_has_priority_in_compact_ui() -> None:
    projects = read("ankiistudio/ui/pages/projects_page.py")
    assert "left_card.setMinimumHeight(430)" in projects
    assert "self.table.setMinimumHeight(330)" in projects
    assert "splitter.setStretchFactor(0, 3)" in projects
    assert "splitter.setStretchFactor(1, 2)" in projects


def test_create_page_is_searchable_responsive_and_default_template_is_custom() -> None:
    source = read("ankiistudio/ui/pages/create_page.py")
    constants = read("ankiistudio/constants.py")
    assert '"custom": "Personalizado"' in constants
    assert 'TEMPLATES_BY_LANGUAGE' in constants
    assert 'self.template_combo.set_items(items, "custom")' in source
    assert 'self.language_combo.set_items([(label, code) for code, label in LANGUAGE_LABELS.items()], "ja")' in source
    assert "self.custom_content_cell.setVisible(is_custom)" in source
    assert "SearchableComboBox" in source
    assert "RESPONSIVE_BREAKPOINT = 820" in source
    assert "self.structure_grid.addWidget(self.front_editor" in source
    assert "self.structure_grid.addWidget(self.back_editor" in source


def test_standard_templates_autoload_their_default_structure() -> None:
    constants = read("ankiistudio/constants.py")
    create = read("ankiistudio/ui/pages/create_page.py")
    assert '"hiragana": (["word"], ["romanization", "translation", "explanation"])' in constants
    assert '"katakana": (["word"], ["romanization", "translation", "explanation"])' in constants
    assert '"basic_phrases": (["word"], ["romanization", "translation", "explanation"])' in constants
    assert "TEMPLATE_DEFAULT_STRUCTURES.get" in create
    assert "self.front_editor.set_components(list(front))" in create
    assert "self.back_editor.set_components(list(back))" in create


def test_standard_templates_lock_generation_inputs_and_use_builtin_mode() -> None:
    create = read("ankiistudio/ui/pages/create_page.py")
    assert "self.topic_input.setEnabled(is_custom)" in create
    assert "self.quantity_spin.setEnabled(is_custom)" in create
    assert 'self.set_creation_mode("builtin")' in create
    assert 'button.setEnabled(key == "builtin")' in create
    assert 'creation_mode="builtin" if is_standard else self.creation_mode' in create


def test_model_selector_searches_inside_the_existing_combo() -> None:
    widgets = read("ankiistudio/ui/widgets.py")
    create = read("ankiistudio/ui/pages/create_page.py")
    assert "class SearchableComboBox(QComboBox)" in widgets
    assert "_SearchRankingProxy" in widgets
    assert "search_score" in widgets
    assert "QCompleter" in widgets
    assert "UnfilteredPopupCompletion" in widgets
    assert "self._completer.complete()" in widgets
    assert "super().showPopup()" not in widgets
    assert "sem ocultar nenhuma opção" in widgets
    assert "self.template_combo = SearchableComboBox()" in create
    assert "self.language_combo = SearchableComboBox()" in create


def test_language_options_and_standard_model_availability() -> None:
    constants = read("ankiistudio/constants.py")
    assert "'ja': 'Japonês'" in constants
    assert "'en': 'Inglês'" in constants
    assert "'es': 'Espanhol'" in constants
    assert "'ko': 'Coreano'" in constants
    assert "'pt': 'Português'" in constants
    assert "'fr': 'Francês'" in constants
    assert "'ar': 'Árabe'" in constants
    assert '"ja": ["custom", "hiragana", "katakana", "basic_phrases"]' in constants
    assert "normalize_language_code" in constants
    assert '"jlpt_n5"' not in constants
    assert '"basic_kanji"' not in constants
    assert '"thematic_vocabulary"' not in constants


def test_standard_content_json_is_packaged() -> None:
    pyproject = read("pyproject.toml")
    spec = read("AnkiiStudio.spec")
    assert '"data/*.json"' in pyproject
    assert 'data_files' in spec
    assert (ROOT / "ankiistudio" / "data" / "japanese_standard_content.json").is_file()


def test_checkbox_and_radio_states_are_fully_styled() -> None:
    source = read("ankiistudio/ui/theme.py")
    assert "QCheckBox::indicator:unchecked" in source
    assert "QCheckBox::indicator:checked" in source
    assert "check.svg" in source
    assert "QRadioButton::indicator:unchecked" in source
    assert "QRadioButton::indicator:checked" in source
    assert "radio.svg" in source


def test_no_shadow_effects_are_used_in_application_ui() -> None:
    combined = "\n".join(path.read_text(encoding="utf-8") for path in UI.rglob("*.py"))
    assert "QGraphicsDropShadowEffect" not in combined
    assert "box-shadow" not in combined


def test_standalone_images_page_was_removed() -> None:
    assert not (UI / "pages" / "images_page.py").exists()


def test_key_buttons_are_connected_to_actions() -> None:
    create = read("ankiistudio/ui/pages/create_page.py")
    settings = read("ankiistudio/ui/pages/settings_page.py")
    projects = read("ankiistudio/ui/pages/projects_page.py")
    audio = read("ankiistudio/ui/pages/audio_page.py")
    about = read("ankiistudio/ui/pages/about_page.py")
    assert "self.prompt_button.clicked.connect(self.show_prompt)" in create
    assert "self.create_button.clicked.connect(self.create_project)" in create
    assert "save_button.clicked.connect(self.save)" in settings
    assert "self.test_voicevox_button.clicked.connect(self.test_voicevox)" in settings
    assert "self.export_button.clicked.connect(self.export_project)" in projects
    assert "self.image_button.clicked.connect(self.search_image)" in projects
    assert "self.audio_button.clicked.connect(self.generate_card_audio)" in projects
    assert "self.save_button.clicked.connect(self.save_card)" in projects
    assert "self.save_button.clicked.connect(self.save_project)" in audio
    assert "self.generate_button.clicked.connect(self.generate_all)" in audio
    assert "github_button.clicked.connect" in about


def test_windows_build_uses_installed_python_launcher_version() -> None:
    source = read("scripts/build_windows.ps1")
    assert "py -m venv .venv" in source
    assert "py -3.12" not in source


def test_api_keys_remain_editable_inside_settings() -> None:
    settings = read("ankiistudio/ui/pages/settings_page.py")
    assert "self.gemini_key = QLineEdit()" in settings
    assert "self.eleven_key = QLineEdit()" in settings
    assert 'SecretStore.set("GEMINI_API_KEY"' in settings
    assert 'SecretStore.set("ELEVENLABS_API_KEY"' in settings


def test_voice_profiles_are_managed_in_audio_page_and_keys_remain_in_settings() -> None:
    audio = read("ankiistudio/ui/pages/audio_page.py")
    settings = read("ankiistudio/ui/pages/settings_page.py")
    profile_service = read("ankiistudio/services/audio_profile_service.py")
    assert "AudioVoiceProfile" in profile_service
    assert 'provider: Literal["gemini", "elevenlabs"]' in profile_service
    assert "language:" in profile_service
    assert "self.profile_service.upsert" in audio
    assert "Voice ID" in read("ankiistudio/ui/dialogs/audio_profile_dialog.py")
    assert "Voz Natural A" not in settings
    assert "Speaker ID Natural A" not in settings


def test_application_version_is_0_9_0_everywhere() -> None:
    assert 'APP_VERSION = "0.10.0"' in read("ankiistudio/constants.py")
    assert '__version__ = "0.10.0"' in read("ankiistudio/__init__.py")
    assert 'version = "0.10.0"' in read("pyproject.toml")
    assert "AnkiiStudio/0.10.0" in read("ankiistudio/services/wikimedia_service.py")
    assert not (ROOT / "scripts" / "AnkiiStudio.iss").exists()


def test_light_theme_copy_is_professional_and_deck_theme_editor_remains() -> None:
    settings = read("ankiistudio/ui/pages/settings_page.py")
    theme = read("ankiistudio/ui/theme.py")
    models = read("ankiistudio/ui/pages/models_page.py")
    assert 'self.appearance_combo.addItem("Escuro", "dark")' in settings
    assert 'self.appearance_combo.addItem("Claro", "light")' in settings
    assert "O tema escuro é o padrão do AnkiiStudio" not in settings
    assert 'if theme == "light":' in theme
    assert "Tema do baralho" in models
    assert "Estrutura do baralho" in models


def test_bulk_media_and_export_selection_are_preserved() -> None:
    projects = read("ankiistudio/ui/pages/projects_page.py")
    assert 'self.bulk_image_button = QPushButton("Imagens para todos")' in projects
    assert 'self.bulk_audio_button = QPushButton("Áudios para todos")' in projects
    assert 'self.export_selected_button = QPushButton("Exportar selecionados")' in projects
    assert 'self.export_all_button = QPushButton("Exportar todos")' in projects
    assert "self.bulk_image_button.setEnabled(has_project and uses_images)" in projects
    assert "self.bulk_audio_button.setEnabled(has_project and uses_audio)" in projects


def test_projects_editor_hides_fields_outside_selected_structure() -> None:
    projects = read("ankiistudio/ui/pages/projects_page.py")
    assert 'self._set_field_visible(self.reading, "reading" in selected)' in projects
    assert 'self._set_field_visible(self.romanization, "romanization" in selected)' in projects
    assert 'self._set_field_visible(self.translation, "translation" in selected)' in projects
    assert "project.uses_images" in projects


def test_voicevox_worker_is_retained_during_connection_test() -> None:
    settings = read("ankiistudio/ui/pages/settings_page.py")
    provider = read("ankiistudio/services/audio/voicevox.py")
    assert "self._voicevox_worker = worker" in settings
    assert "self.test_voicevox_button.setEnabled(False)" in settings
    assert "self.test_voicevox_button.setEnabled(True)" in settings
    assert "Não foi possível encontrar o VOICEVOX" in provider


def test_voicevox_is_restricted_to_japanese_audio_projects() -> None:
    audio = read("ankiistudio/ui/pages/audio_page.py")
    router = read("ankiistudio/services/audio/router.py")
    assert 'self.current_project.language != "ja"' in audio
    assert 'if project.language != "ja"' in router


def test_create_page_retains_gemini_worker() -> None:
    create = read("ankiistudio/ui/pages/create_page.py")
    assert "self._workers: list[Worker] = []" in create
    assert "self._keep_worker(worker)" in create


def test_projects_page_has_live_media_progress_and_download_exports() -> None:
    source = read("ankiistudio/ui/pages/projects_page.py")
    assert "self.progress = QProgressBar()" in source
    assert "worker.signals.progress.connect(self._bulk_media_progress)" in source
    assert '"Buscando…"' in source
    assert '"Gerando…"' in source
    assert "last_export_dir" in source
    assert "self.paths.downloads_dir" in source


def test_audio_page_has_responsive_provider_grid_and_unlimited_voice_profiles() -> None:
    source = read("ankiistudio/ui/pages/audio_page.py")
    assert "AudioProfileService" in source
    assert "AudioProfileDialog" in source
    assert 'QPushButton("Adicionar voz")' in source
    assert "RESPONSIVE_BREAKPOINT = 1180" in source
    assert "self.provider_grid.addWidget" in source
    assert "GeminiTTSUsageTracker" in source
    assert "refresh_gemini_usage" in source
    assert "load_voicevox_styles" in source
    assert "Personagem / estilo" in source


def test_models_preview_uses_export_style_renderer() -> None:
    source = read("ankiistudio/ui/pages/models_page.py")
    assert "Pré-visualização real" in source
    assert "render_preview_document" in source
    assert "self.front_preview" in source
    assert "self.back_preview" in source


def test_audio_media_is_internal_and_exports_default_to_downloads() -> None:
    config = read("ankiistudio/config.py")
    projects = read("ankiistudio/ui/pages/projects_page.py")
    assert 'self.audio_dir = self.media_dir / "audio"' in config
    assert 'Path.home() / "Downloads"' in config
    assert "self.paths.downloads_dir" in projects


def test_github_publication_files_exist_and_license_is_gpl3() -> None:
    assert (ROOT / "README.md").is_file()
    assert (ROOT / "CHANGELOG.md").is_file()
    assert (ROOT / "LICENSE").is_file()
    assert (ROOT / ".gitignore").is_file()
    assert not (ROOT / ".env.example").exists()
    license_text = read("LICENSE")
    assert "GNU GENERAL PUBLIC LICENSE" in license_text
    assert "Version 3, 29 June 2007" in license_text
    gitignore = read(".gitignore")
    assert ".venv/" in gitignore
    assert ".env" in gitignore
    assert "dist/" in gitignore


def test_simplified_structure_has_one_audio_component() -> None:
    constants = read("ankiistudio/constants.py")
    assert '"audio": "Áudio"' in constants
    labels_block = constants.split("COMPONENT_LABELS", 1)[1].split("LEGACY_COMPONENT_ALIASES", 1)[0]
    assert '"word_audio"' not in labels_block
    assert '"sentence_audio"' not in labels_block
    assert '"part_of_speech"' not in labels_block
    assert '"level"' not in labels_block
    assert '"tags"' not in labels_block
    assert '"example": "Exemplo"' in labels_block


def test_audio_page_plays_voicevox_preview_internally_and_searches_styles() -> None:
    audio = read("ankiistudio/ui/pages/audio_page.py")
    assert "QMediaPlayer" in audio
    assert "QAudioOutput" in audio
    assert "self.preview_player.play()" in audio
    assert "QDesktopServices" not in audio
    assert "self.voicevox_combo = SearchableComboBox()" in audio
    assert "self.voicevox_combo.set_items(items, selected)" in audio
    assert "VoicevoxSettingsDialog" in audio


def test_elevenlabs_profiles_expose_voice_controls() -> None:
    dialog = read("ankiistudio/ui/dialogs/audio_profile_dialog.py")
    provider = read("ankiistudio/services/audio/elevenlabs.py")
    assert "Estabilidade" in dialog
    assert "Similaridade" in dialog
    assert "Estilo" in dialog
    assert "Velocidade" in dialog
    assert "speaker_boost" in dialog
    assert '"voice_settings"' in provider
    assert "PermanentAudioProviderError" in provider
    assert "_error_detail" in provider


def test_wikimedia_svg_uses_commons_raster_thumbnail() -> None:
    wikimedia = read("ankiistudio/services/wikimedia_service.py")
    media = read("ankiistudio/services/media_service.py")
    assert '"image/svg+xml"' in wikimedia
    assert '"iiurlwidth": 900' in wikimedia
    assert 'result.mime == "image/svg+xml"' in media
    assert "result.thumbnail_url" in media


def test_voicevox_selection_label_is_persisted() -> None:
    models = read("ankiistudio/models.py")
    database = read("ankiistudio/database.py")
    audio = read("ankiistudio/ui/pages/audio_page.py")
    assert "voicevox_style_label" in models
    assert "voicevox_style_label" in database
    assert "self._voicevox_selected" in audio


def test_portable_only_storage_and_build_are_configured() -> None:
    config = read("ankiistudio/config.py")
    build = read("scripts/build_windows.ps1")
    assert 'self.base_dir = self.app_dir / "data"' in config
    assert "platformdirs" not in config
    assert "user_data_dir" not in config
    assert "AnkiiStudio-Portable-0.10.0.zip" in build
    assert "AnkiiStudio.iss" not in build
    assert not (ROOT / "scripts" / "AnkiiStudio.iss").exists()


def test_user_supplied_png_and_ico_are_adopted() -> None:
    assert (ICONS / "app.png").is_file()
    assert (ICONS / "app.ico").is_file()
