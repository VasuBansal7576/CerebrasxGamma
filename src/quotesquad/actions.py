from __future__ import annotations

from decimal import Decimal

from quotesquad.schemas import ActionPack, AgentFinding, ConfidenceStatus, QuoteSchema


def build_actions(quote: QuoteSchema, findings: tuple[AgentFinding, ...]) -> ActionPack:
    script_findings = tuple(
        finding
        for finding in findings
        if finding.status in {ConfidenceStatus.VERIFIED, ConfidenceStatus.CAVEATED}
    )
    if not script_findings:
        challenge = (
            "I am reviewing this quote and need itemized source support before approving it. "
            "Please provide labor time guides, part numbers, and retail/source references for each charge."
        )
    else:
        challenge = " ".join(_challenge_line(finding) for finding in script_findings)
    vendor = quote.vendor or "your team"
    email = (
        f"Hi {vendor},\n\n"
        f"{challenge}\n\n"
        "Please send the supporting documentation or an adjusted quote with these items separated.\n\n"
        "Thanks."
    )
    text = f"Can you send source support for the quoted items? {challenge}"
    complaint = _complaint_note(script_findings)
    return ActionPack(
        challenge_script=challenge,
        email_template=email,
        text_template=text,
        complaint_note=complaint,
    )


def _challenge_line(finding: AgentFinding) -> str:
    delta = f"${finding.delta.amount}" if finding.delta is not None else "an unsupported amount"
    return f"Please review {finding.title.lower()}: {finding.finding} Potential issue: {delta}."


def _complaint_note(findings: tuple[AgentFinding, ...]) -> str | None:
    total = sum(
        (finding.delta.amount for finding in findings if finding.delta is not None), Decimal("0")
    )
    if total < Decimal("250"):
        return None
    return (
        f"Potential sourced dispute exceeds ${total.quantize(Decimal('0.01'))}. "
        "If the vendor refuses to provide support, preserve the quote and source trail before filing."
    )
