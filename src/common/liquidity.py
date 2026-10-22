"""
liquidity.py — Liquidity-aware partial settlement for ClearPay.

This module implements the core novelty of the ClearPay extension:
given a batch of posted payments and per-bank available settlement
liquidity, it selects the largest feasible subset that can actually
settle rather than deferring the *entire* batch when one bank falls
short.

Four algorithms are provided for comparison:

1. all_or_nothing     — settle everything or nothing (baseline).
2. greedy_cumulative  — accept payments one-by-one; keep if still
                        feasible (greedy cumulative baseline).
3. removal_heuristic  — start with all payments, remove the smallest
                        payment from the most-over-limit bank until
                        the batch is feasible.  Then do single-payment
                        and bilateral-group add-back.
4. exact_milp         — solve the integer programme exactly with
                        scipy.optimize.milp (only practical for small
                        instances; used to measure the optimality gap).

All monetary amounts are in integer paise to avoid floating-point
rounding errors.  Algorithm correctness is verified by
`is_feasible()` after every mutation.

Data conventions
----------------
Payment dict keys:
    payment_id  : str
    from        : str   (bank identifier)
    to          : str   (bank identifier)
    amount_paise: int   (positive integer, paise)
    priority    : int   (lower = higher business priority; default 0)
    created_at  : str   (ISO-8601; used for age-based tie-breaking)

Liquidity dict:
    {bank_id: available_paise}   — may be 0 or negative (already overdrawn)
"""

from __future__ import annotations

import time
from collections import defaultdict
from copy import deepcopy
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
Payment = Dict
Liquidity = Dict[str, int]
PlanResult = Dict


# ---------------------------------------------------------------------------
# Core feasibility helpers
# ---------------------------------------------------------------------------

def net_debit_positions(payments: List[Payment]) -> Dict[str, int]:
    """Return the net debit required from each bank for this payment set.

    Positive value  → bank must *send* that many paise net.
    Negative value  → bank is a net *receiver* (no liquidity needed).
    """
    pos: Dict[str, int] = defaultdict(int)
    for p in payments:
        pos[p["from"]] += p["amount_paise"]
        pos[p["to"]] -= p["amount_paise"]
    # Return only banks that are net payers.
    return {bank: amount for bank, amount in pos.items() if amount > 0}


def is_feasible(payments: List[Payment], liquidity: Liquidity) -> bool:
    """Return True iff every bank's net debit ≤ its available liquidity."""
    for bank, debit in net_debit_positions(payments).items():
        if debit > liquidity.get(bank, 0):
            return False
    return True


def shortfalls(payments: List[Payment], liquidity: Liquidity) -> Dict[str, int]:
    """Return {bank: shortfall_paise} for every over-limit bank (shortfall > 0)."""
    result = {}
    for bank, debit in net_debit_positions(payments).items():
        avail = liquidity.get(bank, 0)
        if debit > avail:
            result[bank] = debit - avail
    return result


def settlement_metrics(
    selected: List[Payment],
    deferred: List[Payment],
    liquidity: Liquidity,
    algorithm: str,
    elapsed_seconds: float,
) -> PlanResult:
    """Build a standard result dict from a completed selection."""
    total_value = sum(p["amount_paise"] for p in selected + deferred)
    settled_value = sum(p["amount_paise"] for p in selected)
    net_debits = net_debit_positions(selected)
    liquidity_used = sum(net_debits.values())

    return {
        "algorithm": algorithm,
        "selected_count": len(selected),
        "deferred_count": len(deferred),
        "selected_ids": [p["payment_id"] for p in selected],
        "deferred_ids": [p["payment_id"] for p in deferred],
        "settled_value_paise": settled_value,
        "total_value_paise": total_value,
        "settled_pct": (
            round(100.0 * settled_value / total_value, 2) if total_value else 0.0
        ),
        "net_liquidity_used_paise": liquidity_used,
        "elapsed_ms": round(elapsed_seconds * 1000, 3),
        "feasible": is_feasible(selected, liquidity),
    }


# ---------------------------------------------------------------------------
# Algorithm 1 — All-or-nothing (baseline)
# ---------------------------------------------------------------------------

def all_or_nothing(
    payments: List[Payment], liquidity: Liquidity
) -> PlanResult:
    """Settle the complete batch or defer everything.

    This is the simplest baseline: if a single bank cannot cover its
    net debit obligation, the entire batch is deferred.
    """
    t0 = time.perf_counter()
    if is_feasible(payments, liquidity):
        selected, deferred = list(payments), []
    else:
        selected, deferred = [], list(payments)
    return settlement_metrics(
        selected, deferred, liquidity, "all_or_nothing", time.perf_counter() - t0
    )


# ---------------------------------------------------------------------------
# Algorithm 2 — Greedy cumulative (baseline)
# ---------------------------------------------------------------------------

