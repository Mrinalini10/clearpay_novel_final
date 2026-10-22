"""ClearPay live AWS settlement demonstration dashboard.

Cloud: API Gateway -> Lambda -> DynamoDB -> Step Functions -> S3/DynamoDB.
Local Streamlit only displays inputs and verifies cloud-produced outputs.
"""
from __future__ import annotations

import json
import os
import uuid
from decimal import Decimal

import boto3
import certifi
import pandas as pd
import requests
import streamlit as st
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError, ProfileNotFound

st.set_page_config(page_title="ClearPay", layout="wide")

# === cohesive_theme_override_start ===
st.markdown("""
<style>
:root {
    --cp-bg: #fcf8f5;
    --cp-surface: #fffdfb;
    --cp-sidebar: #111827;
    --cp-sidebar-2: #1f2937;
    --cp-pink: #e75480;
    --cp-pink-dark: #cc3f6a;
    --cp-brown: #62432F;
    --cp-brown-soft: #977158;
    --cp-border: #e7d6cb;
    --cp-text: #493124;
    --cp-text-soft: #765642;
    --cp-white: #ffffff;
}

.stApp {
    background: var(--cp-bg) !important;
    color: var(--cp-text) !important;
}

/* ===== SIDEBAR ===== */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, var(--cp-sidebar) 0%, var(--cp-sidebar-2) 100%) !important;
    border-right: 1px solid rgba(255,255,255,0.08) !important;
}

section[data-testid="stSidebar"] * {
    color: #f8ede6 !important;
}

section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] .stMarkdown,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] div {
    color: #f8ede6 !important;
}

section[data-testid="stSidebar"] input {
    background: rgba(255,255,255,0.06) !important;
    color: #ffffff !important;
    border: 1px solid rgba(255,255,255,0.15) !important;
    border-radius: 10px !important;
}

section[data-testid="stSidebar"] [data-baseweb="input"] {
    background: rgba(255,255,255,0.06) !important;
    border-radius: 10px !important;
}

/* ===== MAIN TEXT ===== */
h1, h2, h3, h4, h5, h6 {
    color: var(--cp-brown) !important;
}

p, li, label, .stCaption, .stMarkdown, .stText {
    color: var(--cp-text) !important;
}

/* ===== METRICS / CARDS ===== */
div[data-testid="stMetric"] {
    background: var(--cp-surface) !important;
    border: 1px solid var(--cp-border) !important;
    border-radius: 16px !important;
    padding: 14px !important;
    box-shadow: 0 2px 10px rgba(139, 94, 60, 0.05) !important;
}

div[data-testid="stMetricLabel"] {
    color: var(--cp-text-soft) !important;
}

div[data-testid="stMetricValue"] {
    color: var(--cp-pink) !important;
}

/* ===== BUTTONS ===== */
button[kind="primary"] {
    background: var(--cp-pink) !important;
    border: 1px solid var(--cp-pink) !important;
    color: white !important;
    border-radius: 10px !important;
}

button[kind="primary"]:hover {
    background: var(--cp-pink-dark) !important;
    border-color: var(--cp-pink-dark) !important;
}

button[kind="secondary"] {
    background: var(--cp-surface) !important;
    color: var(--cp-brown) !important;
    border: 1px solid var(--cp-border) !important;
    border-radius: 10px !important;
}

/* ===== SELECTBOX / INPUTS / TABLES ===== */
[data-baseweb="select"] > div,
[data-baseweb="base-input"] > div,
.stTextInput input,
.stNumberInput input,
textarea {
    background: #ffffff !important;
    color: var(--cp-text) !important;
    border: 1px solid var(--cp-border) !important;
    border-radius: 10px !important;
}

div[data-testid="stDataFrame"] {
    border: 1px solid var(--cp-border) !important;
    border-radius: 14px !important;
    overflow: hidden !important;
}

/* ===== INFO / SUCCESS / WARNING MESSAGES ===== */
div[data-baseweb="notification"] {
    border-radius: 12px !important;
}

/* ===== HORIZONTAL RULES ===== */
hr {
    border-color: var(--cp-border) !important;
}
</style>
""", unsafe_allow_html=True)
# === cohesive_theme_override_end ===


