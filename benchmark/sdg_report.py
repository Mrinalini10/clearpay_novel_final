"""
benchmark/sdg_report.py
-----------------------
Generates a measurable SDG alignment report for ClearPay.

This script runs controlled experiments and prints a structured report
that maps measured algorithm outcomes to specific SDG 9 and SDG 8 targets.
No AWS calls are made.

Run from the repo root:
    python benchmark/sdg_report.py

Output:
    benchmark/results/sdg_report.txt   -- human-readable report
    benchmark/results/sdg_metrics.json -- machine-readable metrics
"""

import json
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# pyright: reportMissingImports=false
from common.liquidity import (  # type: ignore
    all_or_nothing,
    greedy_cumulative,
    is_feasible,
    reconsider_deferred,
    removal_heuristic,
    net_debit_positions,
)

# Inline the reconcile function to avoid import path issues.
# (recon.py lives in src/common/ -- same content reproduced here for portability)
from collections import Counter as _Counter

def reconcile(ledger, rows):
    """Compare ledger references and amounts against statement rows."""
    exceptions = []
    counts = _Counter(r.get("reference", "") for r in rows)
    first = {}
    for row in rows:
        first.setdefault(row.get("reference", ""), row)
    for ref, count in counts.items():
        if count > 1:
            exceptions.append({"type": "DUPLICATE", "reference": ref,
                                "detail": f"appears {count} times"})
    matched = 0
    for ref, row in first.items():
        try:
            amount = int(row["amount_paise"])
        except (KeyError, ValueError, TypeError):
            exceptions.append({"type": "MALFORMED_ROW", "reference": ref,
                                "detail": "bad amount"})
            continue
        if ref not in ledger:
            exceptions.append({"type": "MISSING_IN_LEDGER", "reference": ref,
                                "detail": f"statement={amount}"})
        elif amount != ledger[ref]:
            exceptions.append({"type": "AMOUNT_MISMATCH", "reference": ref,
                                "detail": f"ledger={ledger[ref]} statement={amount}"})
        else:
            matched += 1
    for ref in sorted(set(ledger) - set(first)):
        exceptions.append({"type": "MISSING_IN_STATEMENT", "reference": ref,
                            "detail": f"ledger={ledger[ref]}"})
    summary = {"ledger_count": len(ledger), "statement_rows": len(rows),
               "matched": matched,
               "exceptions": dict(_Counter(e["type"] for e in exceptions))}
    return {"summary": summary, "exceptions": exceptions}

OUTPUT_DIR = Path(__file__).parent / "results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SEED = 2026
N_BANKS = 8
REPORT_DATE = "2026-10-21"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_payments(n, seed, banks=N_BANKS, max_amount=500_000):
    rng = random.Random(seed)
    names = [f"B{i:02d}" for i in range(banks)]
    out = []
    for i in range(n):
        a, b = rng.sample(names, 2)
        out.append({
            "payment_id": f"p{seed}-{i}",
            "from": a,
            "to": b,
            "amount_paise": rng.randint(100, max_amount),
            "priority": rng.randint(0, 2),
            "created_at": f"2026-01-01T{i // 3600:02d}:{(i % 3600) // 60:02d}:{i % 60:02d}Z",
        })
    return out


def scale_liquidity(payments, fraction):
    gross = defaultdict(int)
    for p in payments:
        gross[p["from"]] += p["amount_paise"]
    return {b: int(v * fraction) for b, v in gross.items()}


def avg(lst):
    return round(sum(lst) / len(lst), 2) if lst else 0.0


# ---------------------------------------------------------------------------
# SDG 9.1 / 9.5 Metric 1 -- Settlement completion improvement
# Measures how much more payment value the proposed algorithm settles
# compared to the all-or-nothing baseline across tight liquidity conditions.
# ---------------------------------------------------------------------------

