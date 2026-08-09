from __future__ import annotations

import json
import shutil
import socket
from pathlib import Path
from types import MappingProxyType

import pytest

from openmacrostate.api.v1 import CaptureBundleMetadata as PublicCaptureBundleMetadata
from openmacrostate.api.v1.connector_types import (
    CaptureBundleMetadata,
    FetchRequest,
    FrozenArtifact,
    TransportResponse,
)
from openmacrostate.api.v1.errors import ContractError
from openmacrostate.api.v1.types import Observation, parse_timestamp
from openmacrostate.cli import main
from openmacrostate.connectors.frbny_sofr import FrbnySofrConnector
from openmacrostate.runtime.case import evaluate_case
from openmacrostate.runtime.connectors import (
    run_connector,
    validate_connector_spec,
    validate_fetch_request,
)
from openmacrostate.runtime.http import RecordedHttpTransport
from openmacrostate.runtime.jsonio import sha256_bytes

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "connectors" / "frbny_sofr"
RECORDING = FIXTURE / "recording.json"
CORE_TIME = "2026-08-09T15:30:00Z"


def test_public_v1_exports_capture_bundle_metadata() -> None:
    assert PublicCaptureBundleMetadata is CaptureBundleMetadata


def _clock() -> str:
    return CORE_TIME


def _capture(output: Path):
    return run_connector(
        FrbnySofrConnector(),
        {"start": "2023-03-22", "end": "2023-03-22"},
        RecordedHttpTransport(RECORDING),
        output,
        protected_paths=(FIXTURE,),
        clock=_clock,
    )


def _recording_copy(
    tmp_path: Path,
    name: str,
    *,
    recording_kind: str | None = None,
    retrieved_at: str | None = None,
    start: str = "2023-03-22",
    end: str = "2023-03-22",
) -> Path:
    fixture_copy = tmp_path / name
    shutil.copytree(FIXTURE, fixture_copy)
    recording_path = fixture_copy / "recording.json"
    recording = json.loads(recording_path.read_text(encoding="utf-8"))
    url = (
        "https://markets.newyorkfed.org/api/rates/secured/sofr/search.json"
        f"?startDate={start}&endDate={end}"
    )
    recording["request"]["url"] = url
    recording["response"]["final_url"] = url
    if recording_kind is not None:
        recording["recording_kind"] = recording_kind
    if retrieved_at is not None:
        recording["response"]["retrieved_at"] = retrieved_at
    recording_path.write_text(json.dumps(recording), encoding="utf-8")
    return recording_path


def _frozen(
    body: bytes, *, url: str | None = None, retrieved_at: str = CORE_TIME
) -> FrozenArtifact:
    request_url = url or (
        "https://markets.newyorkfed.org/api/rates/secured/sofr/search.json"
        "?startDate=2023-03-20&endDate=2023-03-22"
    )
    return FrozenArtifact(
        source_id="frbny.markets.sofr",
        request_url=request_url,
        final_url=request_url,
        status_code=200,
        media_type="application/json",
        response_headers=MappingProxyType({"content-type": "application/json"}),
        retrieved_at=retrieved_at,
        transport_retrieved_at_claim="2026-08-09T15:18:38Z",
        body=body,
        sha256=sha256_bytes(body),
        byte_length=len(body),
        capture_mode="recorded",
        recording_kind="test_only_excerpt",
        source_authentication="unverified_recording",
        transport_time_core_observed=False,
    )


