"""Pure, local liquidity-selection adapter for ClearPay.

This module creates a proposed settlement plan only.
It does not update balances, payment statuses, or AWS resources.

Integration note
----------------
This is the bridge between the production settlement executor
(settlement_executor.py) and the novel clearing algorithms
(topology_liquidity.py).

The adapter uses bounded_cycle_gridlock_repair as the primary
optimizer — the novel algorithm that extends the removal heuristic
with bilateral pair repair and 3-bank directed cycle recovery.
It falls back to all_or_nothing when the full batch is already
feasible (no liquidity pressure), saving execution time.
"""

from common.liquidity import (
    all_or_nothing,
    is_feasible,
)
from common.topology_liquidity import bounded_cycle_gridlock_repair


def build_settlement_plan(payments, liquidity):
    """Choose a feasible payment subset using the novel clearing algorithm."""
    payments = list(payments)
    liquidity = dict(liquidity)

    ids = [p["payment_id"] for p in payments]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate payment IDs are not allowed")

    for p in payments:
        if (
            not isinstance(p["amount_paise"], int)
            or isinstance(p["amount_paise"], bool)
            or p["amount_paise"] <= 0
        ):
            raise ValueError("Payment amounts must be positive integer paise")

    if any(
        not isinstance(value, int) or isinstance(value, bool)
        for value in liquidity.values()
    ):
        raise ValueError("Liquidity amounts must be integer paise")

    if is_feasible(payments, liquidity):
        # Full batch is feasible — no need for the optimizer.
        result = all_or_nothing(payments, liquidity)
        route = "full_batch"
    else:
        # Use the novel Bounded Cycle Gridlock Repair algorithm.
        # This extends the removal heuristic with:
        #   Phase 2: bilateral pair subset repair
        #   Phase 3: 3-bank directed cycle recovery (A→B→C→A)
        result = bounded_cycle_gridlock_repair(payments, liquidity)
        route = "liquidity_optimizer"

    selected_ids = result["selected_ids"]
    deferred_ids = result["deferred_ids"]

    selected_set = set(selected_ids)
    deferred_set = set(deferred_ids)
    original_set = set(ids)

    if (
        len(selected_ids) != len(selected_set)
        or len(deferred_ids) != len(deferred_set)
        or selected_set & deferred_set
        or selected_set | deferred_set != original_set
    ):
        raise ValueError("Optimizer returned an invalid payment partition")

    selected = [p for p in payments if p["payment_id"] in selected_set]

    if not is_feasible(selected, liquidity):
        raise ValueError("Optimizer selected an infeasible payment set")

    return {
        "route": route,
        "selected_payments": selected,
        "deferred_payments": [
            p for p in payments if p["payment_id"] in deferred_set
        ],
        "metrics": result,
    }
