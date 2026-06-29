from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import httpx2
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from quotesquad.config import Settings
from quotesquad.http_client import create_async_client

type ElementType = Literal["node", "way", "relation"]

USER_AGENT = "Mozilla/5.0 QuoteSquad/0.1"
SEARCH_RADIUS_METERS = 12000
NOMINATIM_BOX_DEGREES = 0.15


class VendorLookupError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class ZipPlace(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    latitude: float
    longitude: float


class ZipResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    places: tuple[ZipPlace, ...] = ()


class OsmTags(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    name: str | None = None
    phone: str | None = None
    contact_phone: str | None = Field(default=None, alias="contact:phone")
    website: str | None = None
    contact_website: str | None = Field(default=None, alias="contact:website")


class OsmElement(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    element_type: ElementType = Field(alias="type")
    id: int
    tags: OsmTags = Field(default_factory=OsmTags)


class OverpassResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    elements: tuple[OsmElement, ...] = ()


class NominatimPlace(BaseModel):
    model_config = ConfigDict(frozen=True)

    display_name: str
    osm_type: ElementType
    osm_id: int


NOMINATIM_RESPONSE = TypeAdapter(tuple[NominatimPlace, ...])


@dataclass(frozen=True, slots=True)
class VendorSearch:
    label: str
    selectors: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class OsmCandidate:
    name: str
    osm_url: str
    phone: str | None
    website: str | None


async def public_candidates(
    settings: Settings,
    search: VendorSearch,
    zip_code: str,
) -> tuple[OsmCandidate, ...]:
    place = await _zip_coordinates(settings, zip_code)
    try:
        response = await _fetch_osm(settings, search, place)
        candidates = overpass_candidates(response)
        if candidates:
            return candidates
    except (httpx2.HTTPError, ValidationError):
        pass
    places = await _fetch_nominatim(settings, search, place)
    return nominatim_candidates(places)


def overpass_candidates(response: OverpassResponse) -> tuple[OsmCandidate, ...]:
    candidates: list[OsmCandidate] = []
    seen: set[str] = set()
    for element in response.elements:
        name = element.tags.name
        if name is None:
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        candidates.append(
            OsmCandidate(
                name=name,
                osm_url=f"https://www.openstreetmap.org/{element.element_type}/{element.id}",
                phone=element.tags.phone or element.tags.contact_phone,
                website=element.tags.website or element.tags.contact_website,
            )
        )
        if len(candidates) == 3:
            break
    return tuple(candidates)


def nominatim_candidates(places: tuple[NominatimPlace, ...]) -> tuple[OsmCandidate, ...]:
    candidates: list[OsmCandidate] = []
    seen: set[str] = set()
    for place in places:
        name = place.display_name.split(",", maxsplit=1)[0].strip()
        if not name:
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        candidates.append(
            OsmCandidate(
                name=name,
                osm_url=f"https://www.openstreetmap.org/{place.osm_type}/{place.osm_id}",
                phone=None,
                website=None,
            )
        )
        if len(candidates) == 3:
            break
    return tuple(candidates)


async def _zip_coordinates(settings: Settings, zip_code: str) -> ZipPlace:
    async with create_async_client(settings.zippopotam_base_url, _headers()) as client:
        response = await client.get(f"/us/{zip_code}")
        _ = response.raise_for_status()
    places = ZipResponse.model_validate_json(response.text).places
    if not places:
        reason = f"No public ZIP coordinate match for {zip_code}."
        raise VendorLookupError(reason)
    return places[0]


async def _fetch_osm(
    settings: Settings,
    search: VendorSearch,
    place: ZipPlace,
) -> OverpassResponse:
    async with create_async_client(settings.overpass_base_url, _headers()) as client:
        response = await client.post("/interpreter", data={"data": _overpass_query(search, place)})
        _ = response.raise_for_status()
    return OverpassResponse.model_validate_json(response.text)


async def _fetch_nominatim(
    settings: Settings,
    search: VendorSearch,
    place: ZipPlace,
) -> tuple[NominatimPlace, ...]:
    async with create_async_client(settings.nominatim_base_url, _headers()) as client:
        response = await client.get("/search", params=_nominatim_params(search, place))
        _ = response.raise_for_status()
    return NOMINATIM_RESPONSE.validate_json(response.text)


def _overpass_query(search: VendorSearch, place: ZipPlace) -> str:
    lat = f"{place.latitude:.6f}"
    lon = f"{place.longitude:.6f}"
    clauses = "\n".join(
        f'  nwr["{tag}"="{value}"]["name"](around:{SEARCH_RADIUS_METERS},{lat},{lon});'
        for tag, value in search.selectors
    )
    return f"[out:json][timeout:8];\n(\n{clauses}\n);\nout tags 12;"


def _nominatim_params(
    search: VendorSearch,
    place: ZipPlace,
) -> tuple[tuple[str, str], ...]:
    return (
        ("q", search.label),
        ("format", "jsonv2"),
        ("limit", "5"),
        ("addressdetails", "0"),
        ("bounded", "1"),
        ("viewbox", _viewbox(place)),
    )


def _viewbox(place: ZipPlace) -> str:
    return (
        f"{place.longitude - NOMINATIM_BOX_DEGREES:.6f},"
        f"{place.latitude + NOMINATIM_BOX_DEGREES:.6f},"
        f"{place.longitude + NOMINATIM_BOX_DEGREES:.6f},"
        f"{place.latitude - NOMINATIM_BOX_DEGREES:.6f}"
    )


def _headers() -> dict[str, str]:
    return {"accept": "application/json", "user-agent": USER_AGENT}
