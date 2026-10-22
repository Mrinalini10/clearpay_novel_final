import heapq
from collections import defaultdict


def net_positions(payments):
    """Positive = net receiver; negative = net payer."""
    pos = defaultdict(int)

    for p in payments:
        pos[p["from"]] -= p["amount_paise"]
        pos[p["to"]] += p["amount_paise"]

    return {k: v for k, v in pos.items() if v != 0}


def positions_from_transfers(transfers):
    pos = defaultdict(int)

    for t in transfers:
        pos[t["from"]] -= t["amount_paise"]
        pos[t["to"]] += t["amount_paise"]

    return {k: v for k, v in pos.items() if v != 0}


def bilateral(payments):
    """Net each pair of participants into one transfer."""
    pair = defaultdict(int)

    for p in payments:
        a, b, amt = p["from"], p["to"], p["amount_paise"]

        if a < b:
            pair[(a, b)] += amt
        else:
            pair[(b, a)] -= amt

    out = []

    for (lo, hi), value in pair.items():
        if value > 0:
            out.append({
                "from": lo,
                "to": hi,
                "amount_paise": value,
            })
        elif value < 0:
            out.append({
                "from": hi,
                "to": lo,
                "amount_paise": -value,
            })

    return out


def multilateral(positions):
    """Greedily match the largest debts with the largest credits."""
    debtors = [
        (value, account)
        for account, value in positions.items()
        if value < 0
    ]
    creditors = [
        (-value, account)
        for account, value in positions.items()
        if value > 0
    ]

    heapq.heapify(debtors)
    heapq.heapify(creditors)
    out = []

    while debtors and creditors:
        debt, debtor = heapq.heappop(debtors)
        credit, creditor = heapq.heappop(creditors)

        debt = -debt
        credit = -credit
        amount = min(debt, credit)

        out.append({
            "from": debtor,
            "to": creditor,
            "amount_paise": amount,
        })

        if debt > amount:
            heapq.heappush(debtors, (-(debt - amount), debtor))

        if credit > amount:
            heapq.heappush(creditors, (-(credit - amount), creditor))

    return out


def hub_spoke(positions, hub):
    """Settle every participant's net position through a central hub."""
    out = []

    for account, value in positions.items():
        if account == hub:
            continue

        if value < 0:
            out.append({
                "from": account,
                "to": hub,
                "amount_paise": -value,
            })
        elif value > 0:
            out.append({
                "from": hub,
                "to": account,
                "amount_paise": value,
            })

    return out


def pick_hub(payments):
    volume = defaultdict(int)

    for p in payments:
        volume[p["from"]] += p["amount_paise"]
        volume[p["to"]] += p["amount_paise"]

    if not volume:
        raise ValueError("Cannot select a hub without payments")

    return max(volume, key=volume.get)


def analyze(payments, hub=None):
    positions = net_positions(payments)
    hub = hub or pick_hub(payments)

    gross = [
        {
            "from": p["from"],
            "to": p["to"],
            "amount_paise": p["amount_paise"],
        }
        for p in payments
    ]

    strategies = {
        "gross": gross,
        "bilateral": bilateral(payments),
        "multilateral": multilateral(positions),
        "hub_spoke": hub_spoke(positions, hub),
    }

    for name, transfers in strategies.items():
        assert (
            positions_from_transfers(transfers) == positions
        ), f"{name} changed net positions"

    gross_value = sum(t["amount_paise"] for t in gross)
    metrics = {}

    for name, transfers in strategies.items():
        value = sum(t["amount_paise"] for t in transfers)

        metrics[name] = {
            "transfers": len(transfers),
            "value_paise": value,
            "transfer_reduction_bps": (
                10000 - (len(transfers) * 10000) // max(len(gross), 1)
            ),
            "value_reduction_bps": (
                10000 - (value * 10000) // max(gross_value, 1)
            ),
        }

    return {
        "hub": hub,
        "positions": positions,
        "strategies": strategies,
        "metrics": metrics,
    }
