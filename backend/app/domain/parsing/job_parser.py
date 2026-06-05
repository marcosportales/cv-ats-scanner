import re

from app.domain.parsing.language_extractor import extract_required_languages
from app.domain.parsing.skills_extractor import extract_skills_from_text
from app.schemas.parsed import JobRequirements, KeywordCategories, ParsedJob

SENIORITY_PATTERNS = {
    "junior": r"\b(junior|jr\.?|entry)\b",
    "mid": r"\b(mid|intermediate|semi[- ]?senior)\b",
    "senior": r"\b(senior|sr\.?|lead)\b",
    "lead": r"\b(lead|principal|staff|architect)\b",
}

MODALITY_PATTERNS = {
    "remote": r"\b(remote|remoto|teletrabajo|work from home)\b",
    "hybrid": r"\b(h[ií]brido|hybrid)\b",
    "onsite": r"\b(presencial|on[- ]?site|oficina)\b",
}

CONTEXTUAL_KEYWORDS = [
    "front-end development",
    "frontend development",
    "desarrollo frontend",
    "digital transformation",
    "transformacion digital",
    "transformación digital",
    "multidisciplinary teams",
    "equipos multidisciplinares",
    "web accessibility",
    "accesibilidad web",
    "trabajo en equipo",
    "teamwork",
    "motivacion",
    "motivación",
]

EDUCATION_KEYWORDS = [
    "daw",
    "dam",
    "cfgs",
    "ingenieria informatica",
    "ingeniería informática",
    "telecomunicaciones",
    "computer science",
    "grado",
    "titulado",
    "recien titulado",
    "recién titulado",
]


def _extract_section(text: str, headers: list[str]) -> str:
    pattern = "|".join(headers)
    match = re.search(rf"(?:{pattern})\s*:?\s*\n", text, re.I)
    if not match:
        return ""
    start = match.end()
    next_section = re.search(
        r"\n(?:requisitos|requirements|responsabilidades|responsibilities|"
        r"nice to have|deseable|qualifications|about)\s*:?\s*\n",
        text[start:],
        re.I,
    )
    end = start + next_section.start() if next_section else len(text)
    return text[start:end].strip()


def _bullet_lines(section: str) -> list[str]:
    lines = []
    for line in section.split("\n"):
        stripped = line.strip().lstrip("•-* ")
        if len(stripped) > 10:
            lines.append(stripped)
    return lines[:30]


def _extract_contextual_keywords(text: str) -> list[str]:
    lowered = text.lower()
    found: list[str] = []
    for keyword in CONTEXTUAL_KEYWORDS:
        if keyword in lowered:
            found.append(keyword)
    return list(dict.fromkeys(found))


def _extract_education_keywords(text: str) -> list[str]:
    lowered = text.lower()
    found: list[str] = []
    for keyword in EDUCATION_KEYWORDS:
        if keyword in lowered:
            found.append(keyword)
    return list(dict.fromkeys(found))


def _categorize_keywords(
    text: str,
    hard_skills: list[str],
    soft_skills: list[str],
    must_requirements: list[str],
    nice_requirements: list[str],
) -> KeywordCategories:
    contextual = _extract_contextual_keywords(text)
    contextual.extend(soft_skills)
    contextual = list(dict.fromkeys(contextual))

    education = _extract_education_keywords(text)
    languages = extract_required_languages(text)
    language_terms = [
        f"{lang.name} {lang.level}".strip()
        for lang in languages
        if lang.level
    ]

    optional = [skill for skill in hard_skills if skill not in must_requirements]
    required = list(dict.fromkeys(hard_skills))

    return KeywordCategories(
        technical_required=required,
        technical_optional=optional,
        contextual=contextual,
        language=language_terms,
        education=education,
    )


def parse_job(text: str, title: str | None = None) -> ParsedJob:
    title_match = re.search(r"^(.{5,80})$", text.strip().split("\n")[0])
    detected_title = title or (title_match.group(1).strip() if title_match else None)

    seniority = None
    for level, pattern in SENIORITY_PATTERNS.items():
        if re.search(pattern, text, re.I):
            seniority = level
            break

    modality = None
    for mod, pattern in MODALITY_PATTERNS.items():
        if re.search(pattern, text, re.I):
            modality = mod
            break

    must_section = _extract_section(
        text, ["requisitos obligatorios", "requisitos", "requirements", "must have", "required"]
    )
    nice_section = _extract_section(
        text, ["deseable", "nice to have", "preferible", "valorable", "plus"]
    )
    resp_section = _extract_section(
        text, ["responsabilidades", "responsibilities", "tu misión", "what you will do"]
    )

    must = _bullet_lines(must_section) or _bullet_lines(text)[:5]
    nice = _bullet_lines(nice_section)
    responsibilities = _bullet_lines(resp_section)

    skills = extract_skills_from_text(text)
    languages = extract_required_languages(text)
    keyword_categories = _categorize_keywords(
        text,
        skills.hard,
        skills.soft,
        must,
        nice,
    )

    return ParsedJob(
        title=detected_title,
        seniority=seniority,
        modality=modality,
        hard_skills=skills.hard,
        soft_skills=skills.soft,
        requirements=JobRequirements(must=must, nice=nice),
        responsibilities=responsibilities,
        languages=languages,
        keywords=keyword_categories.technical_required,
        keyword_categories=keyword_categories,
    )
