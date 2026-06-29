from __future__ import annotations

import re
from dataclasses import dataclass

from quotesquad.schemas import Redaction


@dataclass(frozen=True, slots=True)
class PiiPattern:
    kind: str
    regex: re.Pattern[str]


PII_PATTERNS: tuple[PiiPattern, ...] = (
    PiiPattern("email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
    PiiPattern("phone", re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")),
    PiiPattern("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    PiiPattern("vin", re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b", re.I)),
    PiiPattern(
        "address",
        re.compile(
            r"\b\d{2,6}\s+[A-Z0-9][A-Z0-9 .'-]+\s+(?:ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|BLVD)\b",
            re.I,
        ),
    ),
)


def scrub_pii(text: str) -> tuple[str, tuple[Redaction, ...]]:
    scrubbed = text
    redactions: list[Redaction] = []
    for pattern in PII_PATTERNS:
        scrubbed, count = pattern.regex.subn(f"[REDACTED_{pattern.kind.upper()}]", scrubbed)
        if count > 0:
            redactions.append(Redaction(kind=pattern.kind, count=count))
    return scrubbed, tuple(redactions)
