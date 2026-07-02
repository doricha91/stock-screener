from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.notion_account_keys import normalize_notion_account_id
from core.notion_client import NotionAPIError, NotionClient
from core.notion_mapping import (
    get_mapping_section,
    load_notion_property_mapping,
    resolve_notion_property_name,
)
from core.notion_settings import (
    NotionSettingsError,
    get_notion_data_source_id,
    get_notion_token,
    load_notion_settings,
)
from scripts import runbook_state
from scripts.runbook_state import RunbookState


GATE1_ID = "GATE1"
GATE_RESULT_SCHEMA_VERSION = "runbook_gate_result.v1"
GATE_RUNS_DIRNAME = "gate_runs"
DEFAULT_NEXT_POLL_MINUTES = 60
ALLOWED_GATE_RESULTS = {"PASS", "WAIT", "BLOCKED"}


GateRowFetcher = Callable[[RunbookState], list[dict[str, Any]]]


def check_gate1_readiness(
    workspace: Path,
    account_id: str,
    data_date: str,
    trade_date: str,
    timezone: str = "Asia/Seoul",
    row_fetcher: GateRowFetcher | None = None,
    next_poll_minutes: int = DEFAULT_NEXT_POLL_MINUTES,
) -> dict[str, Any]:
    workspace = Path(workspace)
    state_path = runbook_state.get_state_path_for_context(workspace, account_id, data_date, trade_date)
    if not state_path.exists():
        state = runbook_state.create_initial_state(account_id, data_date, trade_date, timezone)
        return _blocked_without_saved_state(
            workspace,
            state,
            "runbook_state_not_found",
        )

    state = runbook_state.load_state(state_path)
    if not runbook_state.context_matches_state(state, account_id, data_date, trade_date):
        state = runbook_state.block_stage(state, GATE1_ID, "context_mismatch_existing_runbook_state")
        runbook_state.save_state(state, state_path)
        result = create_gate_result(state, "BLOCKED", [], "context_mismatch_existing_runbook_state")
        gate_json, gate_txt = write_gate_result(workspace, state, result)
        return _cli_payload(result, gate_json, gate_txt)

    if state.stage_status.get("A") != "PASS":
        state = runbook_state.block_stage(state, GATE1_ID, "stage_a_not_pass")
        runbook_state.save_state(state, state_path)
        result = create_gate_result(state, "BLOCKED", [], "Stage A must PASS before Gate 1 readiness check.")
        gate_json, gate_txt = write_gate_result(workspace, state, result)
        return _cli_payload(result, gate_json, gate_txt)

    if state.last_error and state.last_error.get("stage_id") != GATE1_ID:
        state = runbook_state.block_stage(state, GATE1_ID, "stage_a_has_last_error", {"last_error": state.last_error})
        runbook_state.save_state(state, state_path)
        result = create_gate_result(state, "BLOCKED", [], "Stage A has active last_error.")
        gate_json, gate_txt = write_gate_result(workspace, state, result)
        return _cli_payload(result, gate_json, gate_txt)

    try:
        raw_rows = row_fetcher(state) if row_fetcher else query_manual_execution_rows(state)
        rows = normalize_gate1_rows(raw_rows, state)
    except Exception as exc:
        state = runbook_state.block_stage(
            state,
            GATE1_ID,
            "notion_manual_execution_query_failed",
            {"error": str(exc)},
        )
        runbook_state.save_state(state, state_path)
        result = create_gate_result(state, "BLOCKED", [], f"Notion manual execution query failed: {exc}")
        gate_json, gate_txt = write_gate_result(workspace, state, result)
        return _cli_payload(result, gate_json, gate_txt)

    runner_result = "PASS" if rows and all(row["ready"] for row in rows) else "WAIT"
    if runner_result == "PASS":
        state = runbook_state.complete_stage(state, GATE1_ID)
        next_poll_time = None
        message = "All manual execution rows are ready."
    else:
        next_poll_time = _next_poll_time(state.timezone, next_poll_minutes)
        state = runbook_state.wait_gate(
            state,
            GATE1_ID,
            "manual_execution_input_not_ready",
            next_poll_time,
        )
        message = "Fill Actual Price and set Status=READY in Notion."
    runbook_state.save_state(state, state_path)
    result = create_gate_result(
        state,
        runner_result,
        rows,
        message,
        next_poll_time=next_poll_time,
    )
    gate_json, gate_txt = write_gate_result(workspace, state, result)
    return _cli_payload(result, gate_json, gate_txt)


