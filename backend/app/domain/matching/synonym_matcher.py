import json
from pathlib import Path

from app.domain.matching.normalizer import normalize_term

_SYNONYMS_PATH = Path(__file__).resolve().parents[3] / "data" / "synonyms.json"
_CACHE: dict[str, list[str]] | None = None


def _load_synonyms() -> dict[str, list[str]]:
    global _CACHE
    if _CACHE is None:
        with open(_SYNONYMS_PATH) as f:
            _CACHE = {
                normalize_term(k): [normalize_term(v) for v in vals]
                for k, vals in json.load(f).items()
            }
    return _CACHE


def expand_terms(terms: list[str]) -> dict[str, set[str]]:
    """Return mapping term → set of normalized variants (term itself + synonyms).

    All returned variants are normalized so they can be compared directly against
    a normalized CV search text.
    """
    synonyms = _load_synonyms()
    expanded: dict[str, set[str]] = {}
    for term in terms:
        norm = normalize_term(term)
        group: set[str] = {norm}  # only normalized forms — cv_text is also normalized
        for key, vals in synonyms.items():
            if norm == key or norm in vals:
                group.add(key)
                group.update(vals)
        expanded[term] = group
    return expanded
