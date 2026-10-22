from copy import deepcopy

from common.settlement_window import plan_pending_window


def payment(payment_id, source, destination, amount):
    return {
        "payment_id": payment_id,
        "from_account": source,
        "to_account": destination,
        "amount_paise": amount,
        "status": "PENDING",
    }


def test_selects_net_feasible_pending_payments_without_mutating_them():
    payments = [
        payment("P1", "A", "B", 1000),
        payment("P2", "B", "A", 600),
    ]
    original = deepcopy(payments)

    decision = plan_pending_window(payments, {"A": 400, "B": 0})

    assert set(decision["selected_ids"]) == {"P1", "P2"}
    assert decision["deferred_ids"] == []
    assert payments == original


def test_defers_unfunded_payment_without_changing_its_status():
    payments = [payment("P3", "A", "B", 1000)]

    decision = plan_pending_window(payments, {"A": 0, "B": 0})

    assert decision["selected_ids"] == []
    assert decision["deferred_ids"] == ["P3"]
    assert payments[0]["status"] == "PENDING"
