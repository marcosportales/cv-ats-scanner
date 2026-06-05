from app.domain.ats.rules_engine import AtsIssue, build_detection_evidence
from app.domain.matching.keyword_matcher import MatchResult
from app.domain.matching.language_matcher import LanguageMatchResult, compare_language_requirements
from app.schemas.parsed import AnalysisResult, ParsedResume, ScoreCategories

LEVEL_THRESHOLDS = [
    (85, "Excellent"),
    (70, "Good"),
    (50, "Fair"),
    (0, "NeedsWork"),
]


def _score_level(total: float) -> str:
    for threshold, level in LEVEL_THRESHOLDS:
        if total >= threshold:
            return level
    return "NeedsWork"


def _format_missing_technical_keywords(missing: list[dict]) -> str:
    if not missing:
        return ""
    terms = [item["term"] for item in missing]
    if len(terms) == 1:
        return f"Falta 1 keyword técnica relevante: {terms[0]}."
    joined = ", ".join(terms)
    return f"Faltan {len(terms)} keywords técnicas relevantes: {joined}."


def score_parseability(
    parsed: ParsedResume,
    issues: list[AtsIssue],
    *,
    needs_ocr: bool,
    chars_per_page: float,
    text_length: int,
) -> float:
    score = 20.0
    if needs_ocr:
        score -= 8
    if chars_per_page < 50:
        score -= 5
    if text_length < 200:
        score -= 5

    has_experience = "experience" in parsed.sections_detected or bool(parsed.experience)
    if not parsed.sections_detected:
        score -= 4
    elif not has_experience:
        score -= 6
    elif "experience" not in parsed.sections_detected:
        score -= 1

    for issue in issues:
        if issue.confidence == "low":
            total_penalty = issue.penalty * 0.25
        elif issue.confidence == "medium":
            total_penalty = issue.penalty * 0.5
        else:
            total_penalty = issue.penalty

        if issue.id == "ATS_NO_EXPERIENCE_SECTION":
            score -= total_penalty * 2
        elif issue.id in ("ATS_TABLES", "ATS_MULTI_COLUMN"):
            score -= total_penalty
        elif issue.id == "ATS_NEEDS_OCR":
            score -= total_penalty * 1.5

    return max(0, min(20, round(score, 1)))


def score_structure(parsed: ParsedResume) -> float:
    expected = {"summary", "experience", "skills", "education"}
    detected = set(parsed.sections_detected)
    if parsed.experience and "experience" not in detected:
        detected.add("experience")
    ratio = len(detected & expected) / len(expected)
    return round(15 * ratio, 1)


def score_contact(parsed: ParsedResume) -> float:
    c = parsed.contact
    score = 0.0
    if c.email:
        score += 4
    if c.phone:
        score += 3
    links_level = c.professional_links_level
    if links_level == "ok" or c.linkedin or c.github or c.portfolio:
        score += 3
    elif links_level == "mention_only":
        score += 1.5
    return min(10, score)


def score_writing(parsed: ParsedResume) -> float:
    bullets = [b for e in parsed.experience for b in e.bullets]
    if not bullets:
        return 3.0
    metric_bullets = sum(1 for b in bullets if any(ch.isdigit() for ch in b))
    action_verbs = sum(
        1
        for b in bullets
        if any(b.lower().startswith(v) for v in ["desarroll", "implement", "lider", "reduj", "mejor", "cre"])
    )
    ratio = (metric_bullets + action_verbs) / (2 * len(bullets))
    return round(min(10, 10 * ratio), 1)


def score_job_match(
    match: MatchResult,
    parsed_job,
    language_match: LanguageMatchResult,
) -> float:
    must_found = sum(1 for r in match.requirements_coverage if r.get("status") == "found")
    must_total = max(len(parsed_job.requirements.must), 1)
    must_ratio = must_found / must_total
    keyword_part = 10 * match.keyword_coverage
    req_part = 10 * must_ratio
    base = min(20, keyword_part + req_part)
    adjusted = max(0, base - language_match.total_penalty * 0.75)
    return round(adjusted, 1)


