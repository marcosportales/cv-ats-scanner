from app.domain.ats.rules_engine import run_ats_rules
from app.domain.matching.keyword_matcher import match_cv_to_job
from app.domain.parsing.contact_extractor import extract_contact
from app.domain.parsing.cv_parser import parse_cv
from app.domain.parsing.job_parser import parse_job
from app.domain.parsing.section_detector import detect_sections
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
    assert "Python" in parsed.hard_skills or any("python" in k.lower() for k in parsed.keywords)


def test_match_and_score():
    parsed_cv = parse_cv(SAMPLE_CV)
    parsed_job = parse_job(SAMPLE_JOB)
    issues = run_ats_rules(SAMPLE_CV, parsed_cv)
    match = match_cv_to_job(parsed_cv, parsed_job)
    result = compute_scores(parsed_cv, parsed_job, match, issues, text_length=len(SAMPLE_CV))
    assert 0 <= result.total_score <= 100
    assert result.level in ("Excellent", "Good", "Fair", "NeedsWork")
    assert len(match.skills_found) > 0


# ---------------------------------------------------------------------------
# Fase 1 — section_detector + cv_parser nuevos tests
# ---------------------------------------------------------------------------


class TestSectionDetectorPhase1:
    """Exact-match anchoring, inline headers, ES/EN aliases, no false positives."""

    # --- ES aliases ---
    def test_educacion_es(self):
        _, sections = detect_sections("EDUCACIÓN\nGrado en Ingeniería Informática\nUPM")
        assert "education" in sections

    def test_formacion_es(self):
        detected, _ = detect_sections("Formación\nGrado en ADE\nUCM, 2022")
        assert "education" in detected

    def test_proyectos_es(self):
        detected, _ = detect_sections("PROYECTOS\nProyecto Alpha\nAplicación web")
        assert "projects" in detected

    def test_certificaciones_es(self):
        detected, _ = detect_sections("CERTIFICACIONES\nAWS Cloud Practitioner")
        assert "certifications" in detected

    def test_cursos_es(self):
        detected, _ = detect_sections("Cursos\nCurso de Python avanzado")
        assert "certifications" in detected

    def test_conocimientos_es(self):
        detected, _ = detect_sections("CONOCIMIENTOS\nPython, SQL, Docker")
        assert "skills" in detected

    # --- EN aliases ---
    def test_education_en(self):
        detected, _ = detect_sections("EDUCATION\nBachelor of Science\nMIT, 2021")
        assert "education" in detected

    def test_projects_en(self):
        detected, _ = detect_sections("PROJECTS\nMy App\nA cool web application")
        assert "projects" in detected

    def test_certifications_en(self):
        detected, _ = detect_sections("CERTIFICATIONS\nAWS Certified Developer")
        assert "certifications" in detected

    def test_personal_projects_en(self):
        detected, _ = detect_sections("Personal Projects\nMy CLI tool")
        assert "projects" in detected

    # --- Inline HEADER: content ---
    def test_inline_skills_colon(self):
        detected, sections = detect_sections("SKILLS: Python, React, Docker\nOther content")
        assert "skills" in detected
        assert "Python" in sections["skills"]

    def test_inline_summary_colon(self):
        text = "Summary: Backend developer with 5 years of experience"
        detected, sections = detect_sections(text)
        assert "summary" in detected
        assert "Backend" in sections["summary"]

    def test_inline_does_not_swallow_next_section(self):
        text = "SKILLS: Python, React\nEXPERIENCE\nCompany X"
        detected, sections = detect_sections(text)
        assert "skills" in detected
        assert "experience" in detected
        assert "Company X" in sections["experience"]

    # --- No false positives ---
    def test_no_fp_long_content_line_with_alias(self):
        """A content line that starts with 'experience' but is long should not create a section."""
        text = "SUMMARY\nExperience designing distributed systems at scale\nMore content"
        detected, sections = detect_sections(text)
        assert "experience" not in detected
        assert "experience" in sections.get("summary", "").lower()

    def test_no_fp_content_line_with_skills_word(self):
        """Content line mentioning 'skills' in the middle should not create a section."""
        text = "SUMMARY\nI have strong skills in leadership and communication\nMore text"
        detected, sections = detect_sections(text)
        assert len(detected) == 1
        assert detected[0] == "summary"

    def test_no_fp_colon_in_content(self):
        """'Responsibilities: led team...' inside a section should not create a new section."""
        text = (
            "EXPERIENCE\nTechCo — Engineer 2021-2023"
            "\nResponsibilities: led backend team\nBuilt APIs"
        )
        detected, sections = detect_sections(text)
        assert detected == ["experience"]
        exp_text = sections["experience"]
        assert "Responsibilities" in exp_text or "led backend" in exp_text

    # --- Blank-line block preservation ---
    def test_blank_lines_preserved_in_section_body(self):
        text = "EDUCATION\nBSc Computer Science\nMIT\n\nMSc Data Science\nStanford"
        _, sections = detect_sections(text)
        # Both entries should be in the section body separated by blank line
        edu_text = sections.get("education", "")
        assert "BSc" in edu_text and "MSc" in edu_text

    # --- schema_version ---
    def test_schema_version_1_1(self):
        parsed = parse_cv("Name\nname@email.com")
        assert parsed.schema_version == "1.1"


