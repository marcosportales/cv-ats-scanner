import re
from dataclasses import dataclass

from app.domain.matching.language_matcher import LanguageMatchResult
from app.domain.parsing.language_extractor import display_language_name
from app.schemas.parsed import ContactInfo, ParsedResume


@dataclass
class AtsIssue:
    id: str
    severity: str
    penalty: float
    message: str
    fix_hint: str | None = None
    confidence: str = "high"
    evidence: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "severity": self.severity,
            "penalty": self.penalty,
            "message": self.message,
            "fix_hint": self.fix_hint,
            "confidence": self.confidence,
            "evidence": self.evidence,
        }


def _has_experience_section(parsed: ParsedResume) -> bool:
    return "experience" in parsed.sections_detected or bool(parsed.experience)


def _experience_confidence(parsed: ParsedResume) -> str:
    if "experience" in parsed.sections_detected:
        return "high"
    if parsed.experience:
        return "low"
    return "high"


def _experience_evidence(parsed: ParsedResume) -> str:
    if "experience" in parsed.sections_detected:
        return "Sección de experiencia reconocida en encabezados del CV"
    if parsed.experience:
        roles = [exp.role for exp in parsed.experience if exp.role]
        if roles:
            return f"Cargos detectados sin encabezado estándar: {', '.join(roles[:3])}"
        return "Bloques de experiencia inferidos por fechas y viñetas"
    return "No se encontraron encabezados ni bloques de experiencia"


def _phone_evidence(contact: ContactInfo) -> str:
    if contact.phone:
        return f"Teléfono: detectado — {contact.phone}"
    return (
        "Teléfono: no detectado — patrones: +34/0034 con 9 dígitos, "
        "formato local 6xx/7xx/9xx con separadores"
    )


def _links_evidence(contact: ContactInfo) -> str:
    urls = []
    if contact.linkedin:
        urls.append(f"LinkedIn: {contact.linkedin}")
    if contact.github:
        urls.append(f"GitHub: {contact.github}")
    if contact.portfolio:
        urls.append(f"Portfolio: {contact.portfolio}")
    if urls:
        return "Enlaces profesionales: detectados — " + "; ".join(urls)
    if contact.professional_link_mentions:
        mentions = ", ".join(contact.professional_link_mentions)
        return f"Enlaces profesionales: menciones sin URL — {mentions}"
    return "Enlaces profesionales: no se detectan URLs completas de LinkedIn/GitHub/Portfolio"


def build_detection_evidence(
    parsed: ParsedResume,
    language_match: LanguageMatchResult | None = None,
) -> list[dict]:
    contact = parsed.contact
    evidence: list[dict] = [
        {
            "field": "phone",
            "status": "detected" if contact.phone else "not_detected",
            "detail": _phone_evidence(contact),
            "confidence": "high" if contact.phone else "high",
        },
        {
            "field": "experience",
            "status": "detected" if _has_experience_section(parsed) else "not_detected",
            "detail": (
                f"Experiencia: detectada — {_experience_evidence(parsed)}"
                if _has_experience_section(parsed)
                else "Experiencia: no detectada — sin encabezado ni bloques inferidos"
            ),
            "confidence": _experience_confidence(parsed) if not _has_experience_section(parsed) else "high",
        },
        {
            "field": "professional_links",
            "status": (
                "detected"
                if contact.professional_links_level == "ok"
                else "partial"
                if contact.professional_link_mentions
                else "not_detected"
            ),
            "detail": _links_evidence(contact),
            "confidence": "high",
        },
    ]

    if language_match and language_match.gaps:
        gap = language_match.gaps[0]
        lang_label = display_language_name(gap.language)
        if gap.status == "missing":
            detail = (
                f"Idioma: no detectado — la oferta pide {lang_label} "
                f"{(gap.required_level or '').upper()}"
            )
            status = "not_detected"
        else:
            detail = (
                f"Idioma: detectado — {lang_label} {(gap.cv_level or '').upper()}, "
                f"por debajo del requisito {(gap.required_level or '').upper()}"
            )
            status = "insufficient"
        evidence.append(
            {
                "field": "language",
                "status": status,
                "detail": detail,
                "confidence": "high" if gap.status == "insufficient" else "high",
            }
        )
    elif parsed.languages:
        langs = ", ".join(
            f"{display_language_name(lang.name)} ({lang.level.upper()})"
            if lang.level
            else display_language_name(lang.name)
            for lang in parsed.languages
        )
        evidence.append(
            {
                "field": "language",
                "status": "detected",
                "detail": f"Idioma: detectado — {langs}",
                "confidence": "high",
            }
        )

    return evidence


