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
GATE2_ID = "GATE2"
GATE_RESULT_SCHEMA_VERSION = "runbook_gate_result.v1"
GATE2_RESULT_SCHEMA_VERSION = "gate2_review_readiness.v1"
GATE_RUNS_DIRNAME = "gate_runs"
DEFAULT_NEXT_POLL_MINUTES = 60
ALLOWED_GATE_RESULTS = {"PASS", "WAIT", "BLOCKED"}
GATE2_REVIEWED_STATUSES = {"REVIEWED", "COMPLETE", "COMPLETED", "DONE"}


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


def check_gate2_readiness(
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
        return _blocked_without_saved_state(workspace, state, "runbook_state_not_found", gate_id=GATE2_ID)

    state = runbook_state.load_state(state_path)
    precondition_error = _gate2_precondition_error(state, workspace, account_id, data_date, trade_date)
    if precondition_error:
        if precondition_error == "context_mismatch_existing_runbook_state":
            state = runbook_state.block_stage(state, GATE2_ID, precondition_error)
        elif precondition_error != "stage_c_required" or state.stage_status.get("C") != "PASS":
            state = runbook_state.block_stage(state, GATE2_ID, precondition_error)
        else:
            state = runbook_state.block_stage(state, GATE2_ID, precondition_error)
        result = create_gate2_result(state, "BLOCKED", [], precondition_error)
        state, gate_json, gate_txt = _write_gate2_result_and_save(workspace, state_path, state, result)
        return _cli_payload(result, gate_json, gate_txt, state_path=state_path)

    try:
        raw_rows = row_fetcher(state) if row_fetcher else query_manual_review_rows(state)
        rows = normalize_gate2_rows(raw_rows, state)
    except Exception as exc:
        state = runbook_state.block_stage(
            state,
            GATE2_ID,
            "notion_manual_review_query_failed",
            {"error": str(exc)},
        )
        result = create_gate2_result(state, "BLOCKED", [], f"Notion manual review query failed: {exc}")
        state, gate_json, gate_txt = _write_gate2_result_and_save(workspace, state_path, state, result)
        return _cli_payload(result, gate_json, gate_txt, state_path=state_path)

    duplicate_ready_keys = _duplicate_ready_gate2_keys(rows)
    if duplicate_ready_keys:
        for row in rows:
            if row.get("dedupe_key") in duplicate_ready_keys and row.get("import_ready"):
                row["missing"] = [*row.get("missing", []), "duplicate_ready_row"]
                row["blocked"] = True
                row["ready"] = False
        state = runbook_state.block_stage(
            state,
            GATE2_ID,
            "duplicate_ready_manual_review_rows",
            {"duplicate_keys": sorted(duplicate_ready_keys)},
        )
        result = create_gate2_result(state, "BLOCKED", rows, "Duplicate READY Manual Review rows make the import target ambiguous.")
        state, gate_json, gate_txt = _write_gate2_result_and_save(workspace, state_path, state, result)
        return _cli_payload(result, gate_json, gate_txt, state_path=state_path)

    blocked_rows = [row for row in rows if row.get("blocked")]
    if blocked_rows:
        state = runbook_state.block_stage(state, GATE2_ID, "manual_review_row_context_mismatch")
        result = create_gate2_result(state, "BLOCKED", rows, "Fix Manual Review row or Notion mapping before retry.")
        state, gate_json, gate_txt = _write_gate2_result_and_save(workspace, state_path, state, result)
        return _cli_payload(result, gate_json, gate_txt, state_path=state_path)

    runner_result = "PASS" if rows and all(row["ready"] for row in rows) else "WAIT"
    if runner_result == "PASS":
        state = runbook_state.complete_step(state, 12, GATE2_ID)
        state = runbook_state.complete_stage(state, GATE2_ID)
        next_poll_time = None
        message = "All manual review rows are ready."
    else:
        next_poll_time = _next_poll_time(state.timezone, next_poll_minutes)
        state = runbook_state.wait_gate(
            state,
            GATE2_ID,
            "manual_review_input_not_ready",
            next_poll_time,
        )
        message = "Fill Manual Review in Notion."

    result = create_gate2_result(state, runner_result, rows, message, next_poll_time=next_poll_time)
    state, gate_json, gate_txt = _write_gate2_result_and_save(workspace, state_path, state, result)
    return _cli_payload(result, gate_json, gate_txt, state_path=state_path)


def query_manual_execution_rows(state: RunbookState) -> list[dict[str, Any]]:
    _load_dotenv_if_available()
    settings = load_notion_settings(allow_missing=True)
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


def query_manual_review_rows(state: RunbookState) -> list[dict[str, Any]]:
    _load_dotenv_if_available()
    settings = load_notion_settings(allow_missing=True)
    mapping_root = load_notion_property_mapping()
    mapping = get_mapping_section(mapping_root, "manual_reviews")
    data_source_id = get_notion_data_source_id(
        settings,
        "manual_reviews",
        env_override="NOTION_MANUAL_REVIEWS_DATA_SOURCE_ID",
    )
    client = NotionClient(get_notion_token(settings))
    account_id = normalize_notion_account_id(state.frozen_context.account_id)
    review_date = state.frozen_context.trade_date
    filter_payload = {
        "and": [
            {
                "property": resolve_notion_property_name(mapping, "account_id"),
                "select": {"equals": account_id},
            },
            {
                "property": resolve_notion_property_name(mapping, "review_date"),
                "date": {"equals": review_date},
            },
        ]
    }
    pages = client.query_data_source(data_source_id, filter_payload=filter_payload, page_size=100)
    return [normalize_notion_manual_review_page(page, mapping) for page in pages]


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


def normalize_gate2_rows(raw_rows: list[dict[str, Any]], state: RunbookState) -> list[dict[str, Any]]:
    account_id = normalize_notion_account_id(state.frozen_context.account_id)
    review_date = state.frozen_context.trade_date
    rows = []
    for raw in raw_rows:
        row = normalize_flat_manual_review_row(raw)
        missing = _gate2_row_missing_reasons(row, account_id, review_date)
        blocked = _gate2_row_has_blocking_mismatch(missing)
        rows.append(
            {
                **row,
                "dedupe_key": _gate2_dedupe_key(row),
                "import_ready": row.get("import_status") == "READY",
                "ready": not missing,
                "blocked": blocked,
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


def normalize_flat_manual_review_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "page_id": str(row.get("page_id") or row.get("id") or "").strip(),
        "external_key": _none_if_blank(row.get("external_key") or row.get("notion_external_key")),
        "account_id": _none_if_blank(row.get("account_id")),
        "review_date": _none_if_blank(row.get("review_date")),
        "symbol": str(row.get("symbol") or "").strip().upper(),
        "question_id": str(row.get("question_id") or "").strip(),
        "manual_answer": str(row.get("manual_answer") or "").strip(),
        "review_status": str(row.get("review_status") or "").strip().upper(),
        "import_status": str(row.get("import_status") or row.get("import_status_raw") or "").strip().upper(),
        "source_template_key": _none_if_blank(row.get("source_template_key")),
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


def normalize_notion_manual_review_page(page: dict[str, Any], mapping: dict[str, str]) -> dict[str, Any]:
    properties = page.get("properties") or {}
    return {
        "page_id": str(page.get("id") or "").strip(),
        "external_key": _extract_optional_text(properties, mapping.get("external_key")),
        "account_id": _extract_select(properties, resolve_notion_property_name(mapping, "account_id")),
        "review_date": _extract_date(properties, resolve_notion_property_name(mapping, "review_date")),
        "symbol": _extract_optional_text(properties, mapping.get("symbol")),
        "question_id": _extract_optional_text(properties, mapping.get("question_id")),
        "manual_answer": _extract_optional_text(properties, resolve_notion_property_name(mapping, "manual_answer")),
        "review_status": _extract_select(properties, resolve_notion_property_name(mapping, "review_status")),
        "import_status": _extract_select(properties, resolve_notion_property_name(mapping, "import_status")),
        "source_template_key": _extract_optional_text(properties, mapping.get("source_template_key")),
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


def create_gate2_result(
    state: RunbookState,
    runner_result: str,
    rows: list[dict[str, Any]],
    message: str,
    next_poll_time: str | None = None,
) -> dict[str, Any]:
    if runner_result not in ALLOWED_GATE_RESULTS:
        raise ValueError(f"runner_result is not allowed: {runner_result}")
    ready_count = sum(1 for row in rows if row.get("ready"))
    candidate_count = len(rows)
    not_ready_count = sum(1 for row in rows if not row.get("ready") and not row.get("blocked"))
    blocked_count = sum(1 for row in rows if row.get("blocked"))
    return {
        "schema_version": GATE2_RESULT_SCHEMA_VERSION,
        "runner_result": runner_result,
        "gate_status": runner_result,
        "gate_id": GATE2_ID,
        "runbook_day_id": state.runbook_day_id,
        "frozen_context": {
            "account_id": state.frozen_context.account_id,
            "data_date": state.frozen_context.data_date,
            "trade_date": state.frozen_context.trade_date,
        },
        "account_id": state.frozen_context.account_id,
        "review_date": state.frozen_context.trade_date,
        "checked_at": _now_iso(state.timezone),
        "candidate_count": candidate_count,
        "required_count": candidate_count,
        "ready_count": ready_count,
        "missing_count": candidate_count - ready_count,
        "not_ready_count": not_ready_count,
        "blocked_count": blocked_count,
        "ready_review_page_ids": [row.get("page_id") for row in rows if row.get("ready")],
        "rows": rows,
        "checks": _gate2_checks(rows),
        "summary": {
            "title": "Gate 2 review readiness",
            "message": message,
            "next_required_action": (
                "Run Stage D review import."
                if runner_result == "PASS"
                else (
                    "Fill Manual Review in Notion."
                    if runner_result == "WAIT"
                    else "Fix Manual Review row or Notion mapping before retry."
                )
            ),
            "next_stage": "D" if runner_result == "PASS" else None,
            "next_poll_time": next_poll_time,
        },
        "next_stage": "D" if runner_result == "PASS" else None,
        "next_required_action": (
            "Run Stage D review import."
            if runner_result == "PASS"
            else ("Fill Manual Review in Notion." if runner_result == "WAIT" else "Fix Manual Review row or Notion mapping before retry.")
        ),
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


def _blocked_without_saved_state(
    workspace: Path,
    state: RunbookState,
    reason: str,
    gate_id: str = GATE1_ID,
) -> dict[str, Any]:
    result = (
        create_gate2_result(state, "BLOCKED", [], reason)
        if gate_id == GATE2_ID
        else create_gate_result(state, "BLOCKED", [], reason)
    )
    gate_json, gate_txt = write_gate_result(workspace, state, result)
    return _cli_payload(result, gate_json, gate_txt)


def _write_gate2_result_and_save(
    workspace: Path,
    state_path: Path,
    state: RunbookState,
    result: dict[str, Any],
) -> tuple[RunbookState, Path, Path]:
    gate_json, gate_txt = write_gate_result(workspace, state, result)
    state = runbook_state.record_artifact(state, "gate2_readiness_json", str(gate_json), workspace)
    state = runbook_state.record_artifact(state, "gate2_readiness_md", str(gate_txt), workspace)
    runbook_state.save_state(state, state_path)
    return state, gate_json, gate_txt


def _cli_payload(result: dict[str, Any], gate_json: Path, gate_txt: Path, state_path: Path | None = None) -> dict[str, Any]:
    paths = get_gate_result_paths(gate_json.parents[2], result["runbook_day_id"], result["gate_id"])
    payload = {
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
    if state_path is not None:
        payload["state_path"] = str(state_path)
    if "candidate_count" in result:
        payload["candidate_count"] = result["candidate_count"]
        payload["not_ready_count"] = result.get("not_ready_count", 0)
        payload["blocked_count"] = result.get("blocked_count", 0)
        payload["next_stage"] = result.get("next_stage")
    return payload


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


def _gate2_precondition_error(
    state: RunbookState,
    workspace: Path,
    account_id: str,
    data_date: str,
    trade_date: str,
) -> str | None:
    if not runbook_state.context_matches_state(state, account_id, data_date, trade_date):
        return "context_mismatch_existing_runbook_state"
    if state.stage_status.get("A") != "PASS":
        return "stage_a_not_pass"
    if state.stage_status.get("GATE1") != "PASS":
        return "gate1_not_pass"
    if state.stage_status.get("B") != "PASS":
        return "stage_b_not_pass"
    verification_ref = state.artifacts.get("stage_b_verification_json")
    if not verification_ref or not _artifact_ref_exists(workspace, verification_ref):
        return "stage_b_verification_required"
    try:
        verification = json.loads(_artifact_ref_path(workspace, verification_ref).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "stage_b_verification_required"
    if verification.get("schema_version") != "stage_b_verification.v1":
        return "stage_b_verification_required"
    if str(verification.get("runner_result") or "").upper() != "PASS":
        return "stage_b_verification_required"
    if state.stage_status.get("C") != "PASS":
        return "stage_c_required"
    if not (
        state.artifacts.get("manual_review_template_csv")
        or state.artifacts.get("notion_review_template_report_json")
    ):
        return "manual_review_template_required"
    if state.last_error and state.last_error.get("stage_id") != GATE2_ID:
        return "active_last_error"
    return None


def _gate2_row_missing_reasons(row: dict[str, Any], account_id: str, review_date: str) -> list[str]:
    missing: list[str] = []
    if row.get("account_id") != account_id:
        missing.append("account_id")
    if row.get("review_date") != review_date:
        missing.append("review_date")
    if not row.get("manual_answer"):
        missing.append("manual_answer")
    if str(row.get("review_status") or "").upper() not in GATE2_REVIEWED_STATUSES:
        missing.append("review_status_reviewed")
    if row.get("import_status") != "READY":
        missing.append("import_status_READY")
    return missing


def _gate2_row_has_blocking_mismatch(missing: list[str]) -> bool:
    return any(reason in {"account_id", "review_date"} for reason in missing)


def _gate2_dedupe_key(row: dict[str, Any]) -> str:
    canonical_parts = [
        str(row.get("account_id") or ""),
        str(row.get("review_date") or ""),
        str(row.get("symbol") or ""),
        str(row.get("question_id") or ""),
    ]
    if all(canonical_parts):
        return ":".join(canonical_parts)
    return str(row.get("external_key") or "")


def _duplicate_ready_gate2_keys(rows: list[dict[str, Any]]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for row in rows:
        if not row.get("import_ready"):
            continue
        key = str(row.get("dedupe_key") or "")
        if not key:
            continue
        if key in seen:
            duplicates.add(key)
        seen.add(key)
    return duplicates


def _gate2_checks(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    checks = []
    for row in rows:
        checks.append(
            {
                "page_id": row.get("page_id"),
                "symbol": row.get("symbol"),
                "question_id": row.get("question_id"),
                "ready": bool(row.get("ready")),
                "blocked": bool(row.get("blocked")),
                "missing": row.get("missing", []),
            }
        )
    return checks


def _artifact_ref_path(workspace: Path, artifact_ref: str) -> Path:
    path = Path(str(artifact_ref))
    return path if path.is_absolute() else workspace / path


def _artifact_ref_exists(workspace: Path, artifact_ref: str) -> bool:
    return _artifact_ref_path(workspace, artifact_ref).exists()


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
    gate2 = subparsers.add_parser("gate2", help="Check Gate 2 manual review readiness")
    gate2.add_argument("--workspace", type=Path, required=True)
    gate2.add_argument("--account-id", required=True)
    gate2.add_argument("--data-date", required=True)
    gate2.add_argument("--trade-date", required=True)
    gate2.add_argument("--timezone", default="Asia/Seoul")
    gate2.add_argument("--next-poll-minutes", type=int, default=DEFAULT_NEXT_POLL_MINUTES)
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
    if args.command == "gate2":
        result = check_gate2_readiness(
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
