"""Contract tests for the proposed liquidity-aware Step Functions workflow."""

import json
from pathlib import Path


WORKFLOW = Path("workflow/liquidity_settlement.asl.json")


def load_workflow():
    return json.loads(WORKFLOW.read_text(encoding="utf-8"))


def test_workflow_starts_by_collecting_pending_payments():
    workflow = load_workflow()
    states = workflow["States"]

    assert workflow["StartAt"] == "CollectPending"
    assert states["CollectPending"]["Next"] == "AnyPending"
    assert states["CollectPending"]["Parameters"]["Payload"] == {
        "start_time.$": "$$.Execution.StartTime",
        "run_id.$": "$.run_id",
    }


def test_empty_batch_skips_settlement():
    choice = load_workflow()["States"]["AnyPending"]

    assert choice["Default"] == "NothingToSettle"
    assert choice["Choices"] == [
        {
            "Variable": "$.collection.Payload.count",
            "NumericGreaterThan": 0,
            "Next": "SettlePending",
        }
    ]


def test_settlement_receives_the_collected_frozen_batch():
    states = load_workflow()["States"]
    settlement = states["SettlePending"]

    assert settlement["Resource"] == "arn:aws:states:::lambda:invoke"
    assert settlement["Parameters"]["Payload.$"] == "$.collection.Payload"
    assert settlement["OutputPath"] == "$.settlement.Payload"
    assert settlement["End"] is True


def test_tasks_have_retries_and_failure_paths():
    states = load_workflow()["States"]

    for name in ("CollectPending", "SettlePending"):
        task = states[name]

        assert task["Retry"]
        assert task["Retry"][0]["MaxAttempts"] == 3
        assert task["Catch"][0]["Next"] == "WindowFailed"

    assert states["WindowFailed"]["Type"] == "Fail"


def test_workflow_does_not_use_legacy_posting_or_finalization():
    states = load_workflow()["States"]

    assert set(states) == {
        "CollectPending",
        "AnyPending",
        "SettlePending",
        "NothingToSettle",
        "WindowFailed",
    }

    assert "PosterFunction" not in WORKFLOW.read_text()
    assert "FinalizeFunction" not in WORKFLOW.read_text()


def test_all_workflow_transitions_target_existing_states():
    workflow = load_workflow()
    states = workflow["States"]

    for state in states.values():
        targets = []

        if "Next" in state:
            targets.append(state["Next"])

        if "Default" in state:
            targets.append(state["Default"])

        targets.extend(
            choice["Next"]
            for choice in state.get("Choices", [])
        )

        targets.extend(
            catcher["Next"]
            for catcher in state.get("Catch", [])
        )

        assert all(target in states for target in targets)
