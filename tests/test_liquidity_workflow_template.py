"""Safety checks for the inactive liquidity settlement SAM template."""

import json
from pathlib import Path


TEMPLATE = Path("template-liquidity-workflow.yaml")
WORKFLOW = Path("workflow/liquidity_settlement.asl.json")


def test_workflow_uses_sam_substituted_function_arns():
    states = json.loads(WORKFLOW.read_text())["States"]

    assert (
        states["CollectPending"]["Parameters"]["FunctionName"]
        == "${CollectPendingFunctionArn}"
    )
    assert (
        states["SettlePending"]["Parameters"]["FunctionName"]
        == "${SettlePendingFunctionArn}"
    )


def test_settlement_function_has_batch_mode_enabled():
    text = TEMPLATE.read_text()

    settlement = text.split(
        "  SettlePendingFunction:", 1
    )[1].split(
        "  LiquiditySettlementStateMachine:", 1
    )[0]

    # The handler raises RuntimeError if this is not "1".
    # Safety is provided by the absence of an automatic trigger,
    # not by crippling the Lambda itself.
    assert 'LIQUIDITY_BATCH_MODE: "1"' in settlement


def test_new_workflow_has_no_automatic_trigger():
    text = TEMPLATE.read_text()

    assert "ScheduleV2" not in text
    assert "ScheduleExpression:" not in text
    assert "Type: HttpApi" not in text
    assert "Type: SQS" not in text
    assert "      Events:" not in text


def test_template_references_existing_tables_as_parameters():
    text = TEMPLATE.read_text()

    for name in (
        "PaymentsTableName",
        "AccountsTableName",
        "LedgerTableName",
        "DataBucketName",
    ):
        assert f"  {name}:" in text


def test_template_does_not_modify_original_stack():
    text = TEMPLATE.read_text()

    assert "PosterFunction:" not in text
    assert "IngestFunction:" not in text
    assert "FinalizeFunction:" not in text
    assert "PaymentsTable:\n" not in text
    assert "AccountsTable:\n" not in text


def test_transaction_permissions_include_transact_write_items():
    text = TEMPLATE.read_text()

    # The settlement executor and reservation both call
    # transact_write_items, which requires this IAM permission.
    assert "dynamodb:TransactWriteItems" in text

    for action in (
        "dynamodb:GetItem",
        "dynamodb:UpdateItem",
        "dynamodb:PutItem",
        "dynamodb:ConditionCheckItem",
    ):
        assert action in text


def test_ledger_writes_are_limited_to_ledger_table():
    text = TEMPLATE.read_text()

    # Scope to the SettlePendingFunction section so the
    # CollectPendingFunction's SettlementsTable PutItem policy
    # (used for window leases) doesn't interfere with the split.
    settle_section = text.split(
        "  SettlePendingFunction:", 1
    )[1].split(
        "  LiquiditySettlementStateMachine:", 1
    )[0]

    ledger_policy = settle_section.split(
        "                - dynamodb:PutItem", 1
    )[1].split(
        "            - Effect: Allow", 1
    )[0]

    assert "table/${LedgerTableName}" in ledger_policy
    assert "table/${PaymentsTableName}" not in ledger_policy
    assert "table/${AccountsTableName}" not in ledger_policy


def test_batch_workflow_remains_disabled_after_iam_changes():
    text = TEMPLATE.read_text()

    # The Lambda must be functional (batch mode enabled) so it can
    # be invoked manually. Safety comes from no automatic trigger.
    assert 'LIQUIDITY_BATCH_MODE: "1"' in text
    assert "ScheduleV2" not in text
    assert "Type: SQS" not in text


def test_workflow_passes_demo_run_id_to_collector():
    states = json.loads(WORKFLOW.read_text())["States"]
    payload = states["CollectPending"]["Parameters"]["Payload"]
    assert payload["run_id.$"] == "$.run_id"
    assert payload["start_time.$"] == "$$.Execution.StartTime"


def test_collector_and_settler_persist_s3_list_permission():
    text = TEMPLATE.read_text()
    assert text.count("- s3:ListBucket") == 2
    assert text.count('arn:${AWS::Partition}:s3:::${DataBucketName}"') == 2
