import json
import os

import boto3

from common.util import maybe_chaos, now_iso


ddb = boto3.client("dynamodb")

PAY = os.environ["PAYMENTS_TABLE"]
ACC = os.environ["ACCOUNTS_TABLE"]
LED = os.environ["LEDGER_TABLE"]


def S(value):
    return {"S": value}


def N(value):
    return {"N": str(value)}


def post_payment(payment_id):
    if os.environ.get("LIQUIDITY_BATCH_MODE", "0") == "1":
        raise RuntimeError(
            "Immediate posting disabled in liquidity batch mode"
        )

    payment = ddb.get_item(
        TableName=PAY,
        Key={"payment_id": S(payment_id)},
        ConsistentRead=True,
    ).get("Item")

    if payment is None:
        raise ValueError(f"unknown payment {payment_id}")

    if payment["status"]["S"] != "PENDING":
        return "already_processed"

    source = payment["from_account"]["S"]
    destination = payment["to_account"]["S"]
    amount = int(payment["amount_paise"]["N"])
    timestamp = now_iso()

    maybe_chaos("before_transaction")

    ddb.transact_write_items(
        TransactItems=[
            {
                "Put": {
                    "TableName": LED,
                    "Item": {
                        "account_id": S(source),
                        "entry_id": S(f"{timestamp}#{payment_id}#D"),
                        "payment_id": S(payment_id),
                        "entry_type": S("DEBIT"),
                        "amount_paise": N(amount),
                    },
                    "ConditionExpression": "attribute_not_exists(entry_id)",
                }
            },
            {
                "Put": {
                    "TableName": LED,
                    "Item": {
                        "account_id": S(destination),
                        "entry_id": S(f"{timestamp}#{payment_id}#C"),
                        "payment_id": S(payment_id),
                        "entry_type": S("CREDIT"),
                        "amount_paise": N(amount),
                    },
                    "ConditionExpression": "attribute_not_exists(entry_id)",
                }
            },
            {
                "Update": {
                    "TableName": ACC,
                    "Key": {"account_id": S(source)},
                    "UpdateExpression": "ADD balance_paise :amount",
                    "ConditionExpression": (
                        "attribute_exists(account_id) "
                        "AND balance_paise >= :required"
                    ),
                    "ExpressionAttributeValues": {
                        ":amount": N(-amount),
                        ":required": N(amount),
                    },
                }
            },
            {
                "Update": {
                    "TableName": ACC,
                    "Key": {"account_id": S(destination)},
                    "UpdateExpression": "ADD balance_paise :amount",
                    "ExpressionAttributeValues": {
                        ":amount": N(amount)
                    },
                }
            },
            {
                "Update": {
                    "TableName": PAY,
                    "Key": {"payment_id": S(payment_id)},
                    "UpdateExpression": "SET #st = :posted, posted_at = :ts",
                    "ConditionExpression": "#st = :pending",
                    "ExpressionAttributeNames": {"#st": "status"},
                    "ExpressionAttributeValues": {
                        ":posted": S("POSTED"),
                        ":pending": S("PENDING"),
                        ":ts": S(timestamp),
                    },
                }
            },
        ]
    )

    return "posted"


def handler(event, context):
    failures = []

    for record in event["Records"]:
        try:
            payment_id = json.loads(record["body"])["payment_id"]
            post_payment(payment_id)

        except ddb.exceptions.TransactionCanceledException as exc:
            reasons = exc.response.get("CancellationReasons", [])

            if (
                len(reasons) == 5
                and reasons[4].get("Code") == "ConditionalCheckFailed"
            ):
                continue

            print("transaction cancelled", reasons)
            failures.append({"itemIdentifier": record["messageId"]})

        except Exception as exc:
            print("failed", record["messageId"], repr(exc))
            failures.append({"itemIdentifier": record["messageId"]})

    return {"batchItemFailures": failures}
