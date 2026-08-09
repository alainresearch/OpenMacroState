from __future__ import annotations

import json
import socket
from copy import deepcopy
from pathlib import Path
from types import MappingProxyType

import pytest

from openmacrostate.api.v1.connector_types import FrozenArtifact
from openmacrostate.api.v1.errors import ContractError
from openmacrostate.cli import main
from openmacrostate.connectors import builtin_connector_ids, get_builtin_connector
from openmacrostate.connectors.treasury_debt_to_penny import (
    TreasuryDebtToPennyConnector,
)
from openmacrostate.runtime.case import evaluate_case
from openmacrostate.runtime.connectors import run_connector
from openmacrostate.runtime.http import RecordedHttpTransport
from openmacrostate.runtime.jsonio import sha256_bytes

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "connectors" / "treasury_debt_to_penny"
RECORDING = FIXTURE / "recording.json"
CORE_TIME = "2026-08-09T16:21:00Z"


def _url(start: str = "2026-08-05", end: str = "2026-08-06") -> str:
    return (
        "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/"
        "v2/accounting/od/debt_to_penny"
        "?fields=record_date%2Ctot_pub_debt_out_amt%2Csrc_line_nbr"
        f"&filter=record_date%3Agte%3A{start}%2Crecord_date%3Alte%3A{end}"
        "&sort=record_date&format=json"
        "&page%5Bnumber%5D=1&page%5Bsize%5D=367"
    )


def _document() -> dict[str, object]:
    return json.loads((FIXTURE / "response.json").read_text(encoding="utf-8"))


def _frozen(
    document: object,
    *,
    url: str | None = None,
    retrieved_at: str = CORE_TIME,
) -> FrozenArtifact:
    body = json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode()
    request_url = url or _url()
    return FrozenArtifact(
        source_id="us.treasury.fiscaldata.debt_to_penny",
        request_url=request_url,
        final_url=request_url,
        status_code=200,
        media_type="application/json",
        response_headers=MappingProxyType({"content-type": "application/json"}),
        retrieved_at=retrieved_at,
        transport_retrieved_at_claim="2026-08-09T16:20:01Z",
        body=body,
        sha256=sha256_bytes(body),
        byte_length=len(body),
        capture_mode="recorded",
        recording_kind="test_only_excerpt",
        source_authentication="unverified_recording",
        transport_time_core_observed=False,
    )


def _capture(output: Path):
    return run_connector(
        TreasuryDebtToPennyConnector(),
        {"start": "2026-08-05", "end": "2026-08-06"},
        RecordedHttpTransport(RECORDING),
        output,
        protected_paths=(FIXTURE,),
        clock=lambda: CORE_TIME,
    )


def test_registry_and_plan_expose_one_fixed_bounded_request() -> None:
    assert builtin_connector_ids() == ("frbny-sofr", "treasury-debt-to-penny")
    connector = get_builtin_connector("treasury-debt-to-penny")
    assert type(connector) is TreasuryDebtToPennyConnector

    plans = connector.plan({"start": "2026-08-05", "end": "2026-08-06"})
    assert len(plans) == 1
    assert plans[0].method == "GET"
    assert plans[0].url == _url()
    assert plans[0].accept == "application/json"
    assert plans[0].max_bytes == 4 * 1024 * 1024

    with pytest.raises(ContractError, match="1993-04-01"):
        connector.plan({"start": "1993-03-31", "end": "1993-04-01"})
    with pytest.raises(ContractError, match="367 calendar days"):
        connector.plan({"start": "2025-01-01", "end": "2026-01-03"})
    with pytest.raises(ContractError, match="only start and end"):
        connector.plan({"start": "2026-08-05", "end": "2026-08-06", "url": "https://evil.example"})


