"""Local tests for the pending-settlement Lambda handler."""

import io
import json
from unittest.mock import MagicMock

import pytest

import handlers.settle_pending as settle_pending


PAYMENTS = [
    {
        "payment_id": "P1",
        "from": "A",
        "to": "B",
        "amount_paise": 500,
    }
]

EVENT = {
    "window_id": "W-001",
    "s3_key": "windows/W-001/pending.json",
    "count": 1,
}


def configure(monkeypatch):
    monkeypatch.setenv("LIQUIDITY_BATCH_MODE", "1")
    monkeypatch.setenv("DATA_BUCKET", "test-bucket")
    monkeypatch.setenv("ACCOUNTS_TABLE", "test-accounts")
    monkeypatch.setenv("PAYMENTS_TABLE", "test-payments")
    monkeypatch.setenv("LEDGER_TABLE", "test-ledger")

    s3 = MagicMock()
    ddb = MagicMock()

    s3.get_object.return_value = {
        "Body": io.BytesIO(json.dumps(PAYMENTS).encode("utf-8"))
    }

    def client(service):
        return {"s3": s3, "dynamodb": ddb}[service]

    monkeypatch.setattr(settle_pending.boto3, "client", client)

    executor = MagicMock(
        return_value={
            "selected_ids": ["P1"],
            "deferred_ids": [],
            "metrics": {"test": True},
        }
    )
    monkeypatch.setattr(
        settle_pending, "execute_settlement_window", executor
    )

    return s3, ddb, executor


def test_handler_executes_frozen_pending_batch(monkeypatch):
    s3, ddb, executor = configure(monkeypatch)

    result = settle_pending.handler(EVENT, None)

    assert result["window_id"] == "W-001"
    assert result["selected_ids"] == ["P1"]
    assert result["deferred_ids"] == []

    s3.get_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="windows/W-001/pending.json",
    )

    arguments = executor.call_args.kwargs
    assert arguments["client"] is ddb
    assert arguments["s3"] is s3
    assert arguments["payments"] == PAYMENTS
    assert arguments["window_id"] == "W-001"


def test_handler_rejects_disabled_batch_mode(monkeypatch):
    _, _, executor = configure(monkeypatch)
    monkeypatch.setenv("LIQUIDITY_BATCH_MODE", "0")

    with pytest.raises(RuntimeError, match="not enabled"):
        settle_pending.handler(EVENT, None)

    executor.assert_not_called()


def test_handler_rejects_wrong_s3_key(monkeypatch):
    _, _, executor = configure(monkeypatch)

    event = dict(EVENT)
    event["s3_key"] = "windows/W-OTHER/pending.json"

    with pytest.raises(ValueError, match="Invalid frozen"):
        settle_pending.handler(event, None)

    executor.assert_not_called()


def test_handler_rejects_changed_batch_count(monkeypatch):
    _, _, executor = configure(monkeypatch)

    event = dict(EVENT)
    event["count"] = 2

    with pytest.raises(ValueError, match="count mismatch"):
        settle_pending.handler(event, None)

    executor.assert_not_called()
