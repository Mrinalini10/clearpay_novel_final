"""AWS Lambda entry point for liquidity-aware settlement planning."""

from common.liquidity_adapter import build_settlement_plan


def handler(event, context):
    """Calculate a settlement plan without changing payment records."""
    if not isinstance(event, dict):
        raise ValueError("Event must be a JSON object")

    return build_settlement_plan(
        payments=event["payments"],
        liquidity=event["liquidity"],
    )
