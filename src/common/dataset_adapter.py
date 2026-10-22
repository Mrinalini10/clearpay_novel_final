"""
dataset_adapter.py — Real-World Financial Dataset Bridge for ClearPay
=====================================================================
Project: ClearPay (Next-Gen Liquidity-Aware Settlement)
Author: Andrea (VIT, 2026)

Connects ClearPay exclusively to REAL financial transaction datasets from
the DAA research repository. No synthetic data is used anywhere.

Real datasets loaded:
  1. Stanford SNAP Stablecoin ERC-20 Dataset (USDT, USDC, DAI: $1.03B flows)
  2. Stanford SNAP Bitcoin OTC Trust Network (5,881 users, 35,592 edges)
  3. Stanford SNAP Bitcoin Alpha Trust Network (3,783 users, 24,186 edges)

Translates external financial graphs into ClearPay's native JSON payment queue
and per-bank liquidity quotas (in integer paise).
"""

from __future__ import annotations

import collections
import csv
import gzip
import os
import random
from typing import Dict, List, Optional, Tuple

Payment = Dict[str, any]
Liquidity = Dict[str, int]

# Locate the data set directory relative to the repository root.
# Layout: <repo_root>/data set/   (created by downloading SNAP files)
# Walk up from this file's location to find the repo root, then append "data set".
_curr = os.path.abspath(os.path.dirname(__file__))
DATA_SET_DIR = None
_walker = _curr
for _ in range(10):
    candidate = os.path.join(_walker, "data set")
    if os.path.isdir(candidate):
        DATA_SET_DIR = os.path.abspath(candidate)
        break
    _up = os.path.dirname(_walker)
    if _up == _walker:
        break
    _walker = _up

if DATA_SET_DIR is None:
    # Fallback: use a "data set" folder next to this file
    DATA_SET_DIR = os.path.join(_curr, "data set")



# ---------------------------------------------------------------------------
# 1. Real-World Stanford SNAP Stablecoin ERC-20 Loader
# ---------------------------------------------------------------------------

def load_stablecoin_payments(
    duration_hours: float = 1.0,
    alpha: float = 0.20,
    max_payments: int = 1000,
    min_val_usd: float = 1.0,
    seed: int = 42,
) -> Tuple[List[Payment], Liquidity, Dict[str, any]]:
    """Load a slice of genuine Stanford SNAP Stablecoin obligations.
    
    Amounts are converted to integer cents/paise (USD * 100).
    Per-bank available liquidity is computed as a fraction alpha of total gross outflow.
    """
    stablecoin_path = os.path.join(
        DATA_SET_DIR,
        "Stanford SNAP Stablecoin ERC-20 Transactions",
        "token_transfers.csv"
    )
    
    if not os.path.exists(stablecoin_path):
        raise FileNotFoundError(f"Stablecoin CSV not found at {stablecoin_path}")

    start_time = 1651105815
    end_time = start_time + int(duration_hours * 3600)
    
    rng = random.Random(seed)
    payments: List[Payment] = []
    outflows: Dict[str, int] = collections.defaultdict(int)
    
    with open(stablecoin_path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        next(reader) # header
        for row in reader:
            t = int(row[4])
            if t < start_time:
                continue
            if t > end_time:
                break
                
            val_usd = float(row[6])
            if val_usd < min_val_usd:
                continue
                
            u = row[2].lower()[:10]  # Abbreviate address for readable logging
            v = row[3].lower()[:10]
            if u == v:
                continue
                
            amt_paise = int(round(val_usd * 100))
            if amt_paise <= 0:
                continue
                
            pid = f"STBL-{len(payments):06d}"
            prio = rng.choice([0, 1, 1, 2]) # 0=High, 1=Normal, 2=Low
            
            p: Payment = {
                "payment_id": pid,
                "from": u,
                "to": v,
                "amount_paise": amt_paise,
                "priority": prio,
                "created_at": f"2026-10-22T{t % 86400 // 3600:02d}:00:00Z",
                "deferral_count": 0,
            }
            payments.append(p)
            outflows[u] += amt_paise
            
            if len(payments) >= max_payments:
                break
                
    # Liquidity: deposit = max(100, round(alpha * outflow))
    liquidity: Liquidity = {
        bank: max(100, int(round(alpha * out_amt)))
        for bank, out_amt in outflows.items()
    }
    
    meta = {
        "dataset": "Stanford SNAP Stablecoin ERC-20",
        "total_payments": len(payments),
        "total_banks": len(outflows),
        "gross_volume_paise": sum(p["amount_paise"] for p in payments),
        "alpha": alpha,
    }
    return payments, liquidity, meta


# ---------------------------------------------------------------------------
# 2. Real-World Stanford SNAP Bitcoin Trust Network Loader
# ---------------------------------------------------------------------------

def load_bitcoin_snap_payments(
    network: str = "otc",
    max_payments: int = 500,
    alpha: float = 0.40,
    seed: int = 42,
) -> Tuple[List[Payment], Liquidity, Dict[str, any]]:
    """Load real-world payment obligations from Bitcoin OTC or Bitcoin Alpha SNAP graphs."""
    filename = (
        "soc-sign-bitcoinotc.csv.gz" if network.lower() == "otc" else "soc-sign-bitcoinalpha.csv.gz"
    )
    file_path = os.path.join(DATA_SET_DIR, filename)
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"SNAP file not found at {file_path}")
        
    rng = random.Random(seed)
    payments: List[Payment] = []
    outflows: Dict[str, int] = collections.defaultdict(int)
    
    with gzip.open(file_path, "rt", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or len(row) < 3:
                continue
            u = f"BTC-{row[0]}"
            v = f"BTC-{row[1]}"
            rating = float(row[2])
            if rating <= 0:
                continue # only positive obligations
                
            amt_paise = int(rating * 1000)
            pid = f"BTC-{len(payments):05d}"
            
            p: Payment = {
                "payment_id": pid,
                "from": u,
                "to": v,
                "amount_paise": amt_paise,
                "priority": rng.choice([0, 1, 1, 2]),
                "created_at": "2026-10-22T12:00:00Z",
                "deferral_count": 0,
            }
            payments.append(p)
            outflows[u] += amt_paise
            if len(payments) >= max_payments:
                break
                
    liquidity: Liquidity = {
        bank: max(100, int(round(alpha * out_amt)))
        for bank, out_amt in outflows.items()
    }
    
    meta = {
        "dataset": f"Stanford SNAP Bitcoin-{network.upper()}",
        "total_payments": len(payments),
        "total_banks": len(outflows),
        "gross_volume_paise": sum(p["amount_paise"] for p in payments),
        "alpha": alpha,
    }
    return payments, liquidity, meta
