"""UI text in English or Japanese.

Japanese when the language Qt reports for Painter (its UI language, or the OS
language) is Japanese; English otherwise.
"""

_lang = None


def _detect() -> str:
    try:
        from PySide6 import QtCore  # pylint: disable=import-outside-toplevel
        return "ja" if QtCore.QLocale().language() == QtCore.QLocale.Language.Japanese else "en"
    except Exception:  # pylint: disable=broad-except
        return "en"


def lang() -> str:
    global _lang  # pylint: disable=global-statement
    if _lang is None:
        _lang = _detect()
    return _lang


def set_lang(code: str) -> None:
    """Force "en" or "ja" (used by tests)."""
    global _lang  # pylint: disable=global-statement
    _lang = code


def tr(en: str, ja: str) -> str:
    return ja if lang() == "ja" else en
