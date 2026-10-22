"""DynamoDB-based window lease for mutual exclusion of settlement windows.

Prevents two concurrent Step Functions executions from processing
the same payment batch.  A lease is a DynamoDB item with a TTL;
if the worker crashes, the lease expires automatically and a retry
can proceed.
"""

import time

from botocore.exceptions import ClientError


def acquire_lease(client, table_name, window_id, ttl_seconds=900):
    """Try to claim a settlement window exclusively.

    Returns True if the lease was acquired (or already held by this
    window), False if another window is already running.

    The lease item uses a TTL attribute so stale leases from crashed
    workers expire automatically without manual cleanup.
    """
    if not isinstance(window_id, str) or not window_id:
        raise ValueError("window_id is required")

    if not isinstance(ttl_seconds, int) or ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be a positive integer")

    expiry = int(time.time()) + ttl_seconds

    try:
        client.put_item(
            TableName=table_name,
            Item={
                "window_id": {"S": f"lease#{window_id}"},
                "status": {"S": "ACTIVE"},
                "expires_at": {"N": str(expiry)},
            },
            ConditionExpression="attribute_not_exists(window_id)",
        )
        return True
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code != "ConditionalCheckFailedException":
            raise

        # Lease already exists — check if it's expired.
        response = client.get_item(
            TableName=table_name,
            Key={"window_id": {"S": f"lease#{window_id}"}},
        )
        item = response.get("Item")

        if item is None:
            # Raced and got deleted; try once more.
            try:
                client.put_item(
                    TableName=table_name,
                    Item={
                        "window_id": {"S": f"lease#{window_id}"},
                        "status": {"S": "ACTIVE"},
                        "expires_at": {"N": str(expiry)},
                    },
                    ConditionExpression="attribute_not_exists(window_id)",
                )
                return True
            except ClientError as exc2:
                if exc2.response.get("Error", {}).get("Code") == (
                    "ConditionalCheckFailedException"
                ):
                    return False
                raise

        expires_at = int(item.get("expires_at", {}).get("N", "0"))
        if expires_at > int(time.time()):
            return False

        # Lease is expired — reclaim it.
        try:
            client.put_item(
                TableName=table_name,
                Item={
                    "window_id": {"S": f"lease#{window_id}"},
                    "status": {"S": "ACTIVE"},
                    "expires_at": {"N": str(expiry)},
                },
                ConditionExpression=(
                    "attribute_exists(window_id) "
                    "AND expires_at <= :now"
                ),
                ExpressionAttributeValues={":now": {"N": str(int(time.time()))}},
            )
            return True
        except ClientError as exc2:
            if exc2.response.get("Error", {}).get("Code") == (
                "ConditionalCheckFailedException"
            ):
                return False
            raise


def release_lease(client, table_name, window_id):
    """Release the lease after settlement completes."""
    if not isinstance(window_id, str) or not window_id:
        raise ValueError("window_id is required")

    client.delete_item(
        TableName=table_name,
        Key={"window_id": {"S": f"lease#{window_id}"}},
    )
