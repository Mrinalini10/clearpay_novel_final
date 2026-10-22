"""Persist approved settlement plans for safe AWS Lambda retries."""

import json
import re

from botocore.exceptions import ClientError


def plan_key(window_id):
    """Build a safe S3 key for a settlement window."""
    if not isinstance(window_id, str) or not re.fullmatch(
        r"W-[A-Za-z0-9_-]+", window_id
    ):
        raise ValueError("Invalid settlement window ID")

    return f"windows/{window_id}/approved_plan.json"


def read_approved_plan(s3, bucket, window_id):
    """Read an existing approved plan, or return None."""
    if not isinstance(bucket, str) or not bucket.strip():
        raise ValueError("S3 bucket name is required")

    try:
        response = s3.get_object(
            Bucket=bucket,
            Key=plan_key(window_id),
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in ("NoSuchKey", "404", "NotFound"):
            return None
        raise

    return json.loads(response["Body"].read())


def save_approved_plan(s3, bucket, window_id, plan):
    """Save a plan only if none exists; otherwise reuse the saved plan."""
    if not isinstance(plan, dict):
        raise ValueError("Settlement plan must be an object")

    existing = read_approved_plan(s3, bucket, window_id)
    if existing is not None:
        return existing

    body = json.dumps(
        plan, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")

    try:
        s3.put_object(
            Bucket=bucket,
            Key=plan_key(window_id),
            Body=body,
            ContentType="application/json",
            IfNoneMatch="*",
        )
        return plan
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code not in (
            "PreconditionFailed",
            "412",
            "ConditionalRequestConflict",
            "409",
        ):
            raise

        existing = read_approved_plan(s3, bucket, window_id)
        if existing is None:
            raise RuntimeError(
                "Approved plan unavailable after S3 write conflict"
            ) from exc
        return existing


def payment_batch_fingerprint(payments):
    """Identify the exact payment contents of a frozen settlement batch."""
    import hashlib

    if not isinstance(payments, list):
        raise ValueError("Payments must be a list")

    normalized = []
    seen_ids = set()

    for payment in payments:
        if not isinstance(payment, dict):
            raise ValueError("Each payment must be an object")

        values = []
        for field in ("payment_id", "from", "to"):
            value = payment.get(field)
            if not isinstance(value, str) or not value:
                raise ValueError(f"Invalid {field}")
            values.append(value)

        amount = payment.get("amount_paise")
        if type(amount) is not int or amount <= 0:
            raise ValueError("Invalid payment amount")

        payment_id = values[0]
        if payment_id in seen_ids:
            raise ValueError("Duplicate payment ID")

        seen_ids.add(payment_id)
        normalized.append([*values, amount])

    normalized.sort(key=lambda row: row[0])

    encoded = json.dumps(
        normalized,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()
