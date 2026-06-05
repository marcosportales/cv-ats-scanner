import hashlib


def embed_text(text: str, dimensions: int = 384) -> list[float]:
    """Deterministic pseudo-embedding for local/dev without ML deps."""
    digest = hashlib.sha256(text.encode()).digest()
    values = []
    for i in range(dimensions):
        byte = digest[i % len(digest)]
        values.append((byte / 255.0) * 2 - 1)
    return values
