import json
from pathlib import Path
from fastapi import Request

DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = {"en", "hi", "ja"}

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

    lang = accept_language.split(",")[0].split("-")[0].strip().lower()

    if lang not in SUPPORTED_LANGUAGES:
        return DEFAULT_LANGUAGE

    return lang


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
        return message.format(**kwargs)

    return message