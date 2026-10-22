"""
topology_liquidity.py — Novel Topology-Aware & Cycle-Resilient Liquidity Settlement Engine
========================================================================================
Project: ClearPay (Next-Gen Liquidity-Aware Settlement)
Author: Andrea (VIT, 2026)

EXTENDS the existing deployed ClearPay system (src/common/liquidity.py) with:
  1. Topology-Aware Hub-Spoke Clearing (HSC) with Adaptive Elbow Selection
  2. Bounded Bilateral & 3-Bank Multilateral Cycle Gridlock Repair
  3. Starvation-Free Priority-Aging Multi-Objective Scoring
  4. Fully Deterministic S3 Frozen Plan Generation with SHA-256 Hashing

This module imports the existing deployed algorithms (all_or_nothing,
greedy_cumulative, removal_heuristic) from src/common/liquidity.py as
baselines and adds two novel algorithms on top.

Pure Python: zero C-library dependencies for AWS Lambda Free Tier compliance.
"""

from __future__ import annotations

import collections
import copy
import hashlib
import json
import math
import os
import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Import EXISTING deployed ClearPay algorithms from src/common/liquidity.py
# These are the baselines already running on AWS (Mumbai ap-south-1)
# ---------------------------------------------------------------------------
_src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)

# pyright: reportMissingImports=false
from common.liquidity import (  # type: ignore
    all_or_nothing as existing_all_or_nothing,
    greedy_cumulative as existing_greedy_cumulative,
    removal_heuristic as existing_removal_heuristic,
    is_feasible as existing_is_feasible,
    net_debit_positions as existing_net_debit_positions,
    shortfalls as existing_shortfalls,
    settlement_metrics as existing_settlement_metrics,
)

# Re-export existing functions so tests can import from one place
is_feasible = existing_is_feasible
net_debit_positions = existing_net_debit_positions
shortfalls = existing_shortfalls

# ---------------------------------------------------------------------------
# Data Types
# ---------------------------------------------------------------------------
Payment = Dict[str, Any]
Liquidity = Dict[str, int]
PlanResult = Dict[str, Any]


# ---------------------------------------------------------------------------
# 1. Multi-Objective Scoring: Value, Priority, and Aging Utility
#    (Enhancement over existing priority sort in src/common/liquidity.py)
# ---------------------------------------------------------------------------

def payment_utility(
    payment: Payment,
    alpha: float = 0.5,
    beta: float = 0.25,
    age_cap: int = 5,
) -> float:
    """Calculate multi-objective utility for a payment.

    U(p) = amount_paise * (1 + alpha * priority_score + beta * age_score)

    The existing ClearPay system sorts by (priority, created_at, payment_id).
    This extends it with a continuous scoring function that accounts for
    payment aging to prevent starvation across settlement windows.
    """
    amt = float(payment["amount_paise"])
    raw_prio = payment.get("priority", 1)
    if raw_prio == 0:
        prio_score = 2.0
    elif raw_prio == 1:
        prio_score = 1.0
    else:
        prio_score = 0.0

    deferral_count = payment.get("deferral_count", 0)
    age_score = min(float(deferral_count) / max(age_cap, 1), 1.0)

    return amt * (1.0 + alpha * prio_score + beta * age_score)


def total_utility(payments: List[Payment], alpha: float = 0.5, beta: float = 0.25) -> float:
    return sum(payment_utility(p, alpha, beta) for p in payments)


# ---------------------------------------------------------------------------
# 2. Adaptive Elbow Detection for Hub Core (select_k_adaptive)
#    (From DAA research paper Section 7.9)
# ---------------------------------------------------------------------------

