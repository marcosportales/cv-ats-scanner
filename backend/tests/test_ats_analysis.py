"""Tests for ATS analysis improvements (phone, sections, keywords, scoring)."""

from app.domain.ats.rules_engine import build_detection_evidence, run_ats_rules
from app.domain.matching.keyword_matcher import match_cv_to_job
from app.domain.matching.language_matcher import compare_language_requirements
from app.domain.parsing.contact_extractor import extract_contact
from app.domain.parsing.cv_parser import parse_cv
from app.domain.parsing.job_parser import parse_job
from app.domain.parsing.language_extractor import extract_languages, extract_required_languages
from app.domain.parsing.section_detector import detect_sections
from app.domain.scoring.engine import compute_scores

SAMPLE_CV = """Marcos Portales
marcos@example.com
+34 601 86 32 35
Madrid, Spain

SUMMARY
Frontend developer with experience building React and Angular interfaces.

SKILLS
HTML, CSS, JavaScript, TypeScript, React, Angular, Git, Agile

WORK EXPERIENCE
Acme Corp
Frontend Developer
2023 - Present
- Built reusable React components and dashboards
- Collaborated in agile remote teams
- Integrated REST APIs into user interfaces

EDUCATION
Bachelor's Degree in Computer Science
University of Example, 2023

LANGUAGES
English (B1)
Spanish (Native)
"""

SAMPLE_JOB = """Desarrollador/a Junior Front-end — Minsait

Requisitos:
- Recién titulado/a en CFGS DAM/DAW, Ingeniería Informática, Telecomunicaciones o similar
- Conocimientos frontend: HTML, CSS, JavaScript, Angular, React, TypeScript
- Inglés B2
- Motivación por la tecnología
- Ganas de trabajar en equipo
- Interés por proyectos de transformación digital y equipos multidisciplinares
"""


class TestPhoneDetection:
    def test_spanish_phone_with_spaces(self):
        contact = extract_contact("Contact: +34 601 86 32 35")
        assert contact.phone == "+34 601 86 32 35"

    def test_spanish_phone_compact(self):
        contact = extract_contact("Tel: +34601863235")
        assert contact.phone is not None
        assert "601863235" in contact.phone.replace(" ", "")

    def test_spanish_phone_local_format(self):
        contact = extract_contact("601 86 32 35")
        assert contact.phone == "601 86 32 35"

    def test_spanish_phone_with_parentheses(self):
        contact = extract_contact("Phone: (+34) 601 86 32 35")
        assert contact.phone is not None

    def test_spanish_phone_with_0034(self):
        contact = extract_contact("0034 601 86 32 35")
        assert contact.phone is not None

    def test_spanish_phone_with_dashes(self):
        contact = extract_contact("Tel: +34-601-86-32-35")
        assert contact.phone is not None


class TestSectionDetection:
    def test_work_experience_header(self):
        text = "WORK EXPERIENCE\nCompany\nRole"
        detected, sections = detect_sections(text)
        assert "experience" in detected
        assert "Company" in sections["experience"]

    def test_professional_experience_header(self):
        text = "Professional Experience\nCompany"
        detected, _ = detect_sections(text)
        assert "experience" in detected

    def test_experiencia_laboral_header(self):
        text = "Experiencia Laboral\nEmpresa"
        detected, _ = detect_sections(text)
        assert "experience" in detected


class TestLanguageDetection:
    def test_comma_separated_languages(self):
        langs = extract_languages("", "Spanish (Native), English (B1)")
        by_name = {lang.name: lang.level for lang in langs}
        assert by_name["english"] == "b1"
        assert by_name["spanish"] == "native"

    def test_english_colon_b1(self):
        langs = extract_languages("Languages\nEnglish: B1")
        assert any(lang.name == "english" and lang.level == "b1" for lang in langs)

    def test_ingles_b1(self):
        langs = extract_languages("Idiomas\nInglés B1")
        assert any(lang.name == "english" and lang.level == "b1" for lang in langs)

    def test_reverse_b1_english(self):
        langs = extract_languages("Languages\nB1 English")
        assert any(lang.name == "english" and lang.level == "b1" for lang in langs)

    def test_language_gap_not_absent_when_b1_present(self):
        cv_langs = extract_languages("", "Spanish (Native), English (B1)")
        job_langs = extract_required_languages("Inglés B2")
        result = compare_language_requirements(cv_langs, job_langs)
        assert len(result.gaps) == 1
        assert result.gaps[0].status == "insufficient"
        assert result.gaps[0].cv_level == "b1"
        assert "no lo menciona" not in result.gaps[0].message.lower()
        assert "brecha moderada" in result.gaps[0].message.lower()


