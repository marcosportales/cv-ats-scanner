from app.domain.ats.rules_engine import run_ats_rules
from app.domain.matching.keyword_matcher import match_cv_to_job
from app.domain.parsing.contact_extractor import extract_contact
from app.domain.parsing.cv_parser import parse_cv
from app.domain.parsing.job_parser import parse_job
from app.domain.scoring.engine import compute_scores
from app.schemas.parsed import ParsedResume


SAMPLE_CV = """
Ana García
ana@email.com
+34 600 000 000
Madrid, España
linkedin.com/in/anagarcia

PERFIL PROFESIONAL
Desarrolladora backend con 5 años en Python y APIs REST.

EXPERIENCIA
TechCo — Backend Developer
2021 - Presente
• Diseñé APIs REST en FastAPI que redujeron latencia un 30%
• Migré servicios a Docker y CI/CD en GitHub Actions

SKILLS
Python, FastAPI, PostgreSQL, Docker, Redis
"""

SAMPLE_JOB = """
Senior Backend Developer
Requisitos:
• 5+ años experiencia backend
• Python y FastAPI en producción
• PostgreSQL
• Docker

Deseable:
• Kubernetes
• Redis
"""


def test_extract_contact():
    contact = extract_contact(SAMPLE_CV)
    assert contact.email == "ana@email.com"
    assert contact.phone is not None


def test_parse_cv():
    parsed = parse_cv(SAMPLE_CV)
    assert "experience" in parsed.sections_detected
    assert "Python" in parsed.skills.hard
    assert parsed.parse_confidence > 0.5


def test_parse_job():
    parsed = parse_job(SAMPLE_JOB, "Senior Backend Developer")
    assert "Python" in parsed.hard_skills or any(
        "python" in k.lower() for k in parsed.keywords
    )


def test_match_and_score():
    parsed_cv = parse_cv(SAMPLE_CV)
    parsed_job = parse_job(SAMPLE_JOB)
    issues = run_ats_rules(SAMPLE_CV, parsed_cv)
    match = match_cv_to_job(parsed_cv, parsed_job)
    result = compute_scores(parsed_cv, parsed_job, match, issues, text_length=len(SAMPLE_CV))
    assert 0 <= result.total_score <= 100
    assert result.level in ("Excellent", "Good", "Fair", "NeedsWork")
    assert len(match.skills_found) > 0
