from __future__ import annotations

import re
import socket
from pathlib import Path
from types import MappingProxyType

import pytest

from openmacrostate.api.v1.connector_types import FrozenArtifact
from openmacrostate.api.v1.errors import ContractError
from openmacrostate.api.v1.types import Observation, parse_timestamp
from openmacrostate.cli import main
from openmacrostate.connectors import builtin_connector_ids, get_builtin_connector
from openmacrostate.connectors.fed_h41_release import FedH41ReleaseConnector
from openmacrostate.runtime.case import evaluate_case
from openmacrostate.runtime.connectors import run_connector
from openmacrostate.runtime.http import RecordedHttpTransport
from openmacrostate.runtime.jsonio import sha256_bytes

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "connectors" / "fed_h41_release"
RECORDING = FIXTURE / "recording.json"
CORE_TIME = "2026-08-09T17:30:00Z"
URL = "https://www.federalreserve.gov/releases/h41/20230316/h41.htm"


def _body() -> bytes:
    return (FIXTURE / "response.html").read_bytes()


def _frozen(
    body: bytes | None = None,
    *,
    url: str = URL,
    retrieved_at: str = CORE_TIME,
) -> FrozenArtifact:
    payload = _body() if body is None else body
    return FrozenArtifact(
        source_id="federal.reserve.board.h41.dated_release",
        request_url=url,
        final_url=url,
        status_code=200,
        media_type="text/html",
        response_headers=MappingProxyType({"content-type": "text/html; charset=utf-8"}),
        retrieved_at=retrieved_at,
        transport_retrieved_at_claim="2026-08-09T17:21:00Z",
        body=payload,
        sha256=sha256_bytes(payload),
        byte_length=len(payload),
        capture_mode="recorded",
        recording_kind="test_only_excerpt",
        source_authentication="unverified_recording",
        transport_time_core_observed=False,
    )


def _capture(output: Path):
    return run_connector(
        FedH41ReleaseConnector(),
        {"start": "2023-03-16", "end": "2023-03-16"},
        RecordedHttpTransport(RECORDING),
        output,
        protected_paths=(FIXTURE,),
        clock=lambda: CORE_TIME,
    )


def _replace(old: str, new: str, *, count: int = -1) -> bytes:
    text = _body().decode("utf-8")
    assert old in text
    return text.replace(old, new, count).encode("utf-8")


def test_registry_and_plan_expose_one_fixed_dated_html_request() -> None:
    assert builtin_connector_ids() == (
        "fed-h41-release",
        "frbny-sofr",
        "treasury-debt-to-penny",
    )
    connector = get_builtin_connector("fed-h41-release")
    assert type(connector) is FedH41ReleaseConnector

    plans = connector.plan({"start": "2023-03-16", "end": "2023-03-16"})
    assert len(plans) == 1
    assert plans[0].method == "GET"
    assert plans[0].url == URL
    assert plans[0].accept == "text/html"
    assert plans[0].max_bytes == 2 * 1024 * 1024

    with pytest.raises(ContractError, match="same release date"):
        connector.plan({"start": "2023-03-16", "end": "2023-03-23"})
    with pytest.raises(ContractError, match="2021-08-12"):
        connector.plan({"start": "2021-08-05", "end": "2021-08-05"})
    with pytest.raises(ContractError, match="only start and end"):
        connector.plan(
            {
                "start": "2023-03-16",
                "end": "2023-03-16",
                "url": "https://evil.example/current",
            }
        )


def test_normalizer_selects_five_wednesday_stock_values() -> None:
    records = tuple(FedH41ReleaseConnector().normalize(_frozen()))

    assert [record.series_id for record in records] == [
        "fed.h41.total_assets",
        "fed.h41.securities_held_outright",
        "fed.h41.primary_credit",
        "fed.h41.treasury_general_account",
        "fed.h41.reserve_balances",
    ]
    assert [record.value for record in records] == [
        "8639300",
        "7940014",
        "152853",
        "277643",
        "3444208",
    ]
    assert {record.unit for record in records} == {"USD_million"}
    assert {record.observed_at for record in records} == {"2023-03-15T00:00:00Z"}
    assert {record.released_at for record in records} == {CORE_TIME}
    assert {record.extensions["source_declared_release_date"] for record in records} == {
        "2023-03-16"
    }
    assert all(
        record.extensions["source_declared_release_date_is_availability_proof"] is False
        for record in records
    )
    assert all(
        record.extensions["observed_at_convention"] == "canonical_utc_date_anchor_not_instant"
        for record in records
    )


