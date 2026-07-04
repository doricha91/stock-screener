from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import runbook_state


SCHEMA_VERSION = "stage_b_verification.v1"
PASS = "PASS"
BLOCKED = "BLOCKED"
FAILED = "FAILED"


def verify_stage_b_completion(
    *,
    workspace: Path,
    account_id: str,
    trade_date: str,
    commit_report: Path,
    sync_report: Path,
    data_date: str | None = None,
    timezone: str = "Asia/Seoul",
) -> dict[str, Any]:
    workspace = Path(workspace)
    runbook_day_id = _runbook_day_id(account_id, data_date, trade_date)
    created_at = _now_iso()
    checks: list[dict[str, Any]] = []
    commit_payload = _load_json_report(commit_report, "commit_report", checks)
    sync_payload = _load_json_report(sync_report, "sync_report", checks)

    if commit_payload is not None and sync_payload is not None:
        _check_commit_report(commit_payload, account_id, trade_date, checks)
        _check_sync_report(sync_payload, account_id, trade_date, checks)
        _check_report_consistency(commit_payload, sync_payload, checks)

    runner_result = _runner_result_from_checks(checks)
    committed_row_count = _committed_row_count(commit_payload or {})
    updated_count = _int_value((sync_payload or {}).get("updated_count"))
    failed_count = _int_value((sync_payload or {}).get("failed_count"))
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "runner_result": runner_result,
        "created_at": created_at,
        "updated_at": created_at,
        "runbook_day_id": runbook_day_id,
        "account_id": account_id,
        "data_date": data_date,
        "trade_date": trade_date,
        "commit_report_json": str(commit_report),
        "sync_report_json": str(sync_report),
        "committed_row_count": committed_row_count,
        "updated_count": updated_count,
        "failed_count": failed_count,
        "checks": checks,
        "next_required_action": (
            "Proceed to Stage C daily review."
            if runner_result == PASS
            else "Inspect Stage B commit/sync reports before Stage C."
        ),
        "state_updated": False,
    }
    json_path, md_path = write_stage_b_verification(workspace, runbook_day_id, payload)
    payload["verification_json"] = str(json_path)
    payload["verification_md"] = str(md_path)
    latest_json = get_stage_b_verification_paths(workspace, runbook_day_id)["latest_json"]
    latest_md = get_stage_b_verification_paths(workspace, runbook_day_id)["latest_md"]
    payload["latest_verification_json"] = str(latest_json)
    payload["latest_verification_md"] = str(latest_md)
    _write_json(json_path, payload)
    _write_json(latest_json, payload)

    if data_date:
        payload["state_updated"] = _pin_verification_to_state(
            workspace=workspace,
            account_id=account_id,
            data_date=data_date,
            trade_date=trade_date,
            verification_json=json_path,
            verification_md=md_path,
            timezone=timezone,
        )
        _write_json(json_path, payload)
        _write_json(latest_json, payload)
    return payload


def get_verification_runs_dir(workspace: Path, runbook_day_id: str) -> Path:
    return Path(workspace) / "verification_runs" / _safe_filename_part(runbook_day_id)


def get_stage_b_verification_paths(
    workspace: Path,
    runbook_day_id: str,
    timestamp: str | None = None,
) -> dict[str, Path]:
    timestamp = timestamp or _timestamp_for_filename()
    directory = get_verification_runs_dir(workspace, runbook_day_id)
    return {
        "json": directory / f"{timestamp}_stage_b_verification.json",
        "md": directory / f"{timestamp}_stage_b_verification.md",
        "latest_json": directory / "latest_stage_b_verification.json",
        "latest_md": directory / "latest_stage_b_verification.md",
    }


def write_stage_b_verification(
    workspace: Path,
    runbook_day_id: str,
    payload: dict[str, Any],
) -> tuple[Path, Path]:
    paths = get_stage_b_verification_paths(workspace, runbook_day_id)
    paths["json"].parent.mkdir(parents=True, exist_ok=True)
    _write_json(paths["json"], payload)
    paths["md"].write_text(format_stage_b_verification_markdown(payload), encoding="utf-8")
    _write_json(paths["latest_json"], payload)
    paths["latest_md"].write_text(format_stage_b_verification_markdown(payload), encoding="utf-8")
    return paths["json"], paths["md"]


def format_stage_b_verification_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# Stage B Verification [{payload.get('runner_result', '-')}]",
        "",
        f"- account_id: {payload.get('account_id', '-')}",
        f"- data_date: {payload.get('data_date') or '-'}",
        f"- trade_date: {payload.get('trade_date', '-')}",
        f"- committed_row_count: {payload.get('committed_row_count', 0)}",
        f"- updated_count: {payload.get('updated_count', 0)}",
        f"- failed_count: {payload.get('failed_count', 0)}",
        f"- next_required_action: {payload.get('next_required_action', '-')}",
        "",
        "## Checks",
    ]
    for check in payload.get("checks", []):
        if not isinstance(check, dict):
            continue
        lines.append(f"- [{check.get('status', '-')}] {check.get('name', '-')}: {check.get('message', '-')}")
    return "\n".join(lines).strip() + "\n"


