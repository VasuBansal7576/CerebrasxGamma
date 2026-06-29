from __future__ import annotations

from collections import defaultdict

from quotesquad.schemas import (
    AgentFinding,
    AgentResult,
    ConfidenceStatus,
    QuoteSchema,
    VerifiedAnalysis,
)


def verify(quote: QuoteSchema, agent_results: tuple[AgentResult, ...]) -> VerifiedAnalysis:
    findings = tuple(
        finding
        for result in agent_results
        for finding in result.findings
        if finding.status is not ConfidenceStatus.SUPPRESSED
    )
    gaps = (*quote.extraction_gaps, *(gap for result in agent_results for gap in result.gaps))
    conflicts = tuple(_conflicts(findings))
    return VerifiedAnalysis(findings=findings, conflicts=conflicts, gaps=gaps)


def _conflicts(findings: tuple[AgentFinding, ...]) -> list[str]:
    by_line: defaultdict[int, set[str]] = defaultdict(set)
    conflicts: list[str] = []
    for finding in findings:
        if finding.line_item_index is None:
            continue
        by_line[finding.line_item_index].add(finding.category)
    for line_index, categories in by_line.items():
        if "necessity" in categories and "parts_price" in categories:
            conflicts.append(
                f"Line {line_index + 1} has both price and necessity concerns; challenge price first."
            )
    return conflicts