REGION = os.getenv("CLEARPAY_REGION", "ap-south-1")
PROFILE = os.getenv("CLEARPAY_AWS_PROFILE", "clearpay-andrea")
API_URL = os.getenv("CLEARPAY_API_URL", "https://h5snzmo5ta.execute-api.ap-south-1.amazonaws.com").rstrip("/")
ACCOUNTS_TABLE = os.getenv("CLEARPAY_ACCOUNTS_TABLE", "clearpay-AccountsTable-3400X4MNWR0S")
PAYMENTS_TABLE = os.getenv("CLEARPAY_PAYMENTS_TABLE", "clearpay-PaymentsTable-1HTN92EG5GI4J")
LEDGER_TABLE = os.getenv("CLEARPAY_LEDGER_TABLE", "clearpay-LedgerTable-9B3EHPG2W9NO")
BUCKET = os.getenv("CLEARPAY_DATA_BUCKET", "clearpay-data-134748918128-ap-south-1")
STATE_MACHINE = os.getenv("CLEARPAY_STATE_MACHINE_ARN", "arn:aws:states:ap-south-1:134748918128:stateMachine:LiquiditySettlementStateMachine-Z8gTz79d0T71")
DEMO_BANKS = ("BANK_A", "BANK_B", "BANK_C")
EXPECTED_ACCOUNT = os.getenv("CLEARPAY_AWS_ACCOUNT", "134748918128")
MAX_PAYMENTS = 10  # Avoid DynamoDB's 100-action limit in live demonstrations.


def aws_session():
    # Profile is used only by local Streamlit server, not sent to browser.
    return boto3.Session(profile_name=PROFILE, region_name=REGION)


def ddb():
    return aws_session().resource("dynamodb")


def money(paise):
    return f"₹{int(paise) / 100:,.2f}"


def account_balances():
    table = ddb().Table(ACCOUNTS_TABLE)
    balances = {}
    for account in DEMO_BANKS:
        item = table.get_item(Key={"account_id": account}, ConsistentRead=True).get("Item")
        if not item or "balance_paise" not in item:
            raise RuntimeError(f"Missing account {account}. Provision demo accounts before testing.")
        balances[account] = int(item["balance_paise"])
    return balances


def payment_status(payment_id):
    return ddb().Table(PAYMENTS_TABLE).get_item(
        Key={"payment_id": payment_id}, ConsistentRead=True
    ).get("Item")


def api_post(payment, key, api_key):
    response = requests.post(
        f"{API_URL}/payments",
        json={
            "from_account": payment["from"],
            "to_account": payment["to"],
            "amount_paise": int(payment["amount_paise"]),
            "currency": "INR",
        },
        headers={"x-api-key": api_key, "Idempotency-Key": key},
        timeout=20,
        verify=certifi.where(),
    )
    try:
        body = response.json()
    except ValueError:
        body = {"response": response.text[:400]}
    if response.status_code not in (200, 202):
        raise RuntimeError(f"API returned HTTP {response.status_code}: {body}")
    if body.get("payment_id") != key:
        raise RuntimeError("API returned an unexpected payment ID")
    return body, response.status_code


def workflow_client():
    return aws_session().client("stepfunctions")


def start_execution(run_id):
    return workflow_client().start_execution(
        stateMachineArn=STATE_MACHINE,
        name=f"dashboard-{run_id}",
        input=json.dumps({"source": "clearpay-streamlit-demo", "run_id": run_id}),
    )["executionArn"]


def describe_execution(arn):
    return workflow_client().describe_execution(executionArn=arn)


def approved_plan(window_id):
    if not window_id:
        return None
    try:
        response = aws_session().client("s3").get_object(
            Bucket=BUCKET, Key=f"windows/{window_id}/approved_plan.json"
        )
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") in ("NoSuchKey", "404", "NotFound"):
            return None
        raise
    return json.loads(response["Body"].read())


def ledger_for_payment(item):
    """Fetch exact debit and credit entries, no expensive scans or fabricated counts."""
    window_id = item.get("window_id")
    if not window_id:
        return []
    table = ddb().Table(LEDGER_TABLE)
    rows = []
    for account, kind in ((item["from_account"], "DEBIT"), (item["to_account"], "CREDIT")):
        entry = table.get_item(
            Key={"account_id": account, "entry_id": f"{window_id}#{item['payment_id']}#{kind[0]}"},
            ConsistentRead=True,
        ).get("Item")
        if entry:
            rows.append(entry)
    return rows


