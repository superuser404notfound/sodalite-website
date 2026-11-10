"""The 26 app languages, their App Store screenshot folders, and the browser-language resolver.

The redirect script on / runs the same algorithm in JS over the same table (rendered by build.py);
check.py verifies both stay in step.
"""

LOCALES = [
    "en", "cs", "da", "de", "el", "es", "fi", "fr", "hr", "hu", "it", "ja", "ko",
    "nb", "nl", "pl", "pt-BR", "pt-PT", "ro", "ru", "sk", "sv", "tr", "uk", "zh-Hans", "zh-Hant",
]

ASC_FOLDER = {"en": "en-US", "de": "de-DE", "es": "es-ES", "fr": "fr-FR", "nl": "nl-NL", "nb": "no"}

ALIASES = {
    "pt": "pt-br", "zh": "zh-hans", "zh-cn": "zh-hans", "zh-sg": "zh-hans",
    "zh-tw": "zh-hant", "zh-hk": "zh-hant", "zh-mo": "zh-hant", "no": "nb", "nn": "nb",
}

ENDONYMS = {
    "en": "English", "cs": "Čeština", "da": "Dansk", "de": "Deutsch", "el": "Ελληνικά", "es": "Español",
    "fi": "Suomi", "fr": "Français", "hr": "Hrvatski", "hu": "Magyar", "it": "Italiano", "ja": "日本語",
    "ko": "한국어", "nb": "Norsk bokmål", "nl": "Nederlands", "pl": "Polski", "pt-BR": "Português (Brasil)",
    "pt-PT": "Português (Portugal)", "ro": "Română", "ru": "Русский", "sk": "Slovenčina", "sv": "Svenska",
    "tr": "Türkçe", "uk": "Українська", "zh-Hans": "简体中文", "zh-Hant": "繁體中文",
}


def asc_folder(code):
    return ASC_FOLDER.get(code, code)


def resolve_language(tag):
    """Browser language tag -> one of LOCALES. Longest matching prefix wins, unknown -> en."""
    by_lower = {c.lower(): c for c in LOCALES}
    parts = tag.lower().replace("_", "-").split("-") if tag else []
    for i in range(len(parts), 0, -1):
        cand = "-".join(parts[:i])
        if cand in by_lower:
            return by_lower[cand]
        if cand in ALIASES:
            return by_lower[ALIASES[cand]]
    return "en"
