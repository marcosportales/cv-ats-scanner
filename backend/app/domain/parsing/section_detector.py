from app.domain.parsing.text_normalizer import normalize_header, singularize_header

SECTION_ALIASES: dict[str, list[str]] = {
    "summary": [
        "perfil",
        "resumen",
        "summary",
        "about",
        "sobre mi",
        "professional profile",
        "profile",
    ],
    "experience": [
        "experiencia",
        "experience",
        "work experience",
        "professional experience",
        "employment history",
        "employment",
        "work history",
        "relevant experience",
        "career history",
        "experiencia profesional",
        "experiencia laboral",
        "historial profesional",
        "trayectoria profesional",
        "trayectoria",
    ],
    "education": [
        "educacion",
        "education",
        "formacion",
        "estudios",
        "academic background",
    ],
    "skills": [
        "habilidades",
        "skills",
        "competencias",
        "technical skills",
        "tecnologias",
        "core skills",
    ],
    "projects": [
        "proyectos",
        "projects",
        "portfolio",
        "selected projects",
    ],
    "languages": [
        "idiomas",
        "languages",
        "language skills",
    ],
    "certifications": [
        "certificaciones",
        "certifications",
        "cursos",
        "licenses",
    ],
}

_NORMALIZED_ALIASES: dict[str, set[str]] = {
    section: {singularize_header(normalize_header(alias)) for alias in aliases}
    for section, aliases in SECTION_ALIASES.items()
}


def _match_section(line: str) -> str | None:
    normalized = singularize_header(normalize_header(line))
    if not normalized or len(normalized) > 60:
        return None

    for section, aliases in _NORMALIZED_ALIASES.items():
        if normalized in aliases:
            return section
        for alias in aliases:
            if normalized.startswith(alias) or alias.startswith(normalized):
                return section
    return None


def detect_sections(text: str) -> tuple[list[str], dict[str, str]]:
    lines = text.split("\n")
    detected: list[str] = []
    sections: dict[str, str] = {}
    current_section: str | None = None
    buffer: list[str] = []

    def flush():
        nonlocal buffer, current_section
        if current_section and buffer:
            sections[current_section] = "\n".join(buffer).strip()
        buffer = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        matched = _match_section(stripped)
        if matched:
            flush()
            current_section = matched
            if matched not in detected:
                detected.append(matched)
            continue
        if current_section:
            buffer.append(stripped)

    flush()
    return detected, sections
