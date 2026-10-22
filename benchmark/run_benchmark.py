# pyright: reportMissingImports=false
# type: ignore
"""
benchmark/run_benchmark.py
--------------------------
Local benchmark comparing all four ClearPay settlement algorithms across
varying liquidity levels.  No AWS calls are made.

Run from the repo root:
    python benchmark/run_benchmark.py

Outputs
-------
  benchmark/results/benchmark_results.json   — raw numbers
  benchmark/results/settled_value.png        — settled value % vs liquidity %
  benchmark/results/settled_count.png        — settled payment count % vs liquidity %
  benchmark/results/exec_time.png            — execution time vs batch size
  benchmark/results/optimality_gap.png       — heuristic gap vs MILP optimum (tiny batches)

Dependencies: numpy, matplotlib (pip install numpy matplotlib)
Optional:      scipy (pip install scipy) — enables exact MILP comparison
"""

import json
import os
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

# Robust path resolution for local execution and IDE imports
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, "..", "src"))
for p in (src_dir, current_dir):
    if p not in sys.path:
        sys.path.insert(0, p)

from common.liquidity import (
    all_or_nothing,
    compare_all,
    exact_milp,
    greedy_cumulative,
    removal_heuristic,
)

# Safe matplotlib import for headless rendering & IDE static analysis
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    plt = None
    HAS_MATPLOTLIB = False


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SEED = 42
N_PAYMENTS = 200          # main experiment batch size
N_BANKS = 8
LIQUIDITY_LEVELS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2]
SCALING_SIZES = [10, 25, 50, 100, 200, 500, 1000, 2000, 5000, 10_000]
MILP_MAX_N = 18           # only run MILP on batches ≤ this size
N_SEEDS = 10              # repeat each experiment with different seeds

OUTPUT_DIR = Path(__file__).parent / "results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Data generation
# ---------------------------------------------------------------------------

def make_payments(n, seed, banks=N_BANKS, max_amount=500_000):
    rng = random.Random(seed)
    names = [f"B{i:02d}" for i in range(banks)]
    out = []
    for i in range(n):
        a, b = rng.sample(names, 2)
        out.append({
            "payment_id": f"{seed}-{i}",
            "from": a,
            "to": b,
            "amount_paise": rng.randint(100, max_amount),
            "priority": rng.randint(0, 2),
            "created_at": f"2026-01-01T{i // 3600:02d}:{(i % 3600) // 60:02d}:{i % 60:02d}Z",
        })
    return out


def gross_outflow(payments):
    """Return {bank: total_paise_sent} across the batch."""
    out = defaultdict(int)
    for p in payments:
        out[p["from"]] += p["amount_paise"]
    return dict(out)


def scale_liquidity(payments, fraction):
    """Each bank gets fraction × its gross outflow as available liquidity."""
    return {bank: int(v * fraction) for bank, v in gross_outflow(payments).items()}


# ---------------------------------------------------------------------------
# Experiment 1 — Settled value across liquidity levels
# ---------------------------------------------------------------------------

def experiment_liquidity_levels():
    print("Experiment 1: liquidity levels ...")
    algos = {
        "all_or_nothing": all_or_nothing,
        "greedy_cumulative": greedy_cumulative,
        "removal_heuristic": removal_heuristic,
    }

    # {algo: {level: [settled_pct, ...]}}
    results = {a: {l: [] for l in LIQUIDITY_LEVELS} for a in algos}
    count_results = {a: {l: [] for l in LIQUIDITY_LEVELS} for a in algos}

    for seed in range(N_SEEDS):
        payments = make_payments(N_PAYMENTS, seed=SEED + seed)
        for level in LIQUIDITY_LEVELS:
            liq = scale_liquidity(payments, level)
            for name, fn in algos.items():
                r = fn(payments, liq)
                results[name][level].append(r["settled_pct"])
                total = len(payments)
                count_pct = 100.0 * r["selected_count"] / total if total else 0.0
                count_results[name][level].append(count_pct)

    # Average across seeds.
    avg_value = {a: {l: sum(v) / len(v) for l, v in lv.items()}
                 for a, lv in results.items()}
    avg_count = {a: {l: sum(v) / len(v) for l, v in lv.items()}
                 for a, lv in count_results.items()}

    return avg_value, avg_count


# ---------------------------------------------------------------------------
# Experiment 2 — Execution time scaling
# ---------------------------------------------------------------------------

def experiment_scaling():
    print("Experiment 2: execution time scaling ...")
    timing = {
        "greedy_cumulative": {},
        "removal_heuristic": {},
    }
    for n in SCALING_SIZES:
        payments = make_payments(n, seed=SEED, banks=max(4, N_BANKS))
        liq = scale_liquidity(payments, 0.5)
        for name, fn in [
            ("greedy_cumulative", greedy_cumulative),
            ("removal_heuristic", removal_heuristic),
        ]:
            t0 = time.perf_counter()
            fn(payments, liq)
            timing[name][n] = (time.perf_counter() - t0) * 1000  # ms
        print(f"  n={n:6d}  rh={timing['removal_heuristic'][n]:.1f}ms  "
              f"greedy={timing['greedy_cumulative'][n]:.1f}ms")
    return timing