def select_k_adaptive(
    payments: List[Payment],
    k_min: int = 2,
    k_max_frac: float = 0.35,
    smooth_window: int = 3,
    hub_ratio_threshold: float = 2.5,
) -> int:
    """Adaptively classify the number of money-center clearing hubs (k)
    based on the degree sequence of the interbank obligation network.

    Adapted from select_k_adaptive() in DAA SEM5/bcp.py for the ClearPay
    payment format (dict-based payments instead of NetworkX DiGraph).
    """
    degrees: Dict[str, int] = collections.defaultdict(int)
    for p in payments:
        degrees[p["from"]] += 1
        degrees[p["to"]] += 1

    n = len(degrees)
    if n <= k_min:
        return max(1, n)

    sorted_degs = sorted(degrees.values(), reverse=True)
    w = min(smooth_window, len(sorted_degs))
    half = w // 2
    smoothed = []
    for i in range(len(sorted_degs)):
        lo = max(0, i - half)
        hi = min(len(sorted_degs), i + half + 1)
        smoothed.append(sum(sorted_degs[lo:hi]) / (hi - lo))

    k_upper = max(k_min, int(math.floor(k_max_frac * n)))
    max_deg = smoothed[0] if smoothed[0] > 0 else 1.0

    ratio_boundary = None
    for i in range(1, min(k_upper + 1, len(smoothed))):
        if max_deg / max(smoothed[i], 0.5) >= hub_ratio_threshold:
            ratio_boundary = i
            break

    if ratio_boundary is not None:
        raw_k = ratio_boundary
    else:
        best_idx, best_gap = 0, -1.0
        for i in range(min(k_upper, len(smoothed) - 1)):
            denom = smoothed[i] if smoothed[i] > 0 else 1.0
            gap = (smoothed[i] - smoothed[i + 1]) / denom
            if gap > best_gap:
                best_gap, best_idx = gap, i
        raw_k = k_min if best_gap < 0.15 else (best_idx + 1)

    return max(k_min, min(raw_k, k_upper))


# ---------------------------------------------------------------------------
# 3. NOVEL ALGORITHM A: Bounded Bilateral & 3-Bank Cycle Gridlock Repair
#    (Extends the existing removal_heuristic from src/common/liquidity.py)
# ---------------------------------------------------------------------------

def bounded_cycle_gridlock_repair(
    payments: List[Payment],
    liquidity: Liquidity,
    max_pair_candidates: int = 10,
    max_cycles: int = 8,
    alpha: float = 0.5,
    beta: float = 0.25,
) -> PlanResult:
    """Novel Algorithm A: Multi-Level Bounded Gridlock Resolver.

    EXTENDS the existing deployed removal_heuristic (src/common/liquidity.py)
    by adding two additional recovery phases:

    Phase 1: Run the EXISTING removal_heuristic to get a feasible base set
             (this is what's already deployed on AWS).
    Phase 2: Identify bilateral pairs (A <-> B) in the deferred set and test
             bounded subsets for restoration.
    Phase 3: Identify 3-bank directed cycles (A -> B -> C -> A) in the
             remaining deferred set where mutual netting neutralizes
             liquidity consumption, settling stalled loops.

    The existing system's bilateral group add-back (Phase 3 of removal_heuristic)
    tests entire groups at once. This novel approach additionally detects and
    exploits directed cycle structure for gridlock resolution.
    """
    t0 = time.perf_counter()

    # Phase 1: Use the EXISTING deployed removal heuristic as the base
    base_res = existing_removal_heuristic(payments, liquidity)
    id_map = {p["payment_id"]: p for p in payments}
    selected = [id_map[pid] for pid in base_res["selected_ids"]]
    deferred = [id_map[pid] for pid in base_res["deferred_ids"]]

    # Phase 2: Bounded Bilateral Subset Repair (beyond existing group add-back)
    pairs: Dict[Tuple[str, str], List[Payment]] = collections.defaultdict(list)
    for p in deferred:
        u, v = p["from"], p["to"]
        pair_key = (u, v) if u < v else (v, u)
        pairs[pair_key].append(p)

    sorted_pairs = sorted(
        pairs.items(),
        key=lambda item: sum(payment_utility(p, alpha, beta) for p in item[1]),
        reverse=True,
    )

    for (u, v), p_list in sorted_pairs:
        has_u_to_v = any(p["from"] == u for p in p_list)
        has_v_to_u = any(p["from"] == v for p in p_list)
        if not (has_u_to_v and has_v_to_u):
            continue

        cands = sorted(p_list, key=lambda p: payment_utility(p, alpha, beta), reverse=True)[:max_pair_candidates]
        for p in cands:
            if p in deferred:
                selected.append(p)
                if is_feasible(selected, liquidity):
                    deferred.remove(p)
                else:
                    selected.pop()

    # Phase 3: Bounded 3-Bank Directed Cycle Recovery (A -> B -> C -> A)
    adj: Dict[str, Dict[str, List[Payment]]] = collections.defaultdict(lambda: collections.defaultdict(list))
    for p in deferred:
        adj[p["from"]][p["to"]].append(p)

    all_banks = list(adj.keys())
    detected_cycles: List[Tuple[Payment, Payment, Payment]] = []

    for a in all_banks:
        for b in adj[a]:
            if b == a:
                continue
            for c in adj[b]:
                if c == a or c == b:
                    continue
                if a in adj[c]:
                    p_ab = max(adj[a][b], key=lambda p: payment_utility(p, alpha, beta))
                    p_bc = max(adj[b][c], key=lambda p: payment_utility(p, alpha, beta))
                    p_ca = max(adj[c][a], key=lambda p: payment_utility(p, alpha, beta))
                    detected_cycles.append((p_ab, p_bc, p_ca))
                    if len(detected_cycles) >= max_cycles:
                        break
            if len(detected_cycles) >= max_cycles:
                break
        if len(detected_cycles) >= max_cycles:
            break

    for p1, p2, p3 in detected_cycles:
        if all(p in deferred for p in (p1, p2, p3)):
            selected.extend([p1, p2, p3])
            if is_feasible(selected, liquidity):
                deferred.remove(p1)
                deferred.remove(p2)
                deferred.remove(p3)
            else:
                for _ in range(3):
                    selected.pop()

    return _build_metrics(selected, deferred, liquidity, "bounded_cycle_gridlock_repair", time.perf_counter() - t0)


