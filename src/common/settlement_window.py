"""Prepare pending payments for liquidity-aware settlement planning."""

from common.liquidity_adapter import build_settlement_plan


def plan_pending_window(payments, liquidity):
    """Plan a pending batch without changing payments or account balances."""
    pending = [
        {
            "payment_id": payment["payment_id"],
            "from": payment["from_account"],
            "to": payment["to_account"],
            "amount_paise": int(payment["amount_paise"]),
        }
        for payment in payments
        if payment["status"] == "PENDING"
    ]

    plan = build_settlement_plan(pending, liquidity)

    return {
        "selected_ids": [
            payment["payment_id"]
            for payment in plan["selected_payments"]
        ],
        "deferred_ids": [
            payment["payment_id"]
            for payment in plan["deferred_payments"]
        ],
        "metrics": plan["metrics"],
    }
