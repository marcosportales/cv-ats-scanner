import re

from app.schemas.parsed import LanguageItem

CEFR_LEVELS: dict[str, int] = {
    "a1": 1,
    "a2": 2,
    "b1": 3,
    "b2": 4,
    "c1": 5,
    "c2": 6,
    "basic": 2,
    "intermediate": 3,
    "advanced": 5,
    "fluent": 5,
    "fluido": 5,
    "native": 6,
    "nativo": 6,
    "bilingual": 6,
    "bilingue": 6,
}

LANGUAGE_ALIASES: dict[str, str] = {
    "english": "english",
    "ingles": "english",
    "inglés": "english",
    "spanish": "spanish",
    "espanol": "spanish",
    "español": "spanish",
    "french": "french",
    "frances": "french",
    "francés": "french",
    "german": "german",
    "aleman": "german",
    "alemán": "german",
    "portuguese": "portuguese",
    "portugues": "portuguese",
    "portugués": "portuguese",
    "italian": "italian",
    "italiano": "italian",
    "catalan": "catalan",
    "catalán": "catalan",
}

LANGUAGE_DISPLAY_NAMES: dict[str, str] = {
    "english": "English",
    "spanish": "Spanish",
    "french": "French",
    "german": "German",
    "portuguese": "Portuguese",
    "italian": "Italian",
    "catalan": "Catalan",
}

_LANG_NAMES = (
    r"english|ingles|inglés|spanish|español|espanol|french|francés|frances|"
    r"german|alemán|aleman|portuguese|portugués|portugues|italian|italiano|catalan|catalán"
)
_LEVEL_NAMES = (
    r"a1|a2|b1|b2|c1|c2|basic|intermediate|advanced|fluent|fluido|native|nativo|bilingual|bilingue"
)

LEVEL_RE = re.compile(rf"\b({_LEVEL_NAMES})\b", re.I)

LANGUAGE_LINE_RE = re.compile(
    rf"\b({_LANG_NAMES})\b(?:\s*[\(\[:,\-]\s*([^\)\]\n,]{{1,30}}))?",
    re.I,
)

LANG_THEN_LEVEL_RE = re.compile(rf"\b({_LANG_NAMES})\s+({_LEVEL_NAMES})\b", re.I)

LEVEL_THEN_LANG_RE = re.compile(rf"\b({_LEVEL_NAMES})\s+({_LANG_NAMES})\b", re.I)

COMMA_SEPARATED_LANG_RE = re.compile(
    rf"\b({_LANG_NAMES})\s*\(\s*({_LEVEL_NAMES})\s*\)",
    re.I,
)


def display_language_name(name: str) -> str:
    canonical = _canonical_language(name)
    return LANGUAGE_DISPLAY_NAMES.get(canonical, name.title())


def _canonical_language(name: str) -> str:
    return LANGUAGE_ALIASES.get(name.lower().strip(), name.lower().strip())


def _parse_level(raw: str | None) -> str | None:
    if not raw:
        return None
    match = LEVEL_RE.search(raw)
    return match.group(1).lower() if match else None


def level_rank(level: str | None) -> int | None:
    if not level:
        return None
    return CEFR_LEVELS.get(level.lower())


def _store_language(
    found: dict[str, LanguageItem],
    name: str,
    level: str | None,
) -> None:
    canonical = _canonical_language(name)
    parsed_level = _parse_level(level) if level else None
    if canonical not in found or (parsed_level and not found[canonical].level):
        found[canonical] = LanguageItem(name=canonical, level=parsed_level)


def extract_languages(text: str, languages_section: str = "") -> list[LanguageItem]:
    combined = f"{languages_section}\n{text}"
    found: dict[str, LanguageItem] = {}

    for match in LANGUAGE_LINE_RE.finditer(combined):
        _store_language(found, match.group(1), match.group(2))

    for match in COMMA_SEPARATED_LANG_RE.finditer(combined):
        _store_language(found, match.group(1), match.group(2))

    for match in LANG_THEN_LEVEL_RE.finditer(combined):
        _store_language(found, match.group(1), match.group(2))

    for match in LEVEL_THEN_LANG_RE.finditer(combined):
        _store_language(found, match.group(2), match.group(1))

    for line in combined.split("\n"):
        stripped = line.strip()
        if not stripped or len(stripped) > 120:
            continue
        for alias, canonical in LANGUAGE_ALIASES.items():
            if re.search(rf"\b{re.escape(alias)}\b", stripped, re.I):
                level = _parse_level(stripped)
                if canonical not in found or (level and not found[canonical].level):
                    found[canonical] = LanguageItem(name=canonical, level=level)

    return list(found.values())


def extract_required_languages(job_text: str) -> list[LanguageItem]:
    """Extract language requirements from a job description."""
    requirements: list[LanguageItem] = []
    seen: set[tuple[str, str | None]] = set()
    patterns = [
        re.compile(
            rf"\b({_LANG_NAMES})\b[^.\n]{{0,25}}\b({_LEVEL_NAMES})\b",
            re.I,
        ),
        re.compile(
            rf"\b({_LEVEL_NAMES})\b[^.\n]{{0,25}}\b({_LANG_NAMES})\b",
            re.I,
        ),
    ]
    for pattern in patterns:
        for match in pattern.finditer(job_text):
            groups = [g for g in match.groups() if g]
            if len(groups) < 2:
                continue
            lang_raw, level_raw = groups[0], groups[1]
            if level_raw.lower() in CEFR_LEVELS:
                name, level = lang_raw, level_raw
            else:
                name, level = level_raw, lang_raw
            canonical = _canonical_language(name)
            parsed_level = _parse_level(level)
            key = (canonical, parsed_level)
            if key in seen:
                continue
            seen.add(key)
            requirements.append(LanguageItem(name=canonical, level=parsed_level))
    return requirements