# ---------------------------------------------------------------------------
# Experiment 3 — Optimality gap (MILP vs removal_heuristic)
# ---------------------------------------------------------------------------

def experiment_optimality_gap():
    print("Experiment 3: optimality gap (MILP vs heuristic) ...")
    try:
        import scipy  # noqa: F401
    except ImportError:
        print("  scipy not installed — skipping MILP experiment.")
        return None

    gaps = []
    for seed in range(20):
        n = min(MILP_MAX_N, 15)
        payments = make_payments(n, seed=seed * 7 + 1, banks=4, max_amount=10_000)
        liq = scale_liquidity(payments, 0.5)

        milp_r = exact_milp(payments, liq)
        rh_r = removal_heuristic(payments, liq)

        opt = milp_r["settled_value_paise"]
        heur = rh_r["settled_value_paise"]
        gap = (opt - heur) / opt * 100 if opt > 0 else 0.0
        gaps.append({
            "seed": seed,
            "n_payments": n,
            "milp_value": opt,
            "heuristic_value": heur,
            "gap_pct": gap,
        })
        print(f"  seed={seed:2d}  MILP={opt:8d}  heuristic={heur:8d}  gap={gap:5.1f}%")

    avg_gap = sum(g["gap_pct"] for g in gaps) / len(gaps) if gaps else 0.0
    print(f"  Average optimality gap: {avg_gap:.2f}%")
    return gaps


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def plot_settled_value(avg_value):
    if not HAS_MATPLOTLIB or plt is None:
        print("matplotlib not installed — skipping charts.")
        return

    levels_pct = [l * 100 for l in LIQUIDITY_LEVELS]
    colours = {
        "all_or_nothing": "#d62728",
        "greedy_cumulative": "#ff7f0e",
        "removal_heuristic": "#2ca02c",
    }
    labels = {
        "all_or_nothing": "All-or-Nothing (baseline)",
        "greedy_cumulative": "Greedy Cumulative",
        "removal_heuristic": "Removal Heuristic (proposed)",
    }
    markers = {
        "all_or_nothing": "s",
        "greedy_cumulative": "^",
        "removal_heuristic": "o",
    }

    fig, ax = plt.subplots(figsize=(9, 5))
    for algo, avg in avg_value.items():
        values = [avg[l] for l in LIQUIDITY_LEVELS]
        ax.plot(
            levels_pct, values,
            label=labels[algo],
            color=colours[algo],
            marker=markers[algo],
            linewidth=2,
            markersize=6,
        )

    ax.set_xlabel("Available Liquidity (% of gross outflow)", fontsize=12)
    ax.set_ylabel("Settled Payment Value (%)", fontsize=12)
    ax.set_title(
        f"ClearPay: Settled Value by Algorithm\n"
        f"({N_PAYMENTS} payments, {N_BANKS} banks, avg of {N_SEEDS} seeds)",
        fontsize=12,
    )
    ax.legend(fontsize=10)
    ax.set_xlim(0, 125)
    ax.set_ylim(-5, 105)
    ax.grid(True, linestyle="--", alpha=0.5)
    fig.tight_layout()
    out = OUTPUT_DIR / "settled_value.png"
    fig.savefig(out, dpi=150)
    print(f"  Saved: {out}")
    plt.close(fig)


def plot_settled_count(avg_count):
    if not HAS_MATPLOTLIB or plt is None:
        return

    levels_pct = [l * 100 for l in LIQUIDITY_LEVELS]
    colours = {
        "all_or_nothing": "#d62728",
        "greedy_cumulative": "#ff7f0e",
        "removal_heuristic": "#2ca02c",
    }
    labels = {
        "all_or_nothing": "All-or-Nothing",
        "greedy_cumulative": "Greedy Cumulative",
        "removal_heuristic": "Removal Heuristic (proposed)",
    }

    fig, ax = plt.subplots(figsize=(9, 5))
    for algo, avg in avg_count.items():
        values = [avg[l] for l in LIQUIDITY_LEVELS]
        ax.plot(levels_pct, values, label=labels[algo], linewidth=2)

    ax.set_xlabel("Available Liquidity (% of gross outflow)", fontsize=12)
    ax.set_ylabel("Settled Payment Count (%)", fontsize=12)
    ax.set_title(
        f"ClearPay: Settled Count by Algorithm\n"
        f"({N_PAYMENTS} payments, {N_BANKS} banks, avg of {N_SEEDS} seeds)",
        fontsize=12,
    )
    ax.legend(fontsize=10)
    ax.set_xlim(0, 125)
    ax.set_ylim(-5, 105)
    ax.grid(True, linestyle="--", alpha=0.5)
    fig.tight_layout()
    out = OUTPUT_DIR / "settled_count.png"
    fig.savefig(out, dpi=150)
    print(f"  Saved: {out}")
    plt.close(fig)


