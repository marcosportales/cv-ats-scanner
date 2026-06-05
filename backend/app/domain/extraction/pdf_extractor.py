from dataclasses import dataclass

import fitz


@dataclass
class PdfExtractionResult:
    text: str
    chars_per_page: float
    page_count: int
    image_count: int
    needs_ocr: bool
    method: str


def extract_pdf_text(content: bytes, ocr_threshold: float = 50.0) -> PdfExtractionResult:
    doc = fitz.open(stream=content, filetype="pdf")
    pages_text: list[str] = []
    image_count = 0
    for page in doc:
        pages_text.append(page.get_text("text"))
        image_count += len(page.get_images())

    text = "\n".join(pages_text).strip()
    page_count = max(len(doc), 1)
    chars_per_page = len(text) / page_count
    needs_ocr = len(text) < 100 or chars_per_page < ocr_threshold
    doc.close()

    return PdfExtractionResult(
        text=text,
        chars_per_page=chars_per_page,
        page_count=page_count,
        image_count=image_count,
        needs_ocr=needs_ocr,
        method="ocr" if needs_ocr else "pymupdf",
    )
