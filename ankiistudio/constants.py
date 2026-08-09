from __future__ import annotations

import re
import unicodedata

APP_NAME = "AnkiiStudio"
APP_VERSION = "0.10.0"
ORGANIZATION_NAME = "LucasTsukasa"
GITHUB_URL = "https://github.com/LucasTsukasa"
DATABASE_FILENAME = "ankiistudio.db"

DEFAULT_GEMINI_TEXT_MODEL = "gemini-3.6-flash"
DEFAULT_GEMINI_TTS_MODEL = "auto"
GEMINI_TTS_MODEL_OPTIONS = [
    ("auto", "Automático — recomendado"),
    ("gemini-3.1-flash-tts-preview", "Gemini 3.1 Flash TTS Preview"),
    ("gemini-2.5-flash-preview-tts", "Gemini 2.5 Flash Preview TTS"),
    ("gemini-2.5-pro-preview-tts", "Gemini 2.5 Pro Preview TTS — pago"),
]
GEMINI_TTS_AUTO_MODELS = [
    "gemini-3.1-flash-tts-preview",
    "gemini-2.5-flash-preview-tts",
]
DEFAULT_GEMINI_VOICE = "Kore"
DEFAULT_ELEVEN_MODEL = "eleven_multilingual_v2"
DEFAULT_VOICEVOX_URL = "http://127.0.0.1:50021"
DEFAULT_VOICEVOX_SPEAKER_ID = 0

