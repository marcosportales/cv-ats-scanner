from dataclasses import dataclass, field

from rapidfuzz import fuzz

from app.domain.matching.normalizer import normalize_term
from app.domain.matching.synonym_matcher import expand_terms
from app.schemas.parsed import ParsedJob, ParsedResume

# Fuzzy similarity threshold (token_set_ratio).  High to avoid false positives.
_FUZZY_THRESHOLD = 88
# Minimum normalized token length for fuzzy matching (skip very short tokens).
_MIN_FUZZY_LEN = 4


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


# ── CV text helpers ──────────────────────────────────────────────────────────


def _section_texts(parsed: ParsedResume) -> dict[str, str]:
    """Return normalized text per CV section for evidence attribution."""
    skills_text = normalize_term(" ".join(parsed.skills.hard))
    summary_text = normalize_term(parsed.summary or "")
    exp_parts: list[str] = []
    for exp in parsed.experience:
        exp_parts.append(exp.role or "")
        exp_parts.append(exp.company or "")
        exp_parts.extend(exp.bullets)
        exp_parts.extend(exp.skills_mentioned)
    exp_text = normalize_term(" ".join(exp_parts))
    proj_text = normalize_term(
        " ".join(
            f"{p.name or ''} {p.description or ''} {' '.join(p.technologies)}"
            for p in parsed.projects
        )
    )
    return {
        "skills": skills_text,
        "summary": summary_text,
        "experience": exp_text,
        "projects": proj_text,
    }


def _cv_search_text(parsed: ParsedResume) -> str:
    sections = _section_texts(parsed)
    return " ".join(sections.values())


# ── Core term matching ───────────────────────────────────────────────────────


def _fuzzy_match(query: str, text: str) -> bool:
    """True if *query* fuzzy-matches any word-group in *text* above threshold."""
    if len(query) < _MIN_FUZZY_LEN:
        return False
    score = fuzz.partial_ratio(query, text)
    return score >= _FUZZY_THRESHOLD


def _match_term_in_text(norm_term: str, variants: set[str], cv_text: str) -> str:
    """Return 'exact', 'synonym', 'fuzzy', or 'none'."""
    for variant in variants:
        if variant in cv_text:
            return "exact" if variant == norm_term else "synonym"
    # Fuzzy fallback for multi-char terms
    if len(norm_term) >= _MIN_FUZZY_LEN and _fuzzy_match(norm_term, cv_text):
        return "fuzzy"
    return "none"


def _find_section(norm_term: str, variants: set[str], section_texts: dict[str, str]) -> str:
    """Return the CV section where the term was found, or 'unknown'."""
    for section, text in section_texts.items():
        for variant in variants:
            if variant in text:
                return section
    return "unknown"


def _match_terms(
    terms: list[str],
    cv_text: str,
    section_texts: dict[str, str],
    *,
    category: str,
) -> tuple[list[dict], list[dict]]:
    expanded = expand_terms(terms)
    found: list[dict] = []
    missing: list[dict] = []

    for keyword in terms:
        norm = normalize_term(keyword)
        variants = expanded.get(keyword, {norm})
        match_type = _match_term_in_text(norm, variants, cv_text)
        entry = {"term": keyword, "match_type": match_type, "category": category}
        if match_type != "none":
            section = _find_section(norm, variants, section_texts)
            found.append({**entry, "section": section})
        else:
            missing.append({**entry, "suggestion": "solo si consta en tu experiencia"})
    return found, missing


# ── Requirements coverage ────────────────────────────────────────────────────


def _req_coverage_entry(
    req_text: str,
    cv_text: str,
    section_texts: dict[str, str],
    *,
    req_type: str = "must",
) -> dict:
    """Compute found/partial/missing for a single requirement line.

    Strategy:
    - Extract individual words from the requirement (length >= 4).
    - Use exact whole-token matching against the CV word set to avoid false positives
      (e.g. "java" substring-matching inside "javascript").
    - found   if all meaningful words covered
    - partial if at least one covered
    - missing if none covered
    """
    norm_req = normalize_term(req_text)
    meaningful = [w for w in norm_req.split() if len(w) >= 4]
    if not meaningful:
        status = "missing"
        evidence = None
    else:
        # Exact whole-word matching — prevents "java" from matching inside "javascript"
        cv_word_set = set(cv_text.split())
        hits = [w for w in meaningful if w in cv_word_set]
        if len(hits) == len(meaningful):
            status = "found"
        elif hits:
            status = "partial"
        else:
            status = "missing"

        evidence_section = None
        for section, stext in section_texts.items():
            swords = set(stext.split())
            if any(w in swords for w in hits):
                evidence_section = section
                break
        evidence = f"words matched: {hits[:3]} (in {evidence_section})" if hits else None

    entry: dict = {"text": req_text, "status": status, "evidence": evidence}
    if req_type == "nice":
        entry["type"] = "nice"
    return entry


# ── Public entry point ───────────────────────────────────────────────────────


def match_cv_to_job(parsed_cv: ParsedResume, parsed_job: ParsedJob) -> MatchResult:
    section_texts = _section_texts(parsed_cv)
    cv_text = _cv_search_text(parsed_cv)
    categories = parsed_job.keyword_categories

    technical_terms = list(
        dict.fromkeys(
            categories.technical_required or parsed_job.hard_skills or parsed_job.keywords
        )
    )
    contextual_terms = list(dict.fromkeys(categories.contextual))
    education_terms = list(dict.fromkeys(categories.education))

    tech_found, tech_missing = _match_terms(
        technical_terms, cv_text, section_texts, category="technical"
    )
    contextual_found, contextual_missing = _match_terms(
        contextual_terms, cv_text, section_texts, category="contextual"
    )
    edu_found, edu_missing = _match_terms(
        education_terms, cv_text, section_texts, category="education"
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
        req_coverage.append(_req_coverage_entry(req, cv_text, section_texts, req_type="must"))
    for req in parsed_job.requirements.nice:
        req_coverage.append(_req_coverage_entry(req, cv_text, section_texts, req_type="nice"))

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
