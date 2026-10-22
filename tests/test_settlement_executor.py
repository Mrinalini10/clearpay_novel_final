"""Tests for persistent settlement decisions and execution failures."""

from unittest.mock import MagicMock

import pytest

import common.settlement_executor as executor
from common.settlement_plan_store import payment_batch_fingerprint


PAYMENTS = [
    {"payment_id": "P1", "from": "A", "to": "B", "amount_paise": 500},
    {"payment_id": "P2", "from": "B", "to": "A", "amount_paise": 500},
]


def approved_plan(selected=None, deferred=None, fingerprint=None):
    return {
        "window_id": "W-001",
        "batch_fingerprint": (
            fingerprint
            if fingerprint is not None
            else payment_batch_fingerprint(PAYMENTS)
        ),
        "selected_ids": ["P1", "P2"] if selected is None else selected,
        "deferred_ids": [] if deferred is None else deferred,
        "metrics": {},
        "settled_at": "2026-10-22T12:00:00Z",
    }


def run_window(client, s3=None):
    return executor.execute_settlement_window(
        client=client,
        s3=s3 or MagicMock(),
        bucket="test-bucket",
        payments=PAYMENTS,
        window_id="W-001",
        accounts_table="test-accounts",
        payments_table="test-payments",
        ledger_table="test-ledger",
        settled_at="2026-10-22T13:00:00Z",
    )


def test_reservation_happens_before_settlement(monkeypatch):
    events = []
    client = MagicMock()

    monkeypatch.setattr(
        executor, "read_approved_plan",
        lambda *args: approved_plan(),
    )

    def reserve(**kwargs):
        events.append("reserve")

    def settle(**kwargs):
        events.append("settle")

    monkeypatch.setattr(executor, "reserve_batch_atomically", reserve)
    client.transact_write_items.side_effect = settle

    result = run_window(client)

    assert events == ["reserve", "settle"]
    assert result["selected_ids"] == ["P1", "P2"]


