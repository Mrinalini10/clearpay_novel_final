"""Atomic payment reservations for settlement windows."""

from botocore.exceptions import ClientError


def reserve_payment(table, payment_id, window_id):
    """Reserve a pending payment for one settlement window.

    Returns True if reserved, False if another operation already
    changed or reserved the payment.
    """
    if not payment_id or not window_id:
        raise ValueError("payment_id and window_id are required")

    try:
        table.update_item(
            Key={"payment_id": payment_id},
            UpdateExpression="SET #st = :reserved, window_id = :window",
            ConditionExpression=(
                "attribute_exists(payment_id) "
                "AND ((#st = :pending "
                "AND attribute_not_exists(window_id)) "
                "OR (#st = :reserved AND window_id = :window))"
            ),
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":pending": "PENDING",
                ":reserved": "RESERVED",
                ":window": window_id,
            },
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == (
            "ConditionalCheckFailedException"
        ):
            return False
        raise

    return True


class ReservationConflict(RuntimeError):
    """A payment could not be claimed by this settlement window."""


def reserve_selected_batch(table, window_id, frozen_payments, decision):
    """Reserve selected payments only; never reserve deferred payments."""
    batch_ids = [payment["payment_id"] for payment in frozen_payments]
    selected = list(decision["selected_ids"])
    deferred = list(decision["deferred_ids"])

    if len(batch_ids) != len(set(batch_ids)):
        raise ValueError("Frozen batch contains duplicate payment IDs")

    if len(selected) != len(set(selected)):
        raise ValueError("Selected payment IDs contain duplicates")

    if len(deferred) != len(set(deferred)):
        raise ValueError("Deferred payment IDs contain duplicates")

    if set(selected) & set(deferred):
        raise ValueError("A payment cannot be both selected and deferred")

    if set(selected) | set(deferred) != set(batch_ids):
        raise ValueError("Settlement decision does not match frozen batch")

    if not window_id:
        raise ValueError("window_id is required")

    for payment_id in selected:
        if not reserve_payment(table, payment_id, window_id):
            raise ReservationConflict(
                f"Could not reserve payment {payment_id} for {window_id}"
            )

    return selected


def reserve_batch_atomically(
    client, table_name, window_id, frozen_payments, decision
):
    """Atomically reserve up to 100 optimizer-selected payments."""
    if not isinstance(table_name, str) or not table_name.strip():
        raise ValueError("A DynamoDB payments table name is required")

    if not isinstance(window_id, str) or not window_id.strip():
        raise ValueError("window_id is required")

    batch_ids = [payment["payment_id"] for payment in frozen_payments]
    selected = list(decision["selected_ids"])
    deferred = list(decision["deferred_ids"])

    all_ids = batch_ids + selected + deferred
    if any(not isinstance(value, str) or not value for value in all_ids):
        raise ValueError("Payment IDs must be nonempty strings")

    if (
        len(batch_ids) != len(set(batch_ids))
        or len(selected) != len(set(selected))
        or len(deferred) != len(set(deferred))
        or set(selected) & set(deferred)
        or set(selected) | set(deferred) != set(batch_ids)
    ):
        raise ValueError("Invalid settlement decision or frozen batch")

    if len(selected) > 100:
        raise ValueError("Atomic reservation supports at most 100 payments")

    if not selected:
        return []

    operations = []
    for payment_id in selected:
        operations.append({
            "Update": {
                "TableName": table_name,
                "Key": {"payment_id": {"S": payment_id}},
                "UpdateExpression": (
                    "SET #st = :reserved, window_id = :window"
                ),
                "ConditionExpression": (
                    "attribute_exists(payment_id) AND "
                    "((#st = :pending AND attribute_not_exists(window_id)) "
                    "OR (#st = :reserved AND window_id = :window))"
                ),
                "ExpressionAttributeNames": {"#st": "status"},
                "ExpressionAttributeValues": {
                    ":pending": {"S": "PENDING"},
                    ":reserved": {"S": "RESERVED"},
                    ":window": {"S": window_id},
                },
            }
        })

    client.transact_write_items(TransactItems=operations)
    return selected
