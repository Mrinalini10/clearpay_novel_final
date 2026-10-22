"""Read account balances for liquidity-aware settlement planning."""


def read_account_balances(client, table_name, payments):
    """Read participant balances from DynamoDB without changing them."""
    if not isinstance(table_name, str) or not table_name.strip():
        raise ValueError("Accounts table name is required")

    if not isinstance(payments, list):
        raise ValueError("Payments must be a list")

    participants = set()

    for payment in payments:
        if not isinstance(payment, dict):
            raise ValueError("Each payment must be an object")

        for field in ("from", "to"):
            account_id = payment.get(field)

            if not isinstance(account_id, str) or not account_id:
                raise ValueError("Invalid account ID")

            participants.add(account_id)

    balances = {}

    for account_id in sorted(participants):
        response = client.get_item(
            TableName=table_name,
            Key={"account_id": {"S": account_id}},
            ConsistentRead=True,
        )

        item = response.get("Item")

        if not item or "balance_paise" not in item:
            raise ValueError(f"Missing balance for account {account_id}")

        raw_balance = item["balance_paise"].get("N")

        try:
            if raw_balance is None:
                raise ValueError("Missing numeric balance")

            balance = int(raw_balance)

            if str(balance) != raw_balance or balance < 0:
                raise ValueError("Invalid numeric balance")
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid balance for account {account_id}"
            ) from exc

        balances[account_id] = balance

    return balances
