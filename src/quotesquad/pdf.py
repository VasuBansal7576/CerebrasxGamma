from __future__ import annotations

from io import BytesIO

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen.canvas import Canvas

from quotesquad.schemas import AnalysisRead


def render_pdf(analysis: AnalysisRead) -> bytes:
    buffer = BytesIO()
    canvas = Canvas(buffer, pagesize=LETTER)
    width, height = LETTER
    y = height - 54
    canvas.setTitle(f"QuoteSquad Audit {analysis.id}")
    canvas.setFont("Helvetica-Bold", 16)
    canvas.drawString(54, y, "QuoteSquad Audit")
    y -= 28
    canvas.setFont("Helvetica", 10)
    for line in _lines(analysis):
        if y < 54:
            canvas.showPage()
            y = height - 54
            canvas.setFont("Helvetica", 10)
        canvas.drawString(54, y, line[:115])
        y -= 15
    canvas.drawRightString(width - 54, 36, analysis.id)
    canvas.save()
    return buffer.getvalue()


def _lines(analysis: AnalysisRead) -> tuple[str, ...]:
    lines = [
        f"Verdict: {analysis.synthesis.verdict}",
        f"Summary: {analysis.synthesis.summary}",
        f"Savings range: ${analysis.synthesis.savings_low.amount} - ${analysis.synthesis.savings_high.amount}",
        "",
        "Findings:",
    ]
    for finding in analysis.findings:
        lines.extend(
            (
                f"- {finding.title} [{finding.status.value}, {finding.confidence:.0%}]",
                f"  {finding.finding}",
            )
        )
        for citation in finding.citations:
            lines.append(f"  Source: {citation.title} ({citation.url})")
    if analysis.gaps:
        lines.append("")
        lines.append("Provider gaps:")
        lines.extend(f"- {gap.provider}: {gap.reason}" for gap in analysis.gaps)
    return tuple(lines)