def plot_execution_time(timing):
    if not HAS_MATPLOTLIB or plt is None:
        return

    fig, ax = plt.subplots(figsize=(9, 5))
    colours = {"greedy_cumulative": "#ff7f0e", "removal_heuristic": "#2ca02c"}
    labels = {
        "greedy_cumulative": "Greedy Cumulative",
        "removal_heuristic": "Removal Heuristic (proposed)",
    }
    for algo, data in timing.items():
        xs = sorted(data.keys())
        ys = [data[x] for x in xs]
        ax.plot(xs, ys, label=labels[algo], color=colours[algo], marker="o", linewidth=2)

    ax.set_xlabel("Batch Size (number of payments)", fontsize=12)
    ax.set_ylabel("Execution Time (ms)", fontsize=12)
    ax.set_title("ClearPay: Algorithm Execution Time vs Batch Size", fontsize=12)
    ax.legend(fontsize=10)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.grid(True, linestyle="--", alpha=0.5, which="both")
    fig.tight_layout()
    out = OUTPUT_DIR / "exec_time.png"
    fig.savefig(out, dpi=150)
    print(f"  Saved: {out}")
    plt.close(fig)


def plot_optimality_gap(gaps):
    if gaps is None or not HAS_MATPLOTLIB or plt is None:
        return

    seeds = [g["seed"] for g in gaps]
    gap_pcts = [g["gap_pct"] for g in gaps]
    avg_gap = sum(gap_pcts) / len(gap_pcts) if gap_pcts else 0.0

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(seeds, gap_pcts, color="#2ca02c", alpha=0.8, label="Gap per trial")
    ax.axhline(avg_gap, color="#d62728", linestyle="--", linewidth=2,
               label=f"Mean gap = {avg_gap:.1f}%")
    ax.set_xlabel("Trial (random seed)", fontsize=12)
    ax.set_ylabel("Optimality Gap (%)", fontsize=12)
    ax.set_title(
        "ClearPay: Removal Heuristic vs MILP Optimum\n"
        f"(n≤{MILP_MAX_N} payments, liquidity=50% of gross outflow)",
        fontsize=12,
    )
    ax.legend(fontsize=10)
    ax.set_ylim(bottom=0)
    ax.grid(True, linestyle="--", alpha=0.5, axis="y")
    fig.tight_layout()
    out = OUTPUT_DIR / "optimality_gap.png"
    fig.savefig(out, dpi=150)
    print(f"  Saved: {out}")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------

def print_summary_table(avg_value):
    print("\n" + "=" * 60)
    print("Settled Value % (averaged across seeds)")
    print("=" * 60)
    header = f"{'Liquidity%':>12}" + "".join(
        f"{'AoN':>10}{'Greedy':>10}{'Removal':>10}"
    )
    print(header)
    print("-" * 42)
    for l in LIQUIDITY_LEVELS:
        aon = avg_value["all_or_nothing"][l]
        grdy = avg_value["greedy_cumulative"][l]
        rh = avg_value["removal_heuristic"][l]
        print(f"{l*100:>11.0f}%{aon:>10.1f}{grdy:>10.1f}{rh:>10.1f}")
    print()


# ---------------------------------------------------------------------------
# Save raw results to JSON
# ---------------------------------------------------------------------------

def save_results(avg_value, avg_count, timing, gaps):
    data = {
        "config": {
            "seed": SEED,
            "n_payments": N_PAYMENTS,
            "n_banks": N_BANKS,
            "n_seeds": N_SEEDS,
            "liquidity_levels": LIQUIDITY_LEVELS,
        },
        "settled_value_pct": {
            algo: {str(l): v for l, v in lv.items()}
            for algo, lv in avg_value.items()
        },
        "settled_count_pct": {
            algo: {str(l): v for l, v in lv.items()}
            for algo, lv in avg_count.items()
        },
        "exec_time_ms": {
            algo: {str(n): ms for n, ms in data.items()}
            for algo, data in timing.items()
        },
        "optimality_gaps": gaps or [],
    }
    out = OUTPUT_DIR / "benchmark_results.json"
    with open(out, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  Saved: {out}")
    return data


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("ClearPay Local Benchmark")
    print(f"  Payments per run : {N_PAYMENTS}")
    print(f"  Banks            : {N_BANKS}")
    print(f"  Seeds averaged   : {N_SEEDS}")
    print(f"  Liquidity levels : {[f'{l*100:.0f}%' for l in LIQUIDITY_LEVELS]}")
    print("=" * 60)

    t_total = time.perf_counter()

    avg_value, avg_count = experiment_liquidity_levels()
    timing = experiment_scaling()
    gaps = experiment_optimality_gap()

    print_summary_table(avg_value)

    print("Saving results ...")
    save_results(avg_value, avg_count, timing, gaps)

    print("Plotting ...")
    plot_settled_value(avg_value)
    plot_settled_count(avg_count)
    plot_execution_time(timing)
    plot_optimality_gap(gaps)

    print(f"\nDone in {time.perf_counter() - t_total:.1f}s")
    print(f"Charts and data in: {OUTPUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
