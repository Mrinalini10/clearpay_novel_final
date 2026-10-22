import os

import boto3

from common.util import authorized, response


table = boto3.resource("dynamodb").Table(os.environ["PAYMENTS_TABLE"])
HIDDEN = {"request_hash"}


def handler(event, context):
    headers = {
        key.lower(): value
        for key, value in (event.get("headers") or {}).items()
    }

    if not authorized(headers):
        return response(401, {"error": "unauthorized"})

    path_parameters = event.get("pathParameters") or {}
    payment_id = path_parameters.get("payment_id")

    if not payment_id:
        return response(400, {"error": "payment_id is required"})

    item = table.get_item(
        Key={"payment_id": payment_id},
        ConsistentRead=True,
    ).get("Item")

    if not item:
        return response(404, {"error": "not found"})

    return response(
        200,
        {key: value for key, value in item.items() if key not in HIDDEN},
    )
