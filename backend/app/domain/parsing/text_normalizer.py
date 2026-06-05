import re
import unicodedata


def normalize_header(text: str) -> str:
    """Normalize a CV section header for flexible matching."""
    text = text.lower().strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def singularize_header(text: str) -> str:
    """Reduce simple plural forms for header equivalence."""
    words = text.split()
    normalized_words: list[str] = []
    for word in words:
        if word.endswith("ies") and len(word) > 4:
            normalized_words.append(word[:-3] + "y")
        elif word.endswith("s") and not word.endswith("ss") and len(word) > 3:
            normalized_words.append(word[:-1])
        else:
            normalized_words.append(word)
    return " ".join(normalized_words)
