from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

MAKES: Final = (
    "acura",
    "audi",
    "bmw",
    "buick",
    "cadillac",
    "chevrolet",
    "chrysler",
    "dodge",
    "ford",
    "gmc",
    "honda",
    "hyundai",
    "infiniti",
    "jeep",
    "kia",
    "lexus",
    "mazda",
    "mercedes",
    "nissan",
    "subaru",
    "tesla",
    "toyota",
    "volkswagen",
    "volvo",
)
VEHICLE_PATTERN: Final = (
    rf"\b(?P<year>19[8-9]\d|20[0-3]\d)\s+(?P<make>{'|'.join(MAKES)})\s+(?P<model>[a-z][a-z0-9-]*)\b"
)
VEHICLE_RE: Final[re.Pattern[str]] = re.compile(VEHICLE_PATTERN, re.I)


@dataclass(frozen=True, slots=True)
class VehicleContext:
    year: int
    make: str
    model: str


def parse_vehicle(text: str) -> VehicleContext | None:
    match = VEHICLE_RE.search(text)
    if match is None:
        return None
    return VehicleContext(
        year=int(match.group("year")),
        make=match.group("make").title(),
        model=match.group("model").upper(),
    )
