import json
import os

import boto3
from botocore.exceptions import ClientError

from common.util import authorized, now_iso, request_hash, response
from common.validation import validate


table = boto3.resource("dynamodb").Table(os.environ["PAYMENTS_TABLE"])
sqs = boto3.client("sqs")
QUEUE_URL = os.environ["QUEUE_URL"]
BATCH_MODE = os.environ.get("LIQUIDITY_BATCH_MODE", "0") == "1"

PUBLIC_FIELDS = (
    "payment_id",
    "from_account",
    "to_account",
    "amount_paise",
    "currency",
    "status",
    "created_at",
    "posted_at",
    "window_id",
)


def public_view(item):
    return {key: item[key] for key in PUBLIC_FIELDS if key in item}


def enqueue(payment_id):
    sqs.send_message(
        QueueUrl=QUEUE_URL,
        MessageBody=json.dumps({"payment_id": payment_id}),
    )


def handler(event, context):
    headers = {
        key.lower(): value
        for key, value in (event.get("headers") or {}).items()
    }

    if not authorized(headers):
        return response(401, {"error": "unauthorized"})

    key = headers.get("idempotency-key")
    if not key or not (8 <= len(key) <= 64):
        return response(
            400,
            {"error": "Idempotency-Key header required (8-64 chars)"},
        )

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return response(400, {"error": "invalid JSON"})

    clean, error = validate(body)
    if error:
        return response(400, {"error": error})

    payload_hash = request_hash(clean)
    item = {
        "payment_id": key,
        "from_account": clean["from_account"],
        "to_account": clean["to_account"],
        "amount_paise": clean["amount_paise"],
        "currency": clean["currency"],
        "status": "PENDING",
        "request_hash": payload_hash,
        "created_at": now_iso(),
    }

    try:
        table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(payment_id)",
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise

        existing = table.get_item(
            Key={"payment_id": key},
            ConsistentRead=True,
        ).get("Item")

        if existing is None:
            raise RuntimeError(
                "Payment disappeared after an idempotency conflict"
            )

        if existing["request_hash"] != payload_hash:
            return response(
                422,
                {"error": "Idempotency-Key reused with a different payload"},
            )

        if existing["status"] == "PENDING" and not BATCH_MODE:
            enqueue(key)

        return response(
            200,
            public_view(existing),
            {"Idempotent-Replay": "true"},
        )

    if not BATCH_MODE:
        enqueue(key)
    return response(202, public_view(item))
