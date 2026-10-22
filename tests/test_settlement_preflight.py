"""Tests for liquidity-aware settlement preparation."""

import pytest

from common.settlement_preflight import prepare_settlement


def prepare(payments, balances):
    return prepare_settlement(
        payments=payments,
        account_balances=balances,
        window_id="W-001",
        accounts_table="test-accounts",
        payments_table="test-payments",
        ledger_table="test-ledger",
        settled_at="2026-10-22T12:00:00Z",
    )


def test_net_feasible_payments_are_selected():
    payments = [
        {"payment_id": "P1", "from": "A", "to": "B", "amount_paise": 1000},
        {"payment_id": "P2", "from": "B", "to": "A", "amount_paise": 1000},
    ]

    result = prepare(payments, {"A": 0, "B": 0})

    assert set(result["selected_ids"]) == {"P1", "P2"}
    assert result["deferred_ids"] == []
    assert len(result["settlement_operations"]) == 8


def test_infeasible_payment_is_deferred():
    payments = [
        {"payment_id": "P1", "from": "A", "to": "B", "amount_paise": 1000},
    ]

    result = prepare(payments, {"A": 0, "B": 0})

    assert result["selected_ids"] == []
    assert result["deferred_ids"] == ["P1"]
    assert result["settlement_operations"] == []


def test_missing_account_balance_is_rejected():
    payments = [
        {"payment_id": "P1", "from": "A", "to": "B", "amount_paise": 100},
    ]

    with pytest.raises(ValueError, match="balance"):
        prepare(payments, {"A": 100})


def test_oversized_settlement_is_rejected_before_reservation():
    payments = [
        {
            "payment_id": f"P{i}",
            "from": "A" if i % 2 == 0 else "B",
            "to": "B" if i % 2 == 0 else "A",
            "amount_paise": 100,
        }
        for i in range(34)
    ]

    with pytest.raises(ValueError, match="100-action"):
        prepare(payments, {"A": 0, "B": 0})


from unittest.mock import MagicMock

from common.settlement_preflight import prepare_settlement_from_dynamodb


def test_dynamodb_balances_drive_settlement_selection():
    client = MagicMock()
    client.get_item.side_effect = [
        {"Item": {"balance_paise": {"N": "0"}}},
        {"Item": {"balance_paise": {"N": "0"}}},
    ]

    payments = [
        {"payment_id": "P1", "from": "A", "to": "B", "amount_paise": 500},
        {"payment_id": "P2", "from": "B", "to": "A", "amount_paise": 500},
    ]

    result = prepare_settlement_from_dynamodb(
        client=client,
        payments=payments,
        window_id="W-001",
        accounts_table="test-accounts",
        payments_table="test-payments",
        ledger_table="test-ledger",
        settled_at="2026-10-22T12:00:00Z",
    )

    assert set(result["selected_ids"]) == {"P1", "P2"}
    assert result["deferred_ids"] == []
    assert len(result["settlement_operations"]) == 8
    assert client.get_item.call_count == 2
    assert all(
        call.kwargs["ConsistentRead"] is True
        for call in client.get_item.call_args_list
    )
    client.transact_write_items.assert_not_called()


def test_dynamodb_liquidity_defers_unfunded_payment():
    client = MagicMock()
    client.get_item.return_value = {
        "Item": {"balance_paise": {"N": "0"}}
    }

    result = prepare_settlement_from_dynamodb(
        client=client,
        payments=[
            {"payment_id": "P1", "from": "A", "to": "B", "amount_paise": 500}
        ],
        window_id="W-001",
        accounts_table="test-accounts",
        payments_table="test-payments",
        ledger_table="test-ledger",
        settled_at="2026-10-22T12:00:00Z",
    )

    assert result["selected_ids"] == []
    assert result["deferred_ids"] == ["P1"]
    assert result["settlement_operations"] == []
    client.transact_write_items.assert_not_called()
