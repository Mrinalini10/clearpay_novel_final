from common.liquidity_adapter import build_settlement_plan


PAYMENTS = [
    {"payment_id": "P1", "from": "A", "to": "B", "amount_paise": 100},
    {"payment_id": "P2", "from": "B", "to": "A", "amount_paise": 60},
    {"payment_id": "P3", "from": "A", "to": "C", "amount_paise": 30},
]


def test_full_batch_when_liquidity_is_sufficient():
    plan = build_settlement_plan(PAYMENTS, {"A": 100, "B": 0, "C": 0})

    assert plan["route"] == "full_batch"
    assert len(plan["selected_payments"]) == 3
    assert len(plan["deferred_payments"]) == 0
    assert plan["metrics"]["feasible"] is True


def test_optimizer_when_liquidity_is_insufficient():
    plan = build_settlement_plan(PAYMENTS, {"A": 50, "B": 0, "C": 0})

    assert plan["route"] == "liquidity_optimizer"
    assert len(plan["selected_payments"]) == 2
    assert len(plan["deferred_payments"]) == 1
    assert plan["metrics"]["feasible"] is True


def test_duplicate_payment_ids_are_rejected():
    try:
        build_settlement_plan([PAYMENTS[0], PAYMENTS[0]], {"A": 100})
    except ValueError:
        pass
    else:
        raise AssertionError("Duplicate payment IDs were accepted")