def test_recorded_capture_is_a_valid_prospective_case(tmp_path: Path) -> None:
    output = tmp_path / "capture"
    capture = _capture(output)
    evaluation = evaluate_case(output)

    assert capture.case_id.startswith("capture-fed-h41-release-")
    assert len(capture.case_id.rsplit("-", 1)[-1]) == 32
    assert evaluation.summary()["accepted_observations"] == 5
    assert evaluation.summary()["quarantined_observations"] == 0
    assert evaluation.summary()["historical_evidence"] is False
    assert evaluation.case["information_cutoff"] == CORE_TIME
    assert evaluation.case["fixture_kind"] == "licensed_public"
    assert evaluation.case["extensions"]["source_authentication"] == "unverified_recording"
    assert evaluation.case["extensions"]["real_source_data"] is False
    assert evaluation.case["extensions"]["complete_source_response"] is False

    records = list(evaluation.accepted_observations)
    assert {record["released_at"] for record in records} == {CORE_TIME}
    assert {record["vintage_at"] for record in records} == {CORE_TIME}
    assert {record["ingested_at"] for record in records} == {CORE_TIME}
    artifact = evaluation.artifacts[0]
    assert artifact["source_published_at"] is None
    assert artifact["extensions"]["test_only_excerpt"] is True
    assert artifact["extensions"]["historical_version_authenticated"] is False
    assert artifact["license"] == {
        "license_id": "Federal-Reserve-Board-Public-Domain-Website-Information",
        "terms_url": "https://www.federalreserve.gov/disclaimer.htm",
        "redistribution": "restricted",
        "commercial_use": "allowed",
        "attribution": "Board of Governors of the Federal Reserve System",
        "reviewed_at": "2026-08-09T17:00:00Z",
    }
    raw_path = output / str(artifact["storage_uri"])
    assert raw_path.read_bytes() == _body()

    notice = (output / "LICENSES.md").read_text(encoding="utf-8")
    assert "public domain" in notice
    assert "excludes Federal Reserve seals, logos" in notice
    assert "not affiliated with or endorsed by the Board" in notice


def test_old_release_page_cannot_pass_an_old_information_cutoff(tmp_path: Path) -> None:
    evaluation = evaluate_case(_capture(tmp_path / "capture").case_dir)
    observation = Observation.from_mapping(evaluation.accepted_observations[0])
    old_cutoff = parse_timestamp("2023-03-16T22:00:00Z")

    assert observation.cutoff_reasons(old_cutoff, require_ingested_by_cutoff=True) == (
        "released_after_information_cutoff",
        "vintage_after_information_cutoff",
        "ingested_after_information_cutoff",
    )


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (
            lambda: _replace(
                "Release Date: Thursday, March 16, 2023",
                "Release Date: Thursday, March 23, 2023",
            ),
            "path date",
        ),
        (
            lambda: _replace(
                "Release Date: Thursday, March 16, 2023",
                "Release Date: Friday, March 16, 2023",
            ),
            "weekday",
        ),
        (
            lambda: _replace(
                "<p><i>Release Date: Thursday, March 16, 2023</i></p>",
                "<p><i>Release Date: Thursday, March 16, 2023</i></p>"
                "<p>Release Date: Thursday, March 16, 2023</p>",
            ),
            "exactly one Release Date",
        ),
        (
            lambda: _replace("<span>Millions</span>", "<span>Thousands</span>", count=1),
            "unit",
        ),
        (
            lambda: _replace(
                "Wednesday</span> <span>Mar 15",
                "Tuesday</span> <span>Mar 15",
                count=1,
            ),
            "Wednesday stock column",
        ),
        (
            lambda: _replace("Mar 15, 2023</span></th>", "Mar 8, 2023</span></th>", count=1),
            "share one Wednesday date",
        ),
        (
            lambda: _replace(
                'header="t1r1c1 t1h1c3">152,853',
                'header="t1r1c1 t1h2c1">152,853',
            ),
            "Wednesday stock column",
        ),
        (
            lambda: _replace("Primary credit", "Primary credіt"),
            "Primary credit",
        ),
        (
            lambda: _replace('<td id="t1r16c5"', '<td id="t1r16c5"></td><td id="t1r16c5"'),
            "duplicate cell ID",
        ),
        (
            lambda: _replace(
                "</table>",
                '<tr><td id="t1r99c1" header="t1h1c1">Primary credit</td>'
                '<td id="t1r99c5" header="t1r1c1 t1h1c3">1</td></tr></table>',
                count=1,
            ),
            "exactly one row",
        ),
    ],
)
def test_structure_date_and_semantic_drift_fail_closed(body, message: str) -> None:
    with pytest.raises(ContractError, match=message):
        tuple(FedH41ReleaseConnector().normalize(_frozen(body())))


