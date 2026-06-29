from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from quotesquad.config import get_settings
from quotesquad.document import extract_quote
from quotesquad.local_vendors import alternative_vendor_result
from quotesquad.market_web import parse_ebay_prices
from quotesquad.ocr import extract_image_text
from quotesquad.pii import scrub_pii
from quotesquad.public_data import NhtsaData, NhtsaRecall, nhtsa_agent_result
from quotesquad.readiness import InfraReadiness, ProviderReadiness
from quotesquad.schemas import AnalysisRead, ComplianceControl, EnterpriseAuditRead
from quotesquad.synthesis import SynthesisPayload
from quotesquad.vendor_directory import NominatimPlace, OsmCandidate, nominatim_candidates

SAMPLE_QUOTE = "\n".join(
    (
        "Westside Auto Repair",
        "2026-06-29",
        "ZIP 90210",
        "Front brake rotor replacement labor 3.5 hours $525.00",
        "Front brake rotors pair $340.00",
        "Engine flush service $189.00",
        "Shop supplies fee $64.00",
        "Total $1118.00",
        "",
    )
)

CONTRACTOR_QUOTE = "\n".join(
    (
        "Acme Home Services",
        "ZIP 78701",
        "Drywall repair and paint $700.00",
        "Toilet replacement labor $650.00",
        "Total $1350.00",
        "",
    )
)


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("QUOTESQUAD_APP_ENV", "test")
    monkeypatch.setenv("QUOTESQUAD_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("QUOTESQUAD_RATE_LIMIT_PER_MINUTE", "0")
    get_settings.cache_clear()
    from quotesquad.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_scrub_pii_when_contact_details_present() -> None:
    scrubbed, redactions = scrub_pii("Call Jane at 555-123-4567 or jane@example.com")
    assert "555-123-4567" not in scrubbed
    assert "jane@example.com" not in scrubbed
    assert {redaction.kind for redaction in redactions} == {"phone", "email"}


def test_extract_quote_when_text_has_line_items() -> None:
    quote = extract_quote(SAMPLE_QUOTE, "90210")
    assert quote.vendor == "Westside Auto Repair"
    assert quote.quote_total is not None
    assert quote.quote_total.amount == 1118
    assert len(quote.line_items) == 4
    assert quote.line_items[0].quoted_hours == 3.5
    assert quote.line_items[0].description == "Front brake rotor replacement labor"


def test_extract_quote_when_vehicle_context_is_present() -> None:
    quote = extract_quote("2019 Toyota Camry\nFuel pump replacement $900.00", "90210")
    assert quote.vehicle_year == 2019
    assert quote.vehicle_make == "Toyota"
    assert quote.vehicle_model == "CAMRY"
    assert len(quote.line_items) == 1
    assert quote.line_items[0].description == "Fuel pump replacement"


def test_image_ocr_reports_gap_when_tesseract_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", "")
    text, gaps = extract_image_text(b"not a real image", ".png")
    assert text == ""
    assert len(gaps) == 1
    assert gaps[0].provider == "ocr"


def test_cerebras_payload_accepts_guidance_shape() -> None:
    payload = SynthesisPayload.model_validate(
        {"negotiation_guidance": "Ask for the part number and retail benchmark."}
    )
    assert payload.summary == "Ask for the part number and retail benchmark."
    assert payload.negotiation_notes == ("Ask for the part number and retail benchmark.",)


def test_nhtsa_recall_becomes_sourced_finding() -> None:
    quote = extract_quote("2019 Toyota Camry\nFuel pump replacement $900.00", "90210")
    result = nhtsa_agent_result(
        quote,
        NhtsaData(
            recalls=(
                NhtsaRecall(
                    NHTSACampaignNumber="20V682000",
                    Component="FUEL SYSTEM, GASOLINE:DELIVERY:FUEL PUMP",
                    Summary="Fuel pump recall.",
                ),
            ),
            complaints=(),
        ),
    )
    assert result.findings
    assert result.findings[0].agent == "nhtsa"
    assert result.findings[0].citations[0].source_type.value == "external"


def test_parse_ebay_prices_from_public_page_text() -> None:
    prices = parse_ebay_prices("Listing A $89.99 shipping $12.00 Listing B USD 120.00")
    assert prices == (Decimal("89.99"), Decimal("12.00"), Decimal("120.00"))


def test_alternative_vendor_result_uses_public_osm_candidate() -> None:
    quote = extract_quote(SAMPLE_QUOTE, "90210")
    result = alternative_vendor_result(
        quote,
        (
            OsmCandidate(
                name="Beverly Auto Care",
                osm_url="https://www.openstreetmap.org/node/123",
                phone="310-555-0142",
                website=None,
            ),
        ),
        "auto repair",
    )
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.agent == "alternative"
    assert finding.status.value == "unverified"
    assert "Beverly Auto Care" in finding.finding
    assert finding.citations[0].source_type.value == "external"


def test_nominatim_candidates_become_deduped_osm_targets() -> None:
    candidates = nominatim_candidates(
        (
            NominatimPlace(
                display_name="Complete Auto Repair, Los Angeles, California",
                osm_type="way",
                osm_id=425122676,
            ),
            NominatimPlace(
                display_name="Complete Auto Repair, Los Angeles County",
                osm_type="way",
                osm_id=425122676,
            ),
        )
    )
    assert len(candidates) == 1
    assert candidates[0].name == "Complete Auto Repair"
    assert candidates[0].osm_url == "https://www.openstreetmap.org/way/425122676"


def test_create_analysis_when_quote_is_posted(client: TestClient) -> None:
    response = client.post(
        "/api/analyses",
        json={"quote_text": SAMPLE_QUOTE, "zip_code": "90210", "consent_to_learn": True},
    )
    assert response.status_code == 200
    payload = AnalysisRead.model_validate_json(response.text)
    assert payload.quote.quote_type.value == "auto"
    assert payload.synthesis.verdict
    assert payload.actions.challenge_script
    assert any(item.citations for item in payload.findings)


def test_provider_and_infra_readiness_surfaces(client: TestClient) -> None:
    providers = client.get("/api/providers/status")
    infra = client.get("/api/infra/readiness")
    assert providers.status_code == 200
    assert infra.status_code == 200
    provider_payload = ProviderReadiness.model_validate_json(providers.text)
    infra_payload = InfraReadiness.model_validate_json(infra.text)
    provider_names = {item.name for item in provider_payload.providers}
    infra_names = {item.name for item in infra_payload.items}
    assert {"cerebras", "mitchell", "openstreetmap", "tesseract_ocr"} <= provider_names
    assert {"database", "redis", "temporal", "object_storage", "observability"} <= infra_names


def test_report_page_when_analysis_exists(client: TestClient) -> None:
    response = client.post("/api/analyses", json={"quote_text": SAMPLE_QUOTE, "zip_code": "90210"})
    payload = AnalysisRead.model_validate_json(response.text)
    analysis_id = payload.id
    report = client.get(f"/analyses/{analysis_id}")
    assert report.status_code == 200
    assert "QuoteSquad Audit" in report.text
    assert "Challenge script" in report.text
    assert "Record the outcome" in report.text


def test_feedback_calibrates_and_builds_regional_store(client: TestClient) -> None:
    response = client.post(
        "/api/analyses",
        json={"quote_text": SAMPLE_QUOTE, "zip_code": "90210", "consent_to_learn": True},
    )
    analysis = AnalysisRead.model_validate_json(response.text)
    feedback = client.post(
        f"/api/analyses/{analysis.id}/feedback",
        json={"outcome": "won_discount", "negotiated_savings": {"amount": "200.00"}},
    )
    assert feedback.status_code == 200
    regional = client.get("/api/regional/90210")
    calibration = client.get("/api/calibration")
    assert regional.status_code == 200
    assert calibration.status_code == 200
    assert regional.json()
    assert calibration.json()


def test_report_feedback_form_records_outcome(client: TestClient) -> None:
    response = client.post(
        "/api/analyses",
        json={"quote_text": SAMPLE_QUOTE, "zip_code": "90210", "consent_to_learn": True},
    )
    analysis = AnalysisRead.model_validate_json(response.text)
    feedback = client.post(
        f"/analyses/{analysis.id}/feedback",
        data={"outcome": "won_discount", "negotiated_savings": "125.50", "notes": "Vendor cut it."},
        follow_redirects=False,
    )
    assert feedback.status_code == 303
    calibration = client.get("/api/calibration")
    assert calibration.status_code == 200
    assert calibration.json()


def test_contractor_and_enterprise_phase_surfaces(client: TestClient) -> None:
    response = client.post(
        "/api/enterprise/audits",
        json={
            "organization_id": "fleetco",
            "external_ref": "claim-1",
            "use_case": "fleet",
            "quote_text": CONTRACTOR_QUOTE,
            "zip_code": "78701",
        },
    )
    assert response.status_code == 200
    payload = EnterpriseAuditRead.model_validate_json(response.text)
    assert payload.analysis.quote.quote_type.value == "contractor"
    assert any(item.agent == "contractor" for item in payload.analysis.findings)
    fleet = client.get("/api/enterprise/fleet/summary")
    vendors = client.get("/api/vendors/intelligence")
    assert fleet.status_code == 200
    assert vendors.status_code == 200
    assert vendors.json()


def test_white_label_compliance_and_deletion(client: TestClient) -> None:
    config = client.put(
        "/api/white-label/credit-union",
        json={
            "organization_id": "ignored",
            "display_name": "Member Quote Audit",
            "support_email": "support@example.com",
            "primary_color": "#245A86",
        },
    )
    assert config.status_code == 200
    assert config.json()["organization_id"] == "credit-union"
    controls = client.get("/api/compliance/controls")
    assert controls.status_code == 200
    control_rows = TypeAdapter(tuple[ComplianceControl, ...]).validate_json(controls.text)
    assert {item.key for item in control_rows} >= {"right_to_deletion", "soc2_readiness"}
    response = client.post("/api/analyses", json={"quote_text": SAMPLE_QUOTE, "zip_code": "90210"})
    analysis = AnalysisRead.model_validate_json(response.text)
    delete_response = client.delete(f"/api/analyses/{analysis.id}")
    assert delete_response.status_code == 204
    assert client.get(f"/api/analyses/{analysis.id}").status_code == 404
