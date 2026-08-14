from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon


class IconRegistry:
    """Ponto único para resolver ícones e estados do AnkiiStudio."""

    def __init__(self, resource_dir: Path) -> None:
        self.icons_dir = resource_dir / "icons"

    def path(self, name: str, *, state: str | None = None, extension: str = "svg") -> Path:
        suffix = f"_{state}" if state else ""
        return self.icons_dir / f"{name}{suffix}.{extension}"

    def icon(self, name: str, *, stateful: bool = False, size: int | None = None) -> QIcon:
        if not stateful:
            path = self.path(name)
            return QIcon(str(path)) if path.is_file() else QIcon()
        icon = QIcon()
        idle = self.path(name, state="idle")
        active = self.path(name, state="active")
        target = QSize(size or 18, size or 18)
        if idle.is_file():
            icon.addFile(str(idle), target, QIcon.Mode.Normal, QIcon.State.Off)
        if active.is_file():
            icon.addFile(str(active), target, QIcon.Mode.Normal, QIcon.State.On)
        return icon
