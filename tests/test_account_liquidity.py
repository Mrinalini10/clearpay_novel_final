"""Tests for reading account liquidity without contacting AWS."""

from unittest.mock import MagicMock

import pytest

from common.account_liquidity import read_account_balances


PAYMENTS = [
    {"from": "A", "to": "B"},
    {"from": "B", "to": "A"},
]


def test_reads_each_account_once_with_consistent_reads():
    client = MagicMock()
    client.get_item.side_effect = [
        {"Item": {"balance_paise": {"N": "1000"}}},
        {"Item": {"balance_paise": {"N": "500"}}},
    ]

    balances = read_account_balances(
        client, "test-accounts", PAYMENTS
    )

    assert balances == {"A": 1000, "B": 500}
    assert client.get_item.call_count == 2

    for call in client.get_item.call_args_list:
        assert call.kwargs["TableName"] == "test-accounts"
        assert call.kwargs["ConsistentRead"] is True


def test_missing_account_is_rejected():
    client = MagicMock()
    client.get_item.return_value = {}

    with pytest.raises(ValueError, match="Missing balance"):
        read_account_balances(
            client, "test-accounts", PAYMENTS
        )


@pytest.mark.parametrize("raw_balance", ["-100", "abc", "01"])
def test_invalid_balance_is_rejected(raw_balance):
    client = MagicMock()
    client.get_item.return_value = {
        "Item": {"balance_paise": {"N": raw_balance}}
    }

    with pytest.raises(ValueError, match="Invalid balance"):
        read_account_balances(
            client, "test-accounts", PAYMENTS
        )


def test_empty_payment_batch_requires_no_reads():
    client = MagicMock()

    assert read_account_balances(
        client, "test-accounts", []
    ) == {}

    client.get_item.assert_not_called()
