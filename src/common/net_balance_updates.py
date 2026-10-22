"""Build DynamoDB account updates for net settlement."""

from common.net_settlement import build_net_balance_changes


def build_net_balance_updates(selected_payments, accounts_table):
    """Build account updates without executing them."""
    if not isinstance(accounts_table, str) or not accounts_table.strip():
        raise ValueError("A DynamoDB accounts table name is required")

    changes = build_net_balance_changes(selected_payments)
    operations = []

    for account_id, delta in sorted(changes.items()):
        if delta == 0:
            continue

        update = {
            "TableName": accounts_table,
            "Key": {"account_id": {"S": account_id}},
            "UpdateExpression": "ADD balance_paise :delta",
            "ConditionExpression": "attribute_exists(account_id)",
            "ExpressionAttributeValues": {
                ":delta": {"N": str(delta)},
            },
        }

        if delta < 0:
            update["ConditionExpression"] += (
                " AND balance_paise >= :required"
            )
            update["ExpressionAttributeValues"][":required"] = {
                "N": str(-delta)
            }

        operations.append({"Update": update})

    return operations
