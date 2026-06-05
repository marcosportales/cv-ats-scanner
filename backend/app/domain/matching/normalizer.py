import re
import unicodedata


def normalize_term(term: str) -> str:
    term = term.lower().strip()
    term = unicodedata.normalize("NFKD", term)
    term = "".join(c for c in term if not unicodedata.combining(c))
    term = re.sub(r"[^\w\s.+#/-]", "", term)
    return term.strip()