def query_manual_execution_rows(state: RunbookState) -> list[dict[str, Any]]:
    _load_dotenv_if_available()
    settings = load_notion_settings(allow_missing=False)
    mapping_root = load_notion_property_mapping()
    mapping = get_mapping_section(mapping_root, "manual_executions")
    data_source_id = get_notion_data_source_id(
        settings,
        "manual_executions",
        env_override="NOTION_MANUAL_EXECUTIONS_DATA_SOURCE_ID",
    )
    client = NotionClient(get_notion_token(settings))
    account_id = normalize_notion_account_id(state.frozen_context.account_id)
    trade_date = state.frozen_context.trade_date
    linked_daily_plan_key = build_linked_daily_plan_key(account_id, trade_date)
    filter_payload = {
        "and": [
            {
                "property": resolve_notion_property_name(mapping, "account_id"),
                "select": {"equals": account_id},
            },
            {
                "property": resolve_notion_property_name(mapping, "execution_date"),
                "date": {"equals": trade_date},
            },
            {
                "property": resolve_notion_property_name(mapping, "linked_daily_plan_key"),
                "rich_text": {"equals": linked_daily_plan_key},
            },
        ]
    }
    pages = client.query_data_source(data_source_id, filter_payload=filter_payload, page_size=100)
    return [normalize_notion_manual_execution_page(page, mapping) for page in pages]


def build_linked_daily_plan_key(account_id: str, trade_date: str) -> str:
    return f"daily_plan:{normalize_notion_account_id(account_id)}:{trade_date}"


def normalize_gate1_rows(raw_rows: list[dict[str, Any]], state: RunbookState) -> list[dict[str, Any]]:
    account_id = normalize_notion_account_id(state.frozen_context.account_id)
    trade_date = state.frozen_context.trade_date
    linked_daily_plan_key = build_linked_daily_plan_key(account_id, trade_date)
    rows = []
    for raw in raw_rows:
        row = normalize_flat_manual_execution_row(raw)
        missing = _row_missing_reasons(row, account_id, trade_date, linked_daily_plan_key)
        rows.append(
            {
                **row,
                "ready": not missing,
                "missing": missing,
            }
        )
    return rows


def normalize_flat_manual_execution_row(row: dict[str, Any]) -> dict[str, Any]:
    actual_price = row.get("actual_price")
    return {
        "page_id": str(row.get("page_id") or row.get("id") or "").strip(),
        "external_key": _none_if_blank(row.get("external_key")),
        "account_id": _none_if_blank(row.get("account_id")),
        "execution_date": _none_if_blank(row.get("execution_date")),
        "linked_daily_plan_key": _none_if_blank(row.get("linked_daily_plan_key")),
        "symbol": str(row.get("symbol") or "").strip().upper(),
        "side": str(row.get("side") or "").strip().upper(),
        "quantity": row.get("quantity"),
        "actual_price": actual_price,
        "status": str(row.get("status") or "").strip().upper(),
        "import_status": str(row.get("import_status") or row.get("import_status_raw") or "").strip().upper(),
        "failed_count": int(row.get("failed_count") or 0),
    }


def normalize_notion_manual_execution_page(page: dict[str, Any], mapping: dict[str, str]) -> dict[str, Any]:
    properties = page.get("properties") or {}
    return {
        "page_id": str(page.get("id") or "").strip(),
        "external_key": _extract_optional_text(properties, mapping.get("external_key")),
        "account_id": _extract_select(properties, resolve_notion_property_name(mapping, "account_id")),
        "execution_date": _extract_date(properties, resolve_notion_property_name(mapping, "execution_date")),
        "linked_daily_plan_key": _extract_optional_text(properties, mapping.get("linked_daily_plan_key")),
        "symbol": _extract_optional_text(properties, mapping.get("symbol")),
        "side": _extract_select(properties, resolve_notion_property_name(mapping, "side")),
        "quantity": _extract_number(properties, resolve_notion_property_name(mapping, "quantity")),
        "actual_price": _extract_number(properties, resolve_notion_property_name(mapping, "actual_price")),
        "status": _extract_select(properties, resolve_notion_property_name(mapping, "status")),
        "import_status": _extract_select(properties, resolve_notion_property_name(mapping, "import_status")),
        "failed_count": 0,
    }


