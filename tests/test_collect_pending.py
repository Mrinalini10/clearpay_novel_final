"""Tests for pending-payment batch collection without real AWS calls."""

import importlib.util
import json
from pathlib import Path
from unittest.mock import MagicMock

import boto3
from botocore.exceptions import ClientError


def load_collector(monkeypatch):
    monkeypatch.setenv("PAYMENTS_TABLE", "test-payments")
    monkeypatch.setenv("DATA_BUCKET", "test-bucket")

    table = MagicMock()
    s3 = MagicMock()

    monkeypatch.setattr(
        boto3, "resource",
        lambda service: MagicMock(Table=lambda name: table),
    )
    monkeypatch.setattr(boto3, "client", lambda service: s3)

    spec = importlib.util.spec_from_file_location(
        "collect_pending_test",
        Path("src/handlers/collect_pending.py"),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module, table, s3


def test_collects_pending_payments_into_frozen_batch(monkeypatch):
    module, table, s3 = load_collector(monkeypatch)

    s3.get_object.side_effect = ClientError(
        {"Error": {"Code": "NoSuchKey"}},
        "GetObject",
    )

    table.scan.return_value = {
        "Items": [
            {
                "payment_id": "P2",
                "from_account": "B",
                "to_account": "A",
                "amount_paise": 600,
            },
            {
                "payment_id": "P1",
                "from_account": "A",
                "to_account": "B",
                "amount_paise": 1000,
            },
        ]
    }

    result = module.handler(
        {"start_time": "2026-01-01T12:00:00+00:00", "run_id": "abcdef123456"},
        None,
    )

    assert result["count"] == 2
    assert table.scan.call_args.kwargs["ConsistentRead"] is True

    uploaded = s3.put_object.call_args.kwargs
    assert uploaded["IfNoneMatch"] == "*"

    rows = json.loads(uploaded["Body"])
    assert [row["payment_id"] for row in rows] == ["P1", "P2"]


def test_retry_reuses_existing_frozen_batch(monkeypatch):
    module, table, s3 = load_collector(monkeypatch)

    frozen = [
        {
            "payment_id": "P1",
            "from": "A",
            "to": "B",
            "amount_paise": 1000,
        }
    ]

    s3.get_object.return_value = {
        "Body": MagicMock(read=lambda: json.dumps(frozen).encode())
    }

    result = module.handler(
        {"start_time": "2026-01-01T12:00:00+00:00", "run_id": "abcdef123456"},
        None,
    )

    assert result["count"] == 1
    table.scan.assert_not_called()
    s3.put_object.assert_not_called()


def test_collector_rejects_missing_or_invalid_run_id(monkeypatch):
    import pytest

    module, table, s3 = load_collector(monkeypatch)
    for value in (None, "", "../../", "ABCDEF123456", "abc123"):
        with pytest.raises(ValueError, match="run_id"):
            module.handler({"start_time": "2026-01-01T12:00:00Z", "run_id": value}, None)
    table.scan.assert_not_called()
    s3.put_object.assert_not_called()


def test_collect_filters_only_current_demo_run(monkeypatch):
    module, table, s3 = load_collector(monkeypatch)
    s3.get_object.side_effect = ClientError(
        {"Error": {"Code": "NoSuchKey"}}, "GetObject"
    )
    table.scan.return_value = {"Items": [
        {"payment_id": "DEMO-abcdef123456-01", "from_account": "A",
         "to_account": "B", "amount_paise": 1000},
    ]}
    result = module.handler(
        {"start_time": "2026-01-01T12:00:00Z", "run_id": "abcdef123456"}, None
    )
    condition = table.scan.call_args.kwargs["FilterExpression"]
    from boto3.dynamodb.conditions import ConditionExpressionBuilder
    compiled = ConditionExpressionBuilder().build_expression(condition)
    assert "begins_with" in compiled.condition_expression
    assert "DEMO-abcdef123456-" in compiled.attribute_value_placeholders.values()
    assert result["window_id"] == "W-20260101T120000-abcdef123456"
    assert result["run_id"] == "abcdef123456"
    assert result["count"] == 1


def test_retry_uses_only_same_frozen_window(monkeypatch):
    module, table, s3 = load_collector(monkeypatch)
    frozen = [{"payment_id": "DEMO-abcdef123456-01", "from": "A",
               "to": "B", "amount_paise": 1000}]
    s3.get_object.return_value = {
        "Body": MagicMock(read=lambda: json.dumps(frozen).encode())
    }
    result = module.handler(
        {"start_time": "2026-01-01T12:00:00Z", "run_id": "abcdef123456"}, None
    )
    assert result["count"] == 1
    table.scan.assert_not_called()
    assert s3.get_object.call_args.kwargs["Key"] == (
        "windows/W-20260101T120000-abcdef123456/pending.json"
    )