def test_failed_reservation_prevents_settlement(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(
        executor, "read_approved_plan",
        lambda *args: approved_plan(),
    )

    def fail_reservation(**kwargs):
        raise RuntimeError("Reservation failed")

    monkeypatch.setattr(
        executor, "reserve_batch_atomically", fail_reservation
    )

    with pytest.raises(RuntimeError, match="Reservation failed"):
        run_window(client)

    client.transact_write_items.assert_not_called()


def test_failed_settlement_is_not_reported_as_success(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(
        executor, "read_approved_plan",
        lambda *args: approved_plan(),
    )
    monkeypatch.setattr(
        executor, "reserve_batch_atomically", MagicMock()
    )
    client.transact_write_items.side_effect = RuntimeError(
        "Settlement failed"
    )

    with pytest.raises(RuntimeError, match="Settlement failed"):
        run_window(client)


def test_retry_preserves_original_selection(monkeypatch):
    client = MagicMock()
    original = approved_plan(selected=["P1"], deferred=["P2"])

    monkeypatch.setattr(
        executor,
        "read_approved_plan",
        MagicMock(side_effect=[None, original]),
    )

    planner = MagicMock(return_value={
        "selected_ids": ["P1"],
        "deferred_ids": ["P2"],
        "metrics": {},
        "settlement_operations": [],
    })
    monkeypatch.setattr(
        executor, "prepare_settlement_from_dynamodb", planner
    )

    save = MagicMock(return_value=original)
    monkeypatch.setattr(executor, "save_approved_plan", save)
    monkeypatch.setattr(
        executor, "reserve_batch_atomically", MagicMock()
    )

    client.transact_write_items.side_effect = [
        RuntimeError("Settlement failed"),
        None,
    ]

    with pytest.raises(RuntimeError, match="Settlement failed"):
        run_window(client)

    result = run_window(client)

    assert result["selected_ids"] == ["P1"]
    assert result["deferred_ids"] == ["P2"]
    planner.assert_called_once()
    save.assert_called_once()
    assert client.transact_write_items.call_count == 2


def test_changed_frozen_batch_is_rejected(monkeypatch):
    client = MagicMock()
    plan = approved_plan(fingerprint="incorrect-fingerprint")

    monkeypatch.setattr(
        executor, "read_approved_plan", lambda *args: plan
    )
    reserve = MagicMock()
    monkeypatch.setattr(executor, "reserve_batch_atomically", reserve)

    with pytest.raises(ValueError, match="does not match"):
        run_window(client)

    reserve.assert_not_called()
    client.transact_write_items.assert_not_called()


def test_invalid_stored_selection_is_rejected(monkeypatch):
    client = MagicMock()
    plan = approved_plan(selected=["P1", "P1"], deferred=["P2"])

    monkeypatch.setattr(
        executor, "read_approved_plan", lambda *args: plan
    )
    reserve = MagicMock()
    monkeypatch.setattr(executor, "reserve_batch_atomically", reserve)

    with pytest.raises(ValueError, match="Invalid stored payment selection"):
        run_window(client)

    reserve.assert_not_called()
    client.transact_write_items.assert_not_called()


from botocore.exceptions import ClientError


def test_retry_recognizes_already_committed_settlement(monkeypatch):
    client = MagicMock()

    monkeypatch.setattr(
        executor,
        "read_approved_plan",
        lambda *args: approved_plan(),
    )

    client.get_item.side_effect = [
        {
            "Item": {
                "payment_id": {"S": payment["payment_id"]},
                "status": {"S": "SETTLED"},
                "window_id": {"S": "W-001"},
                "settled_at": {"S": "2026-10-22T12:00:00Z"},
                "from_account": {"S": payment["from"]},
                "to_account": {"S": payment["to"]},
                "amount_paise": {"N": str(payment["amount_paise"])},
            }
        }
        for payment in PAYMENTS
    ]

    reservation_error = ClientError(
        {
            "Error": {
                "Code": "TransactionCanceledException",
                "Message": "Payment already settled",
            }
        },
        "TransactWriteItems",
    )

    monkeypatch.setattr(
        executor,
        "reserve_batch_atomically",
        MagicMock(side_effect=reservation_error),
    )

    result = run_window(client)

    assert result["selected_ids"] == ["P1", "P2"]
    assert client.get_item.call_count == 2
    assert all(
        call.kwargs["ConsistentRead"] is True
        for call in client.get_item.call_args_list
    )
    client.transact_write_items.assert_not_called()


def test_retry_rejects_incorrect_settlement_window(monkeypatch):
    client = MagicMock()

    monkeypatch.setattr(
        executor,
        "read_approved_plan",
        lambda *args: approved_plan(),
    )

    client.get_item.return_value = {
        "Item": {
            "payment_id": {"S": "P1"},
            "status": {"S": "SETTLED"},
            "window_id": {"S": "W-DIFFERENT"},
            "settled_at": {"S": "2026-10-22T12:00:00Z"},
            "from_account": {"S": "A"},
            "to_account": {"S": "B"},
            "amount_paise": {"N": "500"},
        }
    }

    reservation_error = ClientError(
        {
            "Error": {
                "Code": "TransactionCanceledException",
                "Message": "Reservation conflict",
            }
        },
        "TransactWriteItems",
    )

    monkeypatch.setattr(
        executor,
        "reserve_batch_atomically",
        MagicMock(side_effect=reservation_error),
    )

    with pytest.raises(ClientError):
        run_window(client)

    client.transact_write_items.assert_not_called()


def test_unrelated_reservation_error_is_not_hidden(monkeypatch):
    client = MagicMock()

    monkeypatch.setattr(
        executor,
        "read_approved_plan",
        lambda *args: approved_plan(),
    )

    reservation_error = ClientError(
        {
            "Error": {
                "Code": "AccessDeniedException",
                "Message": "Access denied",
            }
        },
        "TransactWriteItems",
    )

    monkeypatch.setattr(
        executor,
        "reserve_batch_atomically",
        MagicMock(side_effect=reservation_error),
    )

    with pytest.raises(ClientError):
        run_window(client)

    client.get_item.assert_not_called()
    client.transact_write_items.assert_not_called()


def test_settlement_error_after_commit_is_recognized(monkeypatch):
    client = MagicMock()

    monkeypatch.setattr(
        executor,
        "read_approved_plan",
        lambda *args: approved_plan(),
    )
    monkeypatch.setattr(
        executor,
        "reserve_batch_atomically",
        MagicMock(),
    )

    client.transact_write_items.side_effect = ClientError(
        {
            "Error": {
                "Code": "TransactionCanceledException",
                "Message": "Ambiguous settlement response",
            }
        },
        "TransactWriteItems",
    )

    client.get_item.side_effect = [
        {
            "Item": {
                "payment_id": {"S": payment["payment_id"]},
                "status": {"S": "SETTLED"},
                "window_id": {"S": "W-001"},
                "settled_at": {"S": "2026-10-22T12:00:00Z"},
                "from_account": {"S": payment["from"]},
                "to_account": {"S": payment["to"]},
                "amount_paise": {"N": str(payment["amount_paise"])},
            }
        }
        for payment in PAYMENTS
    ]

    result = run_window(client)

    assert result["selected_ids"] == ["P1", "P2"]
    assert client.get_item.call_count == 2


def test_failed_settlement_without_commit_raises(monkeypatch):
    client = MagicMock()

    monkeypatch.setattr(
        executor,
        "read_approved_plan",
        lambda *args: approved_plan(),
    )
    monkeypatch.setattr(
        executor,
        "reserve_batch_atomically",
        MagicMock(),
    )

    client.transact_write_items.side_effect = ClientError(
        {
            "Error": {
                "Code": "TransactionCanceledException",
                "Message": "Settlement did not commit",
            }
        },
        "TransactWriteItems",
    )

    client.get_item.return_value = {
        "Item": {
            "status": {"S": "RESERVED"},
            "window_id": {"S": "W-001"},
        }
    }

    with pytest.raises(ClientError):
        run_window(client)

    client.get_item.assert_called()


def test_settlement_access_denied_is_not_hidden(monkeypatch):
    client = MagicMock()

    monkeypatch.setattr(
        executor,
        "read_approved_plan",
        lambda *args: approved_plan(),
    )
    monkeypatch.setattr(
        executor,
        "reserve_batch_atomically",
        MagicMock(),
    )

    client.transact_write_items.side_effect = ClientError(
        {
            "Error": {
                "Code": "AccessDeniedException",
                "Message": "Access denied",
            }
        },
        "TransactWriteItems",
    )

    with pytest.raises(ClientError):
        run_window(client)

    client.get_item.assert_not_called()
