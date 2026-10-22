"""Tests for building atomic net-settlement transactions."""

import pytest

from common.settlement_transaction import build_settlement_transaction


def build(payments):
    return build_settlement_transaction(
        selected_payments=payments,
        window_id="W-001",
        accounts_table="test-accounts",
        payments_table="test-payments",
        ledger_table="test-ledger",
        settled_at="2026-10-22T12:00:00Z",
    )


def test_net_settlement_combines_balances_ledger_and_status():
    payments = [
        {"payment_id": "P1", "from": "A", "to": "B", "amount_paise": 1000},
        {"payment_id": "P2", "from": "B", "to": "A", "amount_paise": 600},
    ]

    operations = build(payments)

    account_updates = [
        item["Update"]
        for item in operations
        if "Update" in item
        and item["Update"]["TableName"] == "test-accounts"
    ]
    ledger_entries = [item["Put"] for item in operations if "Put" in item]
    payment_updates = [
        item["Update"]
        for item in operations
        if "Update" in item
        and item["Update"]["TableName"] == "test-payments"
    ]

    assert len(account_updates) == 2
    assert len(ledger_entries) == 4
    assert len(payment_updates) == 2
    assert len(operations) == 8

    changes = {
        item["Key"]["account_id"]["S"]:
        int(item["ExpressionAttributeValues"][":delta"]["N"])
        for item in account_updates
    }
    assert changes == {"A": -400, "B": 400}

    for item in payment_updates:
        assert "#st = :reserved AND window_id = :window" in (
            item["ConditionExpression"]
        )


def test_zero_net_payments_still_check_accounts():
    payments = [
        {"payment_id": "P1", "from": "A", "to": "B", "amount_paise": 500},
        {"payment_id": "P2", "from": "B", "to": "A", "amount_paise": 500},
    ]

    operations = build(payments)

    checks = [
        item["ConditionCheck"]
        for item in operations
        if "ConditionCheck" in item
    ]

    assert len(checks) == 2
    assert {
        item["Key"]["account_id"]["S"] for item in checks
    } == {"A", "B"}


def test_transaction_limit_is_enforced():
    payments = [
        {
            "payment_id": f"P{i}",
            "from": "A",
            "to": "B",
            "amount_paise": 100,
        }
        for i in range(34)
    ]

    with pytest.raises(ValueError, match="100-action"):
        build(payments)


def test_duplicate_payment_is_rejected():
    payments = [
        {"payment_id": "P1", "from": "A", "to": "B", "amount_paise": 100},
        {"payment_id": "P1", "from": "B", "to": "A", "amount_paise": 100},
    ]

    with pytest.raises(ValueError, match="Duplicate"):
        build(payments)


def test_settlement_checks_original_payment_details():
    payments = [
        {
            "payment_id": "P1",
            "from": "A",
            "to": "B",
            "amount_paise": 500,
        }
    ]

    operations = build(payments)

    payment_update = next(
        item["Update"]
        for item in operations
        if "Update" in item
        and item["Update"]["TableName"] == "test-payments"
    )

    condition = payment_update["ConditionExpression"]
    values = payment_update["ExpressionAttributeValues"]

    assert "from_account = :source" in condition
    assert "to_account = :destination" in condition
    assert "amount_paise = :amount" in condition
    assert "#st = :reserved AND window_id = :window" in condition

    assert values[":source"] == {"S": "A"}
    assert values[":destination"] == {"S": "B"}
    assert values[":amount"] == {"N": "500"}
    assert values[":window"] == {"S": "W-001"}
