"""Verify batch mode prevents premature SQS posting."""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import boto3
import pytest
from botocore.exceptions import ClientError


@pytest.mark.parametrize("batch_mode", ["0", "1"])
@pytest.mark.parametrize("replay", [False, True])
def test_enqueue_respects_batch_mode(monkeypatch, batch_mode, replay):
    monkeypatch.setenv("LIQUIDITY_BATCH_MODE", batch_mode)
    monkeypatch.setenv("PAYMENTS_TABLE", "test-payments")
    monkeypatch.setenv("QUEUE_URL", "https://example.com/test-queue")

    table = MagicMock()
    queue = MagicMock()

    monkeypatch.setattr(boto3, "resource", lambda service: MagicMock(Table=lambda name: table))
    monkeypatch.setattr(boto3, "client", lambda service: queue)

    spec = importlib.util.spec_from_file_location(
        "ingest_batch_mode_test",
        Path("src/handlers/ingest.py"),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    clean = {
        "from_account": "A",
        "to_account": "B",
        "amount_paise": 100,
        "currency": "INR",
    }

    monkeypatch.setattr(module, "authorized", lambda headers: True)
    monkeypatch.setattr(module, "validate", lambda body: (clean, None))
    monkeypatch.setattr(module, "request_hash", lambda payload: "test-hash")
    monkeypatch.setattr(module, "now_iso", lambda: "2026-01-01T00:00:00Z")
    monkeypatch.setattr(
        module,
        "response",
        lambda status, body, *args: {"statusCode": status, "body": body},
    )

    if replay:
        table.put_item.side_effect = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException"}},
            "PutItem",
        )
        table.get_item.return_value = {
            "Item": {
                **clean,
                "payment_id": "test-key-123",
                "status": "PENDING",
                "request_hash": "test-hash",
            }
        }

    event = {
        "headers": {"Idempotency-Key": "test-key-123"},
        "body": "{}",
    }

    result = module.handler(event, None)

    assert result["statusCode"] == (200 if replay else 202)
    assert queue.send_message.call_count == (0 if batch_mode == "1" else 1)
