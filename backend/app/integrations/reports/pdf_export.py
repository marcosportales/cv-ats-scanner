from io import BytesIO

DISCLAIMER_HTML = """
<p style="font-size:10px;color:#666;">
  Puntuación estimada con fines orientativos. No garantiza contratación ni decisión automática.
  Revisa manualmente antes de enviar tu CV.
</p>
"""


def generate_analysis_pdf(analysis_result: dict, title: str = "Informe ATS") -> bytes:
    try:
        from weasyprint import HTML
    except OSError as exc:
        raise RuntimeError(
            "Exportación PDF no disponible: faltan librerías del sistema (Pango/Cairo). "
            "Reconstruye la imagen Docker del backend o instala dependencias de WeasyPrint."
        ) from exc

    categories = analysis_result.get("categories", {})
    rows = "".join(
        f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in categories.items()
    )
    issues = analysis_result.get("critical_issues", [])
    issues_html = "".join(f"<li>{i.get('message', '')}</li>" for i in issues[:10])

    html = f"""
    <!DOCTYPE html>
    <html><head><meta charset="utf-8"><title>{title}</title></head>
    <body style="font-family:sans-serif;padding:40px;">
      <h1>{title}</h1>
      <h2>Puntuación total: {analysis_result.get('total_score', 0)}/100</h2>
      <p>Nivel: {analysis_result.get('level', '')}</p>
      <p>{analysis_result.get('summary', '')}</p>
      <h3>Desglose por categorías</h3>
      <table border="1" cellpadding="8" style="border-collapse:collapse;">
        <tr><th>Categoría</th><th>Puntos</th></tr>
        {rows}
      </table>
      <h3>Problemas ATS</h3>
      <ul>{issues_html}</ul>
      {DISCLAIMER_HTML}
    </body></html>
    """
    return HTML(string=html).write_pdf()