def test_recorded_capture_is_a_valid_complete_case(tmp_path: Path) -> None:
    output = tmp_path / "capture"
    capture = _capture(output)
    evaluation = evaluate_case(output)

    assert capture.case_dir == output.resolve()
    assert evaluation.summary()["accepted_observations"] == 6
    assert evaluation.summary()["quarantined_observations"] == 0
    assert evaluation.summary()["historical_evidence"] is False
    assert evaluation.case["fixture_kind"] == "licensed_public"
    assert evaluation.case["information_cutoff"] == CORE_TIME
    assert evaluation.case["extensions"]["recording_completeness_claim"] == "test_only_excerpt"
    assert evaluation.case["extensions"]["source_authentication"] == "unverified_recording"
    assert evaluation.case["extensions"]["real_source_data"] is False
    assert evaluation.case["extensions"]["complete_source_response"] is False
    assert not (output / ".openmacrostate-incomplete").exists()
    assert (output / ".openmacrostate-capture.json").is_file()
    assert (output / "inputs" / "claims.jsonl").read_bytes() == b""
    assert (output / "inputs" / "predictions.jsonl").read_bytes() == b""

    records = list(evaluation.accepted_observations)
    assert [record["series_id"] for record in records] == [
        "frbny.sofr.rate",
        "frbny.sofr.volume",
        "frbny.sofr.p01",
        "frbny.sofr.p25",
        "frbny.sofr.p75",
        "frbny.sofr.p99",
    ]
    assert [record["value"] for record in records] == [
        "4.55",
        "1203",
        "4.50",
        "4.54",
        "4.58",
        "4.63",
    ]
    assert {record["released_at"] for record in records} == {CORE_TIME}
    assert {record["vintage_at"] for record in records} == {CORE_TIME}
    assert {record["ingested_at"] for record in records} == {CORE_TIME}
    assert {record["observed_at"] for record in records} == {"2023-03-22T00:00:00Z"}
    assert all(record["extensions"]["temporal_precision"] == "date" for record in records)
    assert all(
        record["extensions"]["observed_at_convention"] == "canonical_utc_date_anchor_not_instant"
        for record in records
    )

    artifact = evaluation.artifacts[0]
    raw_path = output / str(artifact["storage_uri"])
    assert raw_path.read_bytes() == (FIXTURE / "response.json").read_bytes()
    assert artifact["sha256"] == sha256_bytes(raw_path.read_bytes())
    assert artifact["byte_length"] == len(raw_path.read_bytes())
    assert artifact["source_published_at"] is None
    assert artifact["license"]["redistribution"] == "restricted"
    assert artifact["extensions"]["test_only_excerpt"] is True
    assert artifact["extensions"]["historical_version_authenticated"] is False
    assert artifact["extensions"]["retrieval"]["hash_authority"] == "openmacrostate-core"
    assert artifact["extensions"]["retrieval"]["transport_time_core_observed"] is False
    assert artifact["extensions"]["retrieval"]["source_authentication"] == "unverified_recording"
    assert (
        artifact["extensions"]["retrieval"]["transport_retrieved_at_claim"]
        == "2026-08-09T15:18:38Z"
    )
    notice = (output / "LICENSES.md").read_text(encoding="utf-8")
    assert "not licensed under this repository's Apache-2.0" in notice
    assert "not affiliated with the New York Fed" in notice
    assert "normalized observations are an OpenMacroState transformation" in notice


def test_historical_value_date_cannot_pass_a_historical_cutoff(tmp_path: Path) -> None:
    evaluation = evaluate_case(_capture(tmp_path / "capture").case_dir)
    observation = Observation.from_mapping(evaluation.accepted_observations[0])
    old_cutoff = parse_timestamp("2023-03-23T00:00:00Z")

    assert observation.cutoff_reasons(old_cutoff, require_ingested_by_cutoff=True) == (
        "released_after_information_cutoff",
        "vintage_after_information_cutoff",
        "ingested_after_information_cutoff",
    )


def test_backdated_receipt_claim_cannot_backdate_knowledge_time(tmp_path: Path) -> None:
    fixture_copy = tmp_path / "fixture"
    shutil.copytree(FIXTURE, fixture_copy)
    recording_path = fixture_copy / "recording.json"
    recording = json.loads(recording_path.read_text(encoding="utf-8"))
    recording["recording_kind"] = "complete_response"
    recording["response"]["retrieved_at"] = "2018-01-01T00:00:00Z"
    recording_path.write_text(json.dumps(recording), encoding="utf-8")
    output = tmp_path / "capture"

    run_connector(
        FrbnySofrConnector(),
        {"start": "2023-03-22", "end": "2023-03-22"},
        RecordedHttpTransport(recording_path),
        output,
        protected_paths=(fixture_copy,),
        clock=_clock,
    )
    evaluation = evaluate_case(output)
    assert evaluation.case["information_cutoff"] == CORE_TIME
    assert {record["released_at"] for record in evaluation.accepted_observations} == {CORE_TIME}
    collection = json.loads((output / "collection.json").read_text(encoding="utf-8"))
    assert collection["transport_retrieved_at_claim"] == "2018-01-01T00:00:00Z"
    assert collection["transport_time_core_observed"] is False
    assert collection["source_authentication"] == "unverified_recording"


