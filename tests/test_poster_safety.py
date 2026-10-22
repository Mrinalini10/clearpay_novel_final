"""Safety tests for payment posting. No real AWS calls."""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import boto3


def test_sender_debit_requires_sufficient_balance(monkeypatch):
    monkeypatch.setenv("PAYMENTS_TABLE", "test-payments")
    monkeypatch.setenv("ACCOUNTS_TABLE", "test-accounts")
    monkeypatch.setenv("LEDGER_TABLE", "test-ledger")

    ddb = MagicMock()
    monkeypatch.setattr(boto3, "client", lambda service: ddb)

    spec = importlib.util.spec_from_file_location(
        "poster_safety_test",
        Path("src/handlers/poster.py"),
    )
    poster = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(poster)

    ddb.get_item.return_value = {
        "Item": {
            "payment_id": {"S": "P1"},
            "status": {"S": "PENDING"},
            "from_account": {"S": "A"},
            "to_account": {"S": "B"},
            "amount_paise": {"N": "1000"},
        }
    }

    poster.post_payment("P1")

    operations = ddb.transact_write_items.call_args.kwargs[
        "TransactItems"
    ]

    sender_update = next(
        operation["Update"]
        for operation in operations
        if "Update" in operation
        and operation["Update"]["TableName"] == "test-accounts"
        and operation["Update"]["Key"]["account_id"]["S"] == "A"
    )

    condition = sender_update.get("ConditionExpression", "")
    values = sender_update["ExpressionAttributeValues"]

    assert "balance_paise >= :required" in condition
    assert values[":required"] == {"N": "1000"}


import pytest


@pytest.mark.parametrize("batch_mode", ["1", "0"])
def test_immediate_posting_respects_batch_mode(monkeypatch, batch_mode):
    monkeypatch.setenv("PAYMENTS_TABLE", "test-payments")
    monkeypatch.setenv("ACCOUNTS_TABLE", "test-accounts")
    monkeypatch.setenv("LEDGER_TABLE", "test-ledger")
    monkeypatch.setenv("LIQUIDITY_BATCH_MODE", batch_mode)

    ddb = MagicMock()
    monkeypatch.setattr(boto3, "client", lambda service: ddb)

    spec = importlib.util.spec_from_file_location(
        "poster_batch_mode_test",
        Path("src/handlers/poster.py"),
    )
    poster = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(poster)

    ddb.get_item.return_value = {
        "Item": {
            "payment_id": {"S": "P1"},
            "status": {"S": "PENDING"},
            "from_account": {"S": "A"},
            "to_account": {"S": "B"},
            "amount_paise": {"N": "1000"},
        }
    }

    if batch_mode == "1":
        with pytest.raises(RuntimeError, match="Immediate posting disabled"):
            poster.post_payment("P1")

        ddb.get_item.assert_not_called()
        ddb.transact_write_items.assert_not_called()
    else:
        assert poster.post_payment("P1") == "posted"
        ddb.transact_write_items.assert_called_once()
