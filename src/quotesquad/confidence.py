from __future__ import annotations

from decimal import Decimal

from quotesquad.schemas import ConfidenceStatus, MoneyModel


def confidence_status(confidence: float) -> ConfidenceStatus:
    if confidence >= 0.85:
        return ConfidenceStatus.VERIFIED
    if confidence >= 0.70:
        return ConfidenceStatus.CAVEATED
    if confidence >= 0.50:
        return ConfidenceStatus.UNVERIFIED
    return ConfidenceStatus.SUPPRESSED


def weighted_confidence(source_quality: float, match_confidence: float, sample_size: int) -> float:
    sample_weight = min(1.0, sample_size / 100)
    return round((source_quality * 0.45) + (match_confidence * 0.40) + (sample_weight * 0.15), 2)


def positive_delta(quoted: MoneyModel, benchmark: MoneyModel) -> MoneyModel | None:
    delta = quoted.amount - benchmark.amount
    if delta <= Decimal("0"):
        return None
    return MoneyModel(amount=delta)