def _load_json_report(path: Path, label: str, checks: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not Path(path).exists():
        checks.append(_check(label, FAILED, "missing_report_file", f"{label} not found: {path}"))
        return None
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        checks.append(_check(label, FAILED, "invalid_json_report", str(exc)))
        return None
    if not isinstance(payload, dict):
        checks.append(_check(label, FAILED, "invalid_json_report", f"{label} root must be an object."))
        return None
    checks.append(_check(label, PASS, "report_loaded", f"{label} loaded."))
    return payload


def _check_commit_report(payload: dict[str, Any], account_id: str, trade_date: str, checks: list[dict[str, Any]]) -> None:
    committed_trade_ids = _committed_trade_ids(payload)
    committed_row_count = _committed_row_count(payload)
    status = str(payload.get("status") or "").upper()
    if not status and _rows_all_committed(payload):
        status = "COMMITTED"
    checks.append(
        _check(
            "commit_status",
            PASS if status == "COMMITTED" else BLOCKED,
            "commit_status_not_committed" if status != "COMMITTED" else "commit_status_committed",
            f"status={status or '-'}",
        )
    )
    checks.append(
        _check(
            "commit_account_id",
            PASS if str(payload.get("account_id") or "") == account_id else BLOCKED,
            "account_id_mismatch" if str(payload.get("account_id") or "") != account_id else "account_id_match",
            f"commit_report account_id={payload.get('account_id') or '-'}",
        )
    )
    checks.append(
        _check(
            "commit_execution_date",
            PASS if str(payload.get("execution_date") or "") == trade_date else BLOCKED,
            "trade_date_mismatch" if str(payload.get("execution_date") or "") != trade_date else "trade_date_match",
            f"commit_report execution_date={payload.get('execution_date') or '-'}",
        )
    )
    checks.append(
        _check(
            "committed_row_count",
            PASS if committed_row_count > 0 else BLOCKED,
            "committed_row_count_zero" if committed_row_count <= 0 else "committed_row_count_positive",
            f"committed_row_count={committed_row_count}",
        )
    )
    checks.append(
        _check(
            "committed_trade_ids",
            PASS if len(committed_trade_ids) == committed_row_count else BLOCKED,
            "committed_trade_id_count_mismatch" if len(committed_trade_ids) != committed_row_count else "committed_trade_id_count_match",
            f"trade_ids={len(committed_trade_ids)} committed_row_count={committed_row_count}",
        )
    )
    for field in ("current_state_written", "account_snapshot_written", "position_snapshot_written"):
        value = payload.get(field)
        if value is None and _rows_all_committed(payload):
            value = True
        checks.append(
            _check(
                field,
                PASS if value is True else BLOCKED,
                f"{field}_false" if value is not True else f"{field}_true",
                f"{field}={value}",
            )
        )


def _check_sync_report(payload: dict[str, Any], account_id: str, trade_date: str, checks: list[dict[str, Any]]) -> None:
    overall_status = str(payload.get("overall_status") or "").upper()
    checks.append(
        _check(
            "sync_overall_status",
            PASS if overall_status == "SUCCESS" else BLOCKED,
            "sync_not_success" if overall_status != "SUCCESS" else "sync_success",
            f"overall_status={overall_status or '-'}",
        )
    )
    checks.append(
        _check(
            "sync_account_id",
            PASS if str(payload.get("account_id") or "") == account_id else BLOCKED,
            "account_id_mismatch" if str(payload.get("account_id") or "") != account_id else "account_id_match",
            f"sync_report account_id={payload.get('account_id') or '-'}",
        )
    )
    checks.append(
        _check(
            "sync_execution_date",
            PASS if str(payload.get("execution_date") or "") == trade_date else BLOCKED,
            "trade_date_mismatch" if str(payload.get("execution_date") or "") != trade_date else "trade_date_match",
            f"sync_report execution_date={payload.get('execution_date') or '-'}",
        )
    )
    failed_count = _int_value(payload.get("failed_count"))
    checks.append(
        _check(
            "sync_failed_count",
            PASS if failed_count == 0 else BLOCKED,
            "sync_failed_count_nonzero" if failed_count else "sync_failed_count_zero",
            f"failed_count={failed_count}",
        )
    )


def _check_report_consistency(commit_payload: dict[str, Any], sync_payload: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    committed_row_count = _committed_row_count(commit_payload)
    candidate_count = _int_value(sync_payload.get("candidate_count"))
    updated_count = _int_value(sync_payload.get("updated_count"))
    checks.append(
        _check(
            "sync_candidate_count",
            PASS if candidate_count == committed_row_count else BLOCKED,
            "sync_candidate_count_mismatch" if candidate_count != committed_row_count else "sync_candidate_count_match",
            f"candidate_count={candidate_count} committed_row_count={committed_row_count}",
        )
    )
    checks.append(
        _check(
            "sync_updated_count",
            PASS if updated_count == committed_row_count else BLOCKED,
            "sync_updated_count_mismatch" if updated_count != committed_row_count else "sync_updated_count_match",
            f"updated_count={updated_count} committed_row_count={committed_row_count}",
        )
    )
    commit_ids = set(_committed_trade_ids(commit_payload))
    sync_ids = {
        str(row.get("committed_trade_id") or "").strip()
        for row in sync_payload.get("rows", [])
        if isinstance(row, dict) and str(row.get("committed_trade_id") or "").strip()
    }
    checks.append(
        _check(
            "committed_trade_id_set",
            PASS if sync_ids == commit_ids else BLOCKED,
            "committed_trade_id_set_mismatch" if sync_ids != commit_ids else "committed_trade_id_set_match",
            f"sync_ids={len(sync_ids)} commit_ids={len(commit_ids)}",
        )
    )


def _pin_verification_to_state(
    *,
    workspace: Path,
    account_id: str,
    data_date: str,
    trade_date: str,
    verification_json: Path,
    verification_md: Path,
    timezone: str,
) -> bool:
    state_path = runbook_state.get_state_path_for_context(workspace, account_id, data_date, trade_date)
    if not state_path.exists():
        return False
    state = runbook_state.load_state(state_path)
    if not runbook_state.context_matches_state(state, account_id, data_date, trade_date):
        return False
    state = runbook_state.record_artifact(state, "stage_b_verification_json", str(verification_json), workspace)
    state = runbook_state.record_artifact(state, "stage_b_verification_md", str(verification_md), workspace)
    runbook_state.save_state(state, state_path)
    return True


def _runner_result_from_checks(checks: list[dict[str, Any]]) -> str:
    statuses = {str(check.get("status") or "") for check in checks}
    if FAILED in statuses:
        return FAILED
    if BLOCKED in statuses:
        return BLOCKED
    return PASS


def _check(name: str, status: str, reason_code: str, message: str) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "reason_code": reason_code,
        "message": message,
    }


def _committed_row_count(payload: dict[str, Any]) -> int:
    explicit = payload.get("committed_row_count")
    if explicit is not None:
        return _int_value(explicit)
    rows = payload.get("committed_rows")
    return len(rows) if isinstance(rows, list) else 0


def _committed_trade_ids(payload: dict[str, Any]) -> list[str]:
    explicit = payload.get("committed_trade_ids")
    if isinstance(explicit, list):
        return [str(item).strip() for item in explicit if str(item).strip()]
    rows = payload.get("committed_rows", [])
    if not isinstance(rows, list):
        return []
    return [
        str(row.get("committed_trade_id") or row.get("trade_id") or "").strip()
        for row in rows
        if isinstance(row, dict) and str(row.get("committed_trade_id") or row.get("trade_id") or "").strip()
    ]


def _rows_all_committed(payload: dict[str, Any]) -> bool:
    rows = payload.get("committed_rows", [])
    if not isinstance(rows, list) or not rows:
        return False
    return all(str(row.get("commit_status") or "").upper() == "COMMITTED" for row in rows if isinstance(row, dict))


def _runbook_day_id(account_id: str, data_date: str | None, trade_date: str) -> str:
    if data_date:
        return runbook_state.get_runbook_day_id(account_id, data_date, trade_date)
    return f"{_safe_filename_part(account_id)}_unknown-data-date_{_safe_filename_part(trade_date)}"


def _safe_filename_part(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value).strip())
    return cleaned.strip("_") or "unknown"


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _timestamp_for_filename() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S%f")


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify Stage B completion from pinned reports")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--data-date")
    parser.add_argument("--trade-date", required=True)
    parser.add_argument("--commit-report", type=Path, required=True)
    parser.add_argument("--sync-report", type=Path, required=True)
    parser.add_argument("--timezone", default="Asia/Seoul")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = verify_stage_b_completion(
        workspace=args.workspace,
        account_id=args.account_id,
        data_date=args.data_date,
        trade_date=args.trade_date,
        commit_report=args.commit_report,
        sync_report=args.sync_report,
        timezone=args.timezone,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_stage_b_verification_markdown(payload))
    return 0 if payload["runner_result"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
