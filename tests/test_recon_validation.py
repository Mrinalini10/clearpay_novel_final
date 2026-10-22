from common.recon import reconcile
from common.validation import validate


def test_reconcile_finds_all_exception_types():
    ledger = {"a": 100, "b": 200, "c": 300}
    rows = [
        {"reference": "a", "amount_paise": "100"},
        {"reference": "b", "amount_paise": "999"},
        {"reference": "b", "amount_paise": "999"},
        {"reference": "z", "amount_paise": "50"},
    ]

    types = {
        e["type"]
        for e in reconcile(ledger, rows)["exceptions"]
    }

    assert types == {
        "AMOUNT_MISMATCH",
        "DUPLICATE",
        "MISSING_IN_LEDGER",
        "MISSING_IN_STATEMENT",
    }


def test_validation():
    ok, err = validate({
        "from_account": "A",
        "to_account": "B",
        "amount_paise": 100,
    })
    assert err is None and ok["currency"] == "INR"

    assert validate({
        "from_account": "A",
        "to_account": "A",
        "amount_paise": 100,
    })[1]

    assert validate({
        "from_account": "A",
        "to_account": "B",
        "amount_paise": 1.5,
    })[1]

    assert validate({
        "from_account": "A",
        "to_account": "B",
        "amount_paise": -5,
    })[1]

    assert validate({
        "from_account": "A",
        "to_account": "B",
        "amount_paise": True,
    })[1]