# ---------------------------------------------------------------------------
# 4. NOVEL ALGORITHM B: Topology-Aware Hub-Spoke Clearing (HSC)
#    (Adapts bcp.py fpt_hub_spoke_clearing for ClearPay payment format)
# ---------------------------------------------------------------------------

def topology_hub_spoke_clearing(
    payments: List[Payment],
    liquidity: Liquidity,
    k: Optional[int] = None,
    alpha: float = 0.5,
    beta: float = 0.25,
) -> PlanResult:
    """Novel Algorithm B: Topology-Aware Bank Clearing (HSC).

    Adapts the Hub-Spoke Clearing algorithm from the DAA research paper
    (bcp.py fpt_hub_spoke_clearing) to ClearPay's payment dict format
    and the existing AWS settlement pipeline.

    1. Classifies banks into Hubs (H) and Spokes (S) using adaptive elbow.
    2. Clusters spoke network into connected components (Super-Spokes).
    3. Prioritizes Hub-Core payments first (high-value interbank flow).
    4. Clears spoke-internal and spoke-to-hub obligations greedily.
    5. Deterministic Worklist Repair guarantees 100% deposit feasibility
       (Lemma 2 from the DAA research paper Section 7.7).
    """
    t0 = time.perf_counter()
    if not payments:
        return _build_metrics([], [], liquidity, "topology_hub_spoke_clearing", 0.0)

    # Step 1: Classify Hubs and Spokes
    degree: Dict[str, int] = collections.defaultdict(int)
    for p in payments:
        degree[p["from"]] += 1
        degree[p["to"]] += 1

    ranked_nodes = sorted(degree.keys(), key=lambda n: degree[n], reverse=True)
    if k is None:
        k = select_k_adaptive(payments)
    k = max(1, min(k, len(ranked_nodes)))

    H = set(ranked_nodes[:k])
    S = set(ranked_nodes[k:])

    # Step 2: Super-spoke components (connected components of spoke-spoke graph)
    spoke_adj: Dict[str, Set[str]] = collections.defaultdict(set)
    for p in payments:
        u, v = p["from"], p["to"]
        if u in S and v in S:
            spoke_adj[u].add(v)
            spoke_adj[v].add(u)

    visited = set()
    components: List[Set[str]] = []
    for s_node in S:
        if s_node not in visited:
            comp = set()
            queue = [s_node]
            visited.add(s_node)
            while queue:
                curr = queue.pop(0)
                comp.add(curr)
                for nxt in spoke_adj[curr]:
                    if nxt not in visited:
                        visited.add(nxt)
                        queue.append(nxt)
            components.append(comp)

    # Step 3: Categorize payments by topology position
    hub_payments = [p for p in payments if p["from"] in H and p["to"] in H]
    spoke_to_hub = [p for p in payments if p["from"] in S and p["to"] in H]
    hub_to_spoke = [p for p in payments if p["from"] in H and p["to"] in S]
    spoke_internal = [p for p in payments if p["from"] in S and p["to"] in S]

    selected: List[Payment] = []

    # Hub-hub first (highest value core)
    for p in sorted(hub_payments, key=lambda x: payment_utility(x, alpha, beta), reverse=True):
        selected.append(p)
        if not is_feasible(selected, liquidity):
            selected.pop()

    # Hub-to-spoke (inflow to spokes)
    for p in sorted(hub_to_spoke, key=lambda x: payment_utility(x, alpha, beta), reverse=True):
        selected.append(p)
        if not is_feasible(selected, liquidity):
            selected.pop()

    # Spoke-to-hub with rationing
    for p in sorted(spoke_to_hub, key=lambda x: payment_utility(x, alpha, beta), reverse=True):
        selected.append(p)
        if not is_feasible(selected, liquidity):
            selected.pop()

    # Spoke internal per component
    for comp in components:
        comp_payments = [p for p in spoke_internal if p["from"] in comp]
        for p in sorted(comp_payments, key=lambda x: payment_utility(x, alpha, beta), reverse=True):
            selected.append(p)
            if not is_feasible(selected, liquidity):
                selected.pop()

    # Step 4: Deterministic Repair Phase (Lemma 2 from DAA paper)
    while True:
        violating = shortfalls(selected, liquidity)
        if not violating:
            break
        worst_bank = max(violating, key=lambda b: violating[b])
        outgoing = [p for p in selected if p["from"] == worst_bank]
        if not outgoing:
            break
        victim = min(outgoing, key=lambda p: payment_utility(p, alpha, beta))
        selected.remove(victim)

    selected_set = {p["payment_id"] for p in selected}
    deferred = [p for p in payments if p["payment_id"] not in selected_set]

    res = _build_metrics(selected, deferred, liquidity, "topology_hub_spoke_clearing", time.perf_counter() - t0)
    res["k_selected"] = k
    res["num_super_spokes"] = len(components)
    return res


