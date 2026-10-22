"""Tests for DynamoDB net-settlement balance updates."""

import pytest

from common.net_balance_updates import build_net_balance_updates


def test_only_net_amount_is_debited_and_credited():
    payments = [
        {"payment_id": "P1", "from": "A", "to": "B", "amount_paise": 1000},
        {"payment_id": "P2", "from": "B", "to": "A", "amount_paise": 600},
    ]

    operations = build_net_balance_updates(payments, "test-accounts")

    assert len(operations) == 2

    updates = {
        item["Update"]["Key"]["account_id"]["S"]: item["Update"]
        for item in operations
    }

    assert updates["A"]["ExpressionAttributeValues"][":delta"] == {
        "N": "-400"
    }
    assert updates["B"]["ExpressionAttributeValues"][":delta"] == {
        "N": "400"
    }

    assert "balance_paise >= :required" in updates["A"]["ConditionExpression"]
    assert updates["A"]["ExpressionAttributeValues"][":required"] == {
        "N": "400"
    }

    assert "attribute_exists(account_id)" in updates["B"]["ConditionExpression"]
    assert ":required" not in updates["B"]["ExpressionAttributeValues"]


def test_circular_payments_need_no_balance_updates():
    payments = [
        {"payment_id": "P1", "from": "A", "to": "B", "amount_paise": 500},
        {"payment_id": "P2", "from": "B", "to": "C", "amount_paise": 500},
        {"payment_id": "P3", "from": "C", "to": "A", "amount_paise": 500},
    ]

    assert build_net_balance_updates(payments, "test-accounts") == []


def test_empty_batch_needs_no_balance_updates():
    assert build_net_balance_updates([], "test-accounts") == []


def test_missing_table_name_is_rejected():
    with pytest.raises(ValueError):
        build_net_balance_updates([], "")
