from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import ValidationError

from ankiistudio.models import ImportedDeck


class DeckImportService:
    MAX_AUTOMATIC_REPAIRS = 128

    @staticmethod
    def _strip_bom_and_whitespace(text: str) -> str:
        return text.strip().lstrip("\ufeff").strip()

    @classmethod
    def _extract_json_payload(cls, text: str) -> str:
        """Extrai um único objeto JSON de wrappers comuns de respostas de IA.

        A extração só remove invólucros claros (fence Markdown ou texto antes/depois
        de um único objeto). Estruturas ambíguas continuam sendo rejeitadas mais
        adiante pelo parser, sem inventar conteúdo.
        """
        cleaned = cls._strip_bom_and_whitespace(text)
        if not cleaned:
            return cleaned

        fenced = re.findall(
            r"```(?:json)?\s*(\{.*?\})\s*```",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if len(fenced) == 1:
            return fenced[0].strip()
        if len(fenced) > 1:
            raise ValueError(
                "A resposta contém mais de um bloco JSON. Mantenha somente um objeto para importar."
            )

        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines and lines[0].lstrip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        if cleaned.startswith("{") and cleaned.endswith("}"):
            return cleaned

        first = cleaned.find("{")
        last = cleaned.rfind("}")
        if first >= 0 and last > first:
            return cleaned[first : last + 1].strip()
        return cleaned

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
    def _remove_trailing_commas(cls, text: str) -> str:
        """Remove apenas vírgulas estruturais imediatamente antes de } ou ]."""
        result: list[str] = []
        in_string = False
        index = 0
        length = len(text)
        while index < length:
            char = text[index]
            if char == '"' and not cls._is_escaped(text, index):
                in_string = not in_string
                result.append(char)
                index += 1
                continue
            if char == "," and not in_string:
                cursor = index + 1
                while cursor < length and text[cursor].isspace():
                    cursor += 1
                if cursor < length and text[cursor] in "}]":
                    index += 1
                    continue
            result.append(char)
            index += 1
        return "".join(result)

    @staticmethod
    def _repair_simple_doubled_string_delimiters(text: str) -> str:
        """Normaliza valores simples emitidos como ``""texto""``.

        O reparo é restrito a valores de objeto sem aspas/barras internas e cujo
        próximo token seja vírgula ou fechamento, evitando adivinhar strings
        complexas ou estruturas ambíguas.
        """
        pattern = re.compile(
            r'(:\s*)""([^"\\\r\n]*)""(?=\s*[,}\]])',
            flags=re.DOTALL,
        )
        return pattern.sub(lambda match: f'{match.group(1)}"{match.group(2)}"', text)

    @staticmethod
    def _next_nonspace(text: str, start: int) -> int:
        cursor = start
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1
        return cursor

    @classmethod
    def _repair_unescaped_string_quotes(cls, text: str) -> str | None:
        """Escapa aspas internas reconhecíveis sem tentar reconstruir a estrutura.

        O scanner distingue chaves de valores e só considera uma aspa como
        delimitador de fechamento quando o token seguinte faz sentido naquele
        contexto JSON. Isso cobre frases como ``significa "laranja", a fruta``
        sem confundir a vírgula natural da frase com a vírgula entre propriedades.
        """
        result: list[str] = []
        stack: list[str] = []
        in_string = False
        string_role = "value"
        changed = False
        index = 0

        def previous_nonspace() -> str:
            for char in reversed(result):
                if not char.isspace():
                    return char
            return ""

        while index < len(text):
            char = text[index]
            if char != '"' or cls._is_escaped(text, index):
                if not in_string:
                    if char in "{[":
                        stack.append(char)
                    elif char in "}]" and stack:
                        stack.pop()
                result.append(char)
                index += 1
                continue

            if not in_string:
                top = stack[-1] if stack else ""
                prev = previous_nonspace()
                string_role = "key" if top == "{" and prev in {"{", ","} else (
                    "array_value" if top == "[" else "object_value" if top == "{" else "value"
                )
                in_string = True
                result.append(char)
                index += 1
                continue

            next_index = cls._next_nonspace(text, index + 1)
            next_char = text[next_index] if next_index < len(text) else ""
            closes = False
            if string_role == "key":
                closes = next_char == ":"
            elif not next_char or next_char in "}]":
                closes = True
            elif next_char == ",":
                after_comma = cls._next_nonspace(text, next_index + 1)
                following = text[after_comma] if after_comma < len(text) else ""
                if string_role == "object_value":
                    closes = following in {'"', '}'} or not following
                elif string_role == "array_value":
                    closes = (
                        following in {'"', '{', '[', ']', '-'}
                        or following.isdigit()
                        or following in {'t', 'f', 'n'}
                        or not following
                    )
                else:
                    closes = True

            if closes:
                in_string = False
                result.append(char)
            else:
                result.append('\\"')
                changed = True
            index += 1

        return "".join(result) if changed else None

    @classmethod
    def _repair_common_unescaped_quotes(cls, text: str) -> str | None:
        """Corrige conservadoramente aspas internas não escapadas em strings JSON.

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
                if unexpected in {"{", "}", "[", "]", ",", ":"}:
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

    @staticmethod
    def _format_decode_error(text: str, exc: json.JSONDecodeError) -> str:
        start = max(0, exc.pos - 55)
        end = min(len(text), exc.pos + 55)
        snippet = text[start:end].replace("\r", " ").replace("\n", " ").strip()
        if start > 0:
            snippet = "…" + snippet
        if end < len(text):
            snippet += "…"
        return (
            f"JSON inválido na linha {exc.lineno}, coluna {exc.colno}: {exc.msg}. "
            f"Perto de: {snippet!r}. Revise a resposta da IA e tente novamente."
        )

    @classmethod
    def _parse_json(cls, cleaned: str) -> str:
        try:
            json.loads(cleaned)
            return cleaned
        except json.JSONDecodeError:
            pass

        candidate = cls._remove_trailing_commas(cleaned)
        candidate = cls._repair_simple_doubled_string_delimiters(candidate)
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass

        repaired = cls._repair_unescaped_string_quotes(candidate)
        if repaired is not None:
            try:
                json.loads(repaired)
                return repaired
            except json.JSONDecodeError:
                candidate = repaired

        repaired = cls._repair_common_unescaped_quotes(candidate)
        if repaired is not None:
            return repaired

        try:
            json.loads(candidate)
        except json.JSONDecodeError as final_exc:
            raise ValueError(cls._format_decode_error(candidate, final_exc)) from final_exc
        return candidate

    @classmethod
    def from_text(cls, text: str) -> ImportedDeck:
        cleaned = cls._extract_json_payload(text)
        if not cleaned:
            raise ValueError("O conteúdo para importação está vazio.")

        parsed_text = cls._parse_json(cleaned)
        try:
            return ImportedDeck.model_validate_json(parsed_text)
        except ValidationError as exc:
            raise ValueError(
                f"O arquivo não segue o formato do BenkyouStudio:\n{exc}"
            ) from exc

    @classmethod
    def from_file(cls, path: Path) -> ImportedDeck:
        if path.suffix.lower() not in {".json", ".txt"}:
            raise ValueError("Selecione um arquivo .json ou .txt.")
        return cls.from_text(path.read_text(encoding="utf-8-sig"))
