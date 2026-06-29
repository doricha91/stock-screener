from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts import runbook_command_registry as registry


def test_registry_validation_passes() -> None:
    assert registry.validate_registry() == []


def test_step_0_to_18_are_all_registered() -> None:
    commands = registry.list_commands()

    assert [command.step_id for command in commands] == list(range(19))
    assert [command.command_key for command in commands] == [
        "status",
        "data_prepare",
        "data_freshness",
        "daily_plan",
        "export_daily_plan_notion",
        "export_execution_template",
        "wait_execution_input",
        "execution_preview",
        "execution_commit",
        "sync_execution_status",
        "daily_review",
        "export_review_template",
        "wait_review_input",
        "review_preview",
        "review_append",
        "sync_review_status",
        "eod_dryrun",
        "eod_commit",
        "final_status",
    ]


def test_command_key_and_step_id_are_unique() -> None:
    commands = registry.list_commands()
    command_keys = [command.command_key for command in commands]
    step_ids = [command.step_id for command in commands]

    assert len(command_keys) == len(set(command_keys))
    assert len(step_ids) == len(set(step_ids))


def test_stage_eligibility_mapping() -> None:
    by_step = {command.step_id: command for command in registry.list_commands()}

    assert {by_step[step].stage_id for step in range(0, 6)} == {"A"}
    assert by_step[6].stage_id == "GATE1"
    assert {by_step[step].stage_id for step in range(7, 12)} == {"B"}
    assert by_step[12].stage_id == "GATE2"
    assert {by_step[step].stage_id for step in range(13, 19)} == {"C"}


def test_phase1_auto_execute_and_manual_gates() -> None:
    by_step = {command.step_id: command for command in registry.list_commands()}

    for step in [*range(0, 6), *range(7, 12), *range(13, 19)]:
        assert by_step[step].phase1_auto_execute is True
        assert by_step[step].manual_gate is False

    for step in (6, 12):
        assert by_step[step].manual_gate is True
        assert by_step[step].phase1_auto_execute is False
        assert by_step[step].command_type == "BLOCKED"
        assert by_step[step].argv_template == ()


def test_phase1_and_phase2_policy_are_separated() -> None:
    commit_steps = [
        registry.get_command("execution_commit"),
        registry.get_command("review_append"),
        registry.get_command("eod_commit"),
    ]

    for command in commit_steps:
        assert command.phase1_auto_execute is True
        assert command.phase2_interactive_policy == "request_approve_required"


def test_artifact_dependency_metadata_for_commit_steps() -> None:
    execution_commit = registry.get_command("execution_commit")
    review_append = registry.get_command("review_append")
    eod_commit = registry.get_command("eod_commit")

    assert execution_commit.requires_preview_artifact is True
    assert "execution_preview_json" in execution_commit.required_prior_artifacts
    assert execution_commit.duplicate_run_policy == registry.STRICT_ONCE_PER_ACCOUNT_TRADE_DATE

    assert review_append.requires_preview_artifact is True
    assert "review_preview_json" in review_append.required_prior_artifacts
    assert review_append.duplicate_run_policy == registry.STRICT_ONCE_PER_ACCOUNT_TRADE_DATE

    assert eod_commit.requires_preview_artifact is True
    assert eod_commit.requires_dryrun_pass is True
    assert "eod_dryrun_result" in eod_commit.required_prior_artifacts
    assert eod_commit.duplicate_run_policy == registry.STRICT_ONCE_PER_ACCOUNT_TRADE_DATE


def test_strict_once_commands_are_only_duplicate_sensitive_commit_steps() -> None:
    strict_once = {
        command.step_id: command.command_key
        for command in registry.list_commands()
        if command.duplicate_run_policy == registry.STRICT_ONCE_PER_ACCOUNT_TRADE_DATE
    }

    assert strict_once == {
        8: "execution_commit",
        14: "review_append",
        17: "eod_commit",
    }
    for command_key in strict_once.values():
        command = registry.get_command(command_key)
        assert command.idempotency_key_fields
        assert command.required_prior_artifacts


def test_commit_report_dependency_metadata_for_sync_steps() -> None:
    sync_execution = registry.get_command("sync_execution_status")
    sync_review = registry.get_command("sync_review_status")

    assert sync_execution.requires_commit_report is True
    assert "execution_commit_report" in sync_execution.required_prior_artifacts

    assert sync_review.requires_commit_report is True
    assert "review_commit_report" in sync_review.required_prior_artifacts


def test_argv_templates_are_list_like_without_raw_shell_strings() -> None:
    for command in registry.list_commands():
        assert isinstance(command.argv_template, tuple)
        if command.manual_gate:
            assert command.argv_template == ()
            continue

        assert command.argv_template
        assert all(isinstance(part, str) for part in command.argv_template)
        assert not any(" && " in part or " | " in part or ";" in part for part in command.argv_template)


def test_read_only_cli_validate_registry() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts\\runbook_command_registry.py", "validate-registry"],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )

    assert completed.returncode == 0
    assert '"runner_result": "PASS"' in completed.stdout