def measure_settlement_improvement():
    """
    SDG 9 Target 9.1: Reliable, resilient infrastructure.
    SDG 9 Target 9.5: Technological innovation.

    Metric: Settlement completion rate improvement of the removal heuristic
    vs all-or-nothing at 30%, 50%, and 70% liquidity levels.
    """
    levels = [0.3, 0.5, 0.7]
    improvements = []
    absolute_settled = {"all_or_nothing": [], "removal_heuristic": []}

    for seed in range(20):
        payments = make_payments(200, seed=SEED + seed)
        for level in levels:
            liq = scale_liquidity(payments, level)
            aon = all_or_nothing(payments, liq)["settled_pct"]
            rh = removal_heuristic(payments, liq)["settled_pct"]
            improvement = rh - aon
            improvements.append(improvement)
            absolute_settled["all_or_nothing"].append(aon)
            absolute_settled["removal_heuristic"].append(rh)

    return {
        "metric": "settlement_completion_improvement",
        "sdg_target": "9.1, 9.5",
        "description": (
            "Average improvement in settled payment value (%) "
            "when using the removal heuristic vs all-or-nothing baseline "
            "at 30%, 50%, and 70% liquidity levels."
        ),
        "avg_improvement_pct_points": avg(improvements),
        "avg_aon_settled_pct": avg(absolute_settled["all_or_nothing"]),
        "avg_rh_settled_pct": avg(absolute_settled["removal_heuristic"]),
        "trials": len(improvements),
    }


# ---------------------------------------------------------------------------
# SDG 9.1 Metric 2 -- Multi-window deferred payment recovery
# Measures the proportion of payments that deferred in window 1 can be
# settled in window 2 after a liquidity top-up.
# ---------------------------------------------------------------------------

def measure_deferred_recovery():
    """
    SDG 9 Target 9.1: Resilient infrastructure that defers rather than drops.

    Metric: Proportion of W1-deferred payments that successfully settle in W2.
    """
    w2_recovery_rates = []

    for seed in range(20):
        payments = make_payments(100, seed=SEED + seed)
        liq_w1 = scale_liquidity(payments, 0.3)  # tight
        r_w1 = removal_heuristic(payments, liq_w1)

        if not r_w1["deferred_ids"]:
            continue

        deferred = [p for p in payments if p["payment_id"] in r_w1["deferred_ids"]]
        liq_w2 = scale_liquidity(deferred, 1.2)  # ample for W2
        r_w2 = reconsider_deferred(deferred, liq_w2)

        rate = 100.0 * r_w2["selected_count"] / len(deferred)
        w2_recovery_rates.append(rate)

    return {
        "metric": "deferred_payment_w2_recovery",
        "sdg_target": "9.1",
        "description": (
            "Average % of payments deferred in W1 (30% liquidity) "
            "that successfully settle in W2 (120% liquidity top-up)."
        ),
        "avg_w2_recovery_pct": avg(w2_recovery_rates),
        "trials": len(w2_recovery_rates),
    }


# ---------------------------------------------------------------------------
# SDG 9.5 Metric 3 -- Liquidity efficiency
# Measures how much net liquidity is consumed per unit of settled value.
# Lower is better -- the algorithm does more with less liquidity.
# ---------------------------------------------------------------------------

def measure_liquidity_efficiency():
    """
    SDG 9 Target 9.5: Innovation in financial processing efficiency.

    Metric: Net liquidity consumed per 1,000 paise settled.
    """
    results = {"all_or_nothing": [], "greedy_cumulative": [], "removal_heuristic": []}

    for seed in range(20):
        payments = make_payments(200, seed=SEED + seed)
        liq = scale_liquidity(payments, 0.5)
        for name, fn in [
            ("all_or_nothing", all_or_nothing),
            ("greedy_cumulative", greedy_cumulative),
            ("removal_heuristic", removal_heuristic),
        ]:
            r = fn(payments, liq)
            if r["settled_value_paise"] > 0:
                efficiency = r["net_liquidity_used_paise"] / (r["settled_value_paise"] / 1000)
                results[name].append(efficiency)

    return {
        "metric": "liquidity_efficiency",
        "sdg_target": "9.5",
        "description": (
            "Net liquidity consumed per 1,000 paise settled "
            "(lower = more efficient). Tested at 50% liquidity."
        ),
        "avg_efficiency_paise_per_1k": {
            name: avg(vals) for name, vals in results.items()
        },
        "trials": 20,
    }


# ---------------------------------------------------------------------------
# SDG 8.10 Metric 4 -- Reconciliation accuracy
# Measures how accurately the system detects injected discrepancies.
# ---------------------------------------------------------------------------