LANGUAGE_LABELS: dict[str, str] = {
    'ja': 'Japonês',
    'en': 'Inglês',
    'es': 'Espanhol',
    'ko': 'Coreano',
    'pt': 'Português',
    'fr': 'Francês',
    'de': 'Alemão',
    'it': 'Italiano',
    'zh': 'Chinês',
    'ru': 'Russo',
    'ar': 'Árabe',
    'hi': 'Hindi',
    'ab': 'Abcázio',
    'aa': 'Afar',
    'af': 'Africâner',
    'ay': 'Aimará',
    'ak': 'Akan',
    'sq': 'Albanês',
    'am': 'Amárico',
    'an': 'Aragonês',
    'hy': 'Armênio',
    'as': 'Assamês',
    'av': 'Avárico',
    'ae': 'Avéstico',
    'az': 'Azerbaijano',
    'bm': 'Bambara',
    'eu': 'Basco',
    'ba': 'Bashkir',
    'bn': 'Bengali',
    'be': 'Bielorrusso',
    'my': 'Birmanês',
    'bi': 'Bislamá',
    'bs': 'Bósnio',
    'br': 'Bretão',
    'bg': 'Búlgaro',
    'kn': 'Canarim',
    'kr': 'Canúri',
    'ca': 'Catalão',
    'ks': 'Caxemira',
    'kk': 'Cazaque',
    'ch': 'Chamorro',
    'ce': 'Checheno',
    'si': 'Cingalês',
    'kg': 'Congolês',
    'kw': 'Córnico',
    'co': 'Corso',
    'cr': 'Cree',
    'hr': 'Croata',
    'kj': 'Cuanhama',
    'ku': 'Curdo',
    'da': 'Dinamarquês',
    'dv': 'Divehi',
    'ng': 'Dongo',
    'dz': 'Dzonga',
    'cu': 'Eslavo Eclesiástico',
    'sk': 'Eslovaco',
    'sl': 'Esloveno',
    'eo': 'Esperanto',
    'et': 'Estoniano',
    'ee': 'Ewe',
    'fo': 'Feroês',
    'fj': 'Fijiano',
    'fi': 'Finlandês',
    'fy': 'Frísio Ocidental',
    'ff': 'Fula',
    'gd': 'Gaélico Escocês',
    'gl': 'Galego',
    'cy': 'Galês',
    'ka': 'Georgiano',
    'el': 'Grego',
    'kl': 'Groenlandês',
    'gn': 'Guarani',
    'gu': 'Guzerate',
    'ht': 'Haitiano',
    'ha': 'Hauçá',
    'he': 'Hebraico',
    'hz': 'Herero',
    'ho': 'Hiri Motu',
    'nl': 'Holandês',
    'hu': 'Húngaro',
    'io': 'Ido',
    'ig': 'Igbo',
    'yi': 'Iídiche',
    'id': 'Indonésio',
    'ia': 'Interlíngua',
    'ie': 'Interlingue',
    'iu': 'Inuktitut',
    'ik': 'Inupiaque',
    'yo': 'Iorubá',
    'ga': 'Irlandês',
    'is': 'Islandês',
    'jv': 'Javanês',
    'km': 'Khmer',
    'kv': 'Komi',
    'lo': 'Laosiano',
    'la': 'Latim',
    'lv': 'Letão',
    'li': 'Limburguês',
    'ln': 'Lingala',
    'lt': 'Lituano',
    'lu': 'Luba-Catanga',
    'lg': 'Luganda',
    'lb': 'Luxemburguês',
    'mk': 'Macedônio',
    'ml': 'Malaiala',
    'ms': 'Malaio',
    'mg': 'Malgaxe',
    'mt': 'Maltês',
    'gv': 'Manx',
    'mi': 'Maori',
    'mr': 'Marati',
    'mh': 'Marshalês',
    'mn': 'Mongol',
    'na': 'Nauruano',
    'nv': 'Navajo',
    'nd': 'Ndebele do Norte',
    'nr': 'Ndebele do Sul',
    'ne': 'Nepalês',
    'ny': 'Nianja',
    'no': 'Norueguês',
    'nb': 'Norueguês Bokmål',
    'nn': 'Norueguês Nynorsk',
    'oc': 'Occitânico',
    'oj': 'Ojibwa',
    'or': 'Oriá',
    'om': 'Oromo',
    'os': 'Osseto',
    'pi': 'Páli',
    'pa': 'Panjabi',
    'ps': 'Pashto',
    'fa': 'Persa',
    'pl': 'Polonês',
    'qu': 'Quíchua',
    'ki': 'Quicuio',
    'rw': 'Quiniaruanda',
    'ky': 'Quirguiz',
    'rm': 'Romanche',
    'ro': 'Romeno',
    'rn': 'Rundi',
    'se': 'Sami Setentrional',
    'sm': 'Samoano',
    'sg': 'Sango',
    'sa': 'Sânscrito',
    'sc': 'Sardo',
    'sr': 'Sérvio',
    'sh': 'Servo-croata',
    'sd': 'Sindi',
    'so': 'Somali',
    'st': 'Soto do Sul',
    'sw': 'Suaíli',
    'ss': 'Suázi',
    'sv': 'Sueco',
    'su': 'Sundanês',
    'tg': 'Tadjique',
    'tl': 'Tagalo',
    'th': 'Tailandês',
    'ty': 'Taitiano',
    'ta': 'Tâmil',
    'tt': 'Tártaro',
    'cs': 'Tcheco',
    'cv': 'Tchuvache',
    'te': 'Télugo',
    'bo': 'Tibetano',
    'ti': 'Tigrínia',
    'to': 'Tonganês',
    'ts': 'Tsonga',
    'tn': 'Tswana',
    'tr': 'Turco',
    'tk': 'Turcomeno',
    'tw': 'Twi',
    'uk': 'Ucraniano',
    'ug': 'Uigur',
    'wo': 'Uolofe',
    'ur': 'Urdu',
    'uz': 'Uzbeque',
    'wa': 'Valão',
    've': 'Venda',
    'vi': 'Vietnamita',
    'vo': 'Volapuque',
    'xh': 'Xhosa',
    'sn': 'Xona',
    'ii': 'Yi de Sichuan',
    'za': 'Zhuang',
    'zu': 'Zulu',
}

DEFAULT_LANGUAGE_CODE = "ja"

def _language_lookup_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).casefold().strip()


_LANGUAGE_LABEL_TO_CODE = {
    _language_lookup_key(label): code for code, label in LANGUAGE_LABELS.items()
}
_LANGUAGE_LABEL_TO_CODE.update({
    "japanese": "ja", "english": "en", "spanish": "es", "korean": "ko",
    "portuguese": "pt", "french": "fr", "german": "de", "italian": "it",
    "chinese": "zh", "russian": "ru", "arabic": "ar",
})