def test_capture_identity_binds_recording_receipt_plugin_and_bundle_metadata(
    tmp_path: Path, monkeypatch
) -> None:
    complete_recording = _recording_copy(tmp_path, "complete", recording_kind="complete_response")
    later_receipt = _recording_copy(tmp_path, "later-receipt", retrieved_at="2026-08-09T15:19:00Z")
    baseline = _capture(tmp_path / "baseline")
    different_kind = run_connector(
        FrbnySofrConnector(),
        {"start": "2023-03-22", "end": "2023-03-22"},
        RecordedHttpTransport(complete_recording),
        tmp_path / "different-kind",
        clock=_clock,
    )
    different_receipt = run_connector(
        FrbnySofrConnector(),
        {"start": "2023-03-22", "end": "2023-03-22"},
        RecordedHttpTransport(later_receipt),
        tmp_path / "different-receipt",
        clock=_clock,
    )
    original_metadata = FrbnySofrConnector.bundle_metadata
    monkeypatch.setattr(
        FrbnySofrConnector,
        "bundle_metadata",
        CaptureBundleMetadata(
            title=original_metadata.title,
            fixture_kind=original_metadata.fixture_kind,
            source_notice=original_metadata.source_notice + "\n\nReviewed source notice revision.",
        ),
    )
    different_metadata = run_connector(
        FrbnySofrConnector(),
        {"start": "2023-03-22", "end": "2023-03-22"},
        RecordedHttpTransport(RECORDING),
        tmp_path / "different-metadata",
        clock=_clock,
    )
    monkeypatch.setattr(FrbnySofrConnector, "bundle_metadata", original_metadata)
    modified_spec = dict(FrbnySofrConnector.spec)
    modified_spec["plugin_version"] = "0.1.1"
    monkeypatch.setattr(FrbnySofrConnector, "spec", MappingProxyType(modified_spec))
    different_version = run_connector(
        FrbnySofrConnector(),
        {"start": "2023-03-22", "end": "2023-03-22"},
        RecordedHttpTransport(RECORDING),
        tmp_path / "different-version",
        clock=_clock,
    )

    captures = (
        baseline,
        different_kind,
        different_receipt,
        different_metadata,
        different_version,
    )
    assert len({capture.case_id for capture in captures}) == 5
    assert len({capture.collection_id for capture in captures}) == 5
    assert len({capture.artifact_id for capture in captures}) == 1
    assert len(baseline.case_id.rsplit("-", 1)[-1]) == 32
    assert len(baseline.collection_id.rsplit(":", 1)[-1]) == 32
    collection = json.loads((baseline.case_dir / "collection.json").read_text(encoding="utf-8"))
    assert len(collection["normalized_observations_sha256"]) == 64
    assert collection["connector_ruleset_version"] == "frbny-sofr-normalization/3"
    assert collection["capture_ruleset_version"] == "openmacrostate-connector-capture/3"


def test_invalid_bundle_metadata_fails_before_output(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        FrbnySofrConnector,
        "bundle_metadata",
        CaptureBundleMetadata(
            title="FRBNY SOFR\nforged title",
            fixture_kind="licensed_public",
            source_notice="notice",
        ),
    )
    output = tmp_path / "capture"

    with pytest.raises(ContractError, match="title"):
        _capture(output)
    assert not output.exists()


def test_future_license_review_time_fails_before_output(tmp_path: Path, monkeypatch) -> None:
    modified_spec = dict(FrbnySofrConnector.spec)
    modified_license = dict(modified_spec["license"])
    modified_license["reviewed_at"] = "2099-01-01T00:00:00Z"
    modified_spec["license"] = modified_license
    monkeypatch.setattr(FrbnySofrConnector, "spec", MappingProxyType(modified_spec))
    output = tmp_path / "capture"

    with pytest.raises(ContractError, match="license reviewed_at"):
        _capture(output)
    assert not output.exists()


def test_recording_future_time_claim_fails_closed(tmp_path: Path) -> None:
    fixture_copy = tmp_path / "fixture"
    shutil.copytree(FIXTURE, fixture_copy)
    recording_path = fixture_copy / "recording.json"
    recording = json.loads(recording_path.read_text(encoding="utf-8"))
    recording["response"]["retrieved_at"] = "2099-01-01T00:00:00Z"
    recording_path.write_text(json.dumps(recording), encoding="utf-8")

    with pytest.raises(ContractError, match="must not precede"):
        run_connector(
            FrbnySofrConnector(),
            {"start": "2023-03-22", "end": "2023-03-22"},
            RecordedHttpTransport(recording_path),
            tmp_path / "capture",
            clock=_clock,
        )


