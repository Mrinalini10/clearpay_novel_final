"""AWS Lambda entry point for liquidity-aware pending-payment settlement."""

import json
import os
from datetime import datetime, timezone

import boto3

from common.settlement_executor import execute_settlement_window
from common.settlement_plan_store import plan_key


def handler(event, context):
    """Settle a frozen pending batch using a persistent approved plan."""
    if os.environ.get("LIQUIDITY_BATCH_MODE") != "1":
        raise RuntimeError("Liquidity batch mode is not enabled")

    if not isinstance(event, dict):
        raise ValueError("Event must be a JSON object")

    window_id = event["window_id"]
    plan_key(window_id)

    expected_key = f"windows/{window_id}/pending.json"
    if event.get("s3_key") != expected_key:
        raise ValueError("Invalid frozen pending-batch S3 key")

    bucket = os.environ["DATA_BUCKET"]
    accounts_table = os.environ["ACCOUNTS_TABLE"]
    payments_table = os.environ["PAYMENTS_TABLE"]
    ledger_table = os.environ["LEDGER_TABLE"]

    s3 = boto3.client("s3")
    client = boto3.client("dynamodb")

    response = s3.get_object(Bucket=bucket, Key=expected_key)
    payments = json.loads(response["Body"].read())

    if not isinstance(payments, list):
        raise ValueError("Frozen payment batch must be a list")

    if "count" in event:
        expected_count = event["count"]
        if type(expected_count) is not int or expected_count != len(payments):
            raise ValueError("Frozen payment count mismatch")

    settled_at = datetime.now(timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )

    result = execute_settlement_window(
        client=client,
        s3=s3,
        bucket=bucket,
        payments=payments,
        window_id=window_id,
        accounts_table=accounts_table,
        payments_table=payments_table,
        ledger_table=ledger_table,
        settled_at=settled_at,
    )

    # Release the window lease so future executions can proceed.
    settlements_table = os.environ.get("SETTLEMENTS_TABLE", "")
    if settlements_table:
        from common.settlement_lease import release_lease
        release_lease(client, settlements_table, window_id)

    return {"window_id": window_id, **result}
