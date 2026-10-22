"""Tests for liquidity-aware net balance calculations."""

import pytest

from common.net_settlement import build_net_balance_changes


def test_opposite_payments_cancel_out():
    payments = [
        {"payment_id": "P1", "from": "A", "to": "B", "amount_paise": 500},
        {"payment_id": "P2", "from": "B", "to": "A", "amount_paise": 500},
    ]

    assert build_net_balance_changes(payments) == {}


def test_net_debtor_and_creditor():
    payments = [
        {"payment_id": "P1", "from": "A", "to": "B", "amount_paise": 1000},
        {"payment_id": "P2", "from": "B", "to": "A", "amount_paise": 600},
    ]

    assert build_net_balance_changes(payments) == {
        "A": -400,
        "B": 400,
    }


def test_circular_payments_cancel_out():
    payments = [
        {"payment_id": "P1", "from": "A", "to": "B", "amount_paise": 1000},
        {"payment_id": "P2", "from": "B", "to": "C", "amount_paise": 1000},
        {"payment_id": "P3", "from": "C", "to": "A", "amount_paise": 1000},
    ]

    assert build_net_balance_changes(payments) == {}


def test_empty_batch_has_no_balance_changes():
    assert build_net_balance_changes([]) == {}


@pytest.mark.parametrize(
    "payments",
    [
        [
            {"payment_id": "P1", "from": "A", "to": "B", "amount_paise": 100},
            {"payment_id": "P1", "from": "B", "to": "A", "amount_paise": 50},
        ],
        [
            {"payment_id": "P1", "from": "A", "to": "B", "amount_paise": 0},
        ],
        [
            {"payment_id": "P1", "from": "A", "to": "A", "amount_paise": 100},
        ],
        [
            {"payment_id": "P1", "from": "A", "to": "B", "amount_paise": True},
        ],
    ],
)
def test_invalid_payments_are_rejected(payments):
    with pytest.raises(ValueError):
        build_net_balance_changes(payments)
