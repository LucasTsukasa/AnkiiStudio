# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

project_root = Path(SPECPATH)
icon_dir = project_root / "ankiistudio" / "resources" / "icons"
icon_datas = [
    (str(path), "ankiistudio/resources/icons")
    for path in icon_dir.iterdir()
    if path.is_file() and path.suffix.lower() in {".svg", ".ico", ".png"}
]
data_dir = project_root / "ankiistudio" / "data"
data_files = [
    (str(path), "ankiistudio/data")
    for path in data_dir.iterdir()
    if path.is_file() and path.suffix.lower() == ".json"
]
distribution_docs = [(str(project_root / "LICENSE"), ".")]

language_dir = project_root / "ankiistudio" / "languages"
language_files = [
    (str(path), "ankiistudio/languages")
    for path in language_dir.iterdir()
    if path.is_file() and path.suffix.lower() == ".json"
]

a = Analysis(
    [str(project_root / "run.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=icon_datas + data_files + language_files + distribution_docs,
    hiddenimports=["keyring.backends.Windows", "PySide6.QtMultimedia"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AnkiiStudio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_dir / "app.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="AnkiiStudio",
)