def create_gate_result(
    state: RunbookState,
    runner_result: str,
    rows: list[dict[str, Any]],
    message: str,
    next_poll_time: str | None = None,
) -> dict[str, Any]:
    if runner_result not in ALLOWED_GATE_RESULTS:
        raise ValueError(f"runner_result is not allowed: {runner_result}")
    ready_count = sum(1 for row in rows if row.get("ready"))
    required_count = len(rows)
    missing_count = required_count - ready_count
    return {
        "schema_version": GATE_RESULT_SCHEMA_VERSION,
        "runner_result": runner_result,
        "gate_id": GATE1_ID,
        "runbook_day_id": state.runbook_day_id,
        "frozen_context": {
            "account_id": state.frozen_context.account_id,
            "data_date": state.frozen_context.data_date,
            "trade_date": state.frozen_context.trade_date,
        },
        "checked_at": _now_iso(state.timezone),
        "required_count": required_count,
        "ready_count": ready_count,
        "missing_count": missing_count,
        "rows": rows,
        "summary": {
            "title": "Gate 1 readiness",
            "message": message,
            "next_required_action": (
                "Run Stage B execution preview."
                if runner_result == "PASS"
                else "Fill Actual Price and set Status=READY in Notion."
            ),
            "next_poll_time": next_poll_time,
        },
    }


def write_gate_result(workspace: Path, state: RunbookState, result: dict[str, Any]) -> tuple[Path, Path]:
    paths = get_gate_result_paths(workspace, state.runbook_day_id, result["gate_id"])
    paths["json"].parent.mkdir(parents=True, exist_ok=True)
    json_text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    txt_text = format_gate_result_text(result) + "\n"
    paths["json"].write_text(json_text, encoding="utf-8")
    paths["txt"].write_text(txt_text, encoding="utf-8")
    paths["latest_json"].write_text(json_text, encoding="utf-8")
    paths["latest_txt"].write_text(txt_text, encoding="utf-8")
    return paths["json"], paths["txt"]


def get_gate_runs_dir(workspace: Path, runbook_day_id: str) -> Path:
    return workspace / GATE_RUNS_DIRNAME / _safe_filename_part(runbook_day_id)


def get_gate_result_paths(workspace: Path, runbook_day_id: str, gate_id: str) -> dict[str, Path]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S%f")
    gate_safe = _safe_filename_part(gate_id)
    directory = get_gate_runs_dir(workspace, runbook_day_id)
    return {
        "json": directory / f"{timestamp}_{gate_safe}.json",
        "txt": directory / f"{timestamp}_{gate_safe}.txt",
        "latest_json": directory / f"latest_{gate_safe}.json",
        "latest_txt": directory / f"latest_{gate_safe}.txt",
    }


def format_gate_result_text(result: dict[str, Any]) -> str:
    context = result.get("frozen_context", {})
    summary = result.get("summary", {})
    return "\n".join(
        [
            f"[{result.get('runner_result')}] {result.get('gate_id')} readiness",
            f"Account: {context.get('account_id')}",
            f"Data date: {context.get('data_date')}",
            f"Trade date: {context.get('trade_date')}",
            (
                "Rows: "
                f"{result.get('required_count', 0)} required / "
                f"{result.get('ready_count', 0)} ready / "
                f"{result.get('missing_count', 0)} missing"
            ),
            f"Message: {summary.get('message') or ''}",
            f"Next action: {summary.get('next_required_action') or 'none'}",
            f"Next poll: {summary.get('next_poll_time') or 'none'}",
        ]
    )


def _blocked_without_saved_state(workspace: Path, state: RunbookState, reason: str) -> dict[str, Any]:
    result = create_gate_result(state, "BLOCKED", [], reason)
    gate_json, gate_txt = write_gate_result(workspace, state, result)
    return _cli_payload(result, gate_json, gate_txt)


