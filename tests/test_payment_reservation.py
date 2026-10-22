"""Tests for atomic settlement-window payment reservations."""

from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from common.payment_reservation import reserve_payment


def aws_error(code):
    return ClientError(
        {"Error": {"Code": code, "Message": "Test error"}},
        "UpdateItem",
    )


def test_pending_payment_can_be_reserved():
    table = MagicMock()

    result = reserve_payment(table, "P1", "W-001")

    assert result is True
    table.update_item.assert_called_once()

    arguments = table.update_item.call_args.kwargs
    assert arguments["Key"] == {"payment_id": "P1"}
    assert arguments["ExpressionAttributeValues"][":reserved"] == "RESERVED"
    assert arguments["ExpressionAttributeValues"][":window"] == "W-001"
    assert "attribute_not_exists(window_id)" in arguments["ConditionExpression"]


def test_competing_reservation_is_rejected():
    table = MagicMock()
    table.update_item.side_effect = aws_error(
        "ConditionalCheckFailedException"
    )

    assert reserve_payment(table, "P1", "W-002") is False


def test_unexpected_dynamodb_error_is_raised():
    table = MagicMock()
    table.update_item.side_effect = aws_error(
        "ProvisionedThroughputExceededException"
    )

    with pytest.raises(ClientError):
        reserve_payment(table, "P1", "W-001")


@pytest.mark.parametrize(
    "payment_id,window_id",
    [("", "W-001"), ("P1", "")],
)
def test_missing_identifiers_are_rejected(payment_id, window_id):
    table = MagicMock()

    with pytest.raises(ValueError):
        reserve_payment(table, payment_id, window_id)

    table.update_item.assert_not_called()


def test_same_window_retry_is_allowed_by_reservation_condition():
    table = MagicMock()

    assert reserve_payment(table, "P1", "W-001") is True

    arguments = table.update_item.call_args.kwargs
    condition = arguments["ConditionExpression"]
    values = arguments["ExpressionAttributeValues"]

    assert "#st = :pending" in condition
    assert "attribute_not_exists(window_id)" in condition
    assert "#st = :reserved AND window_id = :window" in condition
    assert values[":pending"] == "PENDING"
    assert values[":reserved"] == "RESERVED"
    assert values[":window"] == "W-001"


from common.payment_reservation import (
    ReservationConflict,
    reserve_selected_batch,
)


def test_only_selected_payments_are_reserved():
    table = MagicMock()
    payments = [
        {"payment_id": "P1"},
        {"payment_id": "P2"},
        {"payment_id": "P3"},
    ]
    decision = {
        "selected_ids": ["P1", "P2"],
        "deferred_ids": ["P3"],
    }

    result = reserve_selected_batch(
        table, "W-001", payments, decision
    )

    assert result == ["P1", "P2"]
    assert table.update_item.call_count == 2

    reserved_ids = [
        call.kwargs["Key"]["payment_id"]
        for call in table.update_item.call_args_list
    ]

    assert reserved_ids == ["P1", "P2"]
    assert "P3" not in reserved_ids


def test_invalid_decision_does_not_reserve_anything():
    table = MagicMock()
    payments = [
        {"payment_id": "P1"},
        {"payment_id": "P2"},
    ]
    decision = {
        "selected_ids": ["P1"],
        "deferred_ids": [],
    }

    with pytest.raises(ValueError):
        reserve_selected_batch(
            table, "W-001", payments, decision
        )

    table.update_item.assert_not_called()


def test_reservation_conflict_stops_batch_processing():
    table = MagicMock()
    table.update_item.side_effect = [
        {},
        aws_error("ConditionalCheckFailedException"),
    ]

    payments = [
        {"payment_id": "P1"},
        {"payment_id": "P2"},
        {"payment_id": "P3"},
    ]
    decision = {
        "selected_ids": ["P1", "P2", "P3"],
        "deferred_ids": [],
    }

    with pytest.raises(ReservationConflict):
        reserve_selected_batch(
            table, "W-001", payments, decision
        )

    assert table.update_item.call_count == 2


from common.payment_reservation import reserve_batch_atomically


def test_atomic_batch_reserves_only_selected_payments():
    client = MagicMock()
    payments = [
        {"payment_id": "P1"},
        {"payment_id": "P2"},
        {"payment_id": "P3"},
    ]
    decision = {
        "selected_ids": ["P1", "P2"],
        "deferred_ids": ["P3"],
    }

    result = reserve_batch_atomically(
        client, "test-payments", "W-001", payments, decision
    )

    assert result == ["P1", "P2"]
    client.transact_write_items.assert_called_once()

    operations = client.transact_write_items.call_args.kwargs[
        "TransactItems"
    ]
    assert len(operations) == 2

    reserved_ids = [
        operation["Update"]["Key"]["payment_id"]["S"]
        for operation in operations
    ]
    assert reserved_ids == ["P1", "P2"]
    assert "P3" not in reserved_ids

    for operation in operations:
        update = operation["Update"]
        assert update["TableName"] == "test-payments"
        assert update["ExpressionAttributeValues"][":window"] == {
            "S": "W-001"
        }
        assert (
            "#st = :reserved AND window_id = :window"
            in update["ConditionExpression"]
        )


def test_atomic_batch_rejects_invalid_decision_before_writing():
    client = MagicMock()

    with pytest.raises(ValueError):
        reserve_batch_atomically(
            client,
            "test-payments",
            "W-001",
            [{"payment_id": "P1"}, {"payment_id": "P2"}],
            {"selected_ids": ["P1"], "deferred_ids": []},
        )

    client.transact_write_items.assert_not_called()


def test_atomic_batch_rejects_more_than_100_selected_payments():
    client = MagicMock()
    ids = [f"P{i}" for i in range(101)]

    with pytest.raises(ValueError, match="at most 100"):
        reserve_batch_atomically(
            client,
            "test-payments",
            "W-001",
            [{"payment_id": payment_id} for payment_id in ids],
            {"selected_ids": ids, "deferred_ids": []},
        )

    client.transact_write_items.assert_not_called()


def test_atomic_batch_skips_transaction_when_nothing_selected():
    client = MagicMock()

    result = reserve_batch_atomically(
        client,
        "test-payments",
        "W-001",
        [{"payment_id": "P1"}],
        {"selected_ids": [], "deferred_ids": ["P1"]},
    )

    assert result == []
    client.transact_write_items.assert_not_called()


def test_atomic_batch_propagates_transaction_failure():
    client = MagicMock()
    client.transact_write_items.side_effect = aws_error(
        "TransactionCanceledException"
    )

    with pytest.raises(ClientError):
        reserve_batch_atomically(
            client,
            "test-payments",
            "W-001",
            [{"payment_id": "P1"}],
            {"selected_ids": ["P1"], "deferred_ids": []},
        )

    client.transact_write_items.assert_called_once()