def greedy_cumulative(
    payments: List[Payment], liquidity: Liquidity
) -> PlanResult:
    """Evaluate payments in priority/age order; accept if still feasible.

    Sort key: (priority ASC, created_at ASC, payment_id ASC).
    This ensures deterministic, reproducible results.
    """
    t0 = time.perf_counter()

    ordered = sorted(
        payments,
        key=lambda p: (
            p.get("priority", 0),
            p.get("created_at", ""),
            p["payment_id"],
        ),
    )

    selected: List[Payment] = []
    deferred: List[Payment] = []

    for payment in ordered:
        candidate = selected + [payment]
        if is_feasible(candidate, liquidity):
            selected.append(payment)
        else:
            deferred.append(payment)

    return settlement_metrics(
        selected, deferred, liquidity, "greedy_cumulative", time.perf_counter() - t0
    )


# ---------------------------------------------------------------------------
# Algorithm 3 — Removal heuristic with add-back (primary novelty)
# ---------------------------------------------------------------------------

def _removal_key(payment: Payment) -> Tuple:
    """Sort key to pick which outgoing payment to remove.

    Prefer removing the smallest payment first — this resolves the deficit
    with minimal collateral damage to total settled value.
    Tie-break: higher priority number (lower business priority) first,
    then by payment_id for determinism.
    """
    return (
        payment["amount_paise"],            # prefer smallest removal
        -payment.get("priority", 0),        # prefer low-priority payments
        payment["payment_id"],
    )


def removal_heuristic(
    payments: List[Payment],
    liquidity: Liquidity,
) -> PlanResult:
    """Start from the full batch; remove payments until feasible; then add back.

    Phase 1 — Removal loop
    ----------------------
    While the current selection is not feasible:
      1. Find the bank with the largest liquidity shortfall.
      2. Among that bank's outgoing payments, remove the one that
         covers the shortfall with minimum total value removed
         (i.e., smallest payment ≥ shortfall; fall back to largest
          payment if no single payment covers it).
      3. Place the removed payment in the deferred set.

    Phase 2 — Single-payment add-back
    ----------------------------------
    Try to restore deferred payments in (priority ASC, created_at ASC,
    payment_id ASC) order.  Keep a payment if re-including it leaves the
    batch feasible.

    Phase 3 — Bilateral group add-back
    -----------------------------------
    For each unordered pair of banks (A, B), collect all deferred payments
    between A and B.  Evaluate groups in descending combined value order.
    Restore a group only when doing so preserves feasibility.
    """
    t0 = time.perf_counter()

    selected = list(payments)
    deferred: List[Payment] = []

    # --- Phase 1: removal ---
    while True:
        sf = shortfalls(selected, liquidity)
        if not sf:
            break
        # Pick the bank with the largest shortfall (tie-break by bank id).
        worst_bank = max(sf, key=lambda b: (sf[b], b))
        worst_shortfall = sf[worst_bank]

        # Payments that, if removed, directly reduce worst_bank's net debit.
        candidates = [p for p in selected if p["from"] == worst_bank]
        if not candidates:
            # No direct removal possible (this bank only receives);
            # break to avoid infinite loop — should not happen in a
            # well-formed batch, but guards against edge cases.
            break

        # Prefer the smallest payment that *alone* covers the shortfall.
        covering = [p for p in candidates if p["amount_paise"] >= worst_shortfall]
        if covering:
            victim = min(covering, key=lambda p: (
                p["amount_paise"], p.get("priority", 0), p["payment_id"]
            ))
        else:
            # No single payment covers it; remove the largest one available.
            victim = max(candidates, key=lambda p: (
                p["amount_paise"], p["payment_id"]
            ))

        selected.remove(victim)
        deferred.append(victim)

    # --- Phase 2: single-payment add-back ---
    deferred_ordered = sorted(
        deferred,
        key=lambda p: (p.get("priority", 0), p.get("created_at", ""), p["payment_id"]),
    )
    still_deferred: List[Payment] = []
    for payment in deferred_ordered:
        candidate = selected + [payment]
        if is_feasible(candidate, liquidity):
            selected.append(payment)
        else:
            still_deferred.append(payment)

    deferred = still_deferred

    # --- Phase 3: bilateral group add-back ---
    # Build groups: {frozenset({A, B}): [payments]}
    groups: Dict[frozenset, List[Payment]] = defaultdict(list)
    for p in deferred:
        key = frozenset({p["from"], p["to"]})
        groups[key].append(p)

    # Sort groups by descending combined value, then pair key for determinism.
    group_order = sorted(
        groups.keys(),
        key=lambda k: (
            -sum(p["amount_paise"] for p in groups[k]),
            sorted(k),
        ),
    )

    still_deferred = []
    restored_ids: set = set()
    for pair_key in group_order:
        group = groups[pair_key]
        candidate = selected + group
        if is_feasible(candidate, liquidity):
            selected.extend(group)
            restored_ids.update(p["payment_id"] for p in group)
        else:
            still_deferred.extend(group)

    deferred = still_deferred

    return settlement_metrics(
        selected, deferred, liquidity, "removal_heuristic", time.perf_counter() - t0
    )


