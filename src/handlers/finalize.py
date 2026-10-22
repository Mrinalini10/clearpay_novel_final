import json
import os

import boto3

from botocore.exceptions import ClientError

from common.util import now_iso


ddb = boto3.client("dynamodb")
s3 = boto3.client("s3")

PAY = os.environ["PAYMENTS_TABLE"]
SET = os.environ["SETTLEMENTS_TABLE"]
BUCKET = os.environ["DATA_BUCKET"]
CHAOS_MIDWAY = os.environ.get("CHAOS_FINALIZE_MIDWAY", "0") == "1"


def chaos_once(window_id):
    """Inject one failure per window when chaos testing is enabled."""
    marker = f"windows/{window_id}/chaos_fired"

    try:
        s3.head_object(Bucket=BUCKET, Key=marker)
        return False
    except ClientError as exc:
        if exc.response["Error"]["Code"] not in (
            "404", "NoSuchKey", "NotFound"
        ):
            raise

    s3.put_object(Bucket=BUCKET, Key=marker, Body=b"1")
    return True


def settle_one(payment_id, window_id):
    ddb.update_item(
        TableName=PAY,
        Key={"payment_id": {"S": payment_id}},
        UpdateExpression="SET #st = :settled, window_id = :w",
        ConditionExpression=(
            "#st = :posted OR (#st = :settled AND window_id = :w)"
        ),
        ExpressionAttributeNames={"#st": "status"},
        ExpressionAttributeValues={
            ":settled": {"S": "SETTLED"},
            ":posted": {"S": "POSTED"},
            ":w": {"S": window_id},
        },
    )


def handler(event, context):
    window_id = event["window_id"]

    obj = s3.get_object(Bucket=BUCKET, Key=event["s3_key"])
    payments = json.loads(obj["Body"].read())

    midpoint = len(payments) // 2

    for index, payment in enumerate(payments):
        if (
            CHAOS_MIDWAY
            and index == midpoint
            and chaos_once(window_id)
        ):
            raise RuntimeError("chaos: finalize crashed midway")

        settle_one(payment["payment_id"], window_id)

    ddb.update_item(
        TableName=SET,
        Key={"window_id": {"S": window_id}},
        UpdateExpression="SET #st = :s, settled_at = :t, settled_count = :n",
        ExpressionAttributeNames={"#st": "status"},
        ExpressionAttributeValues={
            ":s": {"S": "SETTLED"},
            ":t": {"S": now_iso()},
            ":n": {"N": str(len(payments))},
        },
    )

    return {"window_id": window_id, "settled": len(payments)}
