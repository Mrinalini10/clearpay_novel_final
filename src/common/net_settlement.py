"""Prepare validated net balance changes for settlement."""

from common.netting import net_positions


def build_net_balance_changes(selected_payments):
    """Return signed balance changes in paise, keyed by account ID."""
    if not isinstance(selected_payments, list):
        raise ValueError("Selected payments must be a list")

    validated = []
    seen_ids = set()

    for payment in selected_payments:
        if not isinstance(payment, dict):
            raise ValueError("Each payment must be an object")

        payment_id = payment.get("payment_id")
        source = payment.get("from")
        destination = payment.get("to")
        amount = payment.get("amount_paise")

        if not isinstance(payment_id, str) or not payment_id:
            raise ValueError("Invalid payment ID")

        if payment_id in seen_ids:
            raise ValueError("Duplicate payment ID")

        if (
            not isinstance(source, str)
            or not source
            or not isinstance(destination, str)
            or not destination
            or source == destination
        ):
            raise ValueError("Invalid payment participants")

        if type(amount) is not int or amount <= 0:
            raise ValueError("Payment amount must be positive integer paise")

        seen_ids.add(payment_id)
        validated.append({
            "from": source,
            "to": destination,
            "amount_paise": amount,
        })

    changes = net_positions(validated)

    if sum(changes.values()) != 0:
        raise ValueError("Net settlement must balance to zero")

    return changes