def default_payments(scenario, balances):
    if scenario == "Circular gridlock":
        # Every single transfer exceeds each bank's current balance, but net cash flow is zero.
        amount = max(balances.values()) + 10_000
        return [
            {"from": "BANK_A", "to": "BANK_B", "amount_paise": amount},
            {"from": "BANK_B", "to": "BANK_C", "amount_paise": amount},
            {"from": "BANK_C", "to": "BANK_A", "amount_paise": amount},
        ]
    if scenario == "Insufficient liquidity":
        return [{"from": "BANK_A", "to": "BANK_B", "amount_paise": balances["BANK_A"] + 10_000}]
    return [
        {"from": "BANK_A", "to": "BANK_B", "amount_paise": 1_000},
        {"from": "BANK_B", "to": "BANK_C", "amount_paise": 700},
        {"from": "BANK_C", "to": "BANK_A", "amount_paise": 500},
    ]


def validate_rows(frame):
    if frame.empty or len(frame) > MAX_PAYMENTS:
        raise ValueError(f"Enter 1–{MAX_PAYMENTS} payments.")
    payments = []
    for index, row in frame.iterrows():
        src, dst = str(row["From"]), str(row["To"])
        if src not in DEMO_BANKS or dst not in DEMO_BANKS or src == dst:
            raise ValueError(f"Row {index + 1}: choose two different demo banks.")
        try:
            amount = Decimal(str(row["Amount (₹)"]))
            paise = amount * 100
        except Exception as error:
            raise ValueError(f"Row {index + 1}: invalid amount") from error
        if paise != paise.to_integral_value() or not (1 <= paise <= 10_000_000_000):
            raise ValueError(f"Row {index + 1}: amount must be positive with at most 2 decimals.")
        payments.append({"from": src, "to": dst, "amount_paise": int(paise)})
    return payments


