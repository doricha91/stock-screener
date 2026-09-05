from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import runbook_gate_checker
from scripts import runbook_stage_b_verifier
from scripts import runbook_stage_runner
from scripts import runbook_state
from scripts.runbook_no_action import EvidenceError, load_stage_c_summary_evidence


FLOW_EXECUTION_TO_REVIEW = "EXECUTION_TO_REVIEW_PREP"
FLOW_REVIEW_PREVIEW = "REVIEW_PREVIEW"
FLOW_CLOSE_DAY = "CLOSE_DAY"
PASS_RESULTS = {"PASS", "SKIPPED"}
MANUAL_REVIEW_REQUIRED = "Fill Manual Review in Notion, then run primary 03."
MANUAL_REVIEW_NOT_REQUIRED = "No Manual Review input is required. Run primary 03."
REVIEW_PREVIEW_REQUIRED = "Review Stage D preview artifact, then run primary 04."
REVIEW_PREVIEW_NOT_REQUIRED = "No review preview is required. Run primary 04."


def _load_state(
    workspace: Path,
    account_id: str,
    data_date: str,
    trade_date: str,
) -> runbook_state.RunbookState:
    state_path = runbook_state.get_state_path_for_context(
        workspace,
        account_id,
        data_date,
        trade_date,
    )
    if not state_path.is_file():
        raise ValueError("runbook_state_not_found")
    state = runbook_state.load_state(state_path)
    if not runbook_state.context_matches_state(
        state,
        account_id,
        data_date,
        trade_date,
    ):
        raise ValueError("context_mismatch_existing_runbook_state")
    return state


def _outcome(result: dict[str, Any]) -> str:
    return str(result.get("runner_result") or "FAILED").upper()


def _step_status(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "runner_result": _outcome(result),
        "reason": result.get("reason"),
        "next_required_action": result.get("next_required_action"),
    }


def _already_pass() -> dict[str, Any]:
    return {
        "runner_result": "PASS",
        "resumed_from_state": True,
        "reason": "already_pass",
    }


def _not_run() -> dict[str, Any]:
    return {"runner_result": "NOT_RUN"}


def _completed_stage_c_result(
    workspace: Path,
    state: runbook_state.RunbookState,
) -> dict[str, Any]:
    summary, _ = load_stage_c_summary_evidence(workspace, state)
    summary_fields = summary.get("summary")
    return {
        "runner_result": "PASS",
        "next_required_action": (
            summary_fields.get("next_required_action")
            if isinstance(summary_fields, dict)
            else None
        ),
    }


def _primary_02_next_action(stage_c_result: dict[str, Any]) -> str:
    canonical_action = str(stage_c_result.get("next_required_action") or "").strip()
    if (
        canonical_action.startswith("No Manual Review input is required.")
        or canonical_action.startswith("The canonical Manual Review scope is empty.")
    ):
        return MANUAL_REVIEW_NOT_REQUIRED
    if canonical_action.startswith("Fill Manual Review in Notion"):
        return MANUAL_REVIEW_REQUIRED
    return canonical_action or "Inspect the pinned Stage C result before running primary 03."


def _primary_03_next_action(preview_result: dict[str, Any]) -> str:
    preview_skipped = preview_result.get("review_preview_skipped") is True
    preview_missing = not preview_result.get("review_preview_json") and not preview_result.get(
        "review_preview_md"
    )
    if preview_skipped or preview_missing:
        return REVIEW_PREVIEW_NOT_REQUIRED
    return REVIEW_PREVIEW_REQUIRED


def _base_result(flow: str, state: runbook_state.RunbookState) -> dict[str, Any]:
    return {
        "primary_flow": flow,
        "runbook_day_id": state.runbook_day_id,
        "frozen_context": state.to_dict()["frozen_context"],
    }


def _stopped(
    *,
    flow: str,
    state: runbook_state.RunbookState,
    stages: dict[str, dict[str, Any]],
    stopped_at: str,
    result: dict[str, Any],
    recovery_command: str,
) -> dict[str, Any]:
    return {
        **_base_result(flow, state),
        "runner_result": _outcome(result),
        "stopped_at": stopped_at,
        "stages": stages,
        "completed_stages": [
            name
            for name, item in stages.items()
            if item.get("runner_result") == "PASS"
        ],
        "no_downstream_stage_executed": True,
        "recovery_command": recovery_command,
        "next_required_action": (
            result.get("next_required_action")
            or f"Inspect {stopped_at}, then use the detailed recovery command."
        ),
    }


