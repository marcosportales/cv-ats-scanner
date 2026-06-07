import json
import re
from pathlib import Path

from app.schemas.parsed import SkillsBlock

_SKILLS_PATH = Path(__file__).resolve().parents[3] / "data" / "skills_es_en.json"
_SYNONYMS_PATH = Path(__file__).resolve().parents[3] / "data" / "synonyms.json"
_SKILLS_CACHE: list[str] | None = None
_SYNONYMS_RAW_CACHE: dict[str, list[str]] | None = None
# alias_lower → canonical display-name from skills list
_REVERSE_MAP_CACHE: dict[str, str] | None = None

_MIN_SKILL_LEN = 3
_SHORT_SKILLS: frozenset[str] = frozenset({"R", "Go", "C", "C#", "C++", "SQL", "Git"})


def _load_skills() -> list[str]:
    global _SKILLS_CACHE
    if _SKILLS_CACHE is None:
        with open(_SKILLS_PATH) as f:
            _SKILLS_CACHE = json.load(f)
    return _SKILLS_CACHE


def _load_synonyms_raw() -> dict[str, list[str]]:
    global _SYNONYMS_RAW_CACHE
    if _SYNONYMS_RAW_CACHE is None:
        with open(_SYNONYMS_PATH) as f:
            _SYNONYMS_RAW_CACHE = json.load(f)
    return _SYNONYMS_RAW_CACHE


def _get_reverse_map() -> dict[str, str]:
    """Build alias_lower → canonical_skill_display_name map (cached)."""
    global _REVERSE_MAP_CACHE
    if _REVERSE_MAP_CACHE is not None:
        return _REVERSE_MAP_CACHE

    synonyms_raw = _load_synonyms_raw()
    skills = _load_skills()
    skill_by_lower: dict[str, str] = {s.lower(): s for s in skills}
    reverse: dict[str, str] = {}
    for key, aliases in synonyms_raw.items():
        canonical_display = skill_by_lower.get(key.lower())
        if canonical_display is None:
            continue
        for alias in aliases:
            alias_lower = alias.lower()
            if len(alias_lower) >= _MIN_SKILL_LEN:
                reverse.setdefault(alias_lower, canonical_display)
    _REVERSE_MAP_CACHE = reverse
    return reverse


def _skill_pattern(skill: str) -> re.Pattern[str]:
    """Regex that matches *skill* as a whole token (word-boundary aware)."""
    escaped = re.escape(skill)
    return re.compile(rf"(?<![.\w]){escaped}(?![.\w])", re.I)


def _skill_matches(skill: str, combined: str) -> bool:
    """True if skill appears in combined text with appropriate boundary checks."""
    if len(skill) <= 4 or skill in _SHORT_SKILLS or "." in skill or "#" in skill:
        return bool(_skill_pattern(skill).search(combined))
    return skill.lower() in combined.lower()


def extract_skills_from_text(text: str, skills_section: str = "") -> SkillsBlock:
    combined = f"{text}\n{skills_section}"
    hard: list[str] = []

    # Direct match: canonical skill names
    for skill in _load_skills():
        if _skill_matches(skill, combined):
            hard.append(skill)

    # Reverse synonym lookup: alias in text → add canonical skill
    # e.g. "postgres" → "PostgreSQL", "k8s" → "Kubernetes"
    combined_lower = combined.lower()
    reverse = _get_reverse_map()
    for alias, canonical in reverse.items():
        if canonical in hard:
            continue
        if len(alias) <= 4:
            # Use word-boundary for short aliases to avoid false positives
            if re.search(rf"(?<![.\w]){re.escape(alias)}(?![.\w])", combined_lower):
                hard.append(canonical)
        elif alias in combined_lower:
            hard.append(canonical)

    soft_keywords = [
        "trabajo en equipo",
        "trabajar en equipo",
        "teamwork",
        "comunicación",
        "communication",
        "liderazgo",
        "leadership",
        "proactividad",
        "problem solving",
    ]
    soft = [s for s in soft_keywords if s in combined_lower]
    return SkillsBlock(hard=list(dict.fromkeys(hard)), soft=soft)


def collect_evidence_skills(skills: SkillsBlock, experience_bullets: list[str]) -> list[str]:
    evidence = set(skills.hard)
    combined = " ".join(experience_bullets).lower()
    for skill in skills.hard:
        if skill.lower() in combined:
            evidence.add(skill)
    for skill in _load_skills():
        if skill.lower() in combined:
            evidence.add(skill)
    return sorted(evidence)
