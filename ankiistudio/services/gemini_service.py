from __future__ import annotations

from google import genai

from ankiistudio.models import ImportedDeck


class GeminiContentService:
    def __init__(self, api_key: str, model: str) -> None:
        if not api_key.strip():
            raise ValueError("Informe a chave da Gemini API nas Configurações.")
        self.client = genai.Client(api_key=api_key.strip())
        self.model = model.strip()

    def generate_deck(self, prompt: str) -> ImportedDeck:
        interaction = self.client.interactions.create(
            model=self.model,
            input=prompt,
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": ImportedDeck.model_json_schema(),
            },
        )
        if not interaction.output_text:
            raise RuntimeError("A Gemini API não retornou conteúdo textual.")
        return ImportedDeck.model_validate_json(interaction.output_text)
