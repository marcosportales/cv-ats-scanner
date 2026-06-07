import re

from app.domain.parsing.language_extractor import extract_required_languages
from app.domain.parsing.skills_extractor import extract_skills_from_text
from app.schemas.parsed import JobRequirements, KeywordCategories, ParsedJob

# ── Seniority / modality ─────────────────────────────────────────────────────

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

# ── Education / formation detection ─────────────────────────────────────────

_EDUCATION_RE = re.compile(
    r"\b("
    r"daw|dam|cfgs|fp\b|ciclo formativo|grado superior|grado medio"
    r"|ingenieria|ingeniería|informatic[ao]"
    r"|telecomunicaciones|telematica|telemática"
    r"|computer science|software engineering|data science"
    r"|bachelor|grado\b|licenciatura|diplomatura|master|máster"
    r"|titulad[ao]|recien titulad[ao]|recién titulad[ao]"
    r"|degree|estudios|formacion\b|formación\b"
    r")",
    re.I,
)

# ── Soft-skills / contextual detection ───────────────────────────────────────

_SOFT_KEYWORDS: list[str] = [
    "trabajo en equipo",
    "teamwork",
    "comunicación",
    "communication",
    "liderazgo",
    "leadership",
    "proactividad",
    "proactive",
    "problem solving",
    "resolución de problemas",
    "orientado a resultados",
    "results-oriented",
    "autonomía",
    "autonomy",
    "adaptabilidad",
    "adaptability",
    "motivación",
    "motivation",
    "ganas de aprender",
    "willingness to learn",
    "capacidad de aprendizaje",
]

_CONTEXTUAL_KEYWORDS: list[str] = [
    "transformacion digital",
    "transformación digital",
    "digital transformation",
    "equipos multidisciplinares",
    "multidisciplinary teams",
    "accesibilidad web",
    "web accessibility",
    "desarrollo frontend",
    "frontend development",
    "front-end development",
    "desarrollo backend",
    "backend development",
    "desarrollo fullstack",
    "fullstack development",
    "desarrollo movil",
    "mobile development",
    "cloud native",
    "data driven",
    "startups",
    "fintech",
    "e-commerce",
]


# ── Section extraction ───────────────────────────────────────────────────────


def _extract_section(text: str, headers: list[str]) -> str:
    pattern = "|".join(re.escape(h) for h in headers)
    match = re.search(rf"(?:{pattern})\s*:?\s*\n", text, re.I)
    if not match:
        return ""
    start = match.end()
    next_section = re.search(
        r"\n(?:requisitos|requirements|responsabilidades|responsibilities|"
        r"nice to have|deseable|valorable|preferible|qualifications|about|"
        r"se ofrece|what we offer|beneficios|benefits)\s*:?\s*\n",
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


# ── Requirement classification ───────────────────────────────────────────────


def _is_language_req(text: str) -> bool:
    return bool(extract_required_languages(text))


def _is_education_req(text: str) -> bool:
    return bool(_EDUCATION_RE.search(text))


def _is_soft_req(text_lower: str) -> bool:
    return any(kw in text_lower for kw in _SOFT_KEYWORDS)


def _extract_contextual(text: str) -> list[str]:
    lowered = text.lower()
    found: list[str] = []
    for kw in _CONTEXTUAL_KEYWORDS:
        if kw in lowered:
            found.append(kw)
    # Also pick up soft keywords as contextual
    for kw in _SOFT_KEYWORDS:
        if kw in lowered and kw not in found:
            found.append(kw)
    return list(dict.fromkeys(found))


def _extract_education_from_text(text: str) -> list[str]:
    """Return education-related phrases found in the text."""
    found: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip().lstrip("•-* ")
        if stripped and _is_education_req(stripped):
            found.append(stripped)
    return list(dict.fromkeys(found))[:5]


def _split_must_nice_from_single_section(
    lines: list[str],
) -> tuple[list[str], list[str]]:
    """When must and nice requirements appear in a single unlabelled block,
    split by heuristic: education/language/soft lines go to nice, technical to must."""
    must: list[str] = []
    nice: list[str] = []
    for line in lines:
        low = line.lower()
        if _is_language_req(line) or _is_education_req(line) or _is_soft_req(low):
            nice.append(line)
        else:
            must.append(line)
    return must, nice


def _categorize_keywords(
    text: str,
    hard_skills: list[str],
    must: list[str],
    nice: list[str],
) -> KeywordCategories:
    contextual = _extract_contextual(text)
    education = _extract_education_from_text(text)
    languages = extract_required_languages(text)
    language_terms = [f"{lang.name} {lang.level}".strip() for lang in languages if lang.level]

    # technical_required: hard skills that appear in the must section (or everywhere if no must)
    must_text = " ".join(must).lower()
    if must_text.strip():
        technical_required = [s for s in hard_skills if s.lower() in must_text]
        # Fall back: if nothing matched must, use all hard skills
        if not technical_required:
            technical_required = hard_skills
    else:
        technical_required = hard_skills

    # technical_optional: hard skills that appear in nice section but not required
    nice_text = " ".join(nice).lower()
    technical_optional = [
        s for s in hard_skills if s not in technical_required and s.lower() in nice_text
    ]

    return KeywordCategories(
        technical_required=list(dict.fromkeys(technical_required)),
        technical_optional=list(dict.fromkeys(technical_optional)),
        contextual=contextual,
        language=language_terms,
        education=education,
    )


# ── Public entry point ───────────────────────────────────────────────────────


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
        text,
        [
            "requisitos obligatorios",
            "requisitos",
            "requirements",
            "must have",
            "required",
            "se requiere",
        ],
    )
    nice_section = _extract_section(
        text,
        ["deseable", "nice to have", "preferible", "valorable", "plus", "se valorara"],
    )
    resp_section = _extract_section(
        text,
        [
            "responsabilidades",
            "responsibilities",
            "tu misión",
            "what you will do",
            "funciones",
            "tareas",
        ],
    )

    must_raw = _bullet_lines(must_section) if must_section else []
    nice_raw = _bullet_lines(nice_section)
    responsibilities = _bullet_lines(resp_section)

    if not must_raw:
        # No labelled must/nice sections — classify all bullets heuristically
        all_bullets = _bullet_lines(text)[:15]
        must_raw, extra_nice = _split_must_nice_from_single_section(all_bullets)
        if not nice_raw:
            nice_raw = extra_nice
    else:
        # We have a must section — classify its lines too to separate non-technical
        technical_must, non_technical = _split_must_nice_from_single_section(must_raw)
        # Non-technical requirements (language, education, soft) go to nice if not already there
        for item in non_technical:
            if item not in nice_raw:
                nice_raw.append(item)
        must_raw = technical_must or must_raw  # keep originals if classification emptied must

    skills = extract_skills_from_text(text)
    languages = extract_required_languages(text)
    keyword_categories = _categorize_keywords(
        text,
        skills.hard,
        must_raw,
        nice_raw,
    )

    return ParsedJob(
        title=detected_title,
        seniority=seniority,
        modality=modality,
        hard_skills=skills.hard,
        soft_skills=skills.soft,
        requirements=JobRequirements(must=must_raw, nice=nice_raw),
        responsibilities=responsibilities,
        languages=languages,
        keywords=keyword_categories.technical_required,
        keyword_categories=keyword_categories,
    )
