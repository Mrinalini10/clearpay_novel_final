"""Collect pending payments for a liquidity-planning window."""

import json
import os
import re

import boto3
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

from common.util import parse_iso, to_iso


payments = boto3.resource("dynamodb").Table(os.environ["PAYMENTS_TABLE"])
s3 = boto3.client("s3")
BUCKET = os.environ["DATA_BUCKET"]

# Use the SettlementsTable for window leases (it already has window_id as key).
SETTLEMENTS_TABLE = os.environ.get("SETTLEMENTS_TABLE", "")


def read_frozen_batch(key):
    try:
        obj = s3.get_object(Bucket=BUCKET, Key=key)
        return json.loads(obj["Body"].read())
    except ClientError as exc:
        if exc.response["Error"]["Code"] not in ("NoSuchKey", "404"):
            raise
        return None


def handler(event, context):
    # The demo run ID is already embedded in each API payment ID.  Filter on
    # that ID rather than modifying the payment API or the DynamoDB schema.
    run_id = event.get("run_id")
    if not isinstance(run_id, str) or not re.fullmatch(r"[0-9a-f]{12}", run_id):
        raise ValueError("A valid 12-character demo run_id is required")

    start = parse_iso(event["start_time"])
    cutoff = to_iso(start)
    window_id = "W-" + start.strftime("%Y%m%dT%H%M%S") + "-" + run_id
    key = f"windows/{window_id}/pending.json"

    # Acquire exclusive lease so two executions can't process the same window.
    if SETTLEMENTS_TABLE:
        from common.settlement_lease import acquire_lease
        ddb_client = boto3.client("dynamodb")
        if not acquire_lease(ddb_client, SETTLEMENTS_TABLE, window_id):
            raise RuntimeError(
                f"Another settlement execution is already processing {window_id}"
            )

    frozen = read_frozen_batch(key)

    if frozen is None:
        rows = []
        kwargs = {
            "ConsistentRead": True,
            "FilterExpression": (
                Attr("status").eq("PENDING")
                & Attr("created_at").lte(cutoff)
                & Attr("payment_id").begins_with(f"DEMO-{run_id}-")
            ),
        }

        while True:
            result = payments.scan(**kwargs)

            for item in result.get("Items", []):
                rows.append({
                    "payment_id": item["payment_id"],
                    "from": item["from_account"],
                    "to": item["to_account"],
                    "amount_paise": int(item["amount_paise"]),
                    "priority": item.get("priority", 1),
                    "created_at": item.get("created_at", ""),
                    "deferral_count": item.get("deferral_count", 0),
                })

            if "LastEvaluatedKey" not in result:
                break

            kwargs["ExclusiveStartKey"] = result["LastEvaluatedKey"]

        rows.sort(key=lambda payment: payment["payment_id"])

        try:
            s3.put_object(
                Bucket=BUCKET,
                Key=key,
                Body=json.dumps(rows).encode("utf-8"),
                ContentType="application/json",
                IfNoneMatch="*",
            )
            frozen = rows
        except ClientError as exc:
            if exc.response["Error"]["Code"] not in (
                "PreconditionFailed",
                "ConditionalRequestConflict",
                "412",
                "409",
            ):
                raise
            frozen = read_frozen_batch(key)
            if frozen is None:
                raise RuntimeError("Frozen batch unavailable after write conflict")

    return {
        "window_id": window_id,
        "s3_key": key,
        "count": len(frozen),
        "cutoff": cutoff,
        "run_id": run_id,
    }