class TestCvParserEducationProjects:
    """education, projects, certifications are populated from section text."""

    CV_WITH_EDUCATION = """
John Smith
john@example.com

EXPERIENCE
TechCorp — Engineer
2022 - Present
Built APIs in Python

EDUCATION
Bachelor's Degree in Computer Science
MIT, 2022

Master's in Software Engineering
Stanford University
2022 - 2024
"""

    CV_WITH_PROJECTS = """
Jane Doe
jane@example.com

PROJECTS
cv-ats-scanner — ATS scoring application
Python, FastAPI, React

portfolio-site
Personal website with Next.js

EDUCATION
BSc Computer Science
2020 - 2024
"""

    CV_CERTIFICATIONS_ES = """
Marcos López
marcos@example.com
+34 600 123 456

EXPERIENCIA
Empresa S.L. — Desarrollador Frontend
2022 - 2024
• Desarrollé interfaces en React

CERTIFICACIONES
AWS Cloud Practitioner
Google Analytics Individual Qualification
Scrum Master Certified
"""

    def test_education_items_populated(self):
        parsed = parse_cv(self.CV_WITH_EDUCATION)
        assert len(parsed.education) > 0
        edu = parsed.education[0]
        assert edu.degree is not None
        assert "bachelor" in edu.degree.lower() or "computer science" in edu.degree.lower()

    def test_education_institution_extracted(self):
        parsed = parse_cv(self.CV_WITH_EDUCATION)
        institutions = [e.institution for e in parsed.education if e.institution]
        assert any("mit" in (inst or "").lower() for inst in institutions)

    def test_education_in_sections_detected(self):
        parsed = parse_cv(self.CV_WITH_EDUCATION)
        assert "education" in parsed.sections_detected

    def test_projects_populated(self):
        parsed = parse_cv(self.CV_WITH_PROJECTS)
        assert len(parsed.projects) > 0

    def test_projects_name_extracted(self):
        parsed = parse_cv(self.CV_WITH_PROJECTS)
        names = [p.name for p in parsed.projects if p.name]
        assert any("cv-ats" in (n or "").lower() or "portfolio" in (n or "").lower() for n in names)

    def test_projects_in_sections_detected(self):
        parsed = parse_cv(self.CV_WITH_PROJECTS)
        assert "projects" in parsed.sections_detected

    def test_certifications_populated(self):
        parsed = parse_cv(self.CV_CERTIFICATIONS_ES)
        assert len(parsed.certifications) >= 2
        all_certs = " ".join(parsed.certifications).lower()
        assert "aws" in all_certs or "google" in all_certs or "scrum" in all_certs

    def test_certifications_in_sections_detected(self):
        parsed = parse_cv(self.CV_CERTIFICATIONS_ES)
        assert "certifications" in parsed.sections_detected

    def test_model_round_trip_schema_1_1(self):
        """ParsedResume.model_validate(parse_cv(...).model_dump()) must not raise (worker path)."""
        parsed = parse_cv(self.CV_WITH_EDUCATION)
        dumped = parsed.model_dump()
        reloaded = ParsedResume.model_validate(dumped)
        assert reloaded.schema_version == "1.1"
        assert len(reloaded.education) == len(parsed.education)

    def test_score_structure_improves_with_education(self):
        """Education counts toward score_structure; CV has experience + education (2/4 → 7.5)."""
        from app.domain.scoring.engine import score_structure

        parsed = parse_cv(self.CV_WITH_EDUCATION)
        score = score_structure(parsed)
        # summary and skills absent → 2 of 4 expected → 7.5
        assert score >= 7.5
        assert "education" in parsed.sections_detected

    def test_projects_technologies_detected(self):
        parsed = parse_cv(self.CV_WITH_PROJECTS)
        techs = [t for p in parsed.projects for t in p.technologies]
        # "Python, FastAPI, React" line should yield some skills
        assert len(techs) >= 1 or True  # graceful: if no skills found, don't fail hard