def measure_reconciliation_accuracy():
    """
    SDG 8 Target 8.10: Strengthen financial institutions.

    Metric: Detection rate for injected reconciliation discrepancies.
    """
    rng = random.Random(SEED)
    N_RECON = 100  # simulated ledger entries

    # Build a clean ledger.
    ledger = {f"ref-{i:04d}": rng.randint(1000, 500_000) for i in range(N_RECON)}

    # Build a matching statement, then inject controlled discrepancies.
    rows = [
        {"reference": ref, "amount_paise": amt}
        for ref, amt in ledger.items()
    ]

    # Inject 1: remove 5 references (MISSING_IN_STATEMENT).
    missing_refs = rng.sample(list(ledger.keys()), 5)
    rows = [r for r in rows if r["reference"] not in missing_refs]

    # Inject 2: add 3 rows not in ledger (MISSING_IN_LEDGER).
    ghost_refs = [f"ghost-{i}" for i in range(3)]
    for ref in ghost_refs:
        rows.append({"reference": ref, "amount_paise": rng.randint(1000, 50_000)})

    # Inject 3: corrupt amount for 4 rows (AMOUNT_MISMATCH).
    mismatch_refs = rng.sample(
        [r["reference"] for r in rows if r["reference"] in ledger], 4
    )
    for row in rows:
        if row["reference"] in mismatch_refs:
            row["amount_paise"] = row["amount_paise"] + 1  # off by 1 paise

    # Inject 4: duplicate 2 references (DUPLICATE).
    dup_refs = rng.sample(
        [r["reference"] for r in rows if r["reference"] in ledger], 2
    )
    for ref in dup_refs:
        orig = next(r for r in rows if r["reference"] == ref)
        rows.append(dict(orig))

    total_injected = len(missing_refs) + len(ghost_refs) + len(mismatch_refs) + len(dup_refs)
    result = reconcile(ledger, rows)

    total_detected = sum(result["summary"]["exceptions"].values())
    detection_rate = 100.0 * total_detected / total_injected if total_injected else 0.0

    return {
        "metric": "reconciliation_detection_accuracy",
        "sdg_target": "8.10",
        "description": (
            "Proportion of deliberately injected reconciliation discrepancies "
            "detected by the automated reconciliation module."
        ),
        "injected_discrepancies": total_injected,
        "detected_discrepancies": total_detected,
        "detection_rate_pct": round(detection_rate, 2),
        "exception_breakdown": result["summary"]["exceptions"],
    }


# ---------------------------------------------------------------------------
# SDG 8.2 Metric 5 -- Processing throughput
# ---------------------------------------------------------------------------

def measure_processing_throughput():
    """
    SDG 8 Target 8.2: Productivity through technological upgrading.

    Metric: Payments evaluated per second by the removal heuristic.
    """
    sizes = [100, 500, 1000, 5000, 10_000]
    throughputs = []

    for n in sizes:
        payments = make_payments(n, seed=SEED)
        liq = scale_liquidity(payments, 0.5)
        t0 = time.perf_counter()
        removal_heuristic(payments, liq)
        elapsed = time.perf_counter() - t0
        tput = n / elapsed if elapsed > 0 else float("inf")
        throughputs.append({"n": n, "payments_per_second": round(tput, 0)})

    return {
        "metric": "processing_throughput",
        "sdg_target": "8.2",
        "description": (
            "Payments evaluated per second by the removal heuristic "
            "on local hardware (no AWS)."
        ),
        "throughput_by_size": throughputs,
    }


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------

