"""Coordinate settlement using an immutable, persisted payment selection."""

from common.payment_reservation import reserve_batch_atomically
from common.settlement_preflight import prepare_settlement_from_dynamodb
from common.settlement_plan_store import (
    payment_batch_fingerprint,
    read_approved_plan,
    save_approved_plan,
)
from common.settlement_transaction import build_settlement_transaction
from botocore.exceptions import BotoCoreError, ClientError


def _already_settled(
    client, payments_table, selected_payments, window_id, settled_at
):
    """Confirm every selected payment was settled by this window."""
    if not selected_payments:
        return False

    for payment in selected_payments:
        response = client.get_item(
            TableName=payments_table,
            Key={"payment_id": {"S": payment["payment_id"]}},
            ConsistentRead=True,
        )

        item = response.get("Item") or {}
        expected = {
            "payment_id": {"S": payment["payment_id"]},
            "status": {"S": "SETTLED"},
            "window_id": {"S": window_id},
            "settled_at": {"S": settled_at},
            "from_account": {"S": payment["from"]},
            "to_account": {"S": payment["to"]},
            "amount_paise": {"N": str(payment["amount_paise"])},
        }

        if any(item.get(key) != value for key, value in expected.items()):
            return False

    return True


def execute_settlement_window(
    client,
    s3,
    bucket,
    payments,
    window_id,
    accounts_table,
    payments_table,
    ledger_table,
    settled_at,
):
    """Reuse the approved selection on retries; never silently replan."""
    if not isinstance(bucket, str) or not bucket.strip():
        raise ValueError("Plan storage bucket is required")

    fingerprint = payment_batch_fingerprint(payments)
    payment_ids = [payment["payment_id"] for payment in payments]
    by_id = {payment["payment_id"]: payment for payment in payments}

    approved = read_approved_plan(s3, bucket, window_id)

    if approved is None:
        proposal = prepare_settlement_from_dynamodb(
            client=client,
            payments=payments,
            window_id=window_id,
            accounts_table=accounts_table,
            payments_table=payments_table,
            ledger_table=ledger_table,
            settled_at=settled_at,
        )

        candidate = {
            "window_id": window_id,
            "batch_fingerprint": fingerprint,
            "selected_ids": proposal["selected_ids"],
            "deferred_ids": proposal["deferred_ids"],
            "metrics": proposal["metrics"],
            "settled_at": settled_at,
        }

        approved = save_approved_plan(
            s3, bucket, window_id, candidate
        )

    if not isinstance(approved, dict):
        raise ValueError("Invalid stored settlement plan")

    if (
        approved.get("window_id") != window_id
        or approved.get("batch_fingerprint") != fingerprint
    ):
        raise ValueError("Stored plan does not match frozen payment batch")

    selected_ids = approved.get("selected_ids")
    deferred_ids = approved.get("deferred_ids")

    if (
        not isinstance(selected_ids, list)
        or not isinstance(deferred_ids, list)
        or any(
            not isinstance(value, str)
            for value in selected_ids + deferred_ids
        )
        or len(selected_ids) != len(set(selected_ids))
        or len(deferred_ids) != len(set(deferred_ids))
        or set(selected_ids) & set(deferred_ids)
        or set(selected_ids) | set(deferred_ids) != set(payment_ids)
    ):
        raise ValueError("Invalid stored payment selection")

    saved_timestamp = approved.get("settled_at")
    if not isinstance(saved_timestamp, str) or not saved_timestamp.strip():
        raise ValueError("Invalid stored settlement timestamp")

    metrics = approved.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError("Invalid stored settlement metrics")

    selected_payments = [by_id[payment_id] for payment_id in selected_ids]

    operations = build_settlement_transaction(
        selected_payments=selected_payments,
        window_id=window_id,
        accounts_table=accounts_table,
        payments_table=payments_table,
        ledger_table=ledger_table,
        settled_at=saved_timestamp,
    )

    if selected_ids:
        try:
            reserve_batch_atomically(
                client=client,
                table_name=payments_table,
                window_id=window_id,
                frozen_payments=payments,
                decision={
                    "selected_ids": selected_ids,
                    "deferred_ids": deferred_ids,
                },
            )
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")

            if code != "TransactionCanceledException":
                raise

            if not _already_settled(
                client,
                payments_table,
                selected_payments,
                window_id,
                saved_timestamp,
            ):
                raise
        else:
            try:
                client.transact_write_items(TransactItems=operations)
            except (ClientError, BotoCoreError) as exc:
                if isinstance(exc, ClientError):
                    code = exc.response.get("Error", {}).get("Code")
                    if code not in (
                        "TransactionCanceledException",
                        "InternalServerError",
                    ):
                        raise

                # A transaction may have committed despite an ambiguous
                # response. Confirm every selected payment before accepting
                # the operation as successful.
                if not _already_settled(
                    client,
                    payments_table,
                    selected_payments,
                    window_id,
                    saved_timestamp,
                ):
                    raise

    return {
        "selected_ids": selected_ids,
        "deferred_ids": deferred_ids,
        "metrics": metrics,
    }
