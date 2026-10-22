import json
import os

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from common.util import parse_iso, to_iso


payments = boto3.resource("dynamodb").Table(os.environ["PAYMENTS_TABLE"])
s3 = boto3.client("s3")
BUCKET = os.environ["DATA_BUCKET"]


def handler(event, context):
    start = parse_iso(event["start_time"])
    cutoff = to_iso(start)
    window_id = "W-" + start.strftime("%Y%m%dT%H%M%S")
    key = f"windows/{window_id}/payments.json"

    # Reuse a frozen window if this step is retried.
    try:
        obj = s3.get_object(Bucket=BUCKET, Key=key)
        existing = json.loads(obj["Body"].read())
        return {
            "window_id": window_id,
            "s3_key": key,
            "count": len(existing),
            "cutoff": cutoff,
        }
    except ClientError as exc:
        if exc.response["Error"]["Code"] not in ("NoSuchKey", "404"):
            raise

    rows = []
    kwargs = {
        "IndexName": "StatusPostedIndex",
        "KeyConditionExpression": (
            Key("status").eq("POSTED") & Key("posted_at").lte(cutoff)
        ),
    }

    while True:
        result = payments.query(**kwargs)

        for item in result["Items"]:
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

    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=json.dumps(rows).encode(),
        ContentType="application/json",
    )

    return {
        "window_id": window_id,
        "s3_key": key,
        "count": len(rows),
        "cutoff": cutoff,
    }