# ---------------------------------------------------------------------------
# 5. S3 Frozen Settlement Plan (Extends existing AWS Step Functions workflow)
# ---------------------------------------------------------------------------

def build_frozen_plan(
    window_id: str,
    plan_version: int,
    algorithm: str,
    payments: List[Payment],
    liquidity: Liquidity,
    plan_result: PlanResult,
) -> Dict[str, Any]:
    """Construct an immutable, canonical S3 settlement plan with SHA-256 hash.

    This extends the existing ClearPay frozen-plan mechanism (described in
    the project proposal Section 8.3 step 4) with a cryptographic hash
    for deterministic crash recovery verification.
    """
    raw_payload = {
        "window_id": window_id,
        "plan_version": plan_version,
        "algorithm": algorithm,
        "selected_ids": sorted(plan_result["selected_ids"]),
        "deferred_ids": sorted(plan_result["deferred_ids"]),
        "settled_value_paise": plan_result["settled_value_paise"],
        "liquidity_snapshot": {k: int(v) for k, v in sorted(liquidity.items())},
    }
    canonical_json = json.dumps(raw_payload, sort_keys=True)
    plan_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    return {
        **raw_payload,
        "plan_hash": plan_hash,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "net_liquidity_used_paise": plan_result["net_liquidity_used_paise"],
        "settled_pct": plan_result["settled_pct"],
        "feasible": plan_result["feasible"],
    }


# ---------------------------------------------------------------------------
# 6. Metrics (extends existing settlement_metrics with utility tracking)
# ---------------------------------------------------------------------------

def _build_metrics(
    selected: List[Payment],
    deferred: List[Payment],
    liquidity: Liquidity,
    algorithm: str,
    elapsed_seconds: float,
) -> PlanResult:
    """Build output dict — extends existing settlement_metrics with utility."""
    # Use existing metrics builder
    base = existing_settlement_metrics(selected, deferred, liquidity, algorithm, elapsed_seconds)
    # Add novel metrics
    base["priority_utility"] = round(total_utility(selected), 2)
    settled_val = base["settled_value_paise"]
    used_liq = base["net_liquidity_used_paise"]
    base["liquidity_per_1000_settled"] = (
        round(1000.0 * used_liq / settled_val, 2) if settled_val > 0 else 0.0
    )
    return base


# ---------------------------------------------------------------------------
# 7. Convenience: run all algorithms (existing + novel) on same batch
# ---------------------------------------------------------------------------

def compare_all_with_novel(
    payments: List[Payment],
    liquidity: Liquidity,
) -> Dict[str, PlanResult]:
    """Run existing deployed baselines + novel algorithms on same data."""
    return {
        "all_or_nothing": existing_all_or_nothing(payments, liquidity),
        "greedy_cumulative": existing_greedy_cumulative(payments, liquidity),
        "removal_heuristic": existing_removal_heuristic(payments, liquidity),
        "bounded_cycle_gridlock_repair": bounded_cycle_gridlock_repair(payments, liquidity),
        "topology_hub_spoke_clearing": topology_hub_spoke_clearing(payments, liquidity),
    }
