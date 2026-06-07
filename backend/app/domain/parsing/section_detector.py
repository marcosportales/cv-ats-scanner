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
        "objetivo",
        "objective",
        "acerca de mi",
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
        "formacion academica",
        "academic training",
        "titulacion",
        "titulaciones",
    ],
    "skills": [
        "habilidades",
        "skills",
        "competencias",
        "technical skills",
        "tecnologias",
        "core skills",
        "habilidades tecnicas",
        "conocimientos",
        "conocimientos tecnicos",
        "stack tecnologico",
    ],
    "projects": [
        "proyectos",
        "projects",
        "portfolio",
        "selected projects",
        "side projects",
        "personal projects",
        "proyectos personales",
        "proyectos destacados",
    ],
    "languages": [
        "idiomas",
        "languages",
        "language skills",
        "idiomas conocidos",
    ],
    "certifications": [
        "certificaciones",
        "certifications",
        "cursos",
        "licenses",
        "licencias",
        "cursos y certificaciones",
        "formacion complementaria",
        "otros cursos",
    ],
}

_NORMALIZED_ALIASES: dict[str, set[str]] = {
    section: {singularize_header(normalize_header(alias)) for alias in aliases}
    for section, aliases in SECTION_ALIASES.items()
}

# Max characters and words a header token may have — prevents content lines matching
_MAX_HEADER_CHARS = 60
_MAX_HEADER_WORDS = 5
# Inline HEADER: content — only try split when prefix is at most this many chars
_MAX_INLINE_PREFIX_CHARS = 40


def _match_header_text(text: str) -> str | None:
    """Return canonical section name if *text* is a recognized section header, else None.

    Uses exact alias matching only (no prefix tricks) to avoid false positives
    on content lines that happen to start with a known word.
    """
    normalized = singularize_header(normalize_header(text))
    if not normalized:
        return None
    if len(normalized) > _MAX_HEADER_CHARS or len(normalized.split()) > _MAX_HEADER_WORDS:
        return None
    for section, aliases in _NORMALIZED_ALIASES.items():
        if normalized in aliases:
            return section
    return None


def detect_sections(text: str) -> tuple[list[str], dict[str, str]]:
    """Split *text* into named sections.

    Returns:
        detected  -- ordered list of canonical section names found
        sections  -- mapping from canonical name to section body text

    Handles:
    - Standard header-only lines ("WORK EXPERIENCE")
    - Inline "HEADER: content on same line" (prefix ≤ 40 chars)
    - Blank lines preserved in section bodies for downstream block-splitting
    """
    lines = text.split("\n")
    detected: list[str] = []
    sections: dict[str, str] = {}
    current_section: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer, current_section
        if current_section and buffer:
            # Strip leading/trailing blank lines but keep internal ones
            content = "\n".join(buffer).strip()
            if content:
                sections[current_section] = content
        buffer = []

    for line in lines:
        stripped = line.strip()

        if not stripped:
            if current_section:
                buffer.append("")
            continue

        # Try "HEADER: content" inline format (short prefix only)
        inline_match: str | None = None
        inline_content = ""
        colon_idx = stripped.find(":")
        if 0 < colon_idx <= _MAX_INLINE_PREFIX_CHARS:
            prefix = stripped[:colon_idx].strip()
            inline_match = _match_header_text(prefix)
            if inline_match:
                inline_content = stripped[colon_idx + 1 :].strip()

        # Try full line as a standalone header
        full_match = _match_header_text(stripped) if not inline_match else None

        matched = inline_match or full_match
        if matched:
            flush()
            current_section = matched
            if matched not in detected:
                detected.append(matched)
            if inline_content:
                buffer.append(inline_content)
            continue

        if current_section:
            buffer.append(stripped)

    flush()
    return detected, sections
