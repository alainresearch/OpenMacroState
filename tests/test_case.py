from __future__ import annotations

import json
import math
import shutil
from hashlib import sha256
from pathlib import Path

import pytest

from openmacrostate.api.v1.errors import CaseValidationError, ContractError
from openmacrostate.runtime.case import evaluate_case, score_case

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "cases" / "2023-banks"
REVEAL = ROOT / "reveals" / "2023-banks"
EVALUATION_AT = "2023-03-13T22:00:00Z"


def _refresh_research_checksums(case_dir: Path) -> None:
    case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    manifest_path = case_dir / case["extensions"]["checksums_file"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        data = (case_dir / entry["path"]).read_bytes()
        entry["bytes"] = len(data)
        entry["sha256"] = sha256(data).hexdigest()
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def _refresh_reveal_checksums(reveal_dir: Path) -> None:
    reveal = json.loads((reveal_dir / "reveal.json").read_text(encoding="utf-8"))
    manifest_path = reveal_dir / reveal["checksums_file"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        data = (reveal_dir / entry["path"]).read_bytes()
        entry["bytes"] = len(data)
        entry["sha256"] = sha256(data).hexdigest()
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def test_cutoff_closes_transitively() -> None:
    evaluation = evaluate_case(CASE)

    assert [item["observation_id"] for item in evaluation.accepted_observations] == [
        "obs_synth_policy_20230308",
        "obs_synth_deposit_pressure_20230308",
        "obs_synth_deposit_pressure_20230309",
        "obs_synth_funding_spread_20230309",
    ]
    assert len(evaluation.quarantined_observations) == 1
    quarantined = evaluation.quarantined_observations[0]
    assert quarantined["observation_id"] == "obs_synth_post_cutoff_trap"
    assert quarantined["quarantine"]["primary_reason"] == ("released_after_information_cutoff")
    assert [item["claim_id"] for item in evaluation.accepted_claims] == [
        "claim_synth_pressure_rising",
        "claim_synth_funding_elevated",
    ]
    assert tuple(evaluation.rejected_claims[0]["rejection"]["ineligible_evidence_ids"]) == (
        "obs_synth_post_cutoff_trap",
    )


def test_scoring_is_reveal_gated_and_exact() -> None:
    evaluation = evaluate_case(CASE)
    result = score_case(evaluation, REVEAL, evaluation_at=EVALUATION_AT)

    assert len(result["scores"]) == 1
    score = result["scores"][0]
    assert score["brier_score"] == pytest.approx(0.4225, abs=1e-12)
    assert score["binary_log_loss"] == pytest.approx(-math.log(0.35), abs=1e-12)


def test_snapshot_is_deterministic() -> None:
    evaluation = evaluate_case(CASE)
    first = evaluation.snapshot()
    second = evaluation.snapshot()

    assert first == second
    assert len(first["content_sha256"]) == 64
    assert first["created_at"] != first["information_cutoff"]
    with pytest.raises(TypeError):
        evaluation.case["title"] = "mutated"


def test_equivalent_runs_have_the_same_content_root() -> None:
    first = evaluate_case(CASE).snapshot()
    second = evaluate_case(CASE).snapshot()

    assert first["content_sha256"] == second["content_sha256"]
    assert first["extensions"]["eligible_content"]["observations"]
    assert first["extensions"]["eligible_content"]["research_integrity"]["manifest_sha256"]


def test_eligible_snapshot_omits_all_excluded_plaintext() -> None:
    snapshot = evaluate_case(CASE).snapshot()
    encoded = json.dumps(snapshot, sort_keys=True)

    assert "obs_synth_post_cutoff_trap" not in encoded
    assert "artifact_synth_post_cutoff_trap" not in encoded
    assert "claim_synth_leaky_must_reject" not in encoded
    assert "210.0" not in encoded
    assert snapshot["extensions"]["eligible_content"]["exclusion_counts"] == {
        "observations": 1,
        "claims": 1,
        "predictions": 0,
    }
    assert len(snapshot["extensions"]["audit_sha256"]) == 64


def test_checksum_tampering_fails_closed(tmp_path: Path) -> None:
    case_copy = tmp_path / "case"
    shutil.copytree(CASE, case_copy)
    claims_path = case_copy / "inputs" / "claims.jsonl"
    claims_path.write_text(claims_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(CaseValidationError, match="byte length mismatch"):
        evaluate_case(case_copy)


def test_case_path_escape_fails_closed(tmp_path: Path) -> None:
    case_copy = tmp_path / "case"
    shutil.copytree(CASE, case_copy)
    case_path = case_copy / "case.json"
    case = json.loads(case_path.read_text(encoding="utf-8"))
    case["observations_file"] = "../outside.jsonl"
    case_path.write_text(json.dumps(case), encoding="utf-8")

    with pytest.raises(CaseValidationError):
        evaluate_case(case_copy)


def test_impossible_prediction_has_json_safe_infinite_log_loss(tmp_path: Path) -> None:
    case_copy = tmp_path / "case"
    shutil.copytree(CASE, case_copy)
    prediction_path = case_copy / "inputs" / "predictions.jsonl"
    prediction = json.loads(prediction_path.read_text(encoding="utf-8"))
    prediction["probability"] = 0.0
    prediction_path.write_text(
        json.dumps(prediction, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    _refresh_research_checksums(case_copy)
    evaluation = evaluate_case(case_copy)

    score = score_case(evaluation, REVEAL, evaluation_at=EVALUATION_AT)["scores"][0]
    assert score["binary_log_loss"] is None
    assert score["binary_log_loss_is_infinite"] is True


def test_strict_rfc3339_rejects_timezone_free_timestamp() -> None:
    evaluation = evaluate_case(CASE)
    observation = {
        **evaluation.accepted_observations[0],
        "released_at": "2023-03-08T14:00:00",
    }
    from openmacrostate.api.v1 import Observation

    with pytest.raises(ContractError, match="RFC3339"):
        Observation.from_mapping(observation)


def test_retroactively_ingested_observations_require_and_use_proof() -> None:
    evaluation = evaluate_case(CASE)
    cutoff = evaluation.information_cutoff

    assert all(record["ingested_at"] > cutoff for record in evaluation.accepted_observations)
    assert len(evaluation.accepted_observations) == 4


def test_late_ingestion_without_proof_is_quarantined(tmp_path: Path) -> None:
    case_copy = tmp_path / "case"
    shutil.copytree(CASE, case_copy)
    artifacts_path = case_copy / "inputs" / "artifacts.jsonl"
    records = [json.loads(line) for line in artifacts_path.read_text(encoding="utf-8").splitlines()]
    records[0]["extensions"]["availability_proof"]["verified"] = False
    artifacts_path.write_text(
        "".join(json.dumps(record, separators=(",", ":")) + "\n" for record in records),
        encoding="utf-8",
    )
    _refresh_research_checksums(case_copy)

    evaluation = evaluate_case(case_copy)
    assert not evaluation.accepted_observations
    reasons = {
        record["observation_id"]: tuple(record["quarantine"]["reasons"])
        for record in evaluation.quarantined_observations
    }
    assert (
        "post_cutoff_ingestion_without_availability_proof" in reasons["obs_synth_policy_20230308"]
    )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("value", [], "finite JSON scalar"),
        ("quality", "potato", "quality is invalid"),
        ("vintage_at", "2023-03-07T00:00:00Z", "must not precede released_at"),
    ],
)
def test_invalid_observation_contract_fails_closed(
    tmp_path: Path, field: str, value: object, message: str
) -> None:
    case_copy = tmp_path / "case"
    shutil.copytree(CASE, case_copy)
    observations_path = case_copy / "inputs" / "observations.jsonl"
    records = [
        json.loads(line) for line in observations_path.read_text(encoding="utf-8").splitlines()
    ]
    records[0][field] = value
    observations_path.write_text(
        "".join(json.dumps(record, separators=(",", ":")) + "\n" for record in records),
        encoding="utf-8",
    )
    _refresh_research_checksums(case_copy)

    with pytest.raises(CaseValidationError, match=message):
        evaluate_case(case_copy)


def test_claim_evidence_is_closed_at_the_claim_cutoff(tmp_path: Path) -> None:
    case_copy = tmp_path / "case"
    shutil.copytree(CASE, case_copy)
    claims_path = case_copy / "inputs" / "claims.jsonl"
    records = [json.loads(line) for line in claims_path.read_text(encoding="utf-8").splitlines()]
    records[0]["information_cutoff"] = "2023-03-09T12:00:00Z"
    claims_path.write_text(
        "".join(json.dumps(record, separators=(",", ":")) + "\n" for record in records),
        encoding="utf-8",
    )
    _refresh_research_checksums(case_copy)

    evaluation = evaluate_case(case_copy)
    rejected = {record["claim_id"]: record for record in evaluation.rejected_claims}
    assert (
        "ineligible_evidence_at_claim_cutoff"
        in rejected["claim_synth_pressure_rising"]["rejection"]["reasons"]
    )


def test_future_as_of_claim_is_rejected_and_cannot_support_prediction(tmp_path: Path) -> None:
    case_copy = tmp_path / "case"
    shutil.copytree(CASE, case_copy)
    claims_path = case_copy / "inputs" / "claims.jsonl"
    records = [json.loads(line) for line in claims_path.read_text(encoding="utf-8").splitlines()]
    records[0]["as_of"] = "2099-01-01T00:00:00Z"
    claims_path.write_text(
        "".join(json.dumps(record, separators=(",", ":")) + "\n" for record in records),
        encoding="utf-8",
    )
    _refresh_research_checksums(case_copy)

    evaluation = evaluate_case(case_copy)
    rejected = {record["claim_id"]: record for record in evaluation.rejected_claims}
    assert (
        "claim_as_of_after_information_cutoff"
        in rejected["claim_synth_pressure_rising"]["rejection"]["reasons"]
    )
    assert not evaluation.accepted_predictions
    assert "rejected_rationale_claim" in evaluation.rejected_predictions[0]["rejection"]["reasons"]


def test_prediction_evidence_is_closed_at_prediction_time(tmp_path: Path) -> None:
    case_copy = tmp_path / "case"
    shutil.copytree(CASE, case_copy)
    predictions_path = case_copy / "inputs" / "predictions.jsonl"
    prediction = json.loads(predictions_path.read_text(encoding="utf-8"))
    prediction["made_at"] = "2023-03-09T13:01:00Z"
    predictions_path.write_text(
        json.dumps(prediction, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    _refresh_research_checksums(case_copy)

    evaluation = evaluate_case(case_copy)
    assert not evaluation.accepted_predictions
    reasons = evaluation.rejected_predictions[0]["rejection"]["reasons"]
    assert "rationale_claim_not_available_at_prediction_time" in reasons
    assert "ineligible_evidence_at_prediction_time" in reasons


def test_retrospective_proof_is_bound_to_artifact_publication(tmp_path: Path) -> None:
    case_copy = tmp_path / "case"
    shutil.copytree(CASE, case_copy)
    artifacts_path = case_copy / "inputs" / "artifacts.jsonl"
    records = [json.loads(line) for line in artifacts_path.read_text(encoding="utf-8").splitlines()]
    records[0]["source_published_at"] = "2026-08-09T00:00:00Z"
    artifacts_path.write_text(
        "".join(json.dumps(record, separators=(",", ":")) + "\n" for record in records),
        encoding="utf-8",
    )
    _refresh_research_checksums(case_copy)

    evaluation = evaluate_case(case_copy)
    assert not evaluation.accepted_observations
    assert all(
        "post_cutoff_ingestion_without_availability_proof" in record["quarantine"]["reasons"]
        for record in evaluation.quarantined_observations
        if record["artifact_id"] == "artifact_synth_pre_cutoff_snapshot"
    )


def test_artifact_terms_url_must_match_public_schema(tmp_path: Path) -> None:
    case_copy = tmp_path / "case"
    shutil.copytree(CASE, case_copy)
    artifacts_path = case_copy / "inputs" / "artifacts.jsonl"
    records = [json.loads(line) for line in artifacts_path.read_text(encoding="utf-8").splitlines()]
    records[0]["license"]["terms_url"] = "not a uri"
    artifacts_path.write_text(
        "".join(json.dumps(record, separators=(",", ":")) + "\n" for record in records),
        encoding="utf-8",
    )
    _refresh_research_checksums(case_copy)

    with pytest.raises(CaseValidationError, match="absolute URI"):
        evaluate_case(case_copy)


def test_validate_does_not_need_or_read_reveal_bundle(tmp_path: Path) -> None:
    case_copy = tmp_path / "case-only"
    shutil.copytree(CASE, case_copy)

    evaluation = evaluate_case(case_copy)
    assert evaluation.summary()["accepted_observations"] == 4


def test_reveal_gate_fails_before_opening_outcome_bytes(tmp_path: Path) -> None:
    reveal_copy = tmp_path / "reveal"
    shutil.copytree(REVEAL, reveal_copy)
    (reveal_copy / "outcomes.jsonl").unlink()
    evaluation = evaluate_case(CASE)

    with pytest.raises(CaseValidationError, match="embargoed"):
        score_case(
            evaluation,
            reveal_copy,
            evaluation_at="2023-03-13T21:59:59Z",
        )
    with pytest.raises(CaseValidationError, match="cannot read checksummed file"):
        score_case(evaluation, reveal_copy, evaluation_at=EVALUATION_AT)


def test_reveal_bytes_are_verified_at_scoring_time(tmp_path: Path) -> None:
    reveal_copy = tmp_path / "reveal"
    shutil.copytree(REVEAL, reveal_copy)
    outcome_path = reveal_copy / "outcomes.jsonl"
    original = outcome_path.read_text(encoding="utf-8")
    outcome_path.write_text(original.replace('"value":1', '"value":0'), encoding="utf-8")

    with pytest.raises(CaseValidationError, match="SHA-256 mismatch"):
        score_case(evaluate_case(CASE), reveal_copy, evaluation_at=EVALUATION_AT)


@pytest.mark.parametrize(
    ("published_at", "retrieved_at", "message"),
    [
        ("2099-01-01T00:00:00Z", "2099-01-01T00:00:00Z", "published after evaluation_at"),
        ("2023-03-13T22:00:00Z", "2026-08-09T00:00:00Z", "retrieved after evaluation_at"),
    ],
)
def test_reveal_artifact_must_be_available_at_evaluation_time(
    tmp_path: Path, published_at: str, retrieved_at: str, message: str
) -> None:
    reveal_copy = tmp_path / "reveal"
    shutil.copytree(REVEAL, reveal_copy)
    artifacts_path = reveal_copy / "artifacts.jsonl"
    artifact = json.loads(artifacts_path.read_text(encoding="utf-8"))
    artifact["source_published_at"] = published_at
    artifact["retrieved_at"] = retrieved_at
    artifacts_path.write_text(json.dumps(artifact, separators=(",", ":")) + "\n", encoding="utf-8")
    _refresh_reveal_checksums(reveal_copy)

    with pytest.raises(CaseValidationError, match=message):
        score_case(evaluate_case(CASE), reveal_copy, evaluation_at=EVALUATION_AT)


def test_outcome_contract_and_artifact_source_are_enforced(tmp_path: Path) -> None:
    reveal_copy = tmp_path / "reveal"
    shutil.copytree(REVEAL, reveal_copy)
    outcomes_path = reveal_copy / "outcomes.jsonl"
    outcome = json.loads(outcomes_path.read_text(encoding="utf-8"))
    outcome["value"] = []
    outcomes_path.write_text(json.dumps(outcome, separators=(",", ":")) + "\n", encoding="utf-8")
    _refresh_reveal_checksums(reveal_copy)

    with pytest.raises(CaseValidationError, match="finite JSON scalar"):
        score_case(evaluate_case(CASE), reveal_copy, evaluation_at=EVALUATION_AT)

    outcome["value"] = 1
    outcome["source_id"] = "different_source"
    outcomes_path.write_text(json.dumps(outcome, separators=(",", ":")) + "\n", encoding="utf-8")
    _refresh_reveal_checksums(reveal_copy)
    with pytest.raises(CaseValidationError, match="source_id does not match"):
        score_case(evaluate_case(CASE), reveal_copy, evaluation_at=EVALUATION_AT)


def test_duplicate_json_keys_fail_closed(tmp_path: Path) -> None:
    case_copy = tmp_path / "case"
    shutil.copytree(CASE, case_copy)
    claims_path = case_copy / "inputs" / "claims.jsonl"
    first, *rest = claims_path.read_text(encoding="utf-8").splitlines()
    first = first.replace(
        '"claim_id":"claim_synth_pressure_rising",',
        '"claim_id":"claim_synth_pressure_rising","claim_id":"duplicate",',
        1,
    )
    claims_path.write_text("\n".join([first, *rest]) + "\n", encoding="utf-8")
    _refresh_research_checksums(case_copy)

    with pytest.raises(CaseValidationError, match="duplicate JSON object key"):
        evaluate_case(case_copy)


def test_declared_fixture_assertions_match_runtime() -> None:
    research_assertions = json.loads(
        (CASE / "expected" / "assertions.json").read_text(encoding="utf-8")
    )["assertions"]
    reveal_assertions = json.loads(
        (REVEAL / "expected" / "assertions.json").read_text(encoding="utf-8")
    )["assertions"]
    research_expected = {item["assertion_id"]: item["expected"] for item in research_assertions}
    reveal_expected = {item["assertion_id"]: item["expected"] for item in reveal_assertions}
    evaluation = evaluate_case(CASE)
    scoring = score_case(evaluation, REVEAL, evaluation_at=EVALUATION_AT)

    assert len(evaluation.artifacts) == research_expected["A005_artifact_count"]
    assert {record["observation_id"] for record in evaluation.accepted_observations} == set(
        research_expected["A011_pre_cutoff_observations_accepted"]
    )
    assert {record["claim_id"] for record in evaluation.accepted_claims} == set(
        research_expected["A014_valid_claims_accepted"]
    )
    assert (
        evaluation.accepted_predictions[0]["made_at"]
        == research_expected["A016_prediction_frozen_at_cutoff"]
    )
    score = scoring["scores"][0]
    assert score["outcome_value"] == reveal_expected["R006_outcome_value"]
    assert score["brier_score"] == pytest.approx(reveal_expected["R008_brier_score"])
    assert score["binary_log_loss"] == pytest.approx(reveal_expected["R009_log_loss"])