def test_hidden_or_detached_semantic_context_cannot_authorize_units() -> None:
    text = _body().decode("utf-8")
    text = text.replace("<span>Millions</span>", "<span>Thousands</span>")
    text = text.replace(
        "<p><span>Thousands</span> <span>of dollars</span></p>",
        "<p><span>Thousands</span> <span>of dollars</span></p>"
        "<div hidden><div></div><p><span>Millions</span> <span>of dollars</span></p></div>",
    )
    with pytest.raises(ContractError, match="unit|immediately follow"):
        tuple(FedH41ReleaseConnector().normalize(_frozen(text.encode("utf-8"))))

    text = _body().decode("utf-8")
    text = text.replace("<span>Millions</span>", "<span>Thousands</span>")
    text = text.replace(
        "<body>",
        "<head><style>.ghost { display: none; }</style></head><body>",
    )
    text = text.replace(
        "<p><span>Thousands</span> <span>of dollars</span></p>",
        "<p><span>Thousands</span> <span>of dollars</span></p>"
        '<p class="ghost"><span>Millions</span> <span>of dollars</span></p>',
    )
    with pytest.raises(ContractError, match="immediately follow|without id"):
        tuple(FedH41ReleaseConnector().normalize(_frozen(text.encode("utf-8"))))

    text = _body().decode("utf-8")
    text = text.replace("<span>Millions</span>", "<span>Thousands</span>")
    text = text.replace(
        "<body>",
        "<head><style>#ghost-unit { display: none; }</style></head><body>",
    )
    text = text.replace(
        "<p><span>Thousands</span> <span>of dollars</span></p>",
        "<div>Thousands of dollars</div>"
        '<p id="ghost-unit"><span>Millions</span> <span>of dollars</span></p>',
    )
    with pytest.raises(ContractError, match="immediately follow|without id"):
        tuple(FedH41ReleaseConnector().normalize(_frozen(text.encode("utf-8"))))


def test_table_semantics_require_adjacent_sibling_paragraphs() -> None:
    text = _body().decode("utf-8")
    text = text.replace(
        "<p><span>1.</span> <span>Factors Affecting Reserve Balances of "
        "Depository Institutions</span></p>",
        "<p>9. Unrelated Table</p><div>"
        "<p>1. Factors Affecting Reserve Balances of Depository Institutions</p></div>",
        1,
    )
    with pytest.raises(ContractError, match="immediately follow|plain"):
        tuple(FedH41ReleaseConnector().normalize(_frozen(text.encode("utf-8"))))

    for intervening in ("THOUSANDS OF DOLLARS — UNRELATED TABLE", "<hr>"):
        text = (
            _body()
            .decode("utf-8")
            .replace(
                "<p><span>Millions</span> <span>of dollars</span></p>\n  <table>",
                f"<p><span>Millions</span> <span>of dollars</span></p>{intervening}\n  <table>",
                1,
            )
        )
        with pytest.raises(ContractError, match="immediately follow|plain"):
            tuple(FedH41ReleaseConnector().normalize(_frozen(text.encode("utf-8"))))

    text = (
        _body()
        .decode("utf-8")
        .replace(
            "<p><span>Millions</span> <span>of dollars</span></p>\n  <table>",
            "<p><span>Millions</span> <span>of dollars</span></p>"
            "<div><strong>Unrelated table context</strong></div>\n  <table>",
            1,
        )
    )
    with pytest.raises(ContractError, match="immediately follow|plain"):
        tuple(FedH41ReleaseConnector().normalize(_frozen(text.encode("utf-8"))))


