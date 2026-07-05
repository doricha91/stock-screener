from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from typing import Iterable, Sequence


STAGE_IDS = {"A", "GATE1", "B", "GATE2", "C"}
COMMAND_TYPES = {
    "READ_ONLY",
    "READ_ONLY_PREVIEW",
    "LOCAL_ARTIFACT_WRITE",
    "NOTION_WRITE",
    "LEDGER_WRITE",
    "STATE_SNAPSHOT_WRITE",
    "UNKNOWN",
    "BLOCKED",
}
STRICT_ONCE_PER_ACCOUNT_TRADE_DATE = "strict_once_per_account_trade_date"
NO_EXECUTABLE_ARGV: tuple[str, ...] = ()


@dataclass(frozen=True)
class RunbookCommand:
    command_key: str
    step_id: int
    stage_id: str
    stage_order: int
    display_name: str
    argv_template: tuple[str, ...]
    command_type: str
    phase1_auto_execute: bool
    manual_gate: bool
    phase1_stage_policy: str
    phase2_interactive_policy: str
    required_context_fields: tuple[str, ...]
    required_prior_artifacts: tuple[str, ...]
    produces_artifacts: tuple[str, ...]
    expected_outputs: tuple[str, ...]
    success_criteria: str
    failure_policy: str
    post_run_refresh: str
    idempotency_key_fields: tuple[str, ...]
    duplicate_run_policy: str
    requires_preview_artifact: bool
    requires_commit_report: bool
    requires_dryrun_pass: bool
    blocks_next_stage_on_failure: bool
    notes: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _argv(*parts: str) -> tuple[str, ...]:
    return tuple(parts)


def _command(
    *,
    command_key: str,
    step_id: int,
    stage_id: str,
    stage_order: int,
    display_name: str,
    argv_template: Sequence[str],
    command_type: str,
    phase1_auto_execute: bool,
    manual_gate: bool = False,
    phase1_stage_policy: str = "auto_with_stage_guards",
    phase2_interactive_policy: str | None = None,
    required_context_fields: Sequence[str] = ("account_id", "data_date", "trade_date"),
    required_prior_artifacts: Sequence[str] = (),
    produces_artifacts: Sequence[str] = (),
    expected_outputs: Sequence[str] = (),
    success_criteria: str = "exit_code=0",
    failure_policy: str = "stop_stage_and_push_failed",
    post_run_refresh: str = "none",
    idempotency_key_fields: Sequence[str] = ("account_id", "trade_date", "command_key"),
    duplicate_run_policy: str = "allow_readonly_rerun",
    requires_preview_artifact: bool = False,
    requires_commit_report: bool = False,
    requires_dryrun_pass: bool = False,
    blocks_next_stage_on_failure: bool = True,
    notes: str = "",
) -> RunbookCommand:
    if phase2_interactive_policy is None:
        phase2_interactive_policy = (
            "not_executable" if command_type == "BLOCKED"
            else "run_allowed" if command_type in {"READ_ONLY", "READ_ONLY_PREVIEW"}
            else "request_approve_required"
        )
    return RunbookCommand(
        command_key=command_key,
        step_id=step_id,
        stage_id=stage_id,
        stage_order=stage_order,
        display_name=display_name,
        argv_template=tuple(argv_template),
        command_type=command_type,
        phase1_auto_execute=phase1_auto_execute,
        manual_gate=manual_gate,
        phase1_stage_policy=phase1_stage_policy,
        phase2_interactive_policy=phase2_interactive_policy,
        required_context_fields=tuple(required_context_fields),
        required_prior_artifacts=tuple(required_prior_artifacts),
        produces_artifacts=tuple(produces_artifacts),
        expected_outputs=tuple(expected_outputs),
        success_criteria=success_criteria,
        failure_policy=failure_policy,
        post_run_refresh=post_run_refresh,
        idempotency_key_fields=tuple(idempotency_key_fields),
        duplicate_run_policy=duplicate_run_policy,
        requires_preview_artifact=requires_preview_artifact,
        requires_commit_report=requires_commit_report,
        requires_dryrun_pass=requires_dryrun_pass,
        blocks_next_stage_on_failure=blocks_next_stage_on_failure,
        notes=notes,
    )


