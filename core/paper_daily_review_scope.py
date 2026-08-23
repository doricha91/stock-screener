from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from core.notion_account_keys import build_manual_review_canonical_key


SCOPE_SCHEMA_VERSION = "paper_daily_manual_review_scope.v1"
POSITION_REVIEW_QUESTION_ID = "position_review_1"
POSITION_REVIEW_QUESTION_TEXT = (
    "Is there any manual judgment, exception, or follow-up for this open position that is not already "
    "captured by the Daily Plan?"
)
EXECUTION_REVIEW_QUESTION_ID = "execution_review_1"
EXECUTION_REVIEW_QUESTION_TEXT = (
    "Compare this symbol's actual execution with the Daily Plan. Note any quantity, price, skip, partial fill, "
    "or manual judgment exceptions that should affect the next operation."
)
ACCOUNT_REVIEW_QUESTIONS = (
    (
        "account_review_1",
        "After today's execution, did cash ratio or position sizing materially deviate from policy?",
        "position_sizing",
    ),
    (
        "account_review_2",
        "Were there any data, price, quantity, or manual decision exceptions during today's operation?",
        "execution_quality",
    ),
    (
        "account_review_3",
        "Is there any follow-up that must be checked on the next operating day?",
        "risk_management",
    ),
)


class DailyReviewScopeError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_manual_review_symbols(plan_payload: dict[str, Any], plan_markdown: str = "") -> list[str]:
    candidates: list[str] = []
    explicit = plan_payload.get("manual_review_items")
    if isinstance(explicit, list):
        for item in explicit:
            if not isinstance(item, dict):
                continue
            state = str(item.get("action") or item.get("state") or item.get("reason") or "").strip().upper()
            if state == "REVIEW_EXIT":
                candidates.append(str(item.get("symbol") or ""))
    for item in plan_payload.get("items") or []:
        if not isinstance(item, dict):
            continue
        state = str(item.get("action") or item.get("state") or item.get("reason") or "").strip().upper()
        if state == "REVIEW_EXIT":
            candidates.append(str(item.get("symbol") or ""))
    for line in plan_markdown.splitlines():
        if "REVIEW_EXIT" not in line or not line.lstrip().startswith("|"):
            continue
        cells = [re.sub(r"[*`]", "", cell).strip() for cell in line.strip().strip("|").split("|")]
        if "REVIEW_EXIT" in {cell.upper() for cell in cells} and cells:
            candidates.append(cells[0])
    return _ordered_unique_symbols(candidates)


