import io

from docx import Document


def extract_docx_text(content: bytes) -> str:
    doc = Document(io.BytesIO(content))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)
