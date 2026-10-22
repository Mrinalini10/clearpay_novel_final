"""
benchmark_novelty.py — Real-World Comparative Benchmark (No Synthetic Data)
============================================================================
Compares the EXISTING deployed ClearPay algorithms (from src/common/liquidity.py)
against the two NOVEL algorithms, running exclusively on real Stanford SNAP datasets.

Existing (deployed on AWS):
  1. All-or-Nothing
  2. Cumulative Greedy
  3. Removal Heuristic (with bilateral group add-back)

Novel (in new novel/):
  4. Bounded Cycle Gridlock Repair (extends removal heuristic)
  5. Topology-Aware Hub-Spoke Clearing (HSC)
"""

import json
import os
import sys
import time

current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, "..", "src"))
for p in (src_dir, current_dir):
    if p not in sys.path:
        sys.path.insert(0, p)

# pyright: reportMissingImports=false
from common.topology_liquidity import (  # type: ignore
    bounded_cycle_gridlock_repair,
    topology_hub_spoke_clearing,
    compare_all_with_novel,
    existing_all_or_nothing as all_or_nothing,
    existing_greedy_cumulative as greedy_cumulative,
    existing_removal_heuristic as removal_heuristic,
)
from common.dataset_adapter import (  # type: ignore
    load_stablecoin_payments,
    load_bitcoin_snap_payments,
)


def run_real_data_sweep(dataset_loader, dataset_name, loader_kwargs_list):
    """Run all 5 algorithms on real data at varying liquidity levels."""
    print("=" * 90)
    print(f"REAL-WORLD BENCHMARK: {dataset_name}")
    print("=" * 90)

    algorithms = [
        ("All-or-Nothing [existing]", all_or_nothing),
        ("Greedy [existing]", greedy_cumulative),
        ("Removal [existing]", removal_heuristic),
        ("Cycle Repair [NOVEL]", bounded_cycle_gridlock_repair),
        ("Topology HSC [NOVEL]", topology_hub_spoke_clearing),
    ]

    results = []
    header = f"{'Alpha':<7} | {'Algorithm':<26} | {'Settled %':<10} | {'Count':<12} | {'Time (ms)':<9}"
    print(header)
    print("-" * len(header))

    for kwargs in loader_kwargs_list:
        alpha = kwargs["alpha"]
        payments, liquidity, meta = dataset_loader(**kwargs)

        for name, fn in algorithms:
            t0 = time.perf_counter()
            res = fn(payments, liquidity)
            elapsed = (time.perf_counter() - t0) * 1000

            row = {
                "dataset": dataset_name,
                "alpha": alpha,
                "algorithm": name,
                "settled_pct": res["settled_pct"],
                "selected_count": res["selected_count"],
                "total_count": len(payments),
                "settled_value_paise": res["settled_value_paise"],
                "elapsed_ms": round(elapsed, 2),
                "feasible": res["feasible"],
            }
            results.append(row)

            print(
                f"{alpha:<7.2f} | {name:<26} | {res['settled_pct']:<8.1f}%  | "
                f"{res['selected_count']:>4}/{len(payments):<6} | {elapsed:<9.2f}"
            )
        print("-" * len(header))

    return results


def main():
    all_results = []

    # --- Benchmark 1: Stanford SNAP Stablecoin ERC-20 (Real $USD Flows) ---
    # Skip gracefully if the large token_transfers.csv is not present locally.
    stbl_configs = [
        {"duration_hours": 1.0, "alpha": 0.10, "max_payments": 300, "min_val_usd": 1.0},
        {"duration_hours": 1.0, "alpha": 0.20, "max_payments": 300, "min_val_usd": 1.0},
        {"duration_hours": 1.0, "alpha": 0.40, "max_payments": 300, "min_val_usd": 1.0},
        {"duration_hours": 1.0, "alpha": 0.60, "max_payments": 300, "min_val_usd": 1.0},
        {"duration_hours": 1.0, "alpha": 1.00, "max_payments": 300, "min_val_usd": 1.0},
    ]
    try:
        stbl_results = run_real_data_sweep(
            load_stablecoin_payments,
            "Stanford SNAP Stablecoin ERC-20 (USDT/USDC/DAI)",
            stbl_configs,
        )
        all_results.extend(stbl_results)
    except FileNotFoundError as e:
        print(f"[SKIP] Stablecoin dataset not available locally: {e}")
        print("       Download token_transfers.csv from Stanford SNAP to enable this benchmark.")
        stbl_results = []

    print("\n")

    # --- Benchmark 2: Stanford SNAP Bitcoin OTC (Real Trust Network) ---
    btc_configs = [
        {"network": "otc", "alpha": 0.10, "max_payments": 300},
        {"network": "otc", "alpha": 0.20, "max_payments": 300},
        {"network": "otc", "alpha": 0.40, "max_payments": 300},
        {"network": "otc", "alpha": 0.60, "max_payments": 300},
        {"network": "otc", "alpha": 1.00, "max_payments": 300},
    ]
    btc_results = run_real_data_sweep(
        load_bitcoin_snap_payments,
        "Stanford SNAP Bitcoin-OTC Trust Network",
        btc_configs,
    )
    all_results.extend(btc_results)

    print("\n")

    # --- Benchmark 3: Stanford SNAP Bitcoin Alpha (Real Trust Network) ---
    alpha_configs = [
        {"network": "alpha", "alpha": 0.10, "max_payments": 300},
        {"network": "alpha", "alpha": 0.20, "max_payments": 300},
        {"network": "alpha", "alpha": 0.40, "max_payments": 300},
        {"network": "alpha", "alpha": 0.60, "max_payments": 300},
        {"network": "alpha", "alpha": 1.00, "max_payments": 300},
    ]
    alpha_results = run_real_data_sweep(
        load_bitcoin_snap_payments,
        "Stanford SNAP Bitcoin-Alpha Trust Network",
        alpha_configs,
    )
    all_results.extend(alpha_results)

    # Save results
    combined = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "note": "All results from REAL datasets only. No synthetic data used.",
        "stablecoin_benchmark": stbl_results,
        "bitcoin_otc_benchmark": btc_results,
        "bitcoin_alpha_benchmark": alpha_results,
    }

    results_dir = os.path.join(current_dir, "results")
    os.makedirs(results_dir, exist_ok=True)
    out_path = os.path.join(results_dir, "benchmark_results_snap.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2)

    print(f"\n[OK] Benchmark completed. Results: {out_path}")


if __name__ == "__main__":
    main()