def compute_risk_penalties(issues: list[AtsIssue]) -> float:
    total = 0.0
    for issue in issues:
        if issue.severity not in ("high", "medium"):
            continue
        if issue.id in ("ATS_NO_PHONE", "ATS_NO_LINKS", "ATS_LINKS_MENTION_ONLY"):
            continue
        if issue.confidence == "low":
            total += issue.penalty * 0.25
        elif issue.confidence == "medium":
            total += issue.penalty * 0.5
        else:
            total += issue.penalty
    return min(5, total)


def _build_summary(
    total: float,
    job_match_score: float,
    match: MatchResult,
    language_match: LanguageMatchResult,
) -> str:
    summary = (
        f"Puntuación {total}/100 ({_score_level(total)}). "
        f"Coincidencia con la oferta: {job_match_score}%. "
    )

    missing_technical = [k for k in match.missing_keywords if k.get("category", "technical") == "technical"]
    if missing_technical:
        summary += _format_missing_technical_keywords(missing_technical)
    elif match.missing_contextual_keywords:
        terms = ", ".join(item["term"] for item in match.missing_contextual_keywords[:3])
        summary += (
            f"Buena cobertura técnica; podrías reforzar aspectos contextuales "
            f"como {terms}."
        )
    else:
        summary += "Buena cobertura de keywords técnicas."

    if language_match.gaps:
        gap = language_match.gaps[0]
        summary += f" {gap.message}"

    return summary


def compute_scores(
    parsed_cv: ParsedResume,
    parsed_job,
    match: MatchResult,
    issues: list[AtsIssue],
    *,
    needs_ocr: bool = False,
    chars_per_page: float = 500,
    text_length: int = 1000,
    scoring_version: str = "1.2.0",
) -> AnalysisResult:
    language_match = compare_language_requirements(parsed_cv.languages, parsed_job.languages)

    categories = ScoreCategories(
        ats_parseability=score_parseability(
            parsed_cv,
            issues,
            needs_ocr=needs_ocr,
            chars_per_page=chars_per_page,
            text_length=text_length,
        ),
        structure=score_structure(parsed_cv),
        contact_info=score_contact(parsed_cv),
        keywords=round(20 * match.keyword_coverage, 1),
        job_match=score_job_match(match, parsed_job, language_match),
        writing_quality=score_writing(parsed_cv),
        risk_penalties=compute_risk_penalties(issues),
    )

    language_penalty = min(3, language_match.total_penalty)

    raw_total = (
        categories.ats_parseability
        + categories.structure
        + categories.contact_info
        + categories.keywords
        + categories.job_match
        + categories.writing_quality
        - categories.risk_penalties
        - language_penalty
    )
    total = max(0, min(100, round(raw_total, 1)))

    ats_score = round(
        min(
            100,
            categories.ats_parseability
            + categories.structure
            + categories.contact_info
            + categories.writing_quality * 0.5
            - categories.risk_penalties * 0.6,
        ),
        1,
    )
    job_match_score = round(
        min(100, (categories.keywords + categories.job_match) * 2.5),
        1,
    )

    return AnalysisResult(
        total_score=total,
        ats_score=ats_score,
        job_match_score=job_match_score,
        level=_score_level(total),
        summary=_build_summary(total, job_match_score, match, language_match),
        scoring_version=scoring_version,
        categories=categories,
        found_keywords=match.found_keywords,
        missing_keywords=match.missing_keywords,
        missing_contextual_keywords=match.missing_contextual_keywords,
        missing_education_keywords=match.missing_education_keywords,
        keyword_gaps=match.keyword_gaps,
        language_gaps=[gap.__dict__ for gap in language_match.gaps],
        detection_evidence=build_detection_evidence(parsed_cv, language_match),
        requirements_coverage=match.requirements_coverage,
        critical_issues=[i.to_dict() for i in issues],
        matches={
            "skills_found": match.skills_found,
            "skills_missing": match.skills_missing,
            "skills_partial": match.skills_partial,
        },
        recommendations_available=False,
    )