def test_recording_tampering_fails_before_output(tmp_path: Path) -> None:
    fixture_copy = tmp_path / "fixture"
    shutil.copytree(FIXTURE, fixture_copy)
    (fixture_copy / "response.json").write_text("{}\n", encoding="utf-8")
    output = tmp_path / "capture"

    with pytest.raises(ContractError, match="byte length"):
        run_connector(
            FrbnySofrConnector(),
            {"start": "2023-03-22", "end": "2023-03-22"},
            RecordedHttpTransport(fixture_copy / "recording.json"),
            output,
            clock=_clock,
        )
    assert not output.exists()


def test_same_length_recording_tamper_fails_sha256(tmp_path: Path) -> None:
    fixture_copy = tmp_path / "fixture"
    shutil.copytree(FIXTURE, fixture_copy)
    body_path = fixture_copy / "response.json"
    body = body_path.read_bytes()
    assert b"4.55" in body
    body_path.write_bytes(body.replace(b"4.55", b"4.56", 1))
    output = tmp_path / "capture"

    with pytest.raises(ContractError, match="SHA-256"):
        run_connector(
            FrbnySofrConnector(),
            {"start": "2023-03-22", "end": "2023-03-22"},
            RecordedHttpTransport(fixture_copy / "recording.json"),
            output,
            clock=_clock,
        )
    assert not output.exists()


def test_recording_rejects_path_escape_and_ambiguous_headers(tmp_path: Path) -> None:
    fixture_copy = tmp_path / "fixture"
    shutil.copytree(FIXTURE, fixture_copy)
    recording_path = fixture_copy / "recording.json"
    recording = json.loads(recording_path.read_text(encoding="utf-8"))
    recording["response"]["body_file"] = "../response.json"
    recording_path.write_text(json.dumps(recording), encoding="utf-8")
    with pytest.raises(ContractError, match="escapes"):
        RecordedHttpTransport(recording_path).fetch(
            FrbnySofrConnector().plan({"start": "2023-03-22", "end": "2023-03-22"})[0]
        )

    recording["response"]["body_file"] = "response.json"
    recording["response"]["headers"]["Content-Type"] = "text/plain"
    recording_path.write_text(json.dumps(recording), encoding="utf-8")
    with pytest.raises(ContractError, match="duplicate case-insensitive"):
        RecordedHttpTransport(recording_path).fetch(
            FrbnySofrConnector().plan({"start": "2023-03-22", "end": "2023-03-22"})[0]
        )


@pytest.mark.parametrize(
    "url",
    [
        "http://markets.newyorkfed.org/api/x",
        "https://evilmarkets.newyorkfed.org/api/x",
        "https://markets.newyorkfed.org.evil.example/api/x",
        "https://user@markets.newyorkfed.org/api/x",
        "https://127.0.0.1/api/x",
        "https://markets.newyorkfed.org:444/api/x",
        "https://markets.newyorkfed.org/api/x#fragment",
    ],
)
def test_request_policy_rejects_url_attacks(url: str) -> None:
    with pytest.raises(ContractError):
        validate_fetch_request(
            FetchRequest("GET", url, "application/json", 1024),
            allowed_hosts=("markets.newyorkfed.org",),
        )


def test_response_redirect_fails_before_output(tmp_path: Path) -> None:
    recording_path = _recording_copy(tmp_path, "redirect")
    recording = json.loads(recording_path.read_text(encoding="utf-8"))
    recording["response"]["final_url"] = "https://example.com/redirected.json"
    recording_path.write_text(json.dumps(recording), encoding="utf-8")
    output = tmp_path / "capture"
    with pytest.raises(ContractError, match="redirected"):
        run_connector(
            FrbnySofrConnector(),
            {"start": "2023-03-22", "end": "2023-03-22"},
            RecordedHttpTransport(recording_path),
            output,
            clock=_clock,
        )
    assert not output.exists()


@pytest.mark.parametrize(
    ("status_code", "content_type", "message"),
    [
        (503, "application/json", "status must be 200"),
        (200, "text/plain", "media type"),
    ],
)
def test_response_status_and_media_type_fail_before_output(
    tmp_path: Path, status_code: int, content_type: str, message: str
) -> None:
    recording_path = _recording_copy(
        tmp_path, f"invalid-{status_code}-{content_type.replace('/', '-')}"
    )
    recording = json.loads(recording_path.read_text(encoding="utf-8"))
    recording["response"]["status_code"] = status_code
    recording["response"]["headers"]["content-type"] = content_type
    recording_path.write_text(json.dumps(recording), encoding="utf-8")
    output = tmp_path / "capture"
    with pytest.raises(ContractError, match=message):
        run_connector(
            FrbnySofrConnector(),
            {"start": "2023-03-22", "end": "2023-03-22"},
            RecordedHttpTransport(recording_path),
            output,
            clock=_clock,
        )
    assert not output.exists()


