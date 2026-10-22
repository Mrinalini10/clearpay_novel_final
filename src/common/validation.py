import re


MAX_AMOUNT_PAISE = 10_000_000_000  # Rs 10 crore
ACCOUNT_RE = re.compile(r"[A-Za-z0-9_-]{1,40}")


def validate(body):
    """Return (clean_payload, None) or (None, error_message)."""
    if not isinstance(body, dict):
        return None, "body must be a JSON object"

    src = body.get("from_account")
    dst = body.get("to_account")
    amt = body.get("amount_paise")
    cur = body.get("currency", "INR")

    for name, value in (
        ("from_account", src),
        ("to_account", dst),
    ):
        if not isinstance(value, str) or not ACCOUNT_RE.fullmatch(value):
            return None, (
                f"{name} must be 1-40 chars of letters, digits, _ or -"
            )

    if src == dst:
        return None, "from_account and to_account must differ"

    if (
        isinstance(amt, bool)
        or not isinstance(amt, int)
        or not (1 <= amt <= MAX_AMOUNT_PAISE)
    ):
        return None, (
            "amount_paise must be an integer between 1 and 10,000,000,000"
        )

    if cur != "INR":
        return None, "only INR is supported"

    return {
        "from_account": src,
        "to_account": dst,
        "amount_paise": amt,
        "currency": cur,
    }, None
