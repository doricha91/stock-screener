from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.execution_outcome_flow import derive_execution_preview
from core.paper_account_paths import build_paper_account_paths
from scripts import runbook_state
from scripts.runbook_gate_checker import query_manual_execution_rows
from scripts.runbook_state import RunbookState


RECONCILIATION_RUNS_DIRNAME = "reconciliation_runs"
PREVIEW_BASENAME = "execution_reconciliation_preview"

ExecutionRowFetcher = Callable[[RunbookState], list[dict[str, Any]]]


def run_execution_reconciliation_preview(
    workspace: Path,
    account_id: str,
    data_date: str,
    trade_date: str,
    *,
    timezone: str = "Asia/Seoul",
    daily_plan_path: Path | None = None,
    manual_executions_path: Path | None = None,
    row_fetcher: ExecutionRowFetcher | None = None,
    account_root: Path | None = None,
) -> dict[str, Any]:
    workspace = Path(workspace)
    state = _load_or_create_state(workspace, account_id, data_date, trade_date, timezone)
    if not runbook_state.context_matches_state(state, account_id, data_date, trade_date):
        raise ValueError("context_mismatch_existing_runbook_state")

    resolved_plan_path = daily_plan_path or _default_daily_plan_sidecar_path(
        account_id,
        trade_date,
        account_root=account_root,
    )
    daily_plan = _read_json_file(resolved_plan_path)
    execution_rows = _load_execution_rows(state, manual_executions_path, row_fetcher)
    execution_contract = runbook_state.get_execution_contract(state)
    preview = derive_execution_preview(
        daily_plan,
        execution_rows,
        account_id=account_id,
        data_date=data_date,
        trade_date=trade_date,
        contract_version=str(execution_contract.get("version") or ""),
        input_finalized=execution_contract.get("input_finalized"),
        daily_plan_path=str(resolved_plan_path),
    )
    workspace_paths = write_workspace_preview(workspace, state, preview)
    account_paths = write_account_preview(account_id, trade_date, preview, account_root=account_root)
    return {
        "runner_result": preview["runner_result"],
        "runbook_day_id": state.runbook_day_id,
        "planned_count": preview.get("planned_count", 0),
        "actual_count": preview.get("actual_count", preview.get("execution_input_count", 0)),
        "notion_row_count": preview.get("notion_row_count", preview.get("execution_input_count", 0)),
        "matched_count": preview.get("matched_count", preview.get("resolved_count", 0)),
        "deviated_count": preview.get("deviated_count", 0),
        "missing_count": preview.get("missing_count", 0),
        "extra_count": preview.get("extra_count", 0),
        "warning_count": preview.get("warning_count", 0),
        "needs_review_count": preview.get("needs_review_count", preview.get("waiting_count", 0)),
        "blocked_count": preview.get("blocked_count", preview.get("invalid_count", 0)),
        "preview_json": str(workspace_paths["json"]),
        "preview_md": str(workspace_paths["md"]),
        "latest_preview_json": str(workspace_paths["latest_json"]),
        "latest_preview_md": str(workspace_paths["latest_md"]),
        "account_preview_json": str(account_paths["json"]),
        "account_preview_md": str(account_paths["md"]),
        "next_required_action": preview.get("next_required_action", "Proceed to commit." if preview["runner_result"] == "PASS" else "Resolve execution outcome input."),
    }


def write_workspace_preview(workspace: Path, state: RunbookState, preview: dict[str, Any]) -> dict[str, Path]:
    paths = get_workspace_preview_paths(workspace, state.runbook_day_id)
    paths["json"].parent.mkdir(parents=True, exist_ok=True)
    _write_json(paths["json"], preview)
    paths["md"].write_text(format_preview_markdown(preview), encoding="utf-8")
    _write_json(paths["latest_json"], preview)
    paths["latest_md"].write_text(format_preview_markdown(preview), encoding="utf-8")
    return paths


def write_account_preview(
    account_id: str,
    trade_date: str,
    preview: dict[str, Any],
    *,
    account_root: Path | None = None,
) -> dict[str, Path]:
    account_paths = build_paper_account_paths(account_id, account_root=account_root, create=True)
    output_dir = account_paths.root / "reconciliation"
    output_dir.mkdir(parents=True, exist_ok=True)
    compact_date = trade_date.replace("-", "")
    json_path = output_dir / f"{PREVIEW_BASENAME}_{compact_date}.json"
    md_path = output_dir / f"{PREVIEW_BASENAME}_{compact_date}.md"
    _write_json(json_path, preview)
    md_path.write_text(format_preview_markdown(preview), encoding="utf-8")
    return {"json": json_path, "md": md_path}


def get_reconciliation_runs_dir(workspace: Path, runbook_day_id: str) -> Path:
    return Path(workspace) / RECONCILIATION_RUNS_DIRNAME / runbook_day_id


def get_workspace_preview_paths(
    workspace: Path,
    runbook_day_id: str,
    timestamp: str | None = None,
) -> dict[str, Path]:
    timestamp = timestamp or _filename_timestamp()
    base = get_reconciliation_runs_dir(workspace, runbook_day_id)
    return {
        "json": base / f"{timestamp}_{PREVIEW_BASENAME}.json",
        "md": base / f"{timestamp}_{PREVIEW_BASENAME}.md",
        "latest_json": base / f"latest_{PREVIEW_BASENAME}.json",
        "latest_md": base / f"latest_{PREVIEW_BASENAME}.md",
    }


