from collections import Counter


def reconcile(ledger, rows):
    """Compare ledger references and amounts against statement rows."""
    exceptions = []
    counts = Counter(r.get("reference", "") for r in rows)
    first = {}

    for row in rows:
        first.setdefault(row.get("reference", ""), row)

    for ref, count in counts.items():
        if count > 1:
            exceptions.append({
                "type": "DUPLICATE",
                "reference": ref,
                "detail": f"appears {count} times",
            })

    matched = 0

    for ref, row in first.items():
        try:
            amount = int(row["amount_paise"])
        except (KeyError, ValueError, TypeError):
            exceptions.append({
                "type": "MALFORMED_ROW",
                "reference": ref,
                "detail": "bad amount",
            })
            continue

        if ref not in ledger:
            exceptions.append({
                "type": "MISSING_IN_LEDGER",
                "reference": ref,
                "detail": f"statement={amount}",
            })
        elif amount != ledger[ref]:
            exceptions.append({
                "type": "AMOUNT_MISMATCH",
                "reference": ref,
                "detail": f"ledger={ledger[ref]} statement={amount}",
            })
        else:
            matched += 1

    for ref in sorted(set(ledger) - set(first)):
        exceptions.append({
            "type": "MISSING_IN_STATEMENT",
            "reference": ref,
            "detail": f"ledger={ledger[ref]}",
        })

    summary = {
        "ledger_count": len(ledger),
        "statement_rows": len(rows),
        "matched": matched,
        "exceptions": dict(Counter(e["type"] for e in exceptions)),
    }

    return {"summary": summary, "exceptions": exceptions}
