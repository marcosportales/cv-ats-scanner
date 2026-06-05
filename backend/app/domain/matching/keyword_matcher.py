from dataclasses import dataclass, field

from app.domain.matching.normalizer import normalize_term
from app.domain.matching.synonym_matcher import expand_terms
from app.schemas.parsed import ParsedJob, ParsedResume


@dataclass
class MatchResult:
    found_keywords: list[dict] = field(default_factory=list)
    missing_keywords: list[dict] = field(default_factory=list)
    missing_contextual_keywords: list[dict] = field(default_factory=list)
    missing_education_keywords: list[dict] = field(default_factory=list)
    keyword_gaps: dict[str, list[dict]] = field(default_factory=dict)
    skills_found: list[str] = field(default_factory=list)
    skills_missing: list[str] = field(default_factory=list)
    skills_partial: list[str] = field(default_factory=list)
    keyword_coverage: float = 0.0
    contextual_coverage: float = 0.0
    requirements_coverage: list[dict] = field(default_factory=list)


def _cv_search_text(parsed: ParsedResume) -> str:
    parts = [parsed.summary or ""]
    for exp in parsed.experience:
        parts.append(exp.role or "")
        parts.append(exp.company or "")
        parts.extend(exp.bullets)
    parts.extend(parsed.skills.hard)
    parts.extend(parsed.evidence_skills)
    return normalize_term(" ".join(parts))


def _match_terms(
    terms: list[str],
    cv_text: str,
    *,
    category: str,
    parsed_cv: ParsedResume,
) -> tuple[list[dict], list[dict]]:
    expanded = expand_terms(terms)
    found: list[dict] = []
    missing: list[dict] = []

    for keyword in terms:
        variants = expanded.get(keyword, {normalize_term(keyword)})
        matched = False
        match_type = "none"
        for variant in variants:
            if variant in cv_text:
                matched = True
                match_type = "exact" if variant == normalize_term(keyword) else "synonym"
                break
        entry = {"term": keyword, "match_type": match_type, "category": category}
        if matched:
            found.append(
                {
                    **entry,
                    "section": "skills" if keyword in parsed_cv.skills.hard else "experience",
                }
            )
        else:
            missing.append({**entry, "suggestion": "solo si consta en tu experiencia"})
    return found, missing


def match_cv_to_job(parsed_cv: ParsedResume, parsed_job: ParsedJob) -> MatchResult:
    cv_text = _cv_search_text(parsed_cv)
    categories = parsed_job.keyword_categories

    technical_terms = list(
        dict.fromkeys(
            categories.technical_required
            or parsed_job.hard_skills
            or parsed_job.keywords
        )
    )
    contextual_terms = list(dict.fromkeys(categories.contextual))
    education_terms = list(dict.fromkeys(categories.education))

    tech_found, tech_missing = _match_terms(
        technical_terms,
        cv_text,
        category="technical",
        parsed_cv=parsed_cv,
    )
    contextual_found, contextual_missing = _match_terms(
        contextual_terms,
        cv_text,
        category="contextual",
        parsed_cv=parsed_cv,
    )
    edu_found, edu_missing = _match_terms(
        education_terms,
        cv_text,
        category="education",
        parsed_cv=parsed_cv,
    )

    keyword_coverage = len(tech_found) / max(len(technical_terms), 1)
    contextual_coverage = (
        len(contextual_found) / max(len(contextual_terms), 1) if contextual_terms else 1.0
    )

    keyword_gaps = {
        "technical_required": tech_missing,
        "technical_optional": [],
        "contextual": contextual_missing,
        "education": edu_missing,
        "language": [
            {"term": term, "category": "language", "match_type": "none"}
            for term in categories.language
        ],
    }

    skills_found = [item["term"] for item in tech_found]
    skills_missing = [item["term"] for item in tech_missing]

    req_coverage: list[dict] = []
    for req in parsed_job.requirements.must:
        norm_req = normalize_term(req)
        status = "missing"
        if any(word in cv_text for word in norm_req.split() if len(word) > 4):
            status = "partial"
        for skill in parsed_cv.evidence_skills:
            if normalize_term(skill) in norm_req:
                status = "found"
                break
        req_coverage.append({"text": req, "status": status, "evidence": None})

    for req in parsed_job.requirements.nice:
        norm_req = normalize_term(req)
        status = "missing"
        if any(word in cv_text for word in norm_req.split() if len(word) > 4):
            status = "partial"
        req_coverage.append({"text": req, "status": status, "evidence": None, "type": "nice"})

    return MatchResult(
        found_keywords=tech_found + contextual_found + edu_found,
        missing_keywords=tech_missing,
        missing_contextual_keywords=contextual_missing,
        missing_education_keywords=edu_missing,
        keyword_gaps=keyword_gaps,
        skills_found=skills_found,
        skills_missing=skills_missing,
        keyword_coverage=keyword_coverage,
        contextual_coverage=contextual_coverage,
        requirements_coverage=req_coverage,
    )
