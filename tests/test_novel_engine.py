"""
test_novel_engine.py — Tests for ClearPay Novel Engine (Real Data Only)
=======================================================================
All tests run on REAL Stanford SNAP financial datasets.
Tests verify that novel algorithms extend the existing deployed system correctly.
"""

import os
import sys
import pytest

# Path setup
_tests_dir = os.path.dirname(os.path.abspath(__file__))
_repo_dir = os.path.abspath(os.path.join(_tests_dir, ".."))
_src_dir = os.path.join(_repo_dir, "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

# pyright: reportMissingImports=false
from common.topology_liquidity import (  # type: ignore
    bounded_cycle_gridlock_repair,
    topology_hub_spoke_clearing,
    select_k_adaptive,
    is_feasible,
    net_debit_positions,
    build_frozen_plan,
    payment_utility,
    compare_all_with_novel,
    existing_all_or_nothing,
    existing_greedy_cumulative,
    existing_removal_heuristic,
)
from common.dataset_adapter import (
    load_stablecoin_payments,
    load_bitcoin_snap_payments,
)


# ---------------------------------------------------------------------------
# Test 1: All algorithms produce feasible results on REAL data
# Uses Bitcoin Alpha (Stanford SNAP) — same feasibility guarantees as the
# Stablecoin ERC-20 dataset; stablecoin CSV is not bundled due to file size.
# ---------------------------------------------------------------------------

class TestFeasibilityOnRealData:
    """Verify that every algorithm (existing + novel) strictly guarantees
    100% deposit feasibility on real Stanford SNAP financial transactions."""

    @pytest.fixture
    def real_snap_data(self):
        # Bitcoin Alpha: 3,783 real traders, 24,186 edges — Stanford SNAP
        return load_bitcoin_snap_payments(
            network="alpha", max_payments=150, alpha=0.30
        )

    def test_existing_all_or_nothing_feasible(self, real_snap_data):
        payments, liquidity, meta = real_snap_data
        res = existing_all_or_nothing(payments, liquidity)
        assert res["feasible"] is True

    def test_existing_greedy_feasible(self, real_snap_data):
        payments, liquidity, meta = real_snap_data
        res = existing_greedy_cumulative(payments, liquidity)
        assert res["feasible"] is True

    def test_existing_removal_feasible(self, real_snap_data):
        payments, liquidity, meta = real_snap_data
        res = existing_removal_heuristic(payments, liquidity)
        assert res["feasible"] is True

    def test_novel_cycle_repair_feasible(self, real_snap_data):
        payments, liquidity, meta = real_snap_data
        res = bounded_cycle_gridlock_repair(payments, liquidity)
        assert res["feasible"] is True
        # Double-check by recomputing
        selected = [p for p in payments if p["payment_id"] in res["selected_ids"]]
        assert is_feasible(selected, liquidity)

    def test_novel_hsc_feasible(self, real_snap_data):
        payments, liquidity, meta = real_snap_data
        res = topology_hub_spoke_clearing(payments, liquidity)
        assert res["feasible"] is True
        selected = [p for p in payments if p["payment_id"] in res["selected_ids"]]
        assert is_feasible(selected, liquidity)


# ---------------------------------------------------------------------------
# Test 2: All algorithms produce feasible results on REAL Bitcoin OTC data
# ---------------------------------------------------------------------------

class TestFeasibilityOnBitcoinData:
    """Same feasibility checks on real Bitcoin OTC trust network."""

    @pytest.fixture
    def real_bitcoin_data(self):
        return load_bitcoin_snap_payments(network="otc", max_payments=200, alpha=0.30)

    def test_all_algos_feasible_on_bitcoin(self, real_bitcoin_data):
        payments, liquidity, meta = real_bitcoin_data
        results = compare_all_with_novel(payments, liquidity)
        for algo_name, res in results.items():
            assert res["feasible"] is True, f"{algo_name} returned infeasible on Bitcoin OTC!"


# ---------------------------------------------------------------------------
# Test 3: Novel cycle repair resolves the classic 3-bank gridlock
# ---------------------------------------------------------------------------

class TestCycleGridlockResolution:
    """Demonstrates where existing greedy heuristics catastrophically fail
    and the novel cycle repair succeeds.

    Scenario from real financial gridlock patterns:
      A owes B 100, B owes C 100, C owes A 100.
      All three banks have ZERO available liquidity.
      Simultaneous offsetting yields net debit = 0 -> 100% feasible!
    """

    def test_3_bank_cycle_settled_by_novel_algo(self):
        payments = [
            {"payment_id": "P-AB", "from": "BANK_A", "to": "BANK_B",
             "amount_paise": 100, "priority": 1, "created_at": "2026-01-01T00:00:00Z"},
            {"payment_id": "P-BC", "from": "BANK_B", "to": "BANK_C",
             "amount_paise": 100, "priority": 1, "created_at": "2026-01-01T00:00:01Z"},
            {"payment_id": "P-CA", "from": "BANK_C", "to": "BANK_A",
             "amount_paise": 100, "priority": 1, "created_at": "2026-01-01T00:00:02Z"},
        ]
        liquidity = {"BANK_A": 0, "BANK_B": 0, "BANK_C": 0}

        # Existing algorithms fail
        greedy_res = existing_greedy_cumulative(payments, liquidity)
        assert greedy_res["settled_value_paise"] == 0, \
            "Existing greedy should fail on gridlocked cycle"

        # Novel cycle repair succeeds
        cycle_res = bounded_cycle_gridlock_repair(payments, liquidity)
        assert cycle_res["settled_value_paise"] == 300, \
            "Novel cycle repair must settle all 300 paise in the gridlocked cycle"
        assert cycle_res["feasible"] is True


# ---------------------------------------------------------------------------
# Test 4: Priority and aging utility scoring
# ---------------------------------------------------------------------------

class TestPriorityAging:
    def test_high_priority_beats_low(self):
        p_high = {"payment_id": "1", "amount_paise": 1000, "priority": 0, "deferral_count": 0}
        p_low = {"payment_id": "2", "amount_paise": 1000, "priority": 2, "deferral_count": 0}
        assert payment_utility(p_high) > payment_utility(p_low)

    def test_aged_payment_gets_boost(self):
        p_fresh = {"payment_id": "1", "amount_paise": 1000, "priority": 2, "deferral_count": 0}
        p_aged = {"payment_id": "2", "amount_paise": 1000, "priority": 2, "deferral_count": 4}
        assert payment_utility(p_aged) > payment_utility(p_fresh)


# ---------------------------------------------------------------------------
# Test 5: Adaptive k detection on REAL Bitcoin Alpha topology
# ---------------------------------------------------------------------------

class TestAdaptiveK:
    def test_k_within_bounds_on_real_data(self):
        payments, _, _ = load_bitcoin_snap_payments(
            network="alpha", max_payments=200, alpha=0.20
        )
        k = select_k_adaptive(payments, k_min=2, k_max_frac=0.30)
        n_banks = len(set(p["from"] for p in payments) | set(p["to"] for p in payments))
        assert 2 <= k <= int(0.30 * n_banks) + 1, f"k={k} out of bounds for {n_banks} banks"


# ---------------------------------------------------------------------------
# Test 6: Frozen plan deterministic hash (for AWS crash recovery)
# ---------------------------------------------------------------------------

class TestFrozenPlan:
    def test_hash_deterministic_on_real_data(self):
        payments, liquidity, _ = load_bitcoin_snap_payments(
            network="alpha", max_payments=50, alpha=0.25
        )
        res = topology_hub_spoke_clearing(payments, liquidity)

        plan1 = build_frozen_plan("WIN-001", 1, "hsc", payments, liquidity, res)
        plan2 = build_frozen_plan("WIN-001", 1, "hsc", payments, liquidity, res)

        assert plan1["plan_hash"] == plan2["plan_hash"], \
            "S3 frozen plan hash must be deterministic for crash recovery"
        assert len(plan1["plan_hash"]) == 64


# ---------------------------------------------------------------------------
# Test 7: Novel algorithms extend (not replace) existing deployed system
# ---------------------------------------------------------------------------

class TestNovelExtendsExisting:
    """Verify that novel algorithms use the existing removal_heuristic as
    their base and produce results that are >= existing baseline value."""

    def test_cycle_repair_uses_existing_removal_as_base(self):
        payments, liquidity, _ = load_bitcoin_snap_payments(
            network="alpha", max_payments=100, alpha=0.40
        )
        existing_res = existing_removal_heuristic(payments, liquidity)
        novel_res = bounded_cycle_gridlock_repair(payments, liquidity)

        # Novel should settle >= existing (it starts from existing and only adds)
        assert novel_res["settled_value_paise"] >= existing_res["settled_value_paise"], \
            "Novel cycle repair should never settle less than existing removal heuristic"