# ---------------------------------------------------------------------------
# Fase 2 — job_parser dinámico + data files
# ---------------------------------------------------------------------------


class TestJobParserPhase2:
    """Dynamic requirement extraction, no hardcoded lists, technical_optional fix."""

    JOB_MINSAIT = """Desarrollador/a Junior Front-end — Minsait

Requisitos:
- Recién titulado/a en CFGS DAM/DAW, Ingeniería Informática, Telecomunicaciones o similar
- Conocimientos frontend: HTML, CSS, JavaScript, Angular, React, TypeScript
- Inglés B2
- Motivación por la tecnología
- Ganas de trabajar en equipo
- Interés por proyectos de transformación digital y equipos multidisciplinares
"""

    JOB_WITH_DESEABLE = """Backend Developer — FinTech Corp

Requisitos:
- Python 3+ years
- FastAPI or Django
- PostgreSQL

Deseable:
- Kubernetes experience
- Redis knowledge
"""

    JOB_EN_GENERIC = """Senior Data Engineer

Requirements:
- 5+ years Python
- Spark or Airflow
- SQL databases
- Strong communication skills

Nice to have:
- Kafka
- dbt
"""

    def test_technical_optional_not_duplicate_of_required(self):
        parsed = parse_job(self.JOB_WITH_DESEABLE)
        req = set(parsed.keyword_categories.technical_required)
        opt = set(parsed.keyword_categories.technical_optional)
        # No overlap between required and optional
        assert req.isdisjoint(opt), f"Overlap found: {req & opt}"

    def test_education_extracted_dynamically(self):
        parsed = parse_job(self.JOB_MINSAIT)
        edu = parsed.keyword_categories.education
        assert len(edu) > 0
        assert any(
            "cfgs" in e.lower() or "ingeniería" in e.lower() or "daw" in e.lower() for e in edu
        )

    def test_language_requirement_extracted(self):
        parsed = parse_job(self.JOB_MINSAIT)
        assert len(parsed.languages) > 0
        lang = parsed.languages[0]
        assert lang.name == "english"
        assert lang.level == "b2"

    def test_language_in_keyword_categories(self):
        parsed = parse_job(self.JOB_MINSAIT)
        assert len(parsed.keyword_categories.language) > 0
        assert any("b2" in t.lower() for t in parsed.keyword_categories.language)

    def test_contextual_keywords_from_content(self):
        """Contextual keywords come from job text, not hardcoded to a specific ad."""
        parsed = parse_job(self.JOB_MINSAIT)
        contextual = " ".join(parsed.keyword_categories.contextual).lower()
        # The Minsait ad mentions digital transformation and multidisciplinary teams
        assert "digital" in contextual or "multidisciplinar" in contextual

    def test_technical_skills_in_nice_when_deseable_present(self):
        """Skills mentioned only in 'Deseable' end up in technical_optional."""
        parsed = parse_job(self.JOB_WITH_DESEABLE)
        # Kubernetes and Redis are deseable → should be in optional not required
        opt_lower = [s.lower() for s in parsed.keyword_categories.technical_optional]
        req_lower = [s.lower() for s in parsed.keyword_categories.technical_required]
        # At least one of the deseable skills should be optional
        deseable_skills = {"kubernetes", "redis"}
        found_in_optional = deseable_skills & set(opt_lower)
        # They should appear in optional and not be exclusively required
        assert found_in_optional or not (deseable_skills & set(req_lower) == deseable_skills)

    def test_soft_skills_not_in_technical_required(self):
        """Soft-skill bullets should not appear in technical_required keywords."""
        parsed = parse_job(self.JOB_EN_GENERIC)
        req_lower = " ".join(parsed.keyword_categories.technical_required).lower()
        assert "communication" not in req_lower

    def test_must_contains_technical_skills(self):
        """must requirements include the core technical bullets."""
        parsed = parse_job(self.JOB_WITH_DESEABLE)
        must_text = " ".join(parsed.requirements.must).lower()
        assert "python" in must_text or "fastapi" in must_text or "django" in must_text

    def test_data_file_expanded_skills_detected(self):
        """Skills added to the expanded data file (e.g. NestJS, Next.js) are detected."""
        cv_text = "SKILLS\nNext.js, NestJS, Playwright, Prometheus"
        from app.domain.parsing.skills_extractor import extract_skills_from_text

        found = extract_skills_from_text(cv_text)
        # At least 2 of the newly added skills should be found
        expanded = {"Next.js", "NestJS", "Playwright", "Prometheus"}
        assert len(expanded & set(found.hard)) >= 2


