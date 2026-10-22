import json
import os
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

from common.netting import analyze
from common.util import now_iso


s3 = boto3.client("s3")
settlements = boto3.resource("dynamodb").Table(
    os.environ["SETTLEMENTS_TABLE"]
)
BUCKET = os.environ["DATA_BUCKET"]


def handler(event, context):
    window_id = event["window_id"]

    obj = s3.get_object(Bucket=BUCKET, Key=event["s3_key"])
    payments = json.loads(obj["Body"].read())

    result = analyze(payments)

    # Optional Novel Liquidity-Saving Engine integration
    liquidity = event.get("liquidity")
    novel_results = None
    if liquidity:
        try:
            from common.topology_liquidity import (
                bounded_cycle_gridlock_repair,
                topology_hub_spoke_clearing,
            )
            novel_results = {
                "cycle_repair": bounded_cycle_gridlock_repair(payments, liquidity),
                "hub_spoke_clearing": topology_hub_spoke_clearing(payments, liquidity),
            }
        except Exception as exc:
            print(f"Novel liquidity engine warning: {exc}")

    instructions_key = f"windows/{window_id}/instructions.json"
    instructions = {
        "hub": result["hub"],
        "positions": result["positions"],
        "strategies": result["strategies"],
    }
    if novel_results:
        instructions["novel_settlement"] = novel_results

    s3.put_object(
        Bucket=BUCKET,
        Key=instructions_key,
        Body=json.dumps(instructions).encode(),
        ContentType="application/json",
    )

    item = {
        "window_id": window_id,
        "status": "NETTED",
        "created_at": now_iso(),
        "cutoff": event["cutoff"],
        "payment_count": len(payments),
        "hub": result["hub"],
        "metrics": result["metrics"],
        "instructions_key": instructions_key,
    }
    if novel_results:
        item["novel_metrics"] = {
            k: {
                "selected_count": int(v["selected_count"]),
                "settled_value_paise": Decimal(v["settled_value_paise"]),
                "settled_pct": Decimal(str(v["settled_pct"])),
                "feasible": v["feasible"],
            }
            for k, v in novel_results.items()
        }

    try:
        settlements.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(window_id)",
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise

    return {**event, "metrics": result["metrics"]}
