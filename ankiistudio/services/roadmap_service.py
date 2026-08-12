from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from ankiistudio.constants import APP_VERSION

ROADMAP_REMOTE_URL = (
    "https://api.github.com/repos/LucasTsukasa/AnkiiStudio/contents/"
    "ankiistudio/resources/roadmap.json"
)
ROADMAP_USER_AGENT = (
    f"AnkiiStudio/{APP_VERSION} (https://github.com/LucasTsukasa/AnkiiStudio)"
)


class RoadmapService:
    """Carrega o roadmap embutido e, quando possível, uma cópia mais recente do GitHub."""

    def __init__(self, local_path: Path, cache_path: Path, timeout: float = 8.0) -> None:
        self.local_path = local_path
        self.cache_path = cache_path
        self.timeout = timeout

    def load_available(self) -> dict[str, Any]:
        """Retorna a cópia local/cache mais recente sem depender de rede."""
        candidates: list[tuple[str, int, dict[str, Any]]] = []
        for priority, path in ((1, self.cache_path), (0, self.local_path)):
            try:
                payload = self._read_and_validate(path)
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            candidates.append((str(payload.get("updated_at") or ""), priority, payload))
        if not candidates:
            return {"schema_version": 2, "updated_at": "", "items": []}
        candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return candidates[0][2]

    def fetch_remote(self) -> dict[str, Any]:
        """Baixa, valida e armazena a versão pública mais recente do roadmap."""
        headers = {
            "Accept": "application/vnd.github.raw+json",
            "X-GitHub-Api-Version": "2026-03-10",
            "User-Agent": ROADMAP_USER_AGENT,
        }
        with httpx.Client(timeout=self.timeout, headers=headers, follow_redirects=True) as client:
            response = client.get(ROADMAP_REMOTE_URL)
            response.raise_for_status()
            payload = response.json()
        normalized = self._validate(payload)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.cache_path.with_suffix(self.cache_path.suffix + ".part")
        temporary.write_text(
            json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.cache_path)
        return normalized

    @classmethod
    def _read_and_validate(cls, path: Path) -> dict[str, Any]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls._validate(payload)

    @staticmethod
    def _validate(payload: object) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("Roadmap inválido: a raiz deve ser um objeto JSON.")
        schema_version = payload.get("schema_version")
        if schema_version != 2:
            raise ValueError("Roadmap inválido: versão de schema não suportada.")
        items = payload.get("items")
        if not isinstance(items, list):
            raise ValueError("Roadmap inválido: 'items' deve ser uma lista.")

        normalized_items: list[dict[str, Any]] = []
        allowed_status = {"completed", "in_progress", "planned"}
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValueError(f"Roadmap inválido: item {index + 1} não é um objeto.")
            status = str(item.get("status") or "").strip()
            if status not in allowed_status:
                raise ValueError(f"Roadmap inválido: status desconhecido no item {index + 1}.")
            title = item.get("title")
            if not isinstance(title, str) or not title.strip():
                raise ValueError(f"Roadmap inválido: título ausente no item {index + 1}.")
            description = item.get("description") or ""
            if not isinstance(description, str):
                raise ValueError(f"Roadmap inválido: descrição inválida no item {index + 1}.")
            details = item.get("details") or []
            if not isinstance(details, list):
                raise ValueError(f"Roadmap inválido: lista de detalhes inválida no item {index + 1}.")

            normalized_items.append(
                {
                    "id": str(item.get("id") or f"item-{index + 1}"),
                    "status": status,
                    "current": bool(item.get("current", False)),
                    "title": title.strip(),
                    "description": description.strip(),
                    "details": [str(value) for value in details if str(value).strip()],
                }
            )

        return {
            "schema_version": 2,
            "updated_at": str(payload.get("updated_at") or ""),
            "items": normalized_items,
        }
