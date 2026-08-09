from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from scripts import runbook_command_registry
from scripts import runbook_completion_evidence
from scripts import runbook_result
from scripts import runbook_state


def seed_standard_export_evidence(
    workspace: Path,
    state: runbook_state.RunbookState,
) -> runbook_state.RunbookState:
    stage_status = dict(state.stage_status)
    for stage_id in runbook_completion_evidence.STANDARD_REQUIRED_PASS_STAGES:
        stage_status[stage_id] = "PASS"
    state = replace(state, stage_status=stage_status)
    payloads = {
        "export_daily_plan_notion": {
            "json": [{
                "target": "daily_plans",
                "account_id": state.frozen_context.account_id,
                "external_key": (
                    f"daily_plan:{state.frozen_context.account_id}:{state.frozen_context.trade_date}"
                ),
                "failed_count": 0,
                "dry_run": False,
            }],
        },
        "export_execution_template": {
            "target": "manual_execution_template",
            "account_id": state.frozen_context.account_id,
            "execution_date": state.frozen_context.trade_date,
            "candidate_count": 1,
            "create_count": 1,
            "update_count": 0,
            "skip_count": 0,
            "failed_count": 0,
            "dry_run": False,
            "would_write": True,
        },
        "export_review_template": {
            "target": "manual_review_template",
            "account_id": state.frozen_context.account_id,
            "review_date": state.frozen_context.trade_date,
            "candidate_count": 1,
            "create_count": 1,
            "update_count": 0,
            "skip_count": 0,
            "failed_count": 0,
            "dry_run": False,
            "would_write": True,
        },
    }
    results_by_stage: dict[str, list[dict[str, object]]] = {"A": [], "C": []}
    review_result_path: Path | None = None
    for command_key, raw_payload in payloads.items():
        command = runbook_command_registry.get_command(command_key)
        result = runbook_result.create_command_result(
            state,
            command,
            "PASS",
            "PASS",
            raw_payload=raw_payload,
            process={"executed": True, "exit_code": 0, "duration_ms": 1},
            workspace=workspace,
        )
        result_path, _ = runbook_result.write_command_result(workspace, state, command, result)
        stored = json.loads(result_path.read_text(encoding="utf-8"))
        results_by_stage[command.stage_id].append(stored)
        if command_key == "export_review_template":
            review_result_path = result_path
    for stage_id, results in results_by_stage.items():
        summary = runbook_result.create_stage_summary(state, stage_id, results)
        runbook_result.write_stage_summary(workspace, state, summary)
    assert review_result_path is not None
    return runbook_state.record_artifact(
        state,
        "notion_review_template_report_json",
        str(review_result_path),
        workspace,
    )