def test_spoofed_live_transport_and_malicious_connector_are_rejected(tmp_path: Path) -> None:
    class SpoofedLiveTransport:
        def fetch(self, request: FetchRequest) -> TransportResponse:
            return TransportResponse(
                status_code=200,
                final_url=request.url,
                headers={"content-type": "application/json"},
                retrieved_at="2026-08-09T15:29:00Z",
                body=(
                    b'{"refRates":[{"effectiveDate":"2023-03-22","type":"SOFR",'
                    b'"percentRate":99.99}]}'
                ),
            )

    with pytest.raises(ContractError, match="exact core-owned"):
        run_connector(
            FrbnySofrConnector(),
            {"start": "2023-03-22", "end": "2023-03-22"},
            SpoofedLiveTransport(),
            tmp_path / "spoofed-transport",
            clock=_clock,
        )

    class MaliciousConnector(FrbnySofrConnector):
        pass

    with pytest.raises(ContractError, match="exact review-trusted"):
        run_connector(
            MaliciousConnector(),
            {"start": "2023-03-22", "end": "2023-03-22"},
            RecordedHttpTransport(RECORDING),
            tmp_path / "malicious-connector",
            clock=_clock,
        )


def test_spec_with_secrets_fails_closed() -> None:
    spec = dict(FrbnySofrConnector.spec)
    spec["required_secret_names"] = ["API_TOKEN"]
    with pytest.raises(ContractError, match="does not permit secrets"):
        validate_connector_spec(spec)


def test_normalizer_orders_dates_and_series_and_preserves_decimals() -> None:
    body = b"""{"refRates":[
      {"effectiveDate":"2023-03-22","type":"SOFR","percentRate":4.50,
       "percentPercentile1":4.40,"percentPercentile25":4.45,
       "percentPercentile75":4.55,"percentPercentile99":4.60,
       "volumeInBillions":1000,"revisionIndicator":"R","footnoteId":1},
      {"effectiveDate":"2023-03-20","type":"SOFR","percentRate":4.00,
       "revisionIndicator":""}
    ]}"""
    drafts = tuple(FrbnySofrConnector().normalize(_frozen(body)))

    assert [(draft.observed_at, draft.series_id) for draft in drafts] == [
        ("2023-03-20T00:00:00Z", "frbny.sofr.rate"),
        ("2023-03-22T00:00:00Z", "frbny.sofr.rate"),
        ("2023-03-22T00:00:00Z", "frbny.sofr.volume"),
        ("2023-03-22T00:00:00Z", "frbny.sofr.p01"),
        ("2023-03-22T00:00:00Z", "frbny.sofr.p25"),
        ("2023-03-22T00:00:00Z", "frbny.sofr.p75"),
        ("2023-03-22T00:00:00Z", "frbny.sofr.p99"),
    ]
    assert [draft.value for draft in drafts] == [
        "4.00",
        "4.50",
        "1000",
        "4.40",
        "4.45",
        "4.55",
        "4.60",
    ]
    assert drafts[1].extensions["footnote_id"] == "1"


def test_empty_ref_rates_fails_closed() -> None:
    with pytest.raises(ContractError, match="no rows"):
        tuple(FrbnySofrConnector().normalize(_frozen(b'{"refRates":[]}')))


@pytest.mark.parametrize(
    ("effective_date", "message"),
    [
        ("2099-01-01", "strictly earlier"),
        ("2018-04-01", "predates the first valid"),
    ],
)
def test_effective_date_bounds_fail_closed(effective_date: str, message: str) -> None:
    body = (
        '{"refRates":[{"effectiveDate":"' + effective_date + '","type":"SOFR","percentRate":4.55}]}'
    ).encode()
    url = (
        "https://markets.newyorkfed.org/api/rates/secured/sofr/search.json"
        f"?startDate={effective_date}&endDate={effective_date}"
    )
    with pytest.raises(ContractError, match=message):
        tuple(FrbnySofrConnector().normalize(_frozen(body, url=url)))


