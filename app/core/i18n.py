import json
from pathlib import Path
from fastapi import Request

DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = {"en", "hi", "ja"}
CONTENT_TRANSLATION_LANGUAGES = SUPPORTED_LANGUAGES - {DEFAULT_LANGUAGE}

BASE_DIR = Path(__file__).resolve().parent.parent
LOCALES_DIR = BASE_DIR / "locales"

_translations: dict[str, dict[str, str]] = {}


def load_translations() -> None:
    for lang in SUPPORTED_LANGUAGES:
        file_path = LOCALES_DIR / f"{lang}.json"

        if not file_path.exists():
            _translations[lang] = {}
            continue

        with file_path.open("r", encoding="utf-8") as file:
            _translations[lang] = json.load(file)


def get_language(request: Request) -> str:
    accept_language = request.headers.get("accept-language", DEFAULT_LANGUAGE)

    for part in accept_language.split(","):
        lang = part.split(";")[0].strip().lower()
        base_lang = lang.split("-")[0]

        if base_lang in SUPPORTED_LANGUAGES:
            return base_lang

    return DEFAULT_LANGUAGE


def t(request: Request, key: str, **kwargs) -> str:
    if not _translations:
        load_translations()

    lang = get_language(request)

    message = (
        _translations.get(lang, {}).get(key)
        or _translations.get(DEFAULT_LANGUAGE, {}).get(key)
        or key
    )

    if kwargs:
        try:
            return message.format(**kwargs)
        except (KeyError, ValueError):
            return message

    return message
