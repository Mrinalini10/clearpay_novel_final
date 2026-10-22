import random

from common.netting import (
    analyze,
    bilateral,
    hub_spoke,
    multilateral,
    net_positions,
    positions_from_transfers,
)


def make_payments(n, seed=1, banks=12):
    rng = random.Random(seed)
    names = [f"B{i:02d}" for i in range(banks)]
    out = []

    for i in range(n):
        a, b = rng.sample(names, 2)
        out.append({
            "payment_id": str(i),
            "from": a,
            "to": b,
            "amount_paise": rng.randint(100, 5_000_000),
        })

    return out


def test_positions_sum_to_zero():
    assert sum(net_positions(make_payments(500)).values()) == 0


def test_every_strategy_preserves_positions():
    payments = make_payments(2000, seed=7)
    positions = net_positions(payments)

    for transfers in (
        bilateral(payments),
        multilateral(positions),
        hub_spoke(positions, "B00"),
    ):
        assert positions_from_transfers(transfers) == positions


def test_multilateral_at_most_n_minus_1():
    positions = net_positions(make_payments(3000, seed=3))
    assert len(multilateral(positions)) <= len(positions) - 1


def test_hub_spoke_one_transfer_per_participant():
    positions = net_positions(make_payments(3000, seed=4))
    assert len(hub_spoke(positions, "B00")) <= len(positions)


def test_netting_reduces_transfers():
    result = analyze(make_payments(10_000, seed=11))
    assert (
        result["metrics"]["multilateral"]["transfers"]
        < result["metrics"]["gross"]["transfers"]
    )


def test_tiny_example():
    payments = [
        {"from": "A", "to": "B", "amount_paise": 100},
        {"from": "B", "to": "C", "amount_paise": 80},
        {"from": "C", "to": "A", "amount_paise": 30},
    ]

    assert net_positions(payments) == {"A": -70, "B": 20, "C": 50}
    assert len(multilateral(net_positions(payments))) == 2