def _completed(
    *,
    flow: str,
    state: runbook_state.RunbookState,
    stages: dict[str, dict[str, Any]],
    next_required_action: str,
) -> dict[str, Any]:
    return {
        **_base_result(flow, state),
        "runner_result": "PASS",
        "stopped_at": None,
        "stages": stages,
        "completed_stages": list(stages),
        "no_downstream_stage_executed": False,
        "recovery_command": None,
        "next_required_action": next_required_action,
    }


def run_execution_to_review_prep(
    workspace: Path,
    account_id: str,
    data_date: str,
    trade_date: str,
    *,
    timezone: str = "Asia/Seoul",
    confirm_paper_test: bool = False,
) -> dict[str, Any]:
    workspace = Path(workspace).resolve(strict=False)
    try:
        state = _load_state(workspace, account_id, data_date, trade_date)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        return {
            "primary_flow": FLOW_EXECUTION_TO_REVIEW,
            "runner_result": "BLOCKED",
            "stopped_at": "STATE",
            "stages": {},
            "reason": str(exc),
            "recovery_command": "ops\\runbook_wrappers\\01_stage_a_plan_prep.cmd",
            "next_required_action": "Repair or complete Stage A before primary 02.",
        }

    stages = {
        "GATE1": _not_run(),
        "STAGE_B": _not_run(),
        "STAGE_B_VERIFICATION": _not_run(),
        "STAGE_C": _not_run(),
    }
    if state.stage_status.get("C") == "PASS":
        for name in stages:
            stages[name] = _already_pass()
        try:
            stage_c_result = _completed_stage_c_result(workspace, state)
        except EvidenceError as exc:
            return _stopped(
                flow=FLOW_EXECUTION_TO_REVIEW,
                state=state,
                stages=stages,
                stopped_at="STAGE_C_EVIDENCE",
                result={
                    "runner_result": "BLOCKED",
                    "reason": exc.reason,
                    "next_required_action": "Inspect the pinned Stage C result before retrying primary 02.",
                },
                recovery_command="ops\\runbook_wrappers\\05_stage_c_review_prep.cmd",
            )
        return _completed(
            flow=FLOW_EXECUTION_TO_REVIEW,
            state=state,
            stages=stages,
            next_required_action=_primary_02_next_action(stage_c_result),
        )

    if state.stage_status.get("GATE1") == "PASS":
        stages["GATE1"] = _already_pass()
    else:
        gate1 = runbook_gate_checker.check_gate1_execution_input(
            workspace,
            account_id,
            data_date,
            trade_date,
            timezone=timezone,
        )
        stages["GATE1"] = _step_status(gate1)
        if _outcome(gate1) != "PASS":
            return _stopped(
                flow=FLOW_EXECUTION_TO_REVIEW,
                state=state,
                stages=stages,
                stopped_at="GATE1",
                result=gate1,
                recovery_command="ops\\runbook_wrappers\\02_gate1_execution_input.cmd",
            )

    state = _load_state(workspace, account_id, data_date, trade_date)
    if state.stage_status.get("B") == "PASS":
        stages["STAGE_B"] = _already_pass()
    else:
        stage_b = runbook_stage_runner.run_stage_b(
            workspace,
            account_id,
            data_date,
            trade_date,
            timezone=timezone,
            confirm_paper_test=confirm_paper_test,
        )
        stages["STAGE_B"] = _step_status(stage_b)
        if _outcome(stage_b) != "PASS":
            return _stopped(
                flow=FLOW_EXECUTION_TO_REVIEW,
                state=state,
                stages=stages,
                stopped_at="STAGE_B",
                result=stage_b,
                recovery_command="ops\\runbook_wrappers\\03_stage_b_execution_commit_sync.cmd",
            )

    verification = runbook_stage_b_verifier.verify_stage_b_completion(
        workspace=workspace,
        account_id=account_id,
        data_date=data_date,
        trade_date=trade_date,
        timezone=timezone,
    )
    stages["STAGE_B_VERIFICATION"] = _step_status(verification)
    if _outcome(verification) != "PASS":
        return _stopped(
            flow=FLOW_EXECUTION_TO_REVIEW,
            state=_load_state(workspace, account_id, data_date, trade_date),
            stages=stages,
            stopped_at="STAGE_B_VERIFICATION",
            result=verification,
            recovery_command="ops\\runbook_wrappers\\04_stage_b_verify.cmd",
        )

    state = _load_state(workspace, account_id, data_date, trade_date)
    if state.stage_status.get("C") == "PASS":
        stages["STAGE_C"] = _already_pass()
        try:
            stage_c_result = _completed_stage_c_result(workspace, state)
        except EvidenceError as exc:
            return _stopped(
                flow=FLOW_EXECUTION_TO_REVIEW,
                state=state,
                stages=stages,
                stopped_at="STAGE_C_EVIDENCE",
                result={
                    "runner_result": "BLOCKED",
                    "reason": exc.reason,
                    "next_required_action": "Inspect the pinned Stage C result before retrying primary 02.",
                },
                recovery_command="ops\\runbook_wrappers\\05_stage_c_review_prep.cmd",
            )
    else:
        stage_c_result = runbook_stage_runner.run_stage_c(
            workspace,
            account_id,
            data_date,
            trade_date,
            timezone=timezone,
            confirm_paper_test=confirm_paper_test,
        )
        stages["STAGE_C"] = _step_status(stage_c_result)
        if _outcome(stage_c_result) != "PASS":
            return _stopped(
                flow=FLOW_EXECUTION_TO_REVIEW,
                state=state,
                stages=stages,
                stopped_at="STAGE_C",
                result=stage_c_result,
                recovery_command="ops\\runbook_wrappers\\05_stage_c_review_prep.cmd",
            )

    return _completed(
        flow=FLOW_EXECUTION_TO_REVIEW,
        state=_load_state(workspace, account_id, data_date, trade_date),
        stages=stages,
        next_required_action=_primary_02_next_action(stage_c_result),
    )


