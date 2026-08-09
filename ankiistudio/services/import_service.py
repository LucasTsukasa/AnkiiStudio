from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from ankiistudio.models import ImportedDeck


class DeckImportService:
    MAX_AUTOMATIC_REPAIRS = 24

    @staticmethod
    def _strip_markdown_fence(text: str) -> str:
        cleaned = text.strip().lstrip("\ufeff")
        if not cleaned.startswith("```"):
            return cleaned
        lines = cleaned.splitlines()
        if lines and lines[0].lstrip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()

    @staticmethod
    def _is_escaped(text: str, index: int) -> bool:
        backslashes = 0
        cursor = index - 1
        while cursor >= 0 and text[cursor] == "\\":
            backslashes += 1
            cursor -= 1
        return backslashes % 2 == 1

    @classmethod
    def _previous_unescaped_quote(cls, text: str, before: int) -> int:
        cursor = min(before - 1, len(text) - 1)
        while cursor >= 0:
            if text[cursor] == '"' and not cls._is_escaped(text, cursor):
                return cursor
            cursor -= 1
        return -1

    @classmethod
    def _repair_common_unescaped_quotes(cls, text: str) -> str | None:
        """Corrige de forma conservadora aspas internas não escapadas em strings JSON.

        IAs externas ocasionalmente produzem trechos como
        ``"translation":"Diga "exemplo" agora"``. O decoder encerra a string na
        primeira aspa interna e acusa ``Expecting ',' delimiter`` no texto seguinte.
        Somente esse padrão conhecido é reparado; demais erros continuam sendo
        rejeitados para evitar alterações silenciosas em estruturas ambíguas.
        """
        candidate = text
        repairs = 0

        while repairs < cls.MAX_AUTOMATIC_REPAIRS:
            try:
                json.loads(candidate)
                return candidate if repairs else None
            except json.JSONDecodeError as exc:
                if exc.msg != "Expecting ',' delimiter":
                    return None
                if exc.pos >= len(candidate):
                    return None

                unexpected = candidate[exc.pos]
                if unexpected in {'"', "{", "}", "[", "]", ",", ":"}:
                    return None

                quote_index = cls._previous_unescaped_quote(candidate, exc.pos)
                if quote_index < 0:
                    return None

                between = candidate[quote_index + 1 : exc.pos]
                if "\n" in between or "\r" in between:
                    return None

                candidate = candidate[:quote_index] + "\\" + candidate[quote_index:]
                repairs += 1

        return None

    @classmethod
    def _parse_json(cls, cleaned: str) -> str:
        try:
            json.loads(cleaned)
            return cleaned
        except json.JSONDecodeError as original_exc:
            repaired = cls._repair_common_unescaped_quotes(cleaned)
            if repaired is not None:
                return repaired
            raise ValueError(
                f"JSON inválido na linha {original_exc.lineno}, coluna {original_exc.colno}: "
                f"{original_exc.msg}. Revise a resposta da IA e tente novamente."
            ) from original_exc

    @classmethod
    def from_text(cls, text: str) -> ImportedDeck:
        cleaned = cls._strip_markdown_fence(text)
        if not cleaned:
            raise ValueError("O conteúdo para importação está vazio.")

        parsed_text = cls._parse_json(cleaned)
        try:
            return ImportedDeck.model_validate_json(parsed_text)
        except ValidationError as exc:
            raise ValueError(
                f"O arquivo não segue o formato do AnkiiStudio:\n{exc}"
            ) from exc

    @classmethod
    def from_file(cls, path: Path) -> ImportedDeck:
        if path.suffix.lower() not in {".json", ".txt"}:
            raise ValueError("Selecione um arquivo .json ou .txt.")
        return cls.from_text(path.read_text(encoding="utf-8-sig"))