def normalize_language_code(value: str) -> str:
    """Normaliza nomes conhecidos e aceita códigos ISO/BCP-47 sem limitar o projeto a quatro idiomas."""
    raw = str(value or "").strip().replace("_", "-")
    if not raw:
        return DEFAULT_LANGUAGE_CODE
    lowered = raw.casefold()
    if lowered in LANGUAGE_LABELS:
        return lowered
    by_label = _LANGUAGE_LABEL_TO_CODE.get(_language_lookup_key(raw))
    if by_label:
        return by_label
    if re.fullmatch(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", raw):
        return lowered
    raise ValueError("Informe um idioma válido ou um código ISO/BCP-47.")


def language_label(code: str) -> str:
    normalized = normalize_language_code(code)
    return LANGUAGE_LABELS.get(normalized, normalized)

# Componentes que realmente fazem parte da apresentação do flashcard.
# Campos auxiliares continuam existindo internamente para compatibilidade/importação,
# mas não poluem mais o editor de estrutura.
COMPONENT_LABELS: dict[str, str] = {
    "image": "Imagem",
    "word": "Conteúdo principal",
    "reading": "Leitura",
    "romanization": "Romaji / Romanização",
    "translation": "Tradução",
    "audio": "Áudio",
    "example": "Exemplo",
    "explanation": "Explicação",
    "mnemonic": "Mnemônico",
}

# Componentes legados são normalizados ao carregar projetos antigos.
LEGACY_COMPONENT_ALIASES: dict[str, str | None] = {
    "word_audio": "audio",
    "sentence_audio": "audio",
    "example_reading": "example",
    "example_translation": "example",
    "part_of_speech": None,
    "level": None,
    "tags": None,
}

DEFAULT_FRONT_COMPONENTS = ["image", "word"]
DEFAULT_BACK_COMPONENTS = ["translation", "audio", "example", "explanation"]

# Apenas estes modelos são padrão. Personalizado é sempre o primeiro.
TEMPLATE_LABELS: dict[str, str] = {
    "custom": "Personalizado",
    "hiragana": "Hiragana",
    "katakana": "Katakana",
    "basic_phrases": "Frases Básicas",
}

TEMPLATES_BY_LANGUAGE: dict[str, list[str]] = {
    "ja": ["custom", "hiragana", "katakana", "basic_phrases"],
}

TEMPLATE_DEFAULT_STRUCTURES: dict[str, tuple[list[str], list[str]]] = {
    "hiragana": (["word"], ["romanization", "translation", "explanation"]),
    "katakana": (["word"], ["romanization", "translation", "explanation"]),
    "basic_phrases": (["word"], ["romanization", "translation", "explanation"]),
    "custom": (list(DEFAULT_FRONT_COMPONENTS), list(DEFAULT_BACK_COMPONENTS)),
}

TEMPLATE_SECTIONS: dict[str, list[str]] = {
    "hiragana": [
        "Silabário",
        "Dakuten e Handakuten",
        "Yōon",
        "Sokuon",
        "Vogais Longas",
        "Partículas com Leitura Especial",
        "Caracteres Parecidos",
        "Palavras",
        "Revisão",
    ],
    "katakana": [
        "Silabário",
        "Dakuten e Handakuten",
        "Yōon",
        "Sokuon",
        "Prolongador Vocálico",
        "Sons Estrangeiros",
        "Caracteres Parecidos",
        "Palavras",
        "Revisão",
    ],
    "basic_phrases": [
        "Saudações",
        "Apresentações",
        "Educação e Cortesia",
        "Agradecimentos e Desculpas",
        "Compreensão e Comunicação",
        "Conversa Cotidiana",
        "Casa e Rotina",
        "Escola e Estudos",
        "Compras",
        "Restaurante",
        "Konbini",
        "Transporte",
        "Direções",
        "Horários e Datas",
        "Pedindo Permissão",
        "Hotel e Viagem",
        "Emergências",
        "Conversação Casual",
        "Revisão",
    ],
}

AUDIO_PROVIDER_LABELS: dict[str, str] = {
    "voicevox": "VOICEVOX — recomendado para japonês",
    "wikimedia": "Wikimedia Commons — voz humana quando disponível",
    "gemini": "Gemini TTS",
    "elevenlabs": "ElevenLabs",
}

DEFAULT_AUDIO_PROVIDERS = ["wikimedia", "voicevox", "gemini", "elevenlabs"]