def run_review_preview(
    workspace: Path,
    account_id: str,
    data_date: str,
    trade_date: str,
    *,
    timezone: str = "Asia/Seoul",
    confirm_paper_test: bool = False,
) -> dict[str, Any]:
    workspace = Path(workspace).resolve(strict=False)
    try:
        state = _load_state(workspace, account_id, data_date, trade_date)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        return {
            "primary_flow": FLOW_REVIEW_PREVIEW,
            "runner_result": "BLOCKED",
            "stopped_at": "STATE",
            "stages": {},
            "reason": str(exc),
            "recovery_command": "ops\\runbook_wrappers\\05_stage_c_review_prep.cmd",
            "next_required_action": "Repair or complete Stage C before primary 03.",
        }
    stages = {"GATE2": _not_run(), "STAGE_D_PREVIEW": _not_run()}

    if state.stage_status.get("GATE2") == "PASS":
        stages["GATE2"] = _already_pass()
    else:
        gate2 = runbook_stage_runner.check_gate2(
            workspace,
            account_id,
            data_date,
            trade_date,
            timezone=timezone,
            confirm_paper_test=confirm_paper_test,
        )
        stages["GATE2"] = _step_status(gate2)
        if _outcome(gate2) != "PASS":
            return _stopped(
                flow=FLOW_REVIEW_PREVIEW,
                state=state,
                stages=stages,
                stopped_at="GATE2",
                result=gate2,
                recovery_command="ops\\runbook_wrappers\\06_gate2_review_input.cmd",
            )

    preview = runbook_stage_runner.run_stage_d_preview(
        workspace,
        account_id,
        data_date,
        trade_date,
        timezone=timezone,
        confirm_paper_test=confirm_paper_test,
    )
    stages["STAGE_D_PREVIEW"] = _step_status(preview)
    if _outcome(preview) not in {"PASS", "WARNING", "SKIPPED"}:
        return _stopped(
            flow=FLOW_REVIEW_PREVIEW,
            state=_load_state(workspace, account_id, data_date, trade_date),
            stages=stages,
            stopped_at="STAGE_D_PREVIEW",
            result=preview,
            recovery_command="ops\\runbook_wrappers\\07_stage_d_preview.cmd",
        )
    stages["STAGE_D_PREVIEW"]["runner_result"] = "PASS"
    result = _completed(
        flow=FLOW_REVIEW_PREVIEW,
        state=_load_state(workspace, account_id, data_date, trade_date),
        stages=stages,
        next_required_action=_primary_03_next_action(preview),
    )
    result["preview_artifacts"] = {
        "review_preview_json": preview.get("review_preview_json"),
        "review_preview_md": preview.get("review_preview_md"),
    }
    return result