def show_payments(payments, records=None):
    records = records or {}
    rows = []
    for payment in payments:
        pid = payment.get("payment_id", "—")
        rows.append({
            "Payment ID": pid,
            "From": payment["from"],
            "To": payment["to"],
            "Amount": money(payment["amount_paise"]),
            "AWS status": records.get(pid, {}).get("status", "NOT SUBMITTED"),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def validate_identity():
    account = aws_session().client("sts").get_caller_identity()["Account"]
    if account != EXPECTED_ACCOUNT:
        raise RuntimeError(f"AWS account mismatch: {account}. Expected {EXPECTED_ACCOUNT}. No writes permitted.")
    return account



st.markdown("""
<style>
    :root {
        --primary-color: #E75480;
        --background-color: #FFFDFC;
        --secondary-background-color: #F8E9E8;
        --text-color: #62432F;
    }

    .stApp {
        background-color: #FFFDFC;
        color: #62432F;
    }

    section[data-testid="stSidebar"] {
        background-color: #F5E6DF;
        border-right: 1px solid #D7BBA4;
    }

    h1, h2, h3, h4 {
        color: #62432F !important;
    }

    div[data-testid="stMetric"] {
        background-color: #FFFFFF;
        border: 1px solid #E5C9C5;
        border-radius: 12px;
        padding: 14px;
    }

    div[data-testid="stMetricValue"] {
        color: #D94378;
    }

    button[kind="primary"] {
        background-color: #E75480 !important;
        border-color: #E75480 !important;
        color: white !important;
    }

    button[kind="primary"]:hover {
        background-color: #D94372 !important;
        border-color: #D94372 !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("ClearPay")
st.caption("Live AWS Settlement · Real payment submission · isolated AWS settlement run · DynamoDB ledger verification")

with st.sidebar:
    st.subheader("AWS connection")
    st.text(f"Region: {REGION}")
    st.text(f"Profile: {PROFILE}")
    api_key = st.text_input("API key", type="password", value=os.getenv("CLEARPAY_API_KEY", ""))
    st.divider()
    st.caption("This dashboard writes real demo payments and triggers the deployed AWS workflow. AWS usage may incur charges.")

try:
    account_id = validate_identity()
    balances = account_balances()
except (ClientError, BotoCoreError, ProfileNotFound, NoCredentialsError, RuntimeError, Exception) as exc:
    st.error(f"AWS connection/preflight failed: {exc}")
    st.info("Check your AWS profile, permissions, network access and deployed table names. No payments were submitted.")
    st.stop()

st.success(f"Connected to AWS account {account_id} · {REGION} · live DynamoDB balances")

if "run" not in st.session_state:
    st.session_state.run = None
if "scenario" not in st.session_state:
    st.session_state.scenario = "Circular gridlock"

balance_cols = st.columns(4)
for col, bank in zip(balance_cols, DEMO_BANKS):
    col.metric(bank, money(balances[bank]))
balance_cols[3].metric("Total liquidity", money(sum(balances.values())))

st.divider()
st.subheader("1 · Prepare and submit a test batch")
scenario = st.selectbox(
    "Test case",
    ["Circular gridlock", "Normal payments", "Insufficient liquidity", "Custom"],
    key="scenario",
    disabled=st.session_state.run is not None,
)
if scenario == "Circular gridlock":
    st.info("Each bank owes more than its individual balance, but the three payments form a zero-net cycle. The cloud optimizer should assess them together.")
elif scenario == "Insufficient liquidity":
    st.info("One payment exceeds its sender's balance and has no offsetting inflow. Expect deferral rather than overdraft.")

if scenario != "Custom":
    raw_rows = default_payments(scenario, balances)
else:
    raw_rows = [{"from": "BANK_A", "to": "BANK_B", "amount_paise": 1000}]

initial = pd.DataFrame([{
    "From": row["from"], "To": row["to"], "Amount (₹)": row["amount_paise"] / 100,
} for row in raw_rows])

if st.session_state.run is None:
    edited = st.data_editor(
        initial,
        num_rows="dynamic",
        hide_index=True,
        use_container_width=True,
        column_config={
            "From": st.column_config.SelectboxColumn("From", options=list(DEMO_BANKS), required=True),
            "To": st.column_config.SelectboxColumn("To", options=list(DEMO_BANKS), required=True),
            "Amount (₹)": st.column_config.NumberColumn("Amount (₹)", min_value=0.01, step=1.0, format="%.2f", required=True),
        },
        key=f"payments_editor_{scenario}",
    )
    try:
        draft = validate_rows(edited)
        st.caption(f"{len(draft)} payment(s) · Gross value {money(sum(x['amount_paise'] for x in draft))}")
    except ValueError as error:
        draft = None
        st.warning(str(error))
    confirm = st.checkbox("I understand this creates real AWS demo payments and may incur charges.")
    if st.button("Submit payments to AWS", type="primary", disabled=not (draft and confirm and api_key)):
        try:
            validate_identity()
            run_id = uuid.uuid4().hex[:12]
            run = {
                "run_id": run_id,
                "scenario": scenario,
                "payments": [],
                "before": balances.copy(),
                "execution_arn": None,
                "result": None,
            }
            # Save state before first write, so a partial submission is never hidden.
            st.session_state.run = run
            for index, payment in enumerate(draft):
                key = f"DEMO-{run_id}-{index+1:02d}"
                body, http_code = api_post(payment, key, api_key)
                run["payments"].append({**payment, "payment_id": key, "http_status": http_code})
            st.rerun()
        except Exception as exc:
            st.error(f"Submission stopped: {exc}")
            st.warning("If any payments were accepted before the error, they remain on AWS. Do not blindly resubmit.")
else:
    run = st.session_state.run
    st.caption(f"Demo run: {run['run_id']} · {run['scenario']}")
    records = {}
    for payment in run["payments"]:
        try:
            records[payment["payment_id"]] = payment_status(payment["payment_id"]) or {}
        except Exception as exc:
            st.error(f"Could not read {payment['payment_id']}: {exc}")
    show_payments(run["payments"], records)

    st.divider()
    st.subheader("2 · Run settlement on AWS")
    if not run["execution_arn"]:
        st.caption("This starts the deployed LiquiditySettlementStateMachine. Optimization and financial updates run in AWS Lambda/DynamoDB, not in Streamlit.")
        if st.button("Run AWS settlement", type="primary", disabled=not run["payments"]):
            try:
                validate_identity()
                # This execution collects only IDs bearing the current run prefix.
                # Validate our own submissions; earlier deferred batches may stay pending.
                for payment in run["payments"]:
                    record = payment_status(payment["payment_id"])
                    if not record or record.get("status") != "PENDING":
                        raise RuntimeError(
                            f"Payment {payment['payment_id']} is not PENDING; "
                            "refusing to start an ambiguous demo."
                        )
                run["execution_arn"] = start_execution(run["run_id"])
                st.rerun()
            except Exception as exc:
                st.error(f"Unable to start workflow: {exc}")
    else:
        st.code(run["execution_arn"], language=None)
        try:
            execution = describe_execution(run["execution_arn"])
            status = execution["status"]
            st.write(f"**AWS Step Functions status:** `{status}`")
            if status == "RUNNING":
                st.info("AWS is processing this batch. Click Refresh cloud results to check again.")
            elif status == "SUCCEEDED":
                output = json.loads(execution.get("output", "{}"))
                run["result"] = output
                st.success("AWS settlement workflow succeeded.")
                if output.get("window_id"):
                    st.caption(f"Settlement window: {output['window_id']}")
                if output.get("metrics"):
                    with st.expander("Cloud optimizer metrics", expanded=False):
                        st.json(output["metrics"])
            else:
                st.error(f"AWS workflow status: {status}")
                if execution.get("error") or execution.get("cause"):
                    st.code(f"{execution.get('error', '')}: {execution.get('cause', '')}")
        except Exception as exc:
            st.error(f"Cannot inspect execution: {exc}")

        if st.button("Refresh cloud results"):
            st.rerun()

    st.divider()
    st.subheader("3 · Verify AWS settlement and ledger")
    if not run["execution_arn"]:
        st.info("Run AWS settlement first.")
    else:
        try:
            execution = describe_execution(run["execution_arn"])
            if execution["status"] != "SUCCEEDED":
                st.info("Verification becomes available when the cloud execution succeeds.")
            else:
                output = json.loads(execution.get("output", "{}"))
                if not output.get("window_id"):
                    st.warning("Workflow succeeded without a settlement window (possibly an empty collection). Cannot claim payments settled.")
                else:
                    plan = approved_plan(output["window_id"])
                    if not plan:
                        st.error("Cloud-approved settlement plan was not found in S3. Verification incomplete.")
                    else:
                        expected_ids = {p["payment_id"] for p in run["payments"]}
                        selected = set(plan.get("selected_ids", []))
                        deferred = set(plan.get("deferred_ids", []))
                        plan_partition_ok = selected.isdisjoint(deferred) and (selected | deferred) == expected_ids
                        current_balances = account_balances()
                        conserved = sum(current_balances.values()) == sum(run["before"].values())
                        rows, checks = [], []
                        for payment in run["payments"]:
                            pid = payment["payment_id"]
                            record = payment_status(pid) or {}
                            status = record.get("status", "MISSING")
                            entries = ledger_for_payment(record)
                            debits = [x for x in entries if x.get("entry_type") == "DEBIT"]
                            credits = [x for x in entries if x.get("entry_type") == "CREDIT"]
                            ledger_ok = (
                                len(entries) == 2 and len(debits) == 1 and len(credits) == 1
                                and debits[0].get("payment_id") == pid
                                and credits[0].get("payment_id") == pid
                                and int(debits[0]["amount_paise"]) == payment["amount_paise"]
                                and int(credits[0]["amount_paise"]) == payment["amount_paise"]
                                and debits[0]["account_id"] == payment["from"]
                                and credits[0]["account_id"] == payment["to"]
                            )
                            ok = (status == "SETTLED" and ledger_ok) if pid in selected else (status == "PENDING" and not entries)
                            checks.append(ok)
                            rows.append({
                                "Payment ID": pid,
                                "From → To": f"{payment['from']} → {payment['to']}",
                                "Amount": money(payment["amount_paise"]),
                                "Cloud decision": "SETTLE" if pid in selected else "DEFER" if pid in deferred else "UNKNOWN",
                                "DynamoDB status": status,
                                "Ledger": "2 entries verified" if ledger_ok else f"{len(entries)} entries",
                                "Check": "PASS" if ok else "FAIL",
                            })
                        a, b, c, d = st.columns(4)
                        a.metric("Settled", f"{len(selected)} / {len(expected_ids)}")
                        b.metric("Deferred", len(deferred))
                        c.metric("Ledger checks", f"{sum(checks)} / {len(checks)}")
                        d.metric("Total balance conserved", "PASS" if conserved else "FAIL")
                        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                        before_after = pd.DataFrame([
                            {"Bank": bank, "Before": money(run["before"][bank]),
                             "After": money(current_balances[bank]),
                             "Change": money(current_balances[bank] - run["before"][bank])}
                            for bank in DEMO_BANKS
                        ])
                        st.markdown("**Real DynamoDB balances — before vs after**")
                        st.dataframe(before_after, use_container_width=True, hide_index=True)
                        if plan_partition_ok and conserved and all(checks):
                            st.success("PASS — Cloud decision, payment statuses, double-entry ledger, and balance conservation verified.")
                        else:
                            st.error("FAIL — One or more settlement invariants failed. Inspect the payment table and cloud execution.")
                        with st.expander("Actual approved plan saved by AWS in S3"):
                            st.json(plan)
        except Exception as exc:
            st.error(f"Verification failed: {exc}")

    st.divider()
    st.warning("This dashboard does not delete payments or reset balances. A new test uses the balances left by the previous test.")
    if st.button("Start a new test"):
        if run["execution_arn"] and describe_execution(run["execution_arn"])["status"] == "RUNNING":
            st.warning("Wait for the running AWS workflow to finish before starting another test.")
        else:
            st.session_state.run = None
            st.rerun()