def test_effective_date_bound_uses_new_york_calendar_date() -> None:
    effective_date = "2026-08-04"
    body = (
        '{"refRates":[{"effectiveDate":"' + effective_date + '","type":"SOFR","percentRate":4.55}]}'
    ).encode()
    url = (
        "https://markets.newyorkfed.org/api/rates/secured/sofr/search.json"
        f"?startDate={effective_date}&endDate={effective_date}"
    )

    # UTC has crossed midnight, but New York is still on 2026-08-04.
    with pytest.raises(ContractError, match="America/New_York"):
        tuple(
            FrbnySofrConnector().normalize(
                _frozen(body, url=url, retrieved_at="2026-08-05T00:30:00Z")
            )
        )


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ('"percentRate":"4.55"', "JSON number, not a string"),
        ('"percentRate":4.55,"volumeInBillions":-1', "must be non-negative"),
        (
            '"percentRate":4.55,"percentPercentile25":4.60,"percentPercentile75":4.50',
            "percentile ordering",
        ),
    ],
)
def test_numeric_type_and_sofr_invariants_fail_closed(fields: str, message: str) -> None:
    body = ('{"refRates":[{"effectiveDate":"2023-03-22","type":"SOFR",' + fields + "}]}").encode()
    with pytest.raises(ContractError, match=message):
        tuple(FrbnySofrConnector().normalize(_frozen(body)))


def test_output_never_overwrites_or_traverses_symlink(tmp_path: Path) -> None:
    existing = tmp_path / "existing"
    existing.mkdir()
    (existing / "keep.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(ContractError, match="already exists"):
        _capture(existing)
    assert (existing / "keep.txt").read_text(encoding="utf-8") == "keep"

    real_parent = tmp_path / "real"
    real_parent.mkdir()
    linked_parent = tmp_path / "linked"
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    with pytest.raises(ContractError, match="symbolic link"):
        _capture(linked_parent / "capture")


def test_recorded_cli_never_opens_socket(tmp_path: Path, monkeypatch, capsys) -> None:
    def forbidden_socket(*args, **kwargs):
        raise AssertionError("recorded connector attempted to open a network socket")

    monkeypatch.setattr(socket, "socket", forbidden_socket)
    output = tmp_path / "capture"
    assert (
        main(
            [
                "connector",
                "capture",
                "frbny-sofr",
                "--start",
                "2023-03-22",
                "--end",
                "2023-03-22",
                "--recording",
                str(RECORDING),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    assert "mode=recorded" in capsys.readouterr().out
    assert evaluate_case(output).summary()["accepted_observations"] == 6


def test_cli_requires_explicit_network_or_recording(tmp_path: Path, capsys) -> None:
    assert (
        main(
            [
                "connector",
                "capture",
                "frbny-sofr",
                "--start",
                "2023-03-22",
                "--end",
                "2023-03-22",
                "--output",
                str(tmp_path / "capture"),
            ]
        )
        == 2
    )
    assert "network access is never implicit" in capsys.readouterr().err


def test_list_builtin_connectors_exposes_both_reviewed_sources() -> None:
    from openmacrostate.connectors import list_builtin_connectors

    assert list_builtin_connectors() == (
        {
            "connector_id": "frbny-sofr",
            "version": "0.1.0",
            "source_name": "Federal Reserve Bank of New York",
            "allowed_hosts": ["markets.newyorkfed.org"],
            "capture_modes": ["online", "recording"],
            "redistribution_status": "restricted",
            "documentation_link": "https://www.newyorkfed.org/privacy/termsofuse.html",
        },
        {
            "connector_id": "treasury-debt-to-penny",
            "version": "0.1.0",
            "source_name": ("U.S. Department of the Treasury, Bureau of the Fiscal Service"),
            "allowed_hosts": ["api.fiscaldata.treasury.gov"],
            "capture_modes": ["online", "recording"],
            "redistribution_status": "allowed",
            "documentation_link": "https://fiscaldata.treasury.gov/api-documentation/",
        },
    )


def test_listing_connectors_does_not_change_capture_identity(tmp_path: Path) -> None:
    from openmacrostate.connectors import list_builtin_connectors

    baseline = _capture(tmp_path / "baseline")
    list_builtin_connectors()
    after_listing = _capture(tmp_path / "after-listing")

    assert after_listing.case_id == baseline.case_id
    assert after_listing.collection_id == baseline.collection_id
    assert after_listing.artifact_id == baseline.artifact_id
    assert after_listing.observation_ids == baseline.observation_ids
