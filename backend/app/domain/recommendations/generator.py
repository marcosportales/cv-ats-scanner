import json

from app.schemas.parsed import AnalysisResult, ParsedJob, ParsedResume

RECO_PROMPT_VERSION = "reco-v1"

DISCLAIMER = (
    "Recomendaciones generadas por IA o plantillas. Revisa manualmente antes de enviar tu CV. "
    "La puntuación es estimada y no garantiza contratación."
)


def generate_template_recommendations(
    parsed_cv: ParsedResume,
    parsed_job: ParsedJob,
    result: AnalysisResult,
) -> dict:
    items: list[dict] = []

    if parsed_cv.summary and len(parsed_cv.summary) < 80:
        items.append(
            {
                "section": "summary",
                "priority": "high",
                "issue": "Perfil profesional demasiado breve",
                "recommendation": "Amplía el resumen mencionando tu especialidad y años de experiencia",
                "explanation": "Un perfil de 3-4 líneas mejora la primera impresión ATS",
                "optional_rewrite": None,
            }
        )

    for kw in result.missing_keywords[:5]:
        term = kw.get("term", "")
        if term.lower() in [s.lower() for s in parsed_cv.evidence_skills]:
            items.append(
                {
                    "section": "skills",
                    "priority": "medium",
                    "issue": f"'{term}' está en tu CV pero poco visible",
                    "recommendation": f"Haz más visible '{term}' en skills o bullets de experiencia",
                    "explanation": "La evidencia existe; mejora su prominencia sin inventar uso",
                    "optional_rewrite": None,
                }
            )
        else:
            items.append(
                {
                    "section": "skills",
                    "priority": "low",
                    "issue": f"Falta '{term}' en el CV",
                    "recommendation": f"No añadas '{term}' si no la has usado realmente",
                    "explanation": "Solo incluye tecnologías con evidencia en tu experiencia",
                    "optional_rewrite": None,
                }
            )

    bullets_without_metrics = [
        b
        for exp in parsed_cv.experience
        for b in exp.bullets
        if not any(c.isdigit() for c in b)
    ]
    if bullets_without_metrics:
        items.append(
            {
                "section": "experience",
                "priority": "medium",
                "issue": "Bullets sin métricas cuantificables",
                "recommendation": "Añade impacto medible (%, tiempo, volumen) donde sea honesto",
                "explanation": "Las métricas mejoran writing_quality sin inventar tecnologías",
                "optional_rewrite": {
                    "before": bullets_without_metrics[0],
                    "after": bullets_without_metrics[0]
                    + " (añade cifra real si la tienes)",
                },
            }
        )

    for issue in result.critical_issues[:3]:
        items.append(
            {
                "section": "ats",
                "priority": "high" if issue.get("severity") == "high" else "medium",
                "issue": issue.get("message", ""),
                "recommendation": issue.get("fix_hint", "Corrige este problema ATS"),
                "explanation": f"Riesgo ATS: {issue.get('id', '')}",
                "optional_rewrite": None,
            }
        )

    return {
        "analysis_id": None,
        "prompt_version": RECO_PROMPT_VERSION,
        "items": items,
        "ats_risks_highlighted": [i.get("id") for i in result.critical_issues],
        "missing_keywords_addressed": [
            {"term": k.get("term"), "action": "visibility_or_honest_gap"}
            for k in result.missing_keywords[:10]
        ],
        "disclaimer": DISCLAIMER,
    }


def build_llm_messages(
    parsed_cv: ParsedResume,
    parsed_job: ParsedJob,
    result: AnalysisResult,
) -> list[dict]:
    system = """Eres un asesor de carrera experto en ATS. REGLAS ESTRICTAS:
1. NO inventes experiencia, empleos, fechas, empresas ni tecnologías.
2. NO sugieras añadir tecnología salvo que esté en evidence_skills.
3. Responde SOLO JSON válido con keys: items (array), ats_risks_highlighted, missing_keywords_addressed.
4. Cada item: section, priority, issue, recommendation, explanation, optional_rewrite (before/after o null)."""

    user_payload = {
        "parsed_resume": parsed_cv.model_dump(),
        "parsed_job": parsed_job.model_dump(),
        "analysis": result.model_dump(),
        "allowed_skills_evidence": parsed_cv.evidence_skills,
        "missing_keywords": result.missing_keywords,
        "ats_issues": result.critical_issues,
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
    ]