# ---------------------------------------------------------------------------
# Algorithm 4 — Exact MILP (reference optimum, small instances only)
# ---------------------------------------------------------------------------

def exact_milp(
    payments: List[Payment],
    liquidity: Liquidity,
) -> PlanResult:
    """Solve the binary LP exactly using scipy.optimize.milp.

    Maximise  Σ amount_paise[p] · x[p]
    s.t.      for each bank b:
                  Σ_{p: from=b} amount_paise[p]·x[p]
                - Σ_{p: to=b}   amount_paise[p]·x[p]  ≤  liquidity[b]
              x[p] ∈ {0, 1}

    This is NP-hard in general; only practical for n ≲ 30 payments.
    The solver operates in floating point; the returned solution is
    re-verified with exact integer arithmetic.

    Returns the same dict structure as the other algorithms.
    A "solver_status" key is added.
    """
    try:
        import numpy as np
        from scipy.optimize import LinearConstraint, milp, Bounds
    except ImportError:
        # scipy not available — fall back gracefully
        result = removal_heuristic(payments, liquidity)
        result["algorithm"] = "exact_milp_unavailable_fallback"
        result["solver_status"] = "scipy not installed"
        return result

    t0 = time.perf_counter()
    n = len(payments)

    if n == 0:
        return settlement_metrics([], [], liquidity, "exact_milp", 0.0)

    # Objective: minimise −amount (i.e., maximise amount).
    c = np.array([-p["amount_paise"] for p in payments], dtype=float)

    # Collect all banks that appear in payments or liquidity.
    banks = sorted(
        set(p["from"] for p in payments)
        | set(p["to"] for p in payments)
        | set(liquidity.keys())
    )
    bank_index = {b: i for i, b in enumerate(banks)}
    m = len(banks)

    # Constraint matrix A (m × n), rhs = liquidity vector.
    A = np.zeros((m, n), dtype=float)
    for j, p in enumerate(payments):
        fi = bank_index[p["from"]]
        ti = bank_index[p["to"]]
        A[fi, j] += p["amount_paise"]
        A[ti, j] -= p["amount_paise"]

    rhs = np.array([liquidity.get(b, 0) for b in banks], dtype=float)

    constraints = LinearConstraint(A, -np.inf, rhs)
    integrality = np.ones(n)          # all variables are integer
    bounds = Bounds(lb=0.0, ub=1.0)

    res = milp(c, constraints=constraints, integrality=integrality, bounds=bounds)
    elapsed = time.perf_counter() - t0

    if res.success:
        # Round to nearest integer and re-verify with exact arithmetic.
        x = np.round(res.x).astype(int)
        selected = [payments[j] for j in range(n) if x[j] == 1]
        deferred = [payments[j] for j in range(n) if x[j] == 0]
        # Safety: if floating-point rounding produced infeasible result, trim.
        if not is_feasible(selected, liquidity):
            trim = removal_heuristic(payments, liquidity)
            trim["algorithm"] = "exact_milp_post_trim"
            trim["solver_status"] = res.message
            return trim
        result = settlement_metrics(
            selected, deferred, liquidity, "exact_milp", elapsed
        )
        result["solver_status"] = res.message
    else:
        # Infeasible or error — return empty selection.
        result = settlement_metrics(
            [], list(payments), liquidity, "exact_milp", elapsed
        )
        result["solver_status"] = res.message

    return result


# ---------------------------------------------------------------------------
# Convenience: run all four algorithms on the same batch
# ---------------------------------------------------------------------------

def compare_all(
    payments: List[Payment],
    liquidity: Liquidity,
    include_milp: bool = False,
) -> Dict[str, PlanResult]:
    """Run all algorithms and return a dict keyed by algorithm name."""
    results = {
        "all_or_nothing": all_or_nothing(payments, liquidity),
        "greedy_cumulative": greedy_cumulative(payments, liquidity),
        "removal_heuristic": removal_heuristic(payments, liquidity),
    }
    if include_milp:
        results["exact_milp"] = exact_milp(payments, liquidity)
    return results


# ---------------------------------------------------------------------------
# Deferred-payment reconsideration (multi-window support)
# ---------------------------------------------------------------------------

def reconsider_deferred(
    deferred_payments: List[Payment],
    new_liquidity: Liquidity,
    algorithm: str = "removal_heuristic",
) -> PlanResult:
    """Run the chosen algorithm on previously deferred payments with fresh liquidity.

    This supports the multi-window use case described in Section 7 of the
    proposal: deferred payments are reconsidered when liquidity is topped up.
    """
    algorithms = {
        "all_or_nothing": all_or_nothing,
        "greedy_cumulative": greedy_cumulative,
        "removal_heuristic": removal_heuristic,
        "exact_milp": exact_milp,
    }
    fn = algorithms.get(algorithm, removal_heuristic)
    result = fn(deferred_payments, new_liquidity)
    result["reconsidered"] = True
    return result
