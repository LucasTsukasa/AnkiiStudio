from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from ankiistudio.database import Database


VOICEVOX_DEFAULTS_KEY = "voicevox_default_settings_v1"


@dataclass
class VoicevoxSettingsData:
    style_id: int = 0
    style_label: str = ""
    speed_scale: float = 1.0
    pitch_scale: float = 0.0
    intonation_scale: float = 1.0
    volume_scale: float = 1.0
    pause_length_scale: float = 1.0

    # aliases esperados por VoicevoxSettingsDialog
    @property
    def voicevox_speed_scale(self) -> float:
        return self.speed_scale

    @voicevox_speed_scale.setter
    def voicevox_speed_scale(self, value: float) -> None:
        self.speed_scale = float(value)

    @property
    def voicevox_pitch_scale(self) -> float:
        return self.pitch_scale

    @voicevox_pitch_scale.setter
    def voicevox_pitch_scale(self, value: float) -> None:
        self.pitch_scale = float(value)

    @property
    def voicevox_intonation_scale(self) -> float:
        return self.intonation_scale

    @voicevox_intonation_scale.setter
    def voicevox_intonation_scale(self, value: float) -> None:
        self.intonation_scale = float(value)

    @property
    def voicevox_volume_scale(self) -> float:
        return self.volume_scale

    @voicevox_volume_scale.setter
    def voicevox_volume_scale(self, value: float) -> None:
        self.volume_scale = float(value)

    @property
    def voicevox_pause_length_scale(self) -> float:
        return self.pause_length_scale

    @voicevox_pause_length_scale.setter
    def voicevox_pause_length_scale(self, value: float) -> None:
        self.pause_length_scale = float(value)


def load_voicevox_defaults(database: Database) -> VoicevoxSettingsData:
    raw = database.get_setting(VOICEVOX_DEFAULTS_KEY, "")
    if not raw:
        return VoicevoxSettingsData()
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            return VoicevoxSettingsData()
        def number(name: str, default: float) -> float:
            value = payload.get(name, default)
            return float(default if value is None else value)

        return VoicevoxSettingsData(
            style_id=int(payload.get("style_id", 0) or 0),
            style_label=str(payload.get("style_label") or ""),
            speed_scale=number("speed_scale", 1.0),
            pitch_scale=number("pitch_scale", 0.0),
            intonation_scale=number("intonation_scale", 1.0),
            volume_scale=number("volume_scale", 1.0),
            pause_length_scale=number("pause_length_scale", 1.0),
        )
    except Exception:
        return VoicevoxSettingsData()


def save_voicevox_defaults(database: Database, settings: VoicevoxSettingsData) -> None:
    database.set_setting(VOICEVOX_DEFAULTS_KEY, json.dumps(asdict(settings), ensure_ascii=False))


def preview_text(language: str) -> str:
    samples = {
        "ja": "こんにちは。音声テストです。",
        "en": "Hello. This is a voice preview.",
        "es": "Hola. Esta es una prueba de voz.",
        "pt": "Olá. Este é um teste de voz.",
        "ko": "안녕하세요. 음성 테스트입니다.",
        "fr": "Bonjour. Ceci est un test de voix.",
        "de": "Hallo. Dies ist ein Sprachtest.",
        "it": "Ciao. Questa è una prova vocale.",
    }
    return samples.get(language, "Hello. This is a voice preview.")
