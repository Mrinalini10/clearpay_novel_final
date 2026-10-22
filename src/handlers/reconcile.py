import csv
import io
import json
import os
import urllib.parse

import boto3
from boto3.dynamodb.conditions import Attr

from common.recon import reconcile


s3 = boto3.client("s3")
payments = boto3.resource("dynamodb").Table(
    os.environ["PAYMENTS_TABLE"]
)


def load_ledger():
    # This project reconciles payment references and amounts.
    # It reads settled/posted payment records as its comparison source.
    ledger = {}
    kwargs = {
        "FilterExpression": Attr("status").is_in(["POSTED", "SETTLED"])
    }

    while True:
        result = payments.scan(**kwargs)

        for item in result["Items"]:
            ledger[item["payment_id"]] = int(item["amount_paise"])

        if "LastEvaluatedKey" not in result:
            break

        kwargs["ExclusiveStartKey"] = result["LastEvaluatedKey"]

    return ledger


def handler(event, context):
    ledger = load_ledger()

    for record in event["Records"]:
        bucket = record["s3"]["bucket"]["name"]
        key = urllib.parse.unquote_plus(
            record["s3"]["object"]["key"]
        )

        obj = s3.get_object(Bucket=bucket, Key=key)
        text = obj["Body"].read().decode("utf-8")
        rows = list(csv.DictReader(io.StringIO(text)))

        result = reconcile(ledger, rows)
        name = os.path.splitext(os.path.basename(key))[0]

        report = {"statement": key, **result}

        s3.put_object(
            Bucket=bucket,
            Key=f"reports/{name}.json",
            Body=json.dumps(report).encode(),
            ContentType="application/json",
        )

        buffer = io.StringIO()
        writer = csv.DictWriter(
            buffer,
            fieldnames=["type", "reference", "detail"],
        )
        writer.writeheader()
        writer.writerows(result["exceptions"])

        s3.put_object(
            Bucket=bucket,
            Key=f"reports/{name}_exceptions.csv",
            Body=buffer.getvalue().encode(),
            ContentType="text/csv",
        )

        print(json.dumps(result["summary"]))