def format_report(metrics: list) -> str:
    lines = []
    lines.append("-" * 70)
    lines.append("ClearPay -- SDG Alignment Report")
    lines.append(f"Generated : {REPORT_DATE}")
    lines.append(f"Platform  : Local Python (no AWS calls)")
    lines.append("=" * 70)
    lines.append("")
    lines.append("DISCLAIMER: ClearPay is a simulated prototype. The metrics")
    lines.append("below demonstrate technical contributions relevant to the")
    lines.append("stated SDG targets. They do not measure real-world banking")
    lines.append("outcomes, GDP impact, or financial inclusion.")
    lines.append("")

    sdg_sections = [
        ("SDG 9 -- Industry, Innovation and Infrastructure",
         "9.1", "Reliable and resilient digital financial infrastructure"),
        ("SDG 9 -- Industry, Innovation and Infrastructure",
         "9.5", "Technological innovation and enhancement of capabilities"),
        ("SDG 8 -- Decent Work and Economic Growth",
         "8.10", "Strengthen financial institutions"),
        ("SDG 8 -- Decent Work and Economic Growth",
         "8.2", "Productivity through technological upgrading"),
    ]

    seen_sdg = set()
    for sdg_title, target, target_desc in sdg_sections:
        if sdg_title not in seen_sdg:
            lines.append("-" * 70)
            lines.append(sdg_title)
            seen_sdg.add(sdg_title)
        lines.append(f"  Target {target}: {target_desc}")

    lines.append("")
    lines.append("-" * 70)
    lines.append("MEASURED INDICATORS")
    lines.append("-" * 70)
    lines.append("")

    for m in metrics:
        lines.append(f"[{m['metric']}]")
        lines.append(f"  SDG target : {m['sdg_target']}")
        lines.append(f"  Description: {m['description']}")

        # Format specific metrics.
        if m["metric"] == "settlement_completion_improvement":
            lines.append(f"  All-or-Nothing avg settled : {m['avg_aon_settled_pct']:.1f}%")
            lines.append(f"  Removal Heuristic avg settled: {m['avg_rh_settled_pct']:.1f}%")
            lines.append(f"  Average improvement        : +{m['avg_improvement_pct_points']:.1f} percentage points")
            lines.append(f"  Trials                     : {m['trials']}")

        elif m["metric"] == "deferred_payment_w2_recovery":
            lines.append(f"  W2 recovery rate           : {m['avg_w2_recovery_pct']:.1f}%")
            lines.append(f"  Trials                     : {m['trials']}")

        elif m["metric"] == "liquidity_efficiency":
            for algo, val in m["avg_efficiency_paise_per_1k"].items():
                lines.append(f"  {algo:<28}: {val:.2f} paise per 1,000 settled")

        elif m["metric"] == "reconciliation_detection_accuracy":
            lines.append(f"  Injected discrepancies     : {m['injected_discrepancies']}")
            lines.append(f"  Detected                   : {m['detected_discrepancies']}")
            lines.append(f"  Detection rate             : {m['detection_rate_pct']:.1f}%")
            for exc_type, count in m["exception_breakdown"].items():
                lines.append(f"    {exc_type:<30}: {count}")

        elif m["metric"] == "processing_throughput":
            for entry in m["throughput_by_size"]:
                lines.append(
                    f"  n={entry['n']:6d} payments : "
                    f"{entry['payments_per_second']:,.0f} payments/sec"
                )

        lines.append("")

    lines.append("-" * 70)
    lines.append("SUMMARY")
    lines.append("-" * 70)
    lines.append("")

    # Pull key numbers for summary.
    imp_m = next(m for m in metrics if m["metric"] == "settlement_completion_improvement")
    rec_m = next(m for m in metrics if m["metric"] == "deferred_payment_w2_recovery")
    recon_m = next(m for m in metrics if m["metric"] == "reconciliation_detection_accuracy")

    lines.append(
        f"1. The removal heuristic settles {imp_m['avg_improvement_pct_points']:.1f}pp more payment value"
    )
    lines.append("   than all-or-nothing under constrained liquidity (SDG 9.1, 9.5).")
    lines.append(
        f"2. {rec_m['avg_w2_recovery_pct']:.1f}% of deferred payments can settle in a subsequent"
    )
    lines.append("   window when liquidity is replenished (SDG 9.1 -- resilience).")
    lines.append(
        f"3. Automated reconciliation detects {recon_m['detection_rate_pct']:.1f}% of injected"
    )
    lines.append("   discrepancies without manual review (SDG 8.10).")
    lines.append("")
    lines.append("All numbers are reproducible: set SEED=2026 in sdg_report.py.")
    lines.append("=" * 70)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Running SDG metric measurements ...")
    metrics = []

    print("  1/5 Settlement improvement ...")
    metrics.append(measure_settlement_improvement())

    print("  2/5 Deferred recovery ...")
    metrics.append(measure_deferred_recovery())

    print("  3/5 Liquidity efficiency ...")
    metrics.append(measure_liquidity_efficiency())

    print("  4/5 Reconciliation accuracy ...")
    metrics.append(measure_reconciliation_accuracy())

    print("  5/5 Processing throughput ...")
    metrics.append(measure_processing_throughput())

    report_text = format_report(metrics)
    print("\n" + report_text)

    # Save text report.
    txt_out = OUTPUT_DIR / "sdg_report.txt"
    with open(txt_out, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"\nSaved: {txt_out}")

    # Save JSON metrics.
    json_out = OUTPUT_DIR / "sdg_metrics.json"
    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    print(f"Saved: {json_out}")


if __name__ == "__main__":
    main()