def _cli_payload(result: dict[str, Any], gate_json: Path, gate_txt: Path) -> dict[str, Any]:
    paths = get_gate_result_paths(gate_json.parents[2], result["runbook_day_id"], result["gate_id"])
    return {
        "runner_result": result["runner_result"],
        "gate_id": result["gate_id"],
        "runbook_day_id": result["runbook_day_id"],
        "ready_count": result["ready_count"],
        "required_count": result["required_count"],
        "missing_count": result["missing_count"],
        "gate_result_json": str(gate_json),
        "gate_result_txt": str(gate_txt),
        "latest_gate_result_json": str(paths["latest_json"]),
        "latest_gate_result_txt": str(paths["latest_txt"]),
        "next_required_action": result["summary"]["next_required_action"],
    }


def _row_missing_reasons(
    row: dict[str, Any],
    account_id: str,
    trade_date: str,
    linked_daily_plan_key: str,
) -> list[str]:
    missing: list[str] = []
    if row.get("account_id") != account_id:
        missing.append("account_id")
    if row.get("execution_date") != trade_date:
        missing.append("execution_date")
    if row.get("linked_daily_plan_key") != linked_daily_plan_key:
        missing.append("linked_daily_plan_key")
    if row.get("import_status") != "NOT_IMPORTED":
        missing.append("import_status_NOT_IMPORTED")
    if row.get("status") != "READY":
        missing.append("status_READY")
    if row.get("actual_price") is None:
        missing.append("actual_price")
    if int(row.get("failed_count") or 0) != 0:
        missing.append("failed_count")
    return missing


def _next_poll_time(timezone: str, minutes: int) -> str:
    return (datetime.fromisoformat(_now_iso(timezone)) + timedelta(minutes=minutes)).isoformat(timespec="microseconds")


def _now_iso(timezone: str) -> str:
    try:
        tz = ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"unknown timezone: {timezone}") from exc
    return datetime.now(tz).isoformat(timespec="microseconds")


def _safe_filename_part(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value).strip())
    return cleaned.strip("_") or "unknown"


def _none_if_blank(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _extract_select(properties: dict[str, Any], property_name: str) -> str:
    prop = properties.get(property_name) or {}
    return str((prop.get("select") or {}).get("name") or "").strip()


def _extract_date(properties: dict[str, Any], property_name: str) -> str | None:
    prop = properties.get(property_name) or {}
    return (prop.get("date") or {}).get("start")


def _extract_number(properties: dict[str, Any], property_name: str) -> float | int | None:
    prop = properties.get(property_name) or {}
    return prop.get("number")


def _extract_optional_text(properties: dict[str, Any], property_name: str | None) -> str | None:
    if not property_name:
        return None
    prop = properties.get(property_name) or {}
    if prop.get("rich_text"):
        return "".join(part.get("plain_text") or "" for part in prop.get("rich_text") or []).strip() or None
    if prop.get("title"):
        return "".join(part.get("plain_text") or "" for part in prop.get("title") or []).strip() or None
    if prop.get("select"):
        return (prop.get("select") or {}).get("name")
    if prop.get("number") is not None:
        return str(prop.get("number"))
    return None


def _load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Runbook gate checker")
    subparsers = parser.add_subparsers(dest="command", required=True)

    gate1 = subparsers.add_parser("gate1", help="Check Gate 1 manual execution readiness")
    gate1.add_argument("--workspace", type=Path, required=True)
    gate1.add_argument("--account-id", required=True)
    gate1.add_argument("--data-date", required=True)
    gate1.add_argument("--trade-date", required=True)
    gate1.add_argument("--timezone", default="Asia/Seoul")
    gate1.add_argument("--next-poll-minutes", type=int, default=DEFAULT_NEXT_POLL_MINUTES)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "gate1":
        result = check_gate1_readiness(
            workspace=args.workspace,
            account_id=args.account_id,
            data_date=args.data_date,
            trade_date=args.trade_date,
            timezone=args.timezone,
            next_poll_minutes=args.next_poll_minutes,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("runner_result") in {"PASS", "WAIT"} else 1
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