RUNBOOK_COMMANDS: tuple[RunbookCommand, ...] = (
    _command(
        command_key="status",
        step_id=0,
        stage_id="A",
        stage_order=0,
        display_name="Orchestrator status",
        argv_template=_argv(
            "scripts\\paper_daily_ops.py",
            "status",
            "--account-id",
            "{account_id}",
            "--data-date",
            "{data_date}",
            "--trade-date",
            "{trade_date}",
            "--json",
            "--include-notion-read",
        ),
        command_type="READ_ONLY",
        phase1_auto_execute=True,
        produces_artifacts=("operator_summary_json",),
        expected_outputs=("overall_status", "operator_summary"),
        success_criteria="operator_summary exists and blockers are reviewed",
        failure_policy="stop_stage_and_push_failed_or_blocked",
    ),
    _command(
        command_key="data_prepare",
        step_id=1,
        stage_id="A",
        stage_order=1,
        display_name="Data prepare",
        argv_template=_argv("scripts\\paper.py", "prepare-data", "--date", "{data_date}", "--universe"),
        command_type="LOCAL_ARTIFACT_WRITE",
        phase1_auto_execute=True,
        expected_outputs=("prepared_data",),
        success_criteria="prepare errors absent",
        duplicate_run_policy="once_per_data_date",
    ),
    _command(
        command_key="data_freshness",
        step_id=2,
        stage_id="A",
        stage_order=2,
        display_name="Data freshness",
        argv_template=_argv("scripts\\paper.py", "data-freshness", "--date", "{data_date}"),
        command_type="READ_ONLY",
        phase1_auto_execute=True,
        expected_outputs=("freshness_result",),
        success_criteria="result=PASS",
    ),
    _command(
        command_key="daily_plan",
        step_id=3,
        stage_id="A",
        stage_order=3,
        display_name="Daily plan",
        argv_template=_argv(
            "scripts\\paper.py",
            "plan",
            "--data-date",
            "{data_date}",
            "--trade-date",
            "{trade_date}",
            "--account-id",
            "{account_id}",
        ),
        command_type="LOCAL_ARTIFACT_WRITE",
        phase1_auto_execute=True,
        produces_artifacts=("daily_plan_json", "daily_plan_markdown"),
        expected_outputs=("account_plan", "candidate_orders"),
        success_criteria="account plan artifacts written",
        duplicate_run_policy="replaceable_local_artifact_per_account_trade_date",
    ),
    _command(
        command_key="export_daily_plan_notion",
        step_id=4,
        stage_id="A",
        stage_order=4,
        display_name="Export daily plan to Notion",
        argv_template=_argv(
            "scripts\\export_paper_to_notion.py",
            "--daily-plan",
            "--account-id",
            "{account_id}",
            "--date",
            "{trade_date}",
            "--confirm-actual",
            "--json",
        ),
        command_type="NOTION_WRITE",
        phase1_auto_execute=True,
        required_prior_artifacts=("daily_plan_json",),
        expected_outputs=("notion_daily_plan_export_report",),
        success_criteria="failed count is 0",
        duplicate_run_policy="upsert_per_account_trade_date",
    ),
    _command(
        command_key="export_execution_template",
        step_id=5,
        stage_id="A",
        stage_order=5,
        display_name="Export execution template",
        argv_template=_argv(
            "scripts\\export_paper_to_notion.py",
            "--manual-execution-template",
            "--account-id",
            "{account_id}",
            "--date",
            "{trade_date}",
            "--confirm-actual",
            "--json",
        ),
        command_type="NOTION_WRITE",
        phase1_auto_execute=True,
        required_prior_artifacts=("daily_plan_json",),
        expected_outputs=("notion_execution_template_report",),
        success_criteria="candidate rows create/update or no-op",
        duplicate_run_policy="upsert_per_account_trade_date",
    ),
    _command(
        command_key="wait_execution_input",
        step_id=6,
        stage_id="GATE1",
        stage_order=0,
        display_name="Wait for execution input",
        argv_template=NO_EXECUTABLE_ARGV,
        command_type="BLOCKED",
        phase1_auto_execute=False,
        manual_gate=True,
        phase1_stage_policy="manual_gate_poll_only",
        phase2_interactive_policy="not_executable",
        expected_outputs=("gate1_readiness",),
        success_criteria="Actual Price present, Status=READY, Account ID and Execution Date match",
        failure_policy="push_wait_or_blocked_without_advancing_stage",
        idempotency_key_fields=("account_id", "trade_date", "manual_gate"),
        duplicate_run_policy="not_executable",
        blocks_next_stage_on_failure=True,
        notes="Manual Notion input gate; controller polls readiness only.",
    ),
    _command(
        command_key="execution_preview",
        step_id=7,
        stage_id="B",
        stage_order=0,
        display_name="Execution preview",
        argv_template=_argv(
            "scripts\\import_notion_executions.py",
            "--date",
            "{trade_date}",
            "--account-id",
            "{account_id}",
            "--preview",
            "--json",
        ),
        command_type="READ_ONLY_PREVIEW",
        phase1_auto_execute=True,
        produces_artifacts=("execution_preview_json",),
        expected_outputs=("fail_count", "commit_allowed", "execution_preview_json"),
        success_criteria="fail_count=0 and preview artifact is pinned",
    ),
    _command(
        command_key="execution_commit",
        step_id=8,
        stage_id="B",
        stage_order=1,
        display_name="Execution commit",
        argv_template=_argv(
            "scripts\\import_notion_executions.py",
            "--date",
            "{trade_date}",
            "--data-date",
            "{data_date}",
            "--account-id",
            "{account_id}",
            "--commit",
            "--preview-json",
            "{execution_preview_json}",
            "--reconciliation-preview-json",
            "{execution_reconciliation_preview_json}",
            "--json",
        ),
        command_type="LEDGER_WRITE",
        phase1_auto_execute=True,
        required_prior_artifacts=("execution_preview_json", "execution_reconciliation_preview_json"),
        produces_artifacts=("execution_commit_report",),
        expected_outputs=("committed_count", "execution_commit_report"),
        success_criteria="commit report written from pinned execution preview and PASS reconciliation preview",
        duplicate_run_policy=STRICT_ONCE_PER_ACCOUNT_TRADE_DATE,
        requires_preview_artifact=True,
    ),
    _command(
        command_key="sync_execution_status",
        step_id=9,
        stage_id="B",
        stage_order=2,
        display_name="Sync execution status",
        argv_template=_argv(
            "scripts\\sync_notion_execution_status.py",
            "--date",
            "{trade_date}",
            "--account-id",
            "{account_id}",
            "--commit-report",
            "{execution_commit_report}",
            "--json",
        ),
        command_type="NOTION_WRITE",
        phase1_auto_execute=True,
        required_prior_artifacts=("execution_commit_report",),
        expected_outputs=("notion_execution_sync_report",),
        success_criteria="failed count is 0",
        duplicate_run_policy="retry_same_commit_report_until_success",
        requires_commit_report=True,
    ),
    _command(
        command_key="daily_review",
        step_id=10,
        stage_id="B",
        stage_order=3,
        display_name="Daily review",
        argv_template=_argv(
            "scripts\\paper.py",
            "review",
            "--account-id",
            "{account_id}",
            "--date",
            "{trade_date}",
            "--json",
        ),
        command_type="LOCAL_ARTIFACT_WRITE",
        phase1_auto_execute=True,
        required_prior_artifacts=("execution_commit_report",),
        produces_artifacts=("daily_review_report",),
        expected_outputs=("daily_review_report",),
        success_criteria="review artifacts written",
        duplicate_run_policy="replaceable_local_artifact_per_account_trade_date",
    ),
    _command(
        command_key="export_review_template",
        step_id=11,
        stage_id="B",
        stage_order=4,
        display_name="Export review template",
        argv_template=_argv(
            "scripts\\export_paper_to_notion.py",
            "--manual-review-template",
            "--account-id",
            "{account_id}",
            "--date",
            "{trade_date}",
            "--confirm-actual",
            "--json",
        ),
        command_type="NOTION_WRITE",
        phase1_auto_execute=True,
        required_prior_artifacts=("daily_review_report",),
        expected_outputs=("notion_review_template_report",),
        success_criteria="review rows create/update and failed count is 0",
        duplicate_run_policy="upsert_per_account_trade_date",
    ),
    _command(
        command_key="wait_review_input",
        step_id=12,
        stage_id="GATE2",
        stage_order=0,
        display_name="Wait for review input",
        argv_template=NO_EXECUTABLE_ARGV,
        command_type="BLOCKED",
        phase1_auto_execute=False,
        manual_gate=True,
        phase1_stage_policy="manual_gate_poll_only",
        phase2_interactive_policy="not_executable",
        expected_outputs=("gate2_readiness",),
        success_criteria="Manual Answer present, Review Status reviewed, Import Status READY, Account ID and Review Date match",
        failure_policy="push_wait_or_blocked_without_advancing_stage",
        idempotency_key_fields=("account_id", "trade_date", "manual_gate"),
        duplicate_run_policy="not_executable",
        blocks_next_stage_on_failure=True,
        notes="Manual Notion input gate; controller polls readiness only.",
    ),
    _command(
        command_key="review_preview",
        step_id=13,
        stage_id="C",
        stage_order=0,
        display_name="Review preview",
        argv_template=_argv(
            "scripts\\import_notion_reviews.py",
            "--date",
            "{trade_date}",
            "--account-id",
            "{account_id}",
            "--preview",
            "--json",
        ),
        command_type="READ_ONLY_PREVIEW",
        phase1_auto_execute=True,
        produces_artifacts=("review_preview_json",),
        expected_outputs=("fail_count", "append_allowed", "review_preview_json"),
        success_criteria="fail_count=0 and review preview artifact is pinned",
    ),
    _command(
        command_key="review_append",
        step_id=14,
        stage_id="C",
        stage_order=1,
        display_name="Review append",
        argv_template=_argv(
            "scripts\\import_notion_reviews.py",
            "--date",
            "{trade_date}",
            "--account-id",
            "{account_id}",
            "--commit",
            "--preview-json",
            "{review_preview_json}",
            "--json",
        ),
        command_type="LEDGER_WRITE",
        phase1_auto_execute=True,
        required_prior_artifacts=("review_preview_json",),
        produces_artifacts=("review_commit_report",),
        expected_outputs=("appended_count", "review_commit_report"),
        success_criteria="append report written from pinned review preview",
        duplicate_run_policy=STRICT_ONCE_PER_ACCOUNT_TRADE_DATE,
        requires_preview_artifact=True,
    ),
    _command(
        command_key="sync_review_status",
        step_id=15,
        stage_id="C",
        stage_order=2,
        display_name="Sync review status",
        argv_template=_argv(
            "scripts\\sync_notion_review_status.py",
            "--date",
            "{trade_date}",
            "--account-id",
            "{account_id}",
            "--commit-report",
            "{review_commit_report}",
            "--json",
        ),
        command_type="NOTION_WRITE",
        phase1_auto_execute=True,
        required_prior_artifacts=("review_commit_report",),
        expected_outputs=("notion_review_sync_report",),
        success_criteria="failed count is 0",
        duplicate_run_policy="retry_same_commit_report_until_success",
        requires_commit_report=True,
    ),
    _command(
        command_key="eod_dryrun",
        step_id=16,
        stage_id="C",
        stage_order=3,
        display_name="EOD dry-run",
        argv_template=_argv("scripts\\paper.py", "eod", "--date", "{trade_date}", "--account-id", "{account_id}", "--dry-run"),
        command_type="READ_ONLY_PREVIEW",
        phase1_auto_execute=True,
        produces_artifacts=("eod_dryrun_result",),
        expected_outputs=("eod_mode", "would_write_current_state", "eod_dryrun_result"),
        success_criteria="dry-run PASS and accounting_close intent verified",
    ),
    _command(
        command_key="eod_commit",
        step_id=17,
        stage_id="C",
        stage_order=4,
        display_name="EOD commit",
        argv_template=_argv("scripts\\paper.py", "eod", "--date", "{trade_date}", "--account-id", "{account_id}", "--commit"),
        command_type="STATE_SNAPSHOT_WRITE",
        phase1_auto_execute=True,
        required_prior_artifacts=("eod_dryrun_result",),
        produces_artifacts=("eod_commit_report", "current_state_snapshot", "account_snapshot", "position_snapshot"),
        expected_outputs=("eod_commit_report",),
        success_criteria="eod dry-run PASS was pinned and state snapshots are written once",
        duplicate_run_policy=STRICT_ONCE_PER_ACCOUNT_TRADE_DATE,
        requires_preview_artifact=True,
        requires_dryrun_pass=True,
    ),
    _command(
        command_key="final_status",
        step_id=18,
        stage_id="C",
        stage_order=5,
        display_name="Final status",
        argv_template=_argv(
            "scripts\\paper_daily_ops.py",
            "status",
            "--account-id",
            "{account_id}",
            "--data-date",
            "{data_date}",
            "--trade-date",
            "{trade_date}",
            "--json",
            "--include-notion-read",
        ),
        command_type="READ_ONLY",
        phase1_auto_execute=True,
        required_prior_artifacts=("eod_commit_report",),
        expected_outputs=("overall_status", "operator_summary"),
        success_criteria="overall_status PASS or actionable WARNING is summarized",
        failure_policy="push_final_warning_or_failed",
    ),
)


