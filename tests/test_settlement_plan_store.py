"""Tests for durable settlement-plan storage without AWS calls."""

import io
import json
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from common.settlement_plan_store import (
    plan_key,
    read_approved_plan,
    save_approved_plan,
)


ORIGINAL = {"selected_ids": ["P1"], "deferred_ids": ["P2"]}
CHANGED = {"selected_ids": ["P2"], "deferred_ids": ["P1"]}


def s3_error(code):
    return ClientError(
        {"Error": {"Code": code, "Message": "Test error"}},
        "GetObject",
    )


def test_saves_new_plan_only_once():
    s3 = MagicMock()
    s3.get_object.side_effect = s3_error("NoSuchKey")

    result = save_approved_plan(
        s3, "test-bucket", "W-001", ORIGINAL
    )

    assert result == ORIGINAL
    s3.put_object.assert_called_once()
    arguments = s3.put_object.call_args.kwargs
    assert arguments["IfNoneMatch"] == "*"
    assert arguments["Key"] == "windows/W-001/approved_plan.json"
    assert json.loads(arguments["Body"]) == ORIGINAL


def test_existing_plan_cannot_be_overwritten():
    s3 = MagicMock()
    s3.get_object.return_value = {
        "Body": io.BytesIO(json.dumps(ORIGINAL).encode())
    }

    result = save_approved_plan(
        s3, "test-bucket", "W-001", CHANGED
    )

    assert result == ORIGINAL
    s3.put_object.assert_not_called()


def test_concurrent_write_conflict_reuses_winning_plan():
    s3 = MagicMock()
    s3.get_object.side_effect = [
        s3_error("NoSuchKey"),
        {"Body": io.BytesIO(json.dumps(ORIGINAL).encode())},
    ]
    s3.put_object.side_effect = s3_error("PreconditionFailed")

    result = save_approved_plan(
        s3, "test-bucket", "W-001", CHANGED
    )

    assert result == ORIGINAL


def test_unexpected_s3_error_is_not_hidden():
    s3 = MagicMock()
    s3.get_object.side_effect = s3_error("AccessDenied")

    with pytest.raises(ClientError):
        read_approved_plan(s3, "test-bucket", "W-001")


def test_invalid_window_id_is_rejected():
    with pytest.raises(ValueError):
        plan_key("../other-window")


from common.settlement_plan_store import payment_batch_fingerprint


FINGERPRINT_PAYMENTS = [
    {"payment_id": "P1", "from": "A", "to": "B", "amount_paise": 500},
    {"payment_id": "P2", "from": "B", "to": "A", "amount_paise": 300},
]


def test_fingerprint_ignores_payment_order():
    original = payment_batch_fingerprint(FINGERPRINT_PAYMENTS)
    reversed_order = payment_batch_fingerprint(
        list(reversed(FINGERPRINT_PAYMENTS))
    )

    assert original == reversed_order
    assert len(original) == 64


@pytest.mark.parametrize(
    "field,new_value",
    [
        ("payment_id", "P3"),
        ("from", "C"),
        ("to", "C"),
        ("amount_paise", 501),
    ],
)
def test_fingerprint_detects_changed_payment(field, new_value):
    changed = [dict(payment) for payment in FINGERPRINT_PAYMENTS]
    changed[0][field] = new_value

    assert payment_batch_fingerprint(changed) != (
        payment_batch_fingerprint(FINGERPRINT_PAYMENTS)
    )


def test_fingerprint_rejects_duplicate_payment_ids():
    duplicate = [
        FINGERPRINT_PAYMENTS[0],
        dict(FINGERPRINT_PAYMENTS[0]),
    ]

    with pytest.raises(ValueError, match="Duplicate payment ID"):
        payment_batch_fingerprint(duplicate)


def test_fingerprint_rejects_invalid_amount():
    invalid = [dict(FINGERPRINT_PAYMENTS[0])]
    invalid[0]["amount_paise"] = 0

    with pytest.raises(ValueError, match="Invalid payment amount"):
        payment_batch_fingerprint(invalid)
