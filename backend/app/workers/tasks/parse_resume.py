import uuid
from datetime import datetime, timezone

from app.db.sync_session import get_sync_db
from app.domain.ats.rules_engine import run_ats_rules
from app.domain.extraction.docx_extractor import extract_docx_text
from app.domain.extraction.pdf_extractor import extract_pdf_text
from app.domain.parsing.cv_parser import parse_cv
from app.integrations.storage.s3_client import download_file
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.parse_resume.parse_resume_task")
def parse_resume_task(resume_id: str) -> None:
    with get_sync_db() as db:
        from app.db.models.file import File
        from app.db.models.resume import Resume

        resume = db.get(Resume, uuid.UUID(resume_id))
        if not resume or not resume.file_id:
            return

        resume.parse_status = "processing"
        db.commit()

        try:
            file_record = db.get(File, resume.file_id)
            content = download_file(file_record.storage_key)
            needs_ocr = False
            chars_per_page = 500.0
            image_count = 0

            if file_record.mime_type == "application/pdf":
                result = extract_pdf_text(content)
                text = result.text
                needs_ocr = result.needs_ocr
                chars_per_page = result.chars_per_page
                image_count = result.image_count
                method = result.method
            else:
                text = extract_docx_text(content)
                method = "docx"

            resume.raw_text = text
            resume.extraction_method = method
            parsed = parse_cv(text)
            issues = run_ats_rules(
                text,
                parsed,
                needs_ocr=needs_ocr,
                image_count=image_count,
                chars_per_page=chars_per_page,
            )
            parsed_dict = parsed.model_dump()
            parsed_dict["_ats_issues"] = [i.to_dict() for i in issues]
            parsed_dict["_extraction_meta"] = {
                "needs_ocr": needs_ocr,
                "chars_per_page": chars_per_page,
                "text_length": len(text),
                "image_count": image_count,
            }
            resume.parsed_json = parsed_dict
            resume.language_detected = parsed.language
            resume.parse_status = "completed"
            resume.parse_errors = None
        except Exception as exc:
            resume.parse_status = "failed"
            resume.parse_errors = {"error": str(exc)}
        resume.updated_at = datetime.now(timezone.utc)
        db.commit()