def run_ats_rules(
    raw_text: str,
    parsed: ParsedResume,
    *,
    needs_ocr: bool = False,
    image_count: int = 0,
    chars_per_page: float = 0,
) -> list[AtsIssue]:
    issues: list[AtsIssue] = []
    contact = parsed.contact

    if not contact.email:
        issues.append(
            AtsIssue(
                id="ATS_NO_EMAIL",
                severity="high",
                penalty=2,
                message="No se detectó email en el CV",
                fix_hint="Añade un email profesional en la cabecera",
                confidence="high",
                evidence="Email: no detectado en cabecera ni cuerpo del CV",
            )
        )
    if not contact.phone:
        issues.append(
            AtsIssue(
                id="ATS_NO_PHONE",
                severity="medium",
                penalty=1,
                message="No se detectó teléfono",
                fix_hint="Incluye un número de contacto",
                confidence="high",
                evidence=_phone_evidence(contact),
            )
        )

    links_level = contact.professional_links_level or "missing"
    if links_level == "ok":
        pass
    elif links_level == "mention_only":
        mentions = ", ".join(contact.professional_link_mentions) or "perfiles profesionales"
        issues.append(
            AtsIssue(
                id="ATS_LINKS_MENTION_ONLY",
                severity="low",
                penalty=0.5,
                message=f"Se detectaron menciones de {mentions}, pero no URLs completas",
                fix_hint="Añade URLs visibles de LinkedIn, GitHub o portfolio",
                confidence="high",
                evidence=_links_evidence(contact),
            )
        )
    elif not contact.linkedin and not contact.github and not contact.portfolio:
        issues.append(
            AtsIssue(
                id="ATS_NO_LINKS",
                severity="low",
                penalty=0.5,
                message="No se detectaron enlaces profesionales",
                fix_hint="Añade LinkedIn o GitHub si aplica",
                confidence="high",
                evidence=_links_evidence(contact),
            )
        )

    if not _has_experience_section(parsed):
        confidence = _experience_confidence(parsed)
        penalty = 0.5 if confidence == "low" else 2.0
        severity = "medium" if confidence == "low" else "high"
        issues.append(
            AtsIssue(
                id="ATS_NO_EXPERIENCE_SECTION",
                severity=severity,
                penalty=penalty,
                message="No se detectó sección de experiencia",
                fix_hint='Usa un encabezado claro: "Experiencia" o "Experience"',
                confidence=confidence,
                evidence=_experience_evidence(parsed),
            )
        )
    elif "experience" not in parsed.sections_detected and parsed.experience:
        issues.append(
            AtsIssue(
                id="ATS_EXPERIENCE_ALT_HEADER",
                severity="low",
                penalty=0,
                message="Sección de experiencia detectada con nombre alternativo",
                fix_hint='Considera un encabezado estándar como "Work Experience"',
                confidence="medium",
                evidence=_experience_evidence(parsed),
            )
        )

    tab_density = raw_text.count("\t") / max(len(raw_text), 1)
    if tab_density > 0.01:
        issues.append(
            AtsIssue(
                id="ATS_TABLES",
                severity="medium",
                penalty=1,
                message="Se detectaron tablas que pueden dificultar el parsing ATS",
                fix_hint="Usa listas con viñetas en lugar de tablas",
                confidence="medium",
                evidence=f"Densidad de tabuladores: {tab_density:.2%}",
            )
        )

    short_lines = [ln for ln in raw_text.split("\n") if 0 < len(ln.strip()) < 25]
    if len(short_lines) > len(raw_text.split("\n")) * 0.4:
        issues.append(
            AtsIssue(
                id="ATS_MULTI_COLUMN",
                severity="medium",
                penalty=1,
                message="Posible diseño multi-columna",
                fix_hint="Usa un diseño de una sola columna",
                confidence="medium",
                evidence=f"Líneas cortas: {len(short_lines)} de {len(raw_text.split(chr(10)))}",
            )
        )

    non_ascii_ratio = sum(1 for c in raw_text if ord(c) > 127) / max(len(raw_text), 1)
    if non_ascii_ratio > 0.15:
        issues.append(
            AtsIssue(
                id="ATS_SPECIAL_CHARS",
                severity="low",
                penalty=0.5,
                message="Alto ratio de caracteres especiales",
                fix_hint="Evita símbolos decorativos y fuentes raras",
                confidence="low",
                evidence=f"Ratio de caracteres no ASCII: {non_ascii_ratio:.1%}",
            )
        )

    if needs_ocr:
        issues.append(
            AtsIssue(
                id="ATS_NEEDS_OCR",
                severity="high",
                penalty=1.5,
                message="El PDF parece escaneado o sin texto seleccionable",
                fix_hint="Exporta el CV como PDF con texto real, no imagen",
                confidence="high",
                evidence="Extracción PDF requirió OCR o devolvió poco texto seleccionable",
            )
        )

    if image_count > 3:
        issues.append(
            AtsIssue(
                id="ATS_MANY_IMAGES",
                severity="medium",
                penalty=1,
                message="El PDF contiene muchas imágenes",
                fix_hint="Reduce imágenes y logos que ocultan texto",
                confidence="high",
                evidence=f"Imágenes detectadas en PDF: {image_count}",
            )
        )

    generic_phrases = [
        "apasionado por",
        "passionate about",
        "guru",
        "ninja",
        "rockstar",
    ]
    summary = (parsed.summary or "").lower()
    for phrase in generic_phrases:
        if phrase in summary:
            issues.append(
                AtsIssue(
                    id="ATS_GENERIC_PHRASE",
                    severity="low",
                    penalty=0.5,
                    message=f"Frase genérica detectada: '{phrase}'",
                    fix_hint="Usa logros concretos con métricas",
                    confidence="medium",
                    evidence=f"Frase encontrada en resumen: '{phrase}'",
                )
            )
            break

    return issues
