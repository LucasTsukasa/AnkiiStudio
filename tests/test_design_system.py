from pathlib import Path

from ankiistudio.ui.design_system.responsive import breakpoint_for_width, responsive_columns
from ankiistudio.ui.design_system.tokens import Breakpoint, THEMES, get_theme_tokens


ROOT = Path(__file__).resolve().parents[1]
DS = ROOT / "ankiistudio" / "ui" / "design_system"


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_design_system_package_has_all_v1_layers() -> None:
    expected = {
        "tokens.py", "themes.py", "typography.py", "icons.py", "responsive.py", "style.py",
    }
    assert expected.issubset({p.name for p in DS.iterdir() if p.is_file()})
    components = DS / "components"
    expected_components = {
        "button.py", "card.py", "combo_box.py", "context_menu.py", "dialog.py", "input.py",
        "progress.py", "section.py", "sidebar.py", "switch.py", "table.py", "tabs.py", "toast.py",
    }
    assert expected_components.issubset({p.name for p in components.iterdir() if p.is_file()})


def test_theme_tokens_keep_existing_themes_and_requested_crimson_colors() -> None:
    assert set(THEMES) == {"dark", "light", "crimson"}
    crimson = get_theme_tokens("crimson")
    assert crimson.background == "#1A1A1A"
    assert crimson.primary == "#A4133C"
    assert get_theme_tokens("unknown").name == "dark"


def test_responsive_primitives_are_shared() -> None:
    assert breakpoint_for_width(700) is Breakpoint.COMPACT
    assert breakpoint_for_width(1000) is Breakpoint.MEDIUM
    assert breakpoint_for_width(1400) is Breakpoint.WIDE
    assert responsive_columns(200, item_min_width=260, maximum=4) == 1
    assert responsive_columns(800, item_min_width=260, maximum=4) == 3
    assert responsive_columns(800, item_min_width=260, maximum=4, spacing=12) == 2
    assert responsive_columns(2000, item_min_width=260, maximum=4) == 4


def test_application_uses_theme_manager_and_design_components() -> None:
    main = read("ankiistudio/main.py")
    window = read("ankiistudio/ui/main_window.py")
    hub = read("ankiistudio/ui/pages/projects_hub_page.py")
    settings_dialog = read("ankiistudio/ui/dialogs/settings_dialog.py")
    update_dialog = read("ankiistudio/ui/dialogs/update_dialog.py")
    widgets = read("ankiistudio/ui/widgets.py")
    assert "apply_design_system" in main
    assert "ASSidebar" in window and "ASSidebarItem" in window
    assert "IconRegistry" in window
    assert "ASToastManager" in window
    assert "ASTabWidget" in hub
    assert "ASContextMenu" in hub
    assert "class SettingsDialog(ASDialog)" in settings_dialog
    assert "class UpdateDialog(ASDialog)" in update_dialog
    assert "class SectionCard(ASCard)" in widgets
    assert "ASProgressBar" in widgets


def test_current_major_pages_are_migrated_to_as_controls() -> None:
    for relative in (
        "ankiistudio/ui/pages/create_page.py",
        "ankiistudio/ui/pages/projects_page.py",
        "ankiistudio/ui/pages/settings_page.py",
        "ankiistudio/ui/pages/models_page.py",
    ):
        source = read(relative)
        assert "from ankiistudio.ui.design_system.components import" in source
        assert "ASButton(" in source
    assert "ASLineEdit(" in read("ankiistudio/ui/pages/create_page.py")
    assert "ASTableWidget(" in read("ankiistudio/ui/pages/projects_page.py")


def test_import_json_policy_files_are_untouched_by_design_system_dependency() -> None:
    import_service = read("ankiistudio/services/import_service.py")
    prompt_service = read("ankiistudio/services/prompt_service.py")
    assert "design_system" not in import_service
    assert "design_system" not in prompt_service


def test_design_system_documentation_exists() -> None:
    doc = read("docs/DESIGN_SYSTEM.md")
    assert "AnkiiStudio Design System v1" in doc
    assert "Qt/PySide6" in doc
    assert "O objetivo não é reimplementar o Qt" in doc
