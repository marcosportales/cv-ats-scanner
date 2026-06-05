import re

from langdetect import detect, LangDetectException

from app.domain.parsing.contact_extractor import extract_contact
from app.domain.parsing.language_extractor import extract_languages
from app.domain.parsing.section_detector import detect_sections
from app.domain.parsing.skills_extractor import collect_evidence_skills, extract_skills_from_text
from app.schemas.parsed import ExperienceItem, ParsedResume

DATE_RANGE_RE = re.compile(
    r"(\d{4}|\w+\s+\d{4})\s*[-–—]\s*(\d{4}|present|actualidad|actual|hoy)",
    re.I,
)


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


def parse_cv(text: str) -> ParsedResume:
    sections_detected, sections = detect_sections(text)
    contact = extract_contact(text)
    summary = sections.get("summary")
    experience = _parse_experience(sections.get("experience", ""))
    if not experience:
        experience = _infer_experience_from_text(text)
    skills = extract_skills_from_text(text, sections.get("skills", ""))
    languages = extract_languages(text, sections.get("languages", ""))
    all_bullets = [b for exp in experience for b in exp.bullets]
    evidence = collect_evidence_skills(skills, all_bullets)

    if experience and "experience" not in sections_detected:
        sections_detected.append("experience")

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
        languages=languages,
        evidence_skills=evidence,
        parse_confidence=round(confidence, 2),
    )
