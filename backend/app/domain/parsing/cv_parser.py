import re

from langdetect import LangDetectException, detect

from app.domain.parsing.contact_extractor import extract_contact
from app.domain.parsing.language_extractor import extract_languages
from app.domain.parsing.section_detector import detect_sections
from app.domain.parsing.skills_extractor import collect_evidence_skills, extract_skills_from_text
from app.schemas.parsed import EducationItem, ExperienceItem, ParsedResume, ProjectItem

DATE_RANGE_RE = re.compile(
    r"(\d{4}|\w+\s+\d{4})\s*[-–—]\s*(\d{4}|present|actualidad|actual|hoy)",
    re.I,
)

YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")

URL_RE = re.compile(r"https?://\S+|(?:www\.|github\.com|gitlab\.com)\S+", re.I)


def _infer_experience_from_text(text: str) -> list[ExperienceItem]:
    """Infer experience blocks from date ranges when section headers are missing."""
    if not DATE_RANGE_RE.search(text):
        return []

    blocks: list[str] = []
    lines = text.split("\n")
    current: list[str] = []
    for line in lines:
        stripped = line.strip()
        if DATE_RANGE_RE.search(stripped) and current:
            blocks.append("\n".join(current))
            current = [stripped]
        elif stripped:
            current.append(stripped)
    if current:
        blocks.append("\n".join(current))

    items = _parse_experience("\n\n".join(blocks))
    return [item for item in items if item.role or item.bullets]


def _parse_experience(section_text: str) -> list[ExperienceItem]:
    if not section_text:
        return []
    blocks = re.split(r"\n(?=[A-ZÁÉÍÓÚÑ][^\n]{2,50}\n)", section_text)
    items: list[ExperienceItem] = []
    for block in blocks:
        lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
        if not lines:
            continue
        role = lines[0]
        company = lines[1] if len(lines) > 1 else None
        dates = DATE_RANGE_RE.search(block)
        start_date = dates.group(1) if dates else None
        end_date = dates.group(2) if dates else None
        bullets = [
            ln.lstrip("•-* ").strip()
            for ln in lines
            if ln.startswith(("•", "-", "*")) or (len(ln) > 30 and not DATE_RANGE_RE.search(ln))
        ]
        bullets = [b for b in bullets if b and b != role and b != company][:8]
        skills_block = extract_skills_from_text(block)
        items.append(
            ExperienceItem(
                company=company,
                role=role,
                start_date=start_date,
                end_date=end_date,
                bullets=bullets,
                skills_mentioned=skills_block.hard,
            )
        )
    return items[:10]


def _parse_education(section_text: str) -> list[EducationItem]:
    if not section_text:
        return []
    # Blank lines preserved by detect_sections separate distinct entries
    blocks = [b.strip() for b in re.split(r"\n\s*\n", section_text) if b.strip()]
    if not blocks:
        blocks = [section_text.strip()]

    items: list[EducationItem] = []
    for block in blocks:
        lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
        if not lines:
            continue
        degree = institution = start_date = end_date = None
        for line in lines:
            dr = DATE_RANGE_RE.search(line)
            if dr:
                start_date = dr.group(1)
                end_date = dr.group(2)
                continue
            if degree is None:
                degree = line
            elif institution is None:
                yr = YEAR_RE.search(line)
                if yr:
                    end_date = end_date or yr.group(1)
                    # Strip trailing ", YYYY" from institution name
                    institution = re.sub(r",?\s*(19|20)\d{2}$", "", line).strip() or line
                else:
                    institution = line
        if degree:
            items.append(
                EducationItem(
                    degree=degree,
                    institution=institution or None,
                    start_date=start_date,
                    end_date=end_date,
                )
            )
    return items[:5]


def _parse_projects(section_text: str) -> list[ProjectItem]:
    if not section_text:
        return []
    blocks = [b.strip() for b in re.split(r"\n\s*\n", section_text) if b.strip()]
    if not blocks:
        # No blank-line separators — each non-empty line is a project name
        lines = [ln.strip() for ln in section_text.split("\n") if ln.strip()]
        return [ProjectItem(name=ln) for ln in lines[:5]]

    items: list[ProjectItem] = []
    for block in blocks:
        lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
        if not lines:
            continue
        raw_name = lines[0]
        # Strip trailing "— description" from the name line if present
        name = re.split(r"\s*[—–]\s*", raw_name)[0].strip() or raw_name
        description = lines[1] if len(lines) > 1 else None
        # Detect URL in block
        url_match = URL_RE.search(block)
        url = url_match.group(0) if url_match else None
        # Detect tech list: comma-separated line where known skills appear
        techs: list[str] = []
        for line in lines[1:]:
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 2 and all(len(p) < 30 for p in parts):
                found = extract_skills_from_text(line)
                if found.hard:
                    techs = found.hard
                    break
        items.append(ProjectItem(name=name, description=description, technologies=techs, url=url))
    return items[:8]


def _parse_certifications(section_text: str) -> list[str]:
    if not section_text:
        return []
    certs: list[str] = []
    for line in section_text.split("\n"):
        stripped = line.strip().lstrip("•-* ")
        if stripped and len(stripped) > 3:
            certs.append(stripped)
    return certs[:10]


def parse_cv(text: str) -> ParsedResume:
    sections_detected, sections = detect_sections(text)
    contact = extract_contact(text)
    summary = sections.get("summary")
    experience = _parse_experience(sections.get("experience", ""))
    if not experience:
        experience = _infer_experience_from_text(text)
    skills = extract_skills_from_text(text, sections.get("skills", ""))
    languages = extract_languages(text, sections.get("languages", ""))
    education = _parse_education(sections.get("education", ""))
    projects = _parse_projects(sections.get("projects", ""))
    certifications = _parse_certifications(sections.get("certifications", ""))
    all_bullets = [b for exp in experience for b in exp.bullets]
    evidence = collect_evidence_skills(skills, all_bullets)

    if experience and "experience" not in sections_detected:
        sections_detected.append("experience")
    if education and "education" not in sections_detected:
        sections_detected.append("education")
    if projects and "projects" not in sections_detected:
        sections_detected.append("projects")
    if certifications and "certifications" not in sections_detected:
        sections_detected.append("certifications")

    try:
        language = detect(text[:2000])
    except LangDetectException:
        language = "es"

    confidence = 0.5
    if contact.email:
        confidence += 0.1
    if sections_detected:
        confidence += 0.1 * min(len(sections_detected), 4)
    if experience:
        confidence += 0.1
    confidence = min(confidence, 0.95)

    return ParsedResume(
        language=language,
        contact=contact,
        sections_detected=sections_detected,
        summary=summary,
        experience=experience,
        skills=skills,
        education=education,
        projects=projects,
        languages=languages,
        certifications=certifications,
        evidence_skills=evidence,
        parse_confidence=round(confidence, 2),
    )
