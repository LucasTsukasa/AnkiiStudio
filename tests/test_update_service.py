from __future__ import annotations

from pathlib import Path

import sys
import types

if "keyring" not in sys.modules:
    keyring_stub = types.ModuleType("keyring")
    keyring_stub.errors = types.SimpleNamespace(KeyringError=RuntimeError, PasswordDeleteError=RuntimeError)
    keyring_stub.get_password = lambda *args, **kwargs: None
    keyring_stub.set_password = lambda *args, **kwargs: None
    keyring_stub.delete_password = lambda *args, **kwargs: None
    sys.modules["keyring"] = keyring_stub

import pytest

from ankiistudio.config import AppPaths
from ankiistudio.services.update_service import UpdateService


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, payload, *args, **kwargs):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, *args, **kwargs):
        return FakeResponse(self.payload)


def _release(tag: str, *, prerelease: bool) -> dict:
    return {
        "tag_name": tag,
        "name": f"AnkiiStudio {tag}",
        "draft": False,
        "prerelease": prerelease,
        "html_url": f"https://github.com/LucasTsukasa/AnkiiStudio/releases/tag/{tag}",
        "body": "Notas",
        "assets": [
            {
                "name": f"AnkiiStudio-Portable-{tag.lstrip('v')}.zip",
                "browser_download_url": f"https://example.invalid/{tag}.zip",
            }
        ],
    }


def test_semver_order_alpha_beta_rc_stable(tmp_path: Path) -> None:
    service = UpdateService(AppPaths(tmp_path))
    versions = [
        "0.11.0-alpha.1",
        "0.11.0-beta.1",
        "0.11.0-beta.2",
        "0.11.0-rc.1",
        "0.11.0",
    ]
    assert sorted(versions, key=service.version_key) == versions


def test_stable_channel_ignores_prereleases(monkeypatch, tmp_path: Path) -> None:
    payload = [
        _release("v0.12.0-beta.1", prerelease=True),
        _release("v0.11.0", prerelease=False),
    ]
    monkeypatch.setattr(
        "ankiistudio.services.update_service.httpx.Client",
        lambda *args, **kwargs: FakeClient(payload),
    )
    service = UpdateService(AppPaths(tmp_path))
    info = service.check("0.10.0")
    assert info is not None
    assert info.version == "0.11.0"
    assert info.prerelease is False


def test_beta_channel_can_receive_newer_prerelease(monkeypatch, tmp_path: Path) -> None:
    payload = [
        _release("v0.12.0-beta.1", prerelease=True),
        _release("v0.11.0", prerelease=False),
    ]
    monkeypatch.setattr(
        "ankiistudio.services.update_service.httpx.Client",
        lambda *args, **kwargs: FakeClient(payload),
    )
    service = UpdateService(AppPaths(tmp_path))
    info = service.check("0.11.0-beta.2")
    assert info is not None
    assert info.version == "0.12.0-beta.1"
    assert info.prerelease is True


def test_safe_extract_rejects_path_traversal(tmp_path: Path) -> None:
    import zipfile

    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as package:
        package.writestr("../outside.txt", "bad")
    destination = tmp_path / "staging"
    destination.mkdir()
    with pytest.raises(RuntimeError, match="caminho inválido"):
        UpdateService._safe_extract(archive, destination)


def test_windows_updater_preserves_data_and_replaces_application_files(monkeypatch, tmp_path: Path) -> None:
    from ankiistudio.services.update_service import DownloadedUpdate, UpdateInfo

    paths = AppPaths(tmp_path / "portable")
    paths.ensure()
    staging = paths.cache_dir / "updates" / "0.11.0-beta.3" / "staging"
    staging.mkdir(parents=True)
    (staging / "AnkiiStudio.exe").write_bytes(b"exe")
    (staging / "_internal").mkdir()
    archive = staging.parent / "AnkiiStudio-Portable-0.11.0-beta.3.zip"
    archive.write_bytes(b"zip")
    info = UpdateInfo(
        version="0.11.0-beta.3",
        tag_name="v0.11.0-beta.3",
        prerelease=True,
        release_name="AnkiiStudio v0.11.0-beta.3",
        html_url="https://example.test/release",
        notes="",
        asset_name=archive.name,
        asset_url="https://example.test/update.zip",
    )
    downloaded = DownloadedUpdate(info=info, archive_path=archive, staging_dir=staging)
    service = UpdateService(paths)
    monkeypatch.setattr(service, "can_self_update", lambda: True)
    monkeypatch.setattr("ankiistudio.services.update_service.subprocess.Popen", lambda *a, **k: object())

    script = service.schedule_install_and_restart(downloaded)
    text = script.read_text(encoding="utf-8")
    assert "if ($_.Name -ne 'data')" in text
    assert "Get-ChildItem -LiteralPath $appDir -Force" in text
    assert "Remove-Item -LiteralPath $_.FullName -Recurse -Force" in text
    assert "Start-Process -FilePath (Join-Path $appDir 'AnkiiStudio.exe')" in text


def test_update_payload_accepts_executable_at_zip_root(tmp_path: Path) -> None:
    staging = tmp_path / "staging-root"
    staging.mkdir()
    (staging / "AnkiiStudio.exe").write_bytes(b"exe")
    (staging / "_internal").mkdir()
    assert UpdateService._resolve_payload_dir(staging) == staging


def test_update_payload_accepts_single_wrapper_directory(tmp_path: Path) -> None:
    staging = tmp_path / "staging-wrapper"
    payload = staging / "AnkiiStudio"
    payload.mkdir(parents=True)
    (payload / "AnkiiStudio.exe").write_bytes(b"exe")
    (payload / "_internal").mkdir()
    assert UpdateService._resolve_payload_dir(staging) == payload


def test_update_payload_rejects_ambiguous_wrapper(tmp_path: Path) -> None:
    staging = tmp_path / "staging-ambiguous"
    payload = staging / "AnkiiStudio"
    payload.mkdir(parents=True)
    (payload / "AnkiiStudio.exe").write_bytes(b"exe")
    (staging / "extra").mkdir()
    with pytest.raises(RuntimeError, match="build portátil válido"):
        UpdateService._resolve_payload_dir(staging)
