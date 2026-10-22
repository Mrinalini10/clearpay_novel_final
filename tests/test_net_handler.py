"""
test_net_handler.py — Unit tests verifying integration of novel liquidity engine into net.py handler.
"""

import json
from unittest.mock import MagicMock, patch
import os
import sys

# Ensure src is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

os.environ["AWS_DEFAULT_REGION"] = "ap-south-1"
os.environ["AWS_ACCESS_KEY_ID"] = "mock_key"
os.environ["AWS_SECRET_ACCESS_KEY"] = "mock_secret"
os.environ["SETTLEMENTS_TABLE"] = "TestSettlements"
os.environ["DATA_BUCKET"] = "test-clearpay-bucket"
os.environ["PAYMENTS_TABLE"] = "TestPayments"

# pyright: reportMissingImports=false
import handlers.net as net_handler  # type: ignore


def test_net_handler_with_novel_liquidity_engine():
    mock_s3 = MagicMock()
    mock_table = MagicMock()

    # Sample payments with circular offset (A -> B -> C -> A)
    payments_data = [
        {"payment_id": "P1", "from": "A", "to": "B", "amount_paise": 100},
        {"payment_id": "P2", "from": "B", "to": "C", "amount_paise": 100},
        {"payment_id": "P3", "from": "C", "to": "A", "amount_paise": 100},
    ]

    mock_s3.get_object.return_value = {
        "Body": MagicMock(read=lambda: json.dumps(payments_data).encode())
    }

    event = {
        "window_id": "W-20261022T010000",
        "s3_key": "windows/W-20261022T010000/payments.json",
        "cutoff": "2026-10-22T01:00:00Z",
        "liquidity": {"A": 0, "B": 0, "C": 0},
    }

    with patch.object(net_handler, "s3", mock_s3), patch.object(net_handler, "settlements", mock_table):
        result = net_handler.handler(event, None)

        # Check that S3 instructions include novel settlement
        put_call = mock_s3.put_object.call_args[1]
        instructions = json.loads(put_call["Body"].decode())
        assert "novel_settlement" in instructions
        assert "cycle_repair" in instructions["novel_settlement"]
        assert instructions["novel_settlement"]["cycle_repair"]["feasible"] is True
        # The cycle repair settles all 300 paise even with 0 liquidity!
        assert instructions["novel_settlement"]["cycle_repair"]["settled_value_paise"] == 300

        # Check DynamoDB put_item call
        item = mock_table.put_item.call_args[1]["Item"]
        assert "novel_metrics" in item
        assert item["novel_metrics"]["cycle_repair"]["feasible"] is True
        assert item["novel_metrics"]["cycle_repair"]["selected_count"] == 3


def test_net_handler_standard_backwards_compatible():
    mock_s3 = MagicMock()
    mock_table = MagicMock()

    payments_data = [
        {"payment_id": "P1", "from": "A", "to": "B", "amount_paise": 500},
    ]

    mock_s3.get_object.return_value = {
        "Body": MagicMock(read=lambda: json.dumps(payments_data).encode())
    }

    event = {
        "window_id": "W-20261022T020000",
        "s3_key": "windows/W-20261022T020000/payments.json",
        "cutoff": "2026-10-22T02:00:00Z",
    }

    with patch.object(net_handler, "s3", mock_s3), patch.object(net_handler, "settlements", mock_table):
        result = net_handler.handler(event, None)
        assert result["window_id"] == "W-20261022T020000"

        item = mock_table.put_item.call_args[1]["Item"]
        assert "metrics" in item
        assert "novel_metrics" not in item
