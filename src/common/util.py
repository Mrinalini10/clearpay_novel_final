import hashlib
import json
import os
import random
from datetime import datetime, timezone
from decimal import Decimal


ISO_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"


def now_iso():
    return datetime.now(timezone.utc).strftime(ISO_FMT)


def to_iso(dt):
    return dt.astimezone(timezone.utc).strftime(ISO_FMT)


def parse_iso(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


class _Encoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return int(o) if o == o.to_integral_value() else float(o)
        return super().default(o)


def dumps(obj):
    return json.dumps(obj, cls=_Encoder)


def response(status, body, headers=None):
    h = {"Content-Type": "application/json"}
    h.update(headers or {})
    return {
        "statusCode": status,
        "headers": h,
        "body": dumps(body),
    }


def request_hash(payload):
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def authorized(headers):
    expected = os.environ.get("API_KEY", "")
    return (not expected) or headers.get("x-api-key") == expected


def maybe_chaos(point):
    """Randomly raise to simulate crashes."""
    rate = float(os.environ.get("CHAOS_FAIL_RATE", "0"))
    if rate > 0 and random.random() < rate:
        raise RuntimeError(f"chaos injected at {point}")