def list_commands() -> tuple[RunbookCommand, ...]:
    return RUNBOOK_COMMANDS


def get_command(command_key: str) -> RunbookCommand:
    for command in RUNBOOK_COMMANDS:
        if command.command_key == command_key:
            return command
    raise KeyError(f"unknown runbook command_key: {command_key}")


def _duplicates(values: Iterable[object]) -> list[object]:
    seen: set[object] = set()
    duplicates: list[object] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return duplicates


def validate_registry(commands: Sequence[RunbookCommand] = RUNBOOK_COMMANDS) -> list[str]:
    errors: list[str] = []
    command_keys = [command.command_key for command in commands]
    step_ids = [command.step_id for command in commands]

    if len(commands) != 19:
        errors.append(f"expected 19 runbook commands, found {len(commands)}")
    if sorted(step_ids) != list(range(19)):
        errors.append(f"expected step_id coverage 0..18, found {sorted(step_ids)}")
    for duplicate in _duplicates(command_keys):
        errors.append(f"duplicate command_key: {duplicate}")
    for duplicate in _duplicates(step_ids):
        errors.append(f"duplicate step_id: {duplicate}")

    for command in commands:
        if command.stage_id not in STAGE_IDS:
            errors.append(f"{command.command_key}: invalid stage_id {command.stage_id}")
        if command.command_type not in COMMAND_TYPES:
            errors.append(f"{command.command_key}: invalid command_type {command.command_type}")
        if not isinstance(command.argv_template, tuple):
            errors.append(f"{command.command_key}: argv_template must be a tuple")
        if command.manual_gate:
            if command.argv_template:
                errors.append(f"{command.command_key}: manual gate must not define executable argv")
            if command.phase1_auto_execute:
                errors.append(f"{command.command_key}: manual gate must not phase1_auto_execute")
            if command.command_type != "BLOCKED":
                errors.append(f"{command.command_key}: manual gate must be BLOCKED")
        elif not command.argv_template:
            errors.append(f"{command.command_key}: executable command must define argv_template")
        if any(" " in part and part.endswith(".py") for part in command.argv_template):
            errors.append(f"{command.command_key}: argv_template appears to contain raw shell text")
        if command.stage_id == "A" and command.step_id not in range(0, 6):
            errors.append(f"{command.command_key}: Stage A must map to Step 0..5")
        if command.stage_id == "GATE1" and command.step_id != 6:
            errors.append(f"{command.command_key}: GATE1 must map to Step 6")
        if command.stage_id == "B" and command.step_id not in range(7, 12):
            errors.append(f"{command.command_key}: Stage B must map to Step 7..11")
        if command.stage_id == "GATE2" and command.step_id != 12:
            errors.append(f"{command.command_key}: GATE2 must map to Step 12")
        if command.stage_id == "C" and command.step_id not in range(13, 19):
            errors.append(f"{command.command_key}: Stage C must map to Step 13..18")
        if command.requires_preview_artifact and not command.required_prior_artifacts:
            errors.append(f"{command.command_key}: preview artifact requirement must name required_prior_artifacts")
        if command.requires_commit_report and not command.required_prior_artifacts:
            errors.append(f"{command.command_key}: commit report requirement must name required_prior_artifacts")
        if command.requires_dryrun_pass and "eod_dryrun_result" not in command.required_prior_artifacts:
            errors.append(f"{command.command_key}: dry-run PASS requirement must depend on eod_dryrun_result")

    return errors


def _json_default(value: object) -> object:
    if isinstance(value, tuple):
        return list(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _print_json(data: object) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, default=_json_default))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only Paper Daily runbook command registry")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="List registered command keys")
    get_parser = subparsers.add_parser("get", help="Show one registry entry")
    get_parser.add_argument("command_key")
    subparsers.add_parser("validate-registry", help="Validate registry metadata")

    args = parser.parse_args(argv)
    if args.command == "list":
        _print_json([{"step_id": command.step_id, "command_key": command.command_key} for command in RUNBOOK_COMMANDS])
        return 0
    if args.command == "get":
        try:
            _print_json(get_command(args.command_key).to_dict())
        except KeyError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        return 0
    if args.command == "validate-registry":
        errors = validate_registry()
        if errors:
            _print_json({"runner_result": "FAIL", "errors": errors})
            return 1
        _print_json({"runner_result": "PASS", "command_count": len(RUNBOOK_COMMANDS)})
        return 0
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