def test_recorded_capture_is_valid_prospective_case(tmp_path: Path) -> None:
    output = tmp_path / "capture"
    capture = _capture(output)
    evaluation = evaluate_case(output)

    assert capture.case_id.startswith("capture-treasury-debt-to-penny-")
    assert len(capture.case_id.rsplit("-", 1)[-1]) == 32
    assert evaluation.summary()["accepted_observations"] == 2
    assert evaluation.summary()["quarantined_observations"] == 0
    assert evaluation.summary()["historical_evidence"] is False
    assert evaluation.case["information_cutoff"] == CORE_TIME
    assert evaluation.case["fixture_kind"] == "licensed_public"
    assert evaluation.case["title"] == ("U.S. Treasury Debt to the Penny official-source capture")
    assert evaluation.case["extensions"]["source_authentication"] == "unverified_recording"
    assert evaluation.case["extensions"]["real_source_data"] is False
    assert evaluation.case["extensions"]["complete_source_response"] is False

    records = list(evaluation.accepted_observations)
    assert [(record["observed_at"], record["series_id"]) for record in records] == [
        ("2026-08-05T00:00:00Z", "treasury.debt.total_public_outstanding"),
        ("2026-08-06T00:00:00Z", "treasury.debt.total_public_outstanding"),
    ]
    assert [record["value"] for record in records] == [
        "39829652708623.61",
        "39890263441627.83",
    ]
    assert {record["unit"] for record in records} == {"USD"}
    assert {record["released_at"] for record in records} == {CORE_TIME}
    assert {record["vintage_at"] for record in records} == {CORE_TIME}
    assert {record["ingested_at"] for record in records} == {CORE_TIME}
    assert all(
        record["extensions"]["release_calendar_basis"]
        == "estimated_schedule_not_used_as_row_released_at"
        for record in records
    )
    assert all(
        record["extensions"]["record_date_is_release_timestamp"] is False for record in records
    )

    artifact = evaluation.artifacts[0]
    assert artifact["source_published_at"] is None
    assert artifact["extensions"]["test_only_excerpt"] is True
    assert artifact["extensions"]["historical_version_authenticated"] is False
    assert artifact["license"]["redistribution"] == "allowed"
    assert artifact["license"]["commercial_use"] == "allowed"
    assert artifact["license"]["license_id"] == "US-Treasury-Fiscal-Data-Open-Data"
    raw_path = output / str(artifact["storage_uri"])
    assert raw_path.read_bytes() == (FIXTURE / "response.json").read_bytes()

    collection = json.loads((output / "collection.json").read_text(encoding="utf-8"))
    assert collection["connector_id"] == "treasury-debt-to-penny"
    assert collection["connector_ruleset_version"] == ("treasury-debt-to-penny-normalization/1")
    assert collection["capture_ruleset_version"] == "openmacrostate-connector-capture/3"
    assert collection["request"]["url"] == _url()
    assert len(collection["normalized_observations_sha256"]) == 64

    notice = (output / "LICENSES.md").read_text(encoding="utf-8")
    assert "Treasury Fiscal Data's Open Data Policy" in notice
    assert "does not grant rights in trademarks or third-party material" in notice
    assert "does not imply Treasury endorsement" in notice
    assert "17 U.S.C." not in notice


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda doc: doc["meta"].__setitem__("total-pages", 2), "exactly one complete"),
        (lambda doc: doc["links"].__setitem__("next", "&page=2"), "pagination links"),
        (lambda doc: doc["meta"].__setitem__("count", 1), "row count"),
        (lambda doc: doc["meta"].__setitem__("count", "2"), "JSON integer"),
        (lambda doc: doc["meta"].__setitem__("count", 2.0), "JSON integer"),
        (lambda doc: doc["meta"].__setitem__("total-count", 2.0), "JSON integer"),
        (lambda doc: doc["meta"].__setitem__("total-pages", 1.0), "JSON integer"),
        (lambda doc: doc["meta"].__setitem__("unexpected", 1), "meta"),
        (lambda doc: doc["links"].__setitem__("unexpected", None), "links"),
        (lambda doc: doc["data"][0].__setitem__("unexpected", "x"), "exactly"),
    ],
)
def test_pagination_and_unknown_fields_fail_closed(mutation, message: str) -> None:
    document = _document()
    mutation(document)

    with pytest.raises(ContractError, match=message):
        tuple(TreasuryDebtToPennyConnector().normalize(_frozen(document)))


def test_empty_rows_fail_closed() -> None:
    document = _document()
    document["data"] = []
    document["meta"]["count"] = 0
    document["meta"]["total-count"] = 0
    document["meta"]["total-pages"] = 0

    with pytest.raises(ContractError, match="no rows"):
        tuple(TreasuryDebtToPennyConnector().normalize(_frozen(document)))


@pytest.mark.parametrize(
    "bad_value",
    [
        "0.00",
        "null",
        "-1.00",
        "1.0",
        "1e3",
        "1,000.00",
        "$1.00",
        "3٩.٦١",
        1,
        None,
    ],
)
def test_total_debt_requires_positive_fixed_two_decimal_string(bad_value) -> None:
    document = _document()
    document["data"][0]["tot_pub_debt_out_amt"] = bad_value

    with pytest.raises(ContractError, match="JSON strings|positive fixed-two-decimal"):
        tuple(TreasuryDebtToPennyConnector().normalize(_frozen(document)))


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda doc: doc["data"][0].__setitem__("src_line_nbr", "2"), "src_line_nbr"),
        (lambda doc: doc["data"].reverse(), "strictly ascending"),
        (
            lambda doc: doc["data"].__setitem__(1, deepcopy(doc["data"][0])),
            "strictly ascending",
        ),
    ],
)
def test_row_identity_and_order_fail_closed(mutation, message: str) -> None:
    document = _document()
    mutation(document)

    with pytest.raises(ContractError, match=message):
        tuple(TreasuryDebtToPennyConnector().normalize(_frozen(document)))


def test_new_york_calendar_blocks_today_future_and_wrong_endpoint() -> None:
    connector = TreasuryDebtToPennyConnector()
    document = _document()
    document["data"] = [document["data"][1]]
    document["meta"]["count"] = 1
    document["meta"]["total-count"] = 1

    # UTC has crossed midnight, but America/New_York is still 2026-08-06.
    with pytest.raises(ContractError, match="America/New_York"):
        tuple(
            connector.normalize(
                _frozen(
                    document,
                    url=_url("2026-08-06", "2026-08-06"),
                    retrieved_at="2026-08-07T00:30:00Z",
                )
            )
        )
    with pytest.raises(ContractError, match="strictly earlier"):
        tuple(
            connector.normalize(
                _frozen(
                    document,
                    url=_url("2099-01-01", "2099-01-01"),
                )
            )
        )
    with pytest.raises(ContractError, match="fixed endpoint"):
        tuple(connector.normalize(_frozen(_document(), url=_url() + "&extra=true")))


def test_treasury_recorded_cli_is_offline(tmp_path: Path, monkeypatch, capsys) -> None:
    def forbidden_socket(*args, **kwargs):
        raise AssertionError("recorded Treasury connector attempted to open a network socket")

    monkeypatch.setattr(socket, "socket", forbidden_socket)
    output = tmp_path / "capture"
    assert (
        main(
            [
                "connector",
                "capture",
                "treasury-debt-to-penny",
                "--start",
                "2026-08-05",
                "--end",
                "2026-08-06",
                "--recording",
                str(RECORDING),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    assert "mode=recorded" in capsys.readouterr().out
    assert evaluate_case(output).summary()["accepted_observations"] == 2
