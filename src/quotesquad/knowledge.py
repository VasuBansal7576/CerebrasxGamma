from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from quotesquad.money import dollars
from quotesquad.schemas import Citation, MoneyModel, SourceType


@dataclass(frozen=True, slots=True)
class MoneyBenchmark:
    label: str
    p50: MoneyModel
    p75: MoneyModel
    source: Citation
    source_quality: float
    sample_size: int


@dataclass(frozen=True, slots=True)
class LaborBenchmark:
    label: str
    standard_hours: Decimal
    source: Citation
    source_quality: float


SEED_CITATION = Citation(
    title="QuoteSquad seed benchmark catalog",
    url="local://quotesquad/seed-benchmarks",
    source_type=SourceType.SEED,
)

REGIONAL_CITATION = Citation(
    title="QuoteSquad anonymized regional labor baseline",
    url="local://quotesquad/regional-labor-rates",
    source_type=SourceType.SEED,
)


PART_BENCHMARKS: tuple[tuple[str, MoneyBenchmark], ...] = (
    (
        "rotor",
        MoneyBenchmark(
            "front brake rotor pair", dollars("210"), dollars("280"), SEED_CITATION, 0.76, 41
        ),
    ),
    (
        "brake pad",
        MoneyBenchmark(
            "front brake pad set", dollars("120"), dollars("175"), SEED_CITATION, 0.74, 38
        ),
    ),
    (
        "battery",
        MoneyBenchmark(
            "automotive battery", dollars("185"), dollars("240"), SEED_CITATION, 0.73, 29
        ),
    ),
    (
        "oil",
        MoneyBenchmark(
            "synthetic oil service", dollars("75"), dollars("115"), SEED_CITATION, 0.72, 67
        ),
    ),
)

CONTRACTOR_BENCHMARKS: tuple[tuple[str, MoneyBenchmark], ...] = (
    (
        "drywall",
        MoneyBenchmark(
            "drywall repair per patch", dollars("275"), dollars("420"), SEED_CITATION, 0.70, 21
        ),
    ),
    (
        "toilet",
        MoneyBenchmark(
            "toilet replacement labor and install kit",
            dollars("350"),
            dollars("525"),
            SEED_CITATION,
            0.71,
            19,
        ),
    ),
    (
        "water heater",
        MoneyBenchmark(
            "standard water heater install labor",
            dollars("850"),
            dollars("1250"),
            SEED_CITATION,
            0.72,
            26,
        ),
    ),
    (
        "roof",
        MoneyBenchmark(
            "roof repair minimum service call",
            dollars("450"),
            dollars("750"),
            SEED_CITATION,
            0.69,
            17,
        ),
    ),
)

LABOR_BENCHMARKS: tuple[tuple[str, LaborBenchmark], ...] = (
    ("rotor", LaborBenchmark("front rotor replacement", Decimal("1.4"), SEED_CITATION, 0.78)),
    ("brake", LaborBenchmark("front brake service", Decimal("1.6"), SEED_CITATION, 0.76)),
    ("oil", LaborBenchmark("oil service", Decimal("0.5"), SEED_CITATION, 0.72)),
    ("battery", LaborBenchmark("battery replacement", Decimal("0.4"), SEED_CITATION, 0.72)),
)


def regional_labor_rate(zip_code: str | None) -> MoneyBenchmark | None:
    if zip_code is None:
        return None
    return MoneyBenchmark(
        label=f"regional labor rate near {zip_code[:5]}",
        p50=dollars("105"),
        p75=dollars("125"),
        source=REGIONAL_CITATION,
        source_quality=0.78,
        sample_size=84,
    )


def part_benchmark(description: str) -> MoneyBenchmark | None:
    lowered = description.lower()
    for key, benchmark in PART_BENCHMARKS:
        if key in lowered:
            return benchmark
    return None


def contractor_benchmark(description: str) -> MoneyBenchmark | None:
    lowered = description.lower()
    for key, benchmark in CONTRACTOR_BENCHMARKS:
        if key in lowered:
            return benchmark
    return None


def labor_benchmark(description: str) -> LaborBenchmark | None:
    lowered = description.lower()
    for key, benchmark in LABOR_BENCHMARKS:
        if key in lowered:
            return benchmark
    return None
