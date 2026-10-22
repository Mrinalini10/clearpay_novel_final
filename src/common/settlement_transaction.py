"""Build an atomic net-settlement transaction without executing it."""

from common.net_balance_updates import build_net_balance_updates
from common.net_settlement import build_net_balance_changes


def build_settlement_transaction(
    selected_payments,
    window_id,
    accounts_table,
    payments_table,
    ledger_table,
    settled_at,
):
    """Build all-or-nothing DynamoDB settlement operations."""
    for value in (
        window_id, accounts_table, payments_table,
        ledger_table, settled_at,
    ):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Settlement identifiers must be nonempty strings")

    # Validate payments and calculate net changes before creating writes.
    build_net_balance_changes(selected_payments)

    operations = build_net_balance_updates(
        selected_payments, accounts_table
    )

    participants = {
        account
        for payment in selected_payments
        for account in (payment["from"], payment["to"])
    }
    updated_accounts = {
        item["Update"]["Key"]["account_id"]["S"]
        for item in operations
    }

    # Even zero-net participants must have existing account records.
    for account_id in sorted(participants - updated_accounts):
        operations.append({
            "ConditionCheck": {
                "TableName": accounts_table,
                "Key": {"account_id": {"S": account_id}},
                "ConditionExpression": "attribute_exists(account_id)",
            }
        })

    for payment in selected_payments:
        payment_id = payment["payment_id"]
        amount = str(payment["amount_paise"])

        for account_id, entry_type in (
            (payment["from"], "DEBIT"),
            (payment["to"], "CREDIT"),
        ):
            operations.append({
                "Put": {
                    "TableName": ledger_table,
                    "Item": {
                        "account_id": {"S": account_id},
                        "entry_id": {
                            "S": f"{window_id}#{payment_id}#{entry_type[0]}"
                        },
                        "payment_id": {"S": payment_id},
                        "entry_type": {"S": entry_type},
                        "amount_paise": {"N": amount},
                    },
                    "ConditionExpression": (
                        "attribute_not_exists(account_id)"
                    ),
                }
            })

        operations.append({
            "Update": {
                "TableName": payments_table,
                "Key": {"payment_id": {"S": payment_id}},
                "UpdateExpression": (
                    "SET #st = :settled, settled_at = :timestamp"
                ),
                "ConditionExpression": (
                    "#st = :reserved AND window_id = :window "
                    "AND from_account = :source "
                    "AND to_account = :destination "
                    "AND amount_paise = :amount"
                ),
                "ExpressionAttributeNames": {"#st": "status"},
                "ExpressionAttributeValues": {
                    ":reserved": {"S": "RESERVED"},
                    ":settled": {"S": "SETTLED"},
                    ":window": {"S": window_id},
                    ":timestamp": {"S": settled_at},
                    ":source": {"S": payment["from"]},
                    ":destination": {"S": payment["to"]},
                    ":amount": {"N": amount},
                },
            }
        })

    if len(operations) > 100:
        raise ValueError(
            "Settlement exceeds DynamoDB's 100-action transaction limit"
        )

    return operations
