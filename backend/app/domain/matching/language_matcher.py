from dataclasses import dataclass, field

from app.domain.parsing.language_extractor import display_language_name, level_rank
from app.schemas.parsed import LanguageItem


@dataclass
class LanguageGap:
    language: str
    required_level: str | None
    cv_level: str | None
    severity: str
    message: str
    penalty: float = 0.0
    status: str = "missing"  # missing | insufficient | ok


@dataclass
class LanguageMatchResult:
    gaps: list[LanguageGap] = field(default_factory=list)
    total_penalty: float = 0.0


def _format_level(level: str | None) -> str:
    if not level:
        return ""
    return level.upper() if len(level) <= 3 else level.title()


def compare_language_requirements(
    cv_languages: list[LanguageItem],
    job_languages: list[LanguageItem],
) -> LanguageMatchResult:
    if not job_languages:
        return LanguageMatchResult()

    cv_by_name = {lang.name: lang for lang in cv_languages}
    gaps: list[LanguageGap] = []
    penalty = 0.0

    for required in job_languages:
        cv_lang = cv_by_name.get(required.name)
        required_rank = level_rank(required.level)
        cv_rank = level_rank(cv_lang.level) if cv_lang else None
        lang_label = display_language_name(required.name)
        req_level_label = _format_level(required.level)

        if cv_lang is None:
            gaps.append(
                LanguageGap(
                    language=required.name,
                    required_level=required.level,
                    cv_level=None,
                    severity="high",
                    status="missing",
                    message=(
                        f"La oferta pide {lang_label} {req_level_label} "
                        f"y el CV no menciona {lang_label}"
                    ),
                    penalty=2.0,
                )
            )
            penalty += 2.0
            continue

        if required_rank is None:
            continue

        if cv_rank is None:
            gaps.append(
                LanguageGap(
                    language=required.name,
                    required_level=required.level,
                    cv_level=None,
                    severity="medium",
                    status="insufficient",
                    message=(
                        f"La oferta pide {lang_label} {req_level_label} "
                        f"y el CV menciona {lang_label} sin nivel explícito"
                    ),
                    penalty=1.0,
                )
            )
            penalty += 1.0
            continue

        if cv_rank < required_rank:
            cv_level_label = _format_level(cv_lang.level)
            improving = "improving" in (cv_lang.level or "").lower() or "mejorando" in (
                cv_lang.level or ""
            ).lower()
            gap_penalty = 1.0 if improving else 1.5
            gaps.append(
                LanguageGap(
                    language=required.name,
                    required_level=required.level,
                    cv_level=cv_lang.level,
                    severity="medium",
                    status="insufficient",
                    message=(
                        f"La oferta pide {lang_label} {req_level_label}, "
                        f"pero el CV indica {lang_label} {cv_level_label}. "
                        f"Esto representa una brecha moderada respecto al requisito de idioma."
                    ),
                    penalty=gap_penalty,
                )
            )
            penalty += gap_penalty

    return LanguageMatchResult(gaps=gaps, total_penalty=min(penalty, 4.0))