class TestMinsaitCase:
    def test_no_false_positive_phone_or_experience(self):
        parsed = parse_cv(SAMPLE_CV)
        issues = run_ats_rules(SAMPLE_CV, parsed)
        issue_ids = {issue.id for issue in issues}
        assert parsed.contact.phone is not None
        assert "experience" in parsed.sections_detected
        assert "ATS_NO_PHONE" not in issue_ids
        assert "ATS_NO_EXPERIENCE_SECTION" not in issue_ids

    def test_technical_keywords_not_missing(self):
        parsed_cv = parse_cv(SAMPLE_CV)
        parsed_job = parse_job(SAMPLE_JOB)
        match = match_cv_to_job(parsed_cv, parsed_job)
        missing_technical = [k["term"] for k in match.missing_keywords]
        for skill in ["HTML", "CSS", "JavaScript", "TypeScript", "React", "Angular"]:
            assert skill not in missing_technical

    def test_language_gap_detected(self):
        parsed_cv = parse_cv(SAMPLE_CV)
        parsed_job = parse_job(SAMPLE_JOB)
        issues = run_ats_rules(SAMPLE_CV, parsed_cv)
        match = match_cv_to_job(parsed_cv, parsed_job)
        result = compute_scores(parsed_cv, parsed_job, match, issues)
        assert result.language_gaps
        assert result.language_gaps[0]["required_level"] == "b2"
        assert result.language_gaps[0]["cv_level"] == "b1"
        assert result.language_gaps[0]["status"] == "insufficient"
        assert "brecha moderada" in result.language_gaps[0]["message"].lower()

    def test_score_in_reasonable_range(self):
        parsed_cv = parse_cv(SAMPLE_CV)
        parsed_job = parse_job(SAMPLE_JOB)
        issues = run_ats_rules(SAMPLE_CV, parsed_cv)
        match = match_cv_to_job(parsed_cv, parsed_job)
        result = compute_scores(parsed_cv, parsed_job, match, issues)
        assert 68 <= result.total_score <= 85
        assert result.categories.ats_parseability >= 14
        assert "ATS_NO_PHONE" not in {i["id"] for i in result.critical_issues}
        assert "ATS_NO_EXPERIENCE_SECTION" not in {i["id"] for i in result.critical_issues}

    def test_summary_mentions_language_not_false_technical_gaps(self):
        parsed_cv = parse_cv(SAMPLE_CV)
        parsed_job = parse_job(SAMPLE_JOB)
        issues = run_ats_rules(SAMPLE_CV, parsed_cv)
        match = match_cv_to_job(parsed_cv, parsed_job)
        result = compute_scores(parsed_cv, parsed_job, match, issues)
        assert "Faltan" not in result.summary or "keywords técnicas" not in result.summary
        assert "B2" in result.summary or "b2" in result.summary.lower()
        assert "brecha moderada" in result.summary.lower()

    def test_detection_evidence_positive_signals(self):
        parsed_cv = parse_cv(SAMPLE_CV)
        parsed_job = parse_job(SAMPLE_JOB)
        match = match_cv_to_job(parsed_cv, parsed_job)
        issues = run_ats_rules(SAMPLE_CV, parsed_cv)
        result = compute_scores(parsed_cv, parsed_job, match, issues)
        evidence_text = " ".join(item["detail"] for item in result.detection_evidence)
        assert "Teléfono: detectado" in evidence_text
        assert "Experiencia: detectada" in evidence_text
        assert "English B1" in evidence_text or "english b1" in evidence_text.lower()

    def test_missing_keyword_lists_exact_term(self):
        cv = SAMPLE_CV.replace("Angular", "")
        parsed_cv = parse_cv(cv)
        parsed_job = parse_job(SAMPLE_JOB)
        match = match_cv_to_job(parsed_cv, parsed_job)
        issues = run_ats_rules(cv, parsed_cv)
        result = compute_scores(parsed_cv, parsed_job, match, issues)
        assert "Angular" in result.summary
        assert "Falta 1 keyword técnica relevante: Angular" in result.summary


class TestProfessionalLinks:
    def test_urls_detected_as_ok(self):
        text = "linkedin.com/in/user github.com/user"
        contact = extract_contact(text)
        assert contact.professional_links_level == "ok"

    def test_mentions_without_urls(self):
        text = "Profiles: LinkedIn, GitHub"
        contact = extract_contact(text)
        assert contact.professional_links_level == "mention_only"
        issues = run_ats_rules(text, parse_cv(text))
        assert any(i.id == "ATS_LINKS_MENTION_ONLY" for i in issues)

    def test_no_mentions_or_urls(self):
        text = "John Doe\njohn@example.com"
        contact = extract_contact(text)
        assert contact.professional_links_level == "missing"