def run_close_day(
    workspace: Path,
    account_id: str,
    data_date: str,
    trade_date: str,
    *,
    timezone: str = "Asia/Seoul",
    confirm_paper_test: bool = False,
) -> dict[str, Any]:
    workspace = Path(workspace).resolve(strict=False)
    try:
        state = _load_state(workspace, account_id, data_date, trade_date)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        return {
            "primary_flow": FLOW_CLOSE_DAY,
            "runner_result": "BLOCKED",
            "stopped_at": "STATE",
            "stages": {},
            "reason": str(exc),
            "recovery_command": "ops\\runbook_wrappers\\07_stage_d_preview.cmd",
            "next_required_action": "Repair or review Stage D preview before primary 04.",
        }
    stages = {"STAGE_D": _not_run(), "STAGE_E": _not_run(), "STAGE_F": _not_run()}

    if state.stage_status.get("D") == "PASS":
        stages["STAGE_D"] = _already_pass()
    else:
        stage_d = runbook_stage_runner.run_stage_d_append(
            workspace,
            account_id,
            data_date,
            trade_date,
            timezone=timezone,
            confirm_paper_test=confirm_paper_test,
        )
        stages["STAGE_D"] = _step_status(stage_d)
        if _outcome(stage_d) != "PASS":
            return _stopped(
                flow=FLOW_CLOSE_DAY,
                state=state,
                stages=stages,
                stopped_at="STAGE_D",
                result=stage_d,
                recovery_command="ops\\runbook_wrappers\\08_stage_d_append_sync.cmd",
            )

    state = _load_state(workspace, account_id, data_date, trade_date)
    if state.stage_status.get("E") == "PASS":
        stages["STAGE_E"] = _already_pass()
    else:
        stage_e = runbook_stage_runner.run_stage_e(
            workspace,
            account_id,
            data_date,
            trade_date,
            timezone=timezone,
            confirm_paper_test=confirm_paper_test,
        )
        stages["STAGE_E"] = _step_status(stage_e)
        if _outcome(stage_e) != "PASS":
            return _stopped(
                flow=FLOW_CLOSE_DAY,
                state=state,
                stages=stages,
                stopped_at="STAGE_E",
                result=stage_e,
                recovery_command="ops\\runbook_wrappers\\09_stage_e_eod_close.cmd",
            )

    stage_f = runbook_stage_runner.run_stage_f(
        workspace,
        account_id,
        data_date,
        trade_date,
        timezone=timezone,
        confirm_paper_test=confirm_paper_test,
    )
    stages["STAGE_F"] = _step_status(stage_f)
    if _outcome(stage_f) not in PASS_RESULTS:
        return _stopped(
            flow=FLOW_CLOSE_DAY,
            state=_load_state(workspace, account_id, data_date, trade_date),
            stages=stages,
            stopped_at="STAGE_F",
            result=stage_f,
            recovery_command="ops\\runbook_wrappers\\10_stage_f_benchmark_notion_sync.cmd",
        )
    stages["STAGE_F"]["runner_result"] = "PASS"
    return _completed(
        flow=FLOW_CLOSE_DAY,
        state=_load_state(workspace, account_id, data_date, trade_date),
        stages=stages,
        next_required_action="Runbook day complete.",
    )


def format_operator_summary(result: dict[str, Any]) -> str:
    lines = [
        "-" * 50,
        f"Primary flow: {result.get('primary_flow')}",
        f"Runbook: {result.get('runbook_day_id', 'UNKNOWN')}",
    ]
    for name, item in result.get("stages", {}).items():
        lines.append(f"{name}: {item.get('runner_result', 'NOT_RUN')}")
    if result.get("stopped_at"):
        lines.extend(
            [
                f"STOPPED_AT: {result['stopped_at']}",
                "No downstream stage was executed.",
                f"Recovery: {result.get('recovery_command')}",
            ]
        )
    else:
        lines.append(f"STOP: {result.get('next_required_action')}")
    lines.extend([f"Result: {result.get('runner_result')}", "-" * 50])
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one consolidated daily Runbook flow.")
    parser.add_argument("flow", choices=("execution-to-review-prep", "review-preview", "close-day"))
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--data-date", required=True)
    parser.add_argument("--trade-date", required=True)
    parser.add_argument("--timezone", default="Asia/Seoul")
    parser.add_argument("--confirm-paper-test", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    runners: dict[str, Callable[..., dict[str, Any]]] = {
        "execution-to-review-prep": run_execution_to_review_prep,
        "review-preview": run_review_preview,
        "close-day": run_close_day,
    }
    result = runners[args.flow](
        args.workspace,
        args.account_id,
        args.data_date,
        args.trade_date,
        timezone=args.timezone,
        confirm_paper_test=args.confirm_paper_test,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(format_operator_summary(result))
    if result.get("runner_result") == "PASS":
        return 0
    if result.get("runner_result") in {"WAIT", "BLOCKED"}:
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
