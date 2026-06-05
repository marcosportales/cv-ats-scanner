import json
from pathlib import Path

from app.schemas.parsed import SkillsBlock

_SKILLS_PATH = Path(__file__).resolve().parents[3] / "data" / "skills_es_en.json"
_SKILLS_CACHE: list[str] | None = None


def _load_skills() -> list[str]:
    global _SKILLS_CACHE
    if _SKILLS_CACHE is None:
        with open(_SKILLS_PATH) as f:
            _SKILLS_CACHE = json.load(f)
    return _SKILLS_CACHE


def extract_skills_from_text(text: str, skills_section: str = "") -> SkillsBlock:
    combined = f"{text}\n{skills_section}".lower()
    hard: list[str] = []
    for skill in _load_skills():
        if skill.lower() in combined:
            hard.append(skill)
    soft_keywords = [
        "trabajo en equipo",
        "teamwork",
        "comunicación",
        "communication",
        "liderazgo",
        "leadership",
        "proactividad",
        "problem solving",
    ]
    soft = [s for s in soft_keywords if s in combined]
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
