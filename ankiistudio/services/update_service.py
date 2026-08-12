from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

import httpx

from ankiistudio.config import AppPaths
from ankiistudio.constants import APP_VERSION

GITHUB_REPOSITORY = "LucasTsukasa/AnkiiStudio"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases"
USER_AGENT = f"AnkiiStudio/{APP_VERSION} (https://github.com/{GITHUB_REPOSITORY})"


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    tag_name: str
    prerelease: bool
    release_name: str
    html_url: str
    notes: str
    asset_name: str
    asset_url: str


@dataclass(frozen=True)
class DownloadedUpdate:
    info: UpdateInfo
    archive_path: Path
    staging_dir: Path


class UpdateService:
    def __init__(self, paths: AppPaths, timeout: float = 30.0) -> None:
        self.paths = paths
        self.timeout = timeout

    @staticmethod
    def version_key(value: str) -> tuple[int, int, int, int, int]:
        """Converte SemVer do aplicativo para uma chave ordenável.

        Ordem: alpha < beta < rc < estável. Tags podem começar com ``v``.
        """
        text = value.strip().lower().lstrip("v")
        match = re.fullmatch(
            r"(\d+)\.(\d+)\.(\d+)(?:-(alpha|beta|rc)(?:[.-]?(\d+))?)?",
            text,
        )
        if not match:
            raise ValueError(f"Versão não reconhecida: {value}")
        major, minor, patch = (int(match.group(i)) for i in range(1, 4))
        stage = match.group(4)
        sequence = int(match.group(5) or 0)
        stage_rank = {"alpha": 0, "beta": 1, "rc": 2, None: 3}[stage]
        return major, minor, patch, stage_rank, sequence

    @staticmethod
    def is_prerelease_version(value: str) -> bool:
        return bool(re.search(r"-(?:alpha|beta|rc)(?:[.-]?\d+)?$", value.strip(), re.I))

    def check(self, current_version: str = APP_VERSION) -> UpdateInfo | None:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2026-03-10",
            "User-Agent": USER_AGENT,
        }
        with httpx.Client(timeout=self.timeout, headers=headers, follow_redirects=True) as client:
            response = client.get(GITHUB_API, params={"per_page": 30})
            response.raise_for_status()
            releases = response.json()

        current_key = self.version_key(current_version)
        current_is_prerelease = self.is_prerelease_version(current_version)
        candidates: list[tuple[tuple[int, int, int, int, int], UpdateInfo]] = []
        for release in releases:
            if bool(release.get("draft")):
                continue
            prerelease = bool(release.get("prerelease"))
            # Usuários de uma versão estável não entram automaticamente em canal beta.
            # Usuários alpha/beta/rc continuam recebendo pré-lançamentos mais recentes.
            if prerelease and not current_is_prerelease:
                continue
            tag = str(release.get("tag_name") or "").strip()
            try:
                key = self.version_key(tag)
            except ValueError:
                continue
            if key <= current_key:
                continue
            asset = self._portable_asset(release.get("assets") or [])
            if asset is None:
                continue
            version = tag.lstrip("vV")
            candidates.append(
                (
                    key,
                    UpdateInfo(
                        version=version,
                        tag_name=tag,
                        prerelease=prerelease,
                        release_name=str(release.get("name") or tag),
                        html_url=str(release.get("html_url") or ""),
                        notes=str(release.get("body") or ""),
                        asset_name=str(asset.get("name") or ""),
                        asset_url=str(asset.get("browser_download_url") or ""),
                    ),
                )
            )
        if not candidates:
            return None
        candidates.sort(key=lambda pair: pair[0], reverse=True)
        return candidates[0][1]

    @staticmethod
    def _portable_asset(assets: list[dict]) -> dict | None:
        for asset in assets:
            name = str(asset.get("name") or "")
            url = str(asset.get("browser_download_url") or "")
            if name.lower().endswith(".zip") and "portable" in name.lower() and url.startswith("https://"):
                return asset
        return None

    def download(self, info: UpdateInfo) -> DownloadedUpdate:
        target_dir = self.paths.cache_dir / "updates" / info.version
        target_dir.mkdir(parents=True, exist_ok=True)
        archive_path = target_dir / info.asset_name
        partial = archive_path.with_suffix(archive_path.suffix + ".part")
        with httpx.stream(
            "GET",
            info.asset_url,
            timeout=120,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        ) as response:
            response.raise_for_status()
            with partial.open("wb") as handle:
                for chunk in response.iter_bytes():
                    handle.write(chunk)
        partial.replace(archive_path)

        staging = target_dir / "staging"
        if staging.exists():
            import shutil

            shutil.rmtree(staging)
        staging.mkdir(parents=True)
        self._safe_extract(archive_path, staging)
        payload_dir = self._resolve_payload_dir(staging)
        return DownloadedUpdate(info=info, archive_path=archive_path, staging_dir=payload_dir)


    @staticmethod
    def _resolve_payload_dir(staging: Path) -> Path:
        """Localiza a raiz real do build portátil após a extração.

        Releases antigas esperavam ``AnkiiStudio.exe`` diretamente na raiz do ZIP.
        Alguns pacotes foram publicados com uma única pasta ``AnkiiStudio/`` envolvendo
        o build. Ambos os formatos são válidos; estruturas ambíguas continuam sendo
        rejeitadas para não instalar conteúdo inesperado.
        """
        if (staging / "AnkiiStudio.exe").is_file():
            return staging

        ignored_names = {"__MACOSX", ".DS_Store", "Thumbs.db"}
        visible_entries = [
            path for path in staging.iterdir() if path.name not in ignored_names
        ]
        directories = [path for path in visible_entries if path.is_dir()]
        files = [path for path in visible_entries if path.is_file()]
        candidates = [
            path for path in directories if (path / "AnkiiStudio.exe").is_file()
        ]
        if len(candidates) == 1 and len(directories) == 1 and not files:
            return candidates[0]

        raise RuntimeError(
            "O pacote de atualização não contém um build portátil válido do AnkiiStudio "
            "na raiz nem em uma única pasta contêiner."
        )

    @staticmethod
    def _safe_extract(archive: Path, destination: Path) -> None:
        root = destination.resolve()
        with zipfile.ZipFile(archive) as package:
            for member in package.infolist():
                target = (destination / member.filename).resolve()
                try:
                    target.relative_to(root)
                except ValueError as exc:
                    raise RuntimeError("O pacote de atualização contém um caminho inválido.") from exc
            package.extractall(destination)

    def can_self_update(self) -> bool:
        return bool(getattr(sys, "frozen", False) and sys.platform == "win32")

    def schedule_install_and_restart(self, downloaded: DownloadedUpdate) -> Path:
        if not self.can_self_update():
            raise RuntimeError("A atualização automática é executada apenas na versão portátil para Windows.")

        app_dir = self.paths.app_dir.resolve()
        staging = downloaded.staging_dir.resolve()
        script_dir = Path(tempfile.gettempdir()) / "AnkiiStudioUpdater"
        script_dir.mkdir(parents=True, exist_ok=True)
        script = script_dir / f"update-{downloaded.info.version}.ps1"
        pid = os.getpid()

        def ps_quote(path: Path) -> str:
            return str(path).replace("'", "''")

        script.write_text(
            f'''$ErrorActionPreference = "Stop"\n'''
            f'''$pidToWait = {pid}\n'''
            f'''$appDir = '{ps_quote(app_dir)}'\n'''
            f'''$staging = '{ps_quote(staging)}'\n'''
            '''while (Get-Process -Id $pidToWait -ErrorAction SilentlyContinue) { Start-Sleep -Milliseconds 400 }\n'''
            '''Get-ChildItem -LiteralPath $appDir -Force | ForEach-Object {\n'''
            '''    if ($_.Name -ne 'data') { Remove-Item -LiteralPath $_.FullName -Recurse -Force }\n'''
            '''}\n'''
            '''Get-ChildItem -LiteralPath $staging -Force | ForEach-Object {\n'''
            '''    if ($_.Name -ne 'data') {\n'''
            '''        $target = Join-Path $appDir $_.Name\n'''
            '''        Copy-Item -LiteralPath $_.FullName -Destination $target -Recurse -Force\n'''
            '''    }\n'''
            '''}\n'''
            '''Start-Process -FilePath (Join-Path $appDir 'AnkiiStudio.exe')\n'''
            '''Remove-Item -LiteralPath $staging -Recurse -Force -ErrorAction SilentlyContinue\n''',
            encoding="utf-8",
        )
        subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
            ],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            close_fds=True,
        )
        return script