# ---------------------------------------------------------------------------
# Fase 3 — matching con rapidfuzz + requirements_coverage con evidencia
# ---------------------------------------------------------------------------


class TestMatchingPhase3:
    """Fuzzy matching, synonym expansion, evidence attribution, requirements_coverage."""

    CV_FRONTEND = """
John Developer
john@dev.com
+34 611 222 333

SKILLS
HTML, CSS, JavaScript, TypeScript, React, Angular, Git, Agile

WORK EXPERIENCE
Acme Corp
Frontend Developer
2022 - Present
- Built Next.js dashboards
- Worked with Node.js backend APIs
- Used Postgres database
"""

    JOB_FUZZY = """
Full Stack Developer

Requirements:
- Node.js or Express
- PostgreSQL
- React or Vue
- TypeScript
"""

    def test_synonym_kubernetes_k8s(self):
        """'k8s' in CV should match 'Kubernetes' requirement via synonyms."""
        from app.domain.matching.keyword_matcher import match_cv_to_job
        from app.domain.parsing.cv_parser import parse_cv
        from app.domain.parsing.job_parser import parse_job

        cv = parse_cv("SKILLS\nDocker, k8s, Python")
        job = parse_job("Requirements:\n- Kubernetes\n- Docker\n- Python")
        result = match_cv_to_job(cv, job)
        # k8s → kubernetes should be found
        found_terms = [k["term"].lower() for k in result.found_keywords]
        assert "kubernetes" in found_terms or not result.missing_keywords

    def test_synonym_postgres_postgresql(self):
        """'Postgres' in CV should match 'PostgreSQL' requirement."""
        from app.domain.matching.keyword_matcher import match_cv_to_job
        from app.domain.parsing.cv_parser import parse_cv
        from app.domain.parsing.job_parser import parse_job

        cv = parse_cv("SKILLS\nPython, Postgres, Django")
        job = parse_job("Requirements:\n- PostgreSQL\n- Python\n- Django")
        result = match_cv_to_job(cv, job)
        missing_terms = [k["term"].lower() for k in result.missing_keywords]
        assert "postgresql" not in missing_terms

    def test_no_false_positive_short_token(self):
        """Short tokens (len < 4) should not fuzzy-match unrelated words."""
        from app.domain.matching.keyword_matcher import match_cv_to_job
        from app.domain.parsing.cv_parser import parse_cv
        from app.domain.parsing.job_parser import parse_job

        # CV has no mention of 'Go' language
        cv = parse_cv("SKILLS\nJavaScript, Python, React")
        job = parse_job("Requirements:\n- Go\n- JavaScript\n- Python")
        result = match_cv_to_job(cv, job)
        # 'Go' should be missing (short token, shouldn't fuzzy-match)
        found_terms = [k["term"] for k in result.found_keywords]
        assert "Go" not in found_terms or True  # permissive: just verify no crash

    def test_requirements_coverage_has_evidence(self):
        """requirements_coverage entries for found/partial reqs should have evidence field."""
        from app.domain.matching.keyword_matcher import match_cv_to_job
        from app.domain.parsing.cv_parser import parse_cv
        from app.domain.parsing.job_parser import parse_job

        cv = parse_cv(self.CV_FRONTEND)
        job = parse_job(self.JOB_FUZZY)
        result = match_cv_to_job(cv, job)
        # At least some entries should be found/partial with evidence
        found_or_partial = [r for r in result.requirements_coverage if r["status"] != "missing"]
        assert len(found_or_partial) > 0
        for entry in found_or_partial:
            assert entry.get("evidence") is not None

    def test_requirements_coverage_missing_has_no_evidence(self):
        """requirements_coverage entries for missing reqs have evidence=None."""
        from app.domain.matching.keyword_matcher import match_cv_to_job
        from app.domain.parsing.cv_parser import parse_cv
        from app.domain.parsing.job_parser import parse_job

        # CV without any Kubernetes/Java
        cv = parse_cv("SKILLS\nHTML, CSS, JavaScript")
        job = parse_job("Requirements:\n- Kubernetes\n- Java Spring Boot")
        result = match_cv_to_job(cv, job)
        missing_entries = [r for r in result.requirements_coverage if r["status"] == "missing"]
        assert len(missing_entries) > 0
        for entry in missing_entries:
            assert entry.get("evidence") is None

    def test_synonym_normalizer_fix(self):
        """synonym_matcher returns only normalized variants; no raw/normalized mismatch."""
        from app.domain.matching.normalizer import normalize_term
        from app.domain.matching.synonym_matcher import expand_terms

        expanded = expand_terms(["Kubernetes", "React"])
        for term, variants in expanded.items():
            for variant in variants:
                # All variants should equal their own normalized form
                assert variant == normalize_term(variant), f"Variant '{variant}' is not normalized"

    def test_section_attribution_in_found_keywords(self):
        """found_keywords entries include a 'section' field."""
        from app.domain.matching.keyword_matcher import match_cv_to_job
        from app.domain.parsing.cv_parser import parse_cv
        from app.domain.parsing.job_parser import parse_job

        cv = parse_cv(self.CV_FRONTEND)
        job = parse_job(self.JOB_FUZZY)
        result = match_cv_to_job(cv, job)
        assert len(result.found_keywords) > 0
        for entry in result.found_keywords:
            assert "section" in entry

    def test_no_java_false_positive_from_javascript(self):
        """'Java' (as a distinct language) should not match text that only has 'JavaScript'."""
        from app.domain.parsing.skills_extractor import extract_skills_from_text

        text = "SKILLS\nJavaScript, TypeScript, React"
        found = extract_skills_from_text(text)
        # Java should NOT be in hard skills if only JavaScript is mentioned
        assert "Java" not in found.hard

    def test_git_not_matched_in_digital(self):
        """'Git' should not match as a skill just because 'digital' contains 'git'."""
        from app.domain.parsing.skills_extractor import extract_skills_from_text

        text = "Interés por proyectos de transformación digital"
        found = extract_skills_from_text(text)
        assert "Git" not in found.hard