def format_preview_markdown(preview: dict[str, Any]) -> str:
    if preview.get("schema_version") == "execution_reconciliation_preview.v2":
        return _format_outcome_preview_markdown(preview)
    lines = [
        f"# Execution Reconciliation Preview - {preview['runner_result']}",
        "",
        f"- Account: {preview['account_id']}",
        f"- Data date: {preview['data_date']}",
        f"- Trade date: {preview['trade_date']}",
        f"- Planned: {preview['planned_count']}",
        f"- Actual: {preview['actual_count']}",
        f"- Matched: {preview['matched_count']}",
        f"- Deviated: {preview['deviated_count']}",
        f"- Missing: {preview['missing_count']}",
        f"- Extra: {preview['extra_count']}",
        f"- Warning: {preview['warning_count']}",
        f"- Needs review: {preview['needs_review_count']}",
        f"- Blocked: {preview['blocked_count']}",
        f"- Next action: {preview['next_required_action']}",
        "",
        "| Status | Severity | Symbol | Side | Planned Qty | Actual Qty | Planned Price | Actual Price | Message |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in preview.get("rows", []):
        lines.append(
            "| {status} | {severity} | {symbol} | {side} | {p_qty} | {a_qty} | {p_price} | {a_price} | {message} |".format(
                status=row.get("reconciliation_status") or "",
                severity=row.get("severity") or "",
                symbol=row.get("symbol") or "",
                side=row.get("side") or "",
                p_qty=_md_value(row.get("planned_quantity")),
                a_qty=_md_value(row.get("actual_quantity")),
                p_price=_md_value(row.get("planned_price")),
                a_price=_md_value(row.get("actual_price")),
                message=_escape_md_cell(row.get("message")),
            )
        )
    return "\n".join(lines) + "\n"


def _format_outcome_preview_markdown(preview: dict[str, Any]) -> str:
    lines = [
        f"# Execution Outcome Preview - {preview['runner_result']}",
        "",
        f"- Contract: {preview.get('schema_version')}",
        f"- Finalized: {preview.get('input_finalized')}",
        f"- Planned: {preview.get('planned_count', 0)}",
        f"- Executed: {preview.get('executed_count', 0)}",
        f"- Partial: {preview.get('partial_count', 0)}",
        f"- Not executed: {preview.get('not_executed_count', 0)}",
        f"- Waiting: {preview.get('waiting_count', 0)}",
        f"- Invalid: {preview.get('invalid_count', 0)}",
        "",
        "| Outcome | Status | Symbol | Side | Planned Qty | Actual Qty | Actual Price | Reason |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in preview.get("rows", []):
        lines.append(
            "| {outcome} | {status} | {symbol} | {side} | {planned} | {actual} | {price} | {reason} |".format(
                outcome=row.get("outcome") or "",
                status=row.get("status") or "",
                symbol=row.get("symbol") or "",
                side=row.get("side") or "",
                planned=_md_value(row.get("planned_quantity")),
                actual=_md_value(row.get("actual_quantity")),
                price=_md_value(row.get("actual_price")),
                reason=row.get("reason_code") or "",
            )
        )
    return "\n".join(lines) + "\n"


def _load_or_create_state(
    workspace: Path,
    account_id: str,
    data_date: str,
    trade_date: str,
    timezone: str,
) -> RunbookState:
    state_path = runbook_state.get_state_path_for_context(workspace, account_id, data_date, trade_date)
    if state_path.exists():
        return runbook_state.load_state(state_path)
    return runbook_state.create_initial_state(account_id, data_date, trade_date, timezone)


def _default_daily_plan_sidecar_path(
    account_id: str,
    trade_date: str,
    *,
    account_root: Path | None = None,
) -> Path:
    paths = build_paper_account_paths(account_id, account_root=account_root, create=False)
    return paths.daily_action_plan_path(trade_date).with_suffix(".json")


def _load_execution_rows(
    state: RunbookState,
    manual_executions_path: Path | None,
    row_fetcher: ExecutionRowFetcher | None,
) -> list[dict[str, Any]]:
    if manual_executions_path is not None:
        payload = _read_json_file(manual_executions_path)
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
            return payload["rows"]
        raise ValueError("manual executions JSON must be a list or object with rows[]")
    if row_fetcher is not None:
        return row_fetcher(state)
    return query_manual_execution_rows(state)


def _read_json_file(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Missing JSON file: {path}") from exc


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _filename_timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S%f")


def _md_value(value: Any) -> str:
    return "" if value is None else str(value)


def _escape_md_cell(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a read-only execution reconciliation preview.")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--data-date", required=True)
    parser.add_argument("--trade-date", required=True)
    parser.add_argument("--timezone", default="Asia/Seoul")
    parser.add_argument("--daily-plan-json", type=Path, default=None)
    parser.add_argument("--manual-executions-json", type=Path, default=None)
    parser.add_argument("--account-root", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        _validate_timezone(args.timezone)
        result = run_execution_reconciliation_preview(
            args.workspace,
            args.account_id,
            args.data_date,
            args.trade_date,
            timezone=args.timezone,
            daily_plan_path=args.daily_plan_json,
            manual_executions_path=args.manual_executions_json,
            account_root=args.account_root,
        )
    except Exception as exc:
        print(json.dumps({"runner_result": "FAILED", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["runner_result"] in {"BLOCKED", "FAILED"} else 0


def _validate_timezone(timezone: str) -> None:
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"unknown timezone: {timezone}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