def test_relevant_cells_require_unique_ids_and_explicit_table_rows() -> None:
    duplicate_attribute = _replace('id="t1r16c1"', 'id="t1r16c1" id="ignored"', count=1)
    with pytest.raises(ContractError, match="duplicate id attributes"):
        tuple(FedH41ReleaseConnector().normalize(_frozen(duplicate_attribute)))

    text = _body().decode("utf-8")
    text = re.sub(r"</?(?:table|tr)(?: [^>]*)?>", "", text)
    with pytest.raises(ContractError, match="explicit table row"):
        tuple(FedH41ReleaseConnector().normalize(_frozen(text.encode("utf-8"))))


def test_value_headers_must_resolve_to_real_cells_in_the_same_table() -> None:
    body = _replace('id="t1r1c1"', 'id="t1r90c1"', count=1)
    with pytest.raises(ContractError, match="row-group header is missing"):
        tuple(FedH41ReleaseConnector().normalize(_frozen(body)))


@pytest.mark.parametrize(
    "value",
    [
        "-1",
        "152,85",
        "0152",
        "152.853",
        "١٥٢٬٨٥٣",
        "...",
        ",".join(["999"] * 1434),
    ],
)
def test_reported_values_require_nonnegative_ascii_millions(value: str) -> None:
    body = _replace(">152,853</td>", f">{value}</td>")

    with pytest.raises(ContractError, match="ASCII integer|15-digit"):
        tuple(FedH41ReleaseConnector().normalize(_frozen(body)))


def test_total_assets_bounds_selected_balance_sheet_values() -> None:
    body = _replace(">8,639,300</td>", ">100</td>")

    with pytest.raises(ContractError, match="must not exceed total assets"):
        tuple(FedH41ReleaseConnector().normalize(_frozen(body)))


def test_parser_ignores_cover_note_table_order_and_row_numbers() -> None:
    body = _replace(
        "<p><span>1.</span> <span>Factors",
        "<table><tr><td>Cover note only</td></tr></table><p><span>1.</span> <span>Factors",
        count=1,
    ).decode("utf-8")
    body = body.replace("t1r16", "t1r42")

    records = tuple(FedH41ReleaseConnector().normalize(_frozen(body.encode("utf-8"))))
    primary = next(record for record in records if record.series_id == "fed.h41.primary_credit")
    assert primary.value == "152853"
    assert primary.extensions["source_cell_id"] == "t1r42c5"


def test_parser_never_substitutes_weekly_average_for_wednesday_stock() -> None:
    body = _replace(">84,957</td>", ">999,999</td>")

    records = tuple(FedH41ReleaseConnector().normalize(_frozen(body)))
    primary = next(record for record in records if record.series_id == "fed.h41.primary_credit")
    assert primary.value == "152853"
    assert primary.extensions["source_cell_id"] == "t1r16c5"


def test_current_inline_release_date_variant_is_supported() -> None:
    body = _replace(
        "Release Date: Thursday, March 16, 2023",
        "Release Date: March 16, 2023",
    )

    records = tuple(FedH41ReleaseConnector().normalize(_frozen(body)))
    assert len(records) == 5


def test_utf8_endpoint_and_new_york_future_bound_fail_closed() -> None:
    connector = FedH41ReleaseConnector()
    with pytest.raises(ContractError, match="strict UTF-8"):
        tuple(connector.normalize(_frozen(b"\xff\xfe")))
    with pytest.raises(ContractError, match="fixed dated endpoint"):
        tuple(
            connector.normalize(_frozen(url="https://www.federalreserve.gov/releases/h41/current/"))
        )
    with pytest.raises(ContractError, match="America/New_York"):
        tuple(connector.normalize(_frozen(retrieved_at="2023-03-16T00:30:00Z")))

    # UTC and New York are both on the release date after the usual publication window.
    records = tuple(connector.normalize(_frozen(retrieved_at="2023-03-16T21:30:00Z")))
    assert len(records) == 5


def test_recorded_h41_cli_is_offline(tmp_path: Path, monkeypatch, capsys) -> None:
    def forbidden_socket(*args, **kwargs):
        raise AssertionError("recorded H.4.1 connector attempted to open a network socket")

    monkeypatch.setattr(socket, "socket", forbidden_socket)
    output = tmp_path / "capture"
    assert (
        main(
            [
                "connector",
                "capture",
                "fed-h41-release",
                "--start",
                "2023-03-16",
                "--end",
                "2023-03-16",
                "--recording",
                str(RECORDING),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    assert "mode=recorded" in capsys.readouterr().out
    assert evaluate_case(output).summary()["accepted_observations"] == 5