def build_daily_manual_review_scope(
    *,
    runbook_day_id: str,
    account_id: str,
    data_date: str,
    trade_date: str,
    daily_plan: dict[str, Any],
    current_state: dict[str, Any] | None,
    stage_b_verification: dict[str, Any],
    execution_commit_report: dict[str, Any] | None,
    daily_plan_path: Path,
    current_state_path: Path | None,
    stage_b_verification_path: Path,
    execution_commit_report_path: Path | None,
    daily_plan_markdown_path: Path | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    context = {
        "runbook_day_id": runbook_day_id,
        "account_id": account_id,
        "data_date": data_date,
        "trade_date": trade_date,
    }
    _validate_plan_context(daily_plan, account_id, data_date, trade_date)
    _validate_verification_context(stage_b_verification, context)

    action_mode = str((daily_plan.get("execution_intent") or {}).get("action_mode") or "").upper()
    if action_mode not in {"EXECUTION", "NO_ACTION"}:
        raise DailyReviewScopeError("Daily Plan action_mode must be EXECUTION or NO_ACTION")
    if str(stage_b_verification.get("action_mode") or "").upper() != action_mode:
        raise DailyReviewScopeError("Daily Plan and Stage B verification action_mode mismatch")

    plan_markdown = ""
    if daily_plan_markdown_path is not None:
        try:
            plan_markdown = Path(daily_plan_markdown_path).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise DailyReviewScopeError(f"Daily Plan markdown could not be read: {exc}") from exc
    manual_symbols = extract_manual_review_symbols(daily_plan, plan_markdown)
    open_symbols: list[str] = []
    include_account_reviews = False

    if action_mode == "NO_ACTION":
        if (
            stage_b_verification.get("verified_no_action") is not True
            or int(stage_b_verification.get("committed_row_count") or 0) != 0
            or int(stage_b_verification.get("failed_count") or 0) != 0
        ):
            raise DailyReviewScopeError("Stage B no-action verification is inconsistent")
        position_symbols: list[str] = []
        execution_symbols: list[str] = []
        rows: list[dict[str, Any]] = []
    else:
        if current_state is None or current_state_path is None:
            raise DailyReviewScopeError("Canonical current state is required for EXECUTION scope")
        _validate_current_state(
            current_state,
            current_state_path,
            trade_date,
            allow_prior=stage_b_verification.get("verified_zero_write") is True,
        )
        open_symbols = _current_open_symbols(current_state)
        if execution_commit_report is None or execution_commit_report_path is None:
            raise DailyReviewScopeError("Execution commit report is required for EXECUTION scope")
        execution_symbols = _validated_execution_symbols(
            execution_commit_report,
            stage_b_verification,
            account_id=account_id,
            trade_date=trade_date,
        )
        position_symbols = (
            open_symbols
            if stage_b_verification.get("verified_zero_write") is True
            else [symbol for symbol in open_symbols if symbol in set(manual_symbols)]
        )
        include_account_reviews = stage_b_verification.get("verified_zero_write") is not True
        rows = _build_scope_rows(
            account_id,
            trade_date,
            position_symbols,
            execution_symbols,
            include_account_reviews=include_account_reviews,
        )

    source_paths: dict[str, Path | None] = {
        "daily_plan_json": Path(daily_plan_path),
        "daily_plan_markdown": Path(daily_plan_markdown_path) if daily_plan_markdown_path else None,
        "current_state_json": Path(current_state_path) if current_state_path else None,
        "stage_b_verification_json": Path(stage_b_verification_path),
        "execution_commit_report_json": Path(execution_commit_report_path) if execution_commit_report_path else None,
    }
    sources = {
        name: ({"path": str(path), "sha256": sha256_file(path)} if path is not None else None)
        for name, path in source_paths.items()
    }
    scope_basis = {
        "schema_version": SCOPE_SCHEMA_VERSION,
        "frozen_context": context,
        "action_mode": action_mode,
        "sources": sources,
        "manual_review_symbols": manual_symbols,
        "current_open_symbols": open_symbols,
        "position_symbols": position_symbols,
        "execution_symbols": execution_symbols,
        "canonical_keys": [row["canonical_key"] for row in rows],
        "rows": rows,
    }
    scope_sha256 = hashlib.sha256(
        json.dumps(scope_basis, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        **scope_basis,
        "generated_at": generated_at or datetime.now().isoformat(timespec="seconds"),
        "counts": {
            "position": len(position_symbols),
            "execution": len(execution_symbols),
            "account": len(ACCOUNT_REVIEW_QUESTIONS) if include_account_reviews else 0,
            "total": len(rows),
        },
        "scope_sha256": scope_sha256,
    }


def validate_scope_manifest(
    manifest: dict[str, Any],
    *,
    account_id: str | None = None,
    data_date: str | None = None,
    trade_date: str | None = None,
) -> dict[str, Any]:
    if manifest.get("schema_version") != SCOPE_SCHEMA_VERSION:
        raise DailyReviewScopeError("Manual Review scope schema_version is invalid")
    context = manifest.get("frozen_context")
    if not isinstance(context, dict):
        raise DailyReviewScopeError("Manual Review scope frozen_context is required")
    expected = {"account_id": account_id, "data_date": data_date, "trade_date": trade_date}
    for key, value in expected.items():
        if value is not None and context.get(key) != value:
            raise DailyReviewScopeError(f"Manual Review scope {key} mismatch")
    rows = manifest.get("rows")
    keys = manifest.get("canonical_keys")
    if not isinstance(rows, list) or not isinstance(keys, list):
        raise DailyReviewScopeError("Manual Review scope rows/canonical_keys are required")
    actual_keys = [str(row.get("canonical_key") or "") for row in rows if isinstance(row, dict)]
    if not all(actual_keys) or actual_keys != keys or len(set(keys)) != len(keys):
        raise DailyReviewScopeError("Manual Review scope canonical keys are invalid or duplicated")
    counts = manifest.get("counts")
    if not isinstance(counts, dict) or int(counts.get("total") or 0) != len(rows):
        raise DailyReviewScopeError("Manual Review scope counts.total mismatch")
    sources = manifest.get("sources")
    if not isinstance(sources, dict):
        raise DailyReviewScopeError("Manual Review scope sources are required")
    for name, source in sources.items():
        if source is None:
            continue
        if not isinstance(source, dict) or not source.get("path") or not source.get("sha256"):
            raise DailyReviewScopeError(f"Manual Review scope source is invalid: {name}")
        source_path = Path(str(source["path"]))
        if not source_path.exists() or sha256_file(source_path) != source["sha256"]:
            raise DailyReviewScopeError(f"Manual Review scope source hash mismatch: {name}")
    for row in rows:
        expected_key = build_manual_review_canonical_key(
            str(context.get("account_id") or ""),
            str(context.get("trade_date") or ""),
            str(row.get("symbol") or ""),
            str(row.get("question_id") or ""),
        )
        if row.get("canonical_key") != expected_key:
            raise DailyReviewScopeError("Manual Review scope row canonical key mismatch")
    basis = {key: manifest.get(key) for key in (
        "schema_version", "frozen_context", "action_mode", "sources", "manual_review_symbols",
        "current_open_symbols", "position_symbols", "execution_symbols", "canonical_keys", "rows",
    )}
    actual_sha = hashlib.sha256(
        json.dumps(basis, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if manifest.get("scope_sha256") != actual_sha:
        raise DailyReviewScopeError("Manual Review scope SHA-256 mismatch")
    return manifest


def load_scope_manifest(path: Path, **context: str | None) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DailyReviewScopeError(f"Manual Review scope manifest could not be loaded: {exc}") from exc
    if not isinstance(payload, dict):
        raise DailyReviewScopeError("Manual Review scope manifest root must be an object")
    return validate_scope_manifest(payload, **context)


def write_scope_manifest(manifest: dict[str, Any], path: Path) -> None:
    validate_scope_manifest(manifest)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _validate_plan_context(plan: dict[str, Any], account_id: str, data_date: str, trade_date: str) -> None:
    if str(plan.get("account_id") or "") != account_id:
        raise DailyReviewScopeError("Daily Plan account_id mismatch")
    if str(plan.get("data_date") or "") != data_date:
        raise DailyReviewScopeError("Daily Plan data_date mismatch")
    plan_trade_date = str(plan.get("trade_date") or plan.get("plan_date") or "")
    if plan_trade_date != trade_date:
        raise DailyReviewScopeError("Daily Plan trade_date mismatch")


def _validate_verification_context(verification: dict[str, Any], context: dict[str, str]) -> None:
    if verification.get("schema_version") != "stage_b_verification.v1" or str(
        verification.get("runner_result") or ""
    ).upper() != "PASS":
        raise DailyReviewScopeError("Stage B verification must be PASS")
    for key, value in context.items():
        if verification.get(key) != value:
            raise DailyReviewScopeError(f"Stage B verification {key} mismatch")
    if int(verification.get("failed_count") or 0) != 0:
        raise DailyReviewScopeError("Stage B verification failed_count must be 0")


def _validate_current_state(
    state: dict[str, Any],
    path: Path,
    trade_date: str,
    *,
    allow_prior: bool = False,
) -> None:
    if not isinstance(state.get("current_symbols"), list) or not isinstance(state.get("shares"), dict):
        raise DailyReviewScopeError("Current state current_symbols/shares are required")
    compact_date = trade_date.replace("-", "")
    match = re.fullmatch(r"paper_current_state_(\d{8})", Path(path).stem)
    if match is None or match.group(1) > compact_date or (
        not allow_prior and match.group(1) != compact_date
    ):
        raise DailyReviewScopeError("Current state filename is not valid as-of trade_date")


def _current_open_symbols(state: dict[str, Any]) -> list[str]:
    shares = state.get("shares") or {}
    symbols = []
    for raw_symbol in state.get("current_symbols") or []:
        symbol = str(raw_symbol or "").strip().upper()
        try:
            quantity = float(shares.get(raw_symbol, shares.get(symbol, 0)) or 0)
        except (TypeError, ValueError):
            raise DailyReviewScopeError(f"Current state shares are invalid for {symbol}")
        if symbol and quantity > 0:
            symbols.append(symbol)
    return _ordered_unique_symbols(symbols)


def _validated_execution_symbols(
    report: dict[str, Any],
    verification: dict[str, Any],
    *,
    account_id: str,
    trade_date: str,
) -> list[str]:
    if str(report.get("status") or "").upper() != "COMMITTED":
        raise DailyReviewScopeError("Execution commit report status must be COMMITTED")
    if report.get("account_id") != account_id or report.get("execution_date") != trade_date:
        raise DailyReviewScopeError("Execution commit report context mismatch")
    rows = report.get("committed_rows")
    ids = report.get("committed_trade_ids")
    count = int(report.get("committed_row_count") or 0)
    if not isinstance(rows, list) or not isinstance(ids, list) or count != len(rows) or count != len(ids):
        raise DailyReviewScopeError("Execution commit report counts are inconsistent")
    if count != int(verification.get("committed_row_count") or 0):
        raise DailyReviewScopeError("Execution commit and Stage B verification counts differ")
    id_set = {str(value) for value in ids}
    symbols: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            raise DailyReviewScopeError("Execution committed_rows entries must be objects")
        trade_id = str(row.get("committed_trade_id") or "")
        if (
            row.get("account_id") != account_id
            or str(row.get("commit_status") or "").upper() != "COMMITTED"
            or not trade_id
            or trade_id not in id_set
        ):
            raise DailyReviewScopeError("Execution committed row identity is invalid")
        canonical_key = str(row.get("canonical_key") or "")
        if f":{account_id}:{trade_date}:" not in canonical_key:
            raise DailyReviewScopeError("Execution committed row canonical key context mismatch")
        symbols.append(str(row.get("symbol") or ""))
    return _ordered_unique_symbols(symbols)


def _build_scope_rows(
    account_id: str,
    trade_date: str,
    position_symbols: list[str],
    execution_symbols: list[str],
    *,
    include_account_reviews: bool = True,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbol in position_symbols:
        rows.append(_scope_row(account_id, trade_date, symbol, POSITION_REVIEW_QUESTION_ID,
                               POSITION_REVIEW_QUESTION_TEXT, "position_review", "position_follow_up"))
    for symbol in execution_symbols:
        rows.append(_scope_row(account_id, trade_date, symbol, EXECUTION_REVIEW_QUESTION_ID,
                               EXECUTION_REVIEW_QUESTION_TEXT, "execution_review", "execution_quality"))
    if include_account_reviews:
        for question_id, question_text, review_tag in ACCOUNT_REVIEW_QUESTIONS:
            rows.append(_scope_row(account_id, trade_date, "ACCOUNT", question_id, question_text,
                                   "account_review", review_tag))
    return rows


def _scope_row(
    account_id: str,
    trade_date: str,
    symbol: str,
    question_id: str,
    question_text: str,
    question_category: str,
    review_tag: str,
) -> dict[str, Any]:
    return {
        "account_id": account_id,
        "review_date": trade_date,
        "symbol": symbol,
        "question_id": question_id,
        "question_text": question_text,
        "question_category": question_category,
        "review_tag": review_tag,
        "canonical_key": build_manual_review_canonical_key(account_id, trade_date, symbol, question_id),
    }


def _ordered_unique_symbols(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        symbol = re.sub(r"[*`]", "", str(value or "")).strip().upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        result.append(symbol)
    return result
