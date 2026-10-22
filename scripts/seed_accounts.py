#!/usr/bin/env python3
"""One-time account and liquidity provisioning for ClearPay.

Creates initial account records in the DynamoDB AccountsTable with
starting balances so that liquidity-aware settlement can function.

Usage
-----
    # Seed default demo accounts (BANK_A, BANK_B, BANK_C) with 10,000 paise each
    python scripts/seed_accounts.py

    # Seed specific accounts from a JSON file
    python scripts/seed_accounts.py --file accounts.json

    # Specify table name and region explicitly
    python scripts/seed_accounts.py --table ClearPayAccounts --region ap-south-1

    # Dry run (show what would be written without touching DynamoDB)
    python scripts/seed_accounts.py --dry-run

accounts.json format:
    [
        {"account_id": "BANK_A", "balance_paise": 500000},
        {"account_id": "BANK_B", "balance_paise": 300000},
        {"account_id": "BANK_C", "balance_paise": 200000}
    ]
"""

import argparse
import json
import os
import sys

import boto3

DEFAULT_ACCOUNTS = [
    {"account_id": "BANK_A", "balance_paise": 100_000},
    {"account_id": "BANK_B", "balance_paise": 100_000},
    {"account_id": "BANK_C", "balance_paise": 100_000},
]


def seed_accounts(table_name, accounts, region=None, dry_run=False):
    """Insert account records into DynamoDB with conditional puts.

    Each account is written only if it does not already exist
    (attribute_not_exists), so re-running the script is safe and
    will not overwrite existing balances.
    """
    kwargs = {}
    if region:
        kwargs["region_name"] = region

    ddb = boto3.client("dynamodb", **kwargs)

    created = 0
    skipped = 0

    for account in accounts:
        account_id = account["account_id"]
        balance = account["balance_paise"]

        if not isinstance(account_id, str) or not account_id:
            print(f"  ⚠️  Skipping invalid account_id: {account_id!r}")
            continue

        if not isinstance(balance, int) or balance < 0:
            print(f"  ⚠️  Skipping {account_id}: invalid balance {balance}")
            continue

        if dry_run:
            print(f"  [DRY RUN] Would create {account_id} with balance_paise={balance}")
            created += 1
            continue

        try:
            ddb.put_item(
                TableName=table_name,
                Item={
                    "account_id": {"S": account_id},
                    "balance_paise": {"N": str(balance)},
                },
                ConditionExpression="attribute_not_exists(account_id)",
            )
            print(f"  ✅ Created {account_id} with balance_paise={balance}")
            created += 1
        except ddb.exceptions.ConditionalCheckFailedException:
            print(f"  ⏭️  Skipped {account_id} (already exists)")
            skipped += 1
        except Exception as exc:
            print(f"  ❌ Failed to create {account_id}: {exc}")
            raise

    return created, skipped


def load_accounts_from_file(filepath):
    """Load account definitions from a JSON file."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Accounts file must contain a JSON array")

    for entry in data:
        if not isinstance(entry, dict):
            raise ValueError("Each account entry must be a JSON object")
        if "account_id" not in entry or "balance_paise" not in entry:
            raise ValueError(
                "Each account entry must have 'account_id' and 'balance_paise'"
            )

    return data


def main():
    parser = argparse.ArgumentParser(
        description="Seed ClearPay DynamoDB AccountsTable with initial balances"
    )
    parser.add_argument(
        "--table",
        default=os.environ.get("ACCOUNTS_TABLE", "AccountsTable"),
        help="DynamoDB accounts table name (default: ACCOUNTS_TABLE env var or 'AccountsTable')",
    )
    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_DEFAULT_REGION", "ap-south-1"),
        help="AWS region (default: AWS_DEFAULT_REGION env var or 'ap-south-1')",
    )
    parser.add_argument(
        "--file",
        help="JSON file with account definitions (default: built-in demo accounts)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be written without touching DynamoDB",
    )
    args = parser.parse_args()

    if args.file:
        accounts = load_accounts_from_file(args.file)
        print(f"Loaded {len(accounts)} accounts from {args.file}")
    else:
        accounts = DEFAULT_ACCOUNTS
        print(f"Using {len(accounts)} default demo accounts")

    print(f"Target table: {args.table} (region: {args.region})")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print()

    created, skipped = seed_accounts(
        table_name=args.table,
        accounts=accounts,
        region=args.region,
        dry_run=args.dry_run,
    )

    print()
    print(f"Summary: {created} created, {skipped} skipped")

    if not args.dry_run and created > 0:
        print("\nNext steps:")
        print("  1. Ingest payments via POST /payments")
        print("  2. Trigger the settlement state machine")
        print("  3. Check SettlementsTable for results")


if __name__ == "__main__":
    main()
