"""Prepare a liquidity-approved settlement without writing to AWS."""

from common.liquidity_adapter import build_settlement_plan
from common.settlement_transaction import build_settlement_transaction


def prepare_settlement(
    payments,
    account_balances,
    window_id,
    accounts_table,
    payments_table,
    ledger_table,
    settled_at,
):
    """Optimize payments and validate the settlement transaction."""
    if not isinstance(payments, list):
        raise ValueError("Payments must be a list")

    if not isinstance(account_balances, dict):
        raise ValueError("Account balances must be a dictionary")

    participants = {
        account
        for payment in payments
        for account in (payment["from"], payment["to"])
    }

    for account in participants:
        balance = account_balances.get(account)

        if type(balance) is not int or balance < 0:
            raise ValueError(
                f"Missing or invalid available balance for {account}"
            )

    plan = build_settlement_plan(payments, account_balances)

    selected = plan["selected_payments"]
    deferred = plan["deferred_payments"]

    original_ids = [payment["payment_id"] for payment in payments]
    selected_ids = [payment["payment_id"] for payment in selected]
    deferred_ids = [payment["payment_id"] for payment in deferred]

    if (
        len(original_ids) != len(set(original_ids))
        or len(selected_ids) != len(set(selected_ids))
        or len(deferred_ids) != len(set(deferred_ids))
        or set(selected_ids) & set(deferred_ids)
        or set(selected_ids) | set(deferred_ids) != set(original_ids)
    ):
        raise ValueError("Optimizer decision does not match payment batch")

    operations = build_settlement_transaction(
        selected_payments=selected,
        window_id=window_id,
        accounts_table=accounts_table,
        payments_table=payments_table,
        ledger_table=ledger_table,
        settled_at=settled_at,
    )

    return {
        "selected_ids": selected_ids,
        "deferred_ids": deferred_ids,
        "metrics": plan["metrics"],
        "settlement_operations": operations,
    }


def prepare_settlement_from_dynamodb(
    client,
    payments,
    window_id,
    accounts_table,
    payments_table,
    ledger_table,
    settled_at,
):
    """Read account liquidity and prepare settlement without writing."""
    from common.account_liquidity import read_account_balances

    balances = read_account_balances(
        client=client,
        table_name=accounts_table,
        payments=payments,
    )

    return prepare_settlement(
        payments=payments,
        account_balances=balances,
        window_id=window_id,
        accounts_table=accounts_table,
        payments_table=payments_table,
        ledger_table=ledger_table,
        settled_at=settled_at,
    )
