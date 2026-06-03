from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

from core.paper_account_paths import build_paper_account_paths
from core.paper_account_profile import validate_account_id


REPLAY_DIFF_SCHEMA_VERSION = "paper_daily_plan_replay_diff.v1"

STATUS_PASS = "PASS"
STATUS_PASS_WITH_METADATA_DIFF = "PASS_WITH_METADATA_DIFF"
STATUS_WARNING = "WARNING"
STATUS_FAIL = "FAIL"

CATEGORY_NO_DIFF = "NO_DIFF"
CATEGORY_METADATA_DIFF = "METADATA_DIFF"
CATEGORY_WARNING_DIFF = "WARNING_DIFF"
CATEGORY_PRICE_DIFF = "PRICE_DIFF"
CATEGORY_QUANTITY_DIFF = "QUANTITY_DIFF"
CATEGORY_ACTION_DIFF = "ACTION_DIFF"
CATEGORY_SYMBOL_SET_DIFF = "SYMBOL_SET_DIFF"
CATEGORY_DUPLICATE_ROW_KEY = "DUPLICATE_ROW_KEY"
CATEGORY_CONFIG_OR_UNIVERSE_DIFF = "CONFIG_OR_UNIVERSE_DIFF"
CATEGORY_STATE_OR_MARKET_FINGERPRINT_DIFF = "STATE_OR_MARKET_FINGERPRINT_DIFF"
CATEGORY_MALFORMED_INPUT = "MALFORMED_INPUT"
CATEGORY_ACCOUNT_DATE_MISMATCH = "ACCOUNT_DATE_MISMATCH"
CATEGORY_MISSING_INPUT = "MISSING_INPUT"

FAIL_CATEGORIES = {
    CATEGORY_SYMBOL_SET_DIFF,
    CATEGORY_ACTION_DIFF,
    CATEGORY_QUANTITY_DIFF,
    CATEGORY_MALFORMED_INPUT,
    CATEGORY_ACCOUNT_DATE_MISMATCH,
    CATEGORY_MISSING_INPUT,
}
WARNING_CATEGORIES = {
    CATEGORY_WARNING_DIFF,
    CATEGORY_PRICE_DIFF,
    CATEGORY_DUPLICATE_ROW_KEY,
    CATEGORY_CONFIG_OR_UNIVERSE_DIFF,
    CATEGORY_STATE_OR_MARKET_FINGERPRINT_DIFF,
}
CORE_FIELDS = ("symbol", "action", "quantity", "price", "warning", "reason", "note")
OPTIONAL_FIELDS = ("cash_impact", "allocation", "target_weight", "stop_price")
FINGERPRINT_FIELDS = (
    "config_hash",
    "universe_hash",
    "state_snapshot_hash",
    "state_snapshot_path",
    "market_data_asof",
    "indicator_snapshot_hash",
    "code_commit_sha",
    "generator_version",
)


def normalize_replay_diff_date(date_str: str) -> str:
    value = str(date_str).strip()
    if re.fullmatch(r"\d{8}", value):
        return f"{value[:4]}-{value[4:6]}-{value[6:]}"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return value
    raise ValueError("date must be YYYY-MM-DD or YYYYMMDD")


def compact_replay_diff_date(date_str: str) -> str:
    return normalize_replay_diff_date(date_str).replace("-", "")


@dataclass(frozen=True)
class LoadedPlan:
    payload: dict[str, Any] | None
    path: str
    error_category: str | None = None
    error_message: str = ""


def load_daily_plan_json(path: str | Path) -> LoadedPlan:
    source_path = Path(path)
    if not source_path.exists():
        return LoadedPlan(
            payload=None,
            path=str(source_path),
            error_category=CATEGORY_MISSING_INPUT,
            error_message="Daily Plan JSON input file does not exist.",
        )
    try:
        with source_path.open("r", encoding="utf-8-sig") as handle:
            payload = json.load(handle)
    except json.JSONDecodeError as exc:
        return LoadedPlan(
            payload=None,
            path=str(source_path),
            error_category=CATEGORY_MALFORMED_INPUT,
            error_message=f"Daily Plan JSON input could not be parsed: {exc.msg}.",
        )
    if not isinstance(payload, dict):
        return LoadedPlan(
            payload=None,
            path=str(source_path),
            error_category=CATEGORY_MALFORMED_INPUT,
            error_message="Daily Plan JSON input must contain an object.",
        )
    return LoadedPlan(payload=payload, path=str(source_path))


def compare_daily_plan_files(
    *,
    account_id: str,
    plan_date: str,
    baseline_plan_path: str | Path,
    regenerated_plan_path: str | Path,
) -> dict[str, Any]:
    baseline = load_daily_plan_json(baseline_plan_path)
    regenerated = load_daily_plan_json(regenerated_plan_path)
    return compare_daily_plan_payloads(
        account_id=account_id,
        plan_date=plan_date,
        baseline_plan=baseline.payload,
        regenerated_plan=regenerated.payload,
        baseline_path=baseline.path,
        regenerated_path=regenerated.path,
        input_errors=[error for error in (baseline, regenerated) if error.error_category],
    )


def compare_daily_plan_payloads(
    *,
    account_id: str,
    plan_date: str,
    baseline_plan: dict[str, Any] | None,
    regenerated_plan: dict[str, Any] | None,
    baseline_path: str = "",
    regenerated_path: str = "",
    input_errors: list[LoadedPlan] | None = None,
) -> dict[str, Any]:
    resolved_account_id = validate_account_id(account_id)
    resolved_date = normalize_replay_diff_date(plan_date)
    diffs: list[dict[str, Any]] = []
    fingerprint_diffs: list[dict[str, Any]] = []
    cause_candidates: list[str] = []

    for error in input_errors or []:
        if error.error_category:
            diffs.append(
                _diff_item(
                    category=error.error_category,
                    severity=STATUS_FAIL,
                    message=error.error_message,
                    source_path=error.path,
                )
            )

    if baseline_plan is None or regenerated_plan is None:
        return _build_report(
            account_id=resolved_account_id,
            plan_date=resolved_date,
            diffs=diffs,
            fingerprint_diffs=fingerprint_diffs,
            cause_candidates=cause_candidates,
            baseline_path=baseline_path,
            regenerated_path=regenerated_path,
            metadata_diff=False,
        )

    diffs.extend(
        _validate_account_date(
            baseline_plan,
            label="baseline",
            account_id=resolved_account_id,
            plan_date=resolved_date,
        )
    )
    diffs.extend(
        _validate_account_date(
            regenerated_plan,
            label="regenerated",
            account_id=resolved_account_id,
            plan_date=resolved_date,
        )
    )

    baseline_rows = _extract_plan_rows(baseline_plan)
    regenerated_rows = _extract_plan_rows(regenerated_plan)
    diffs.extend(_compare_rows(baseline_rows, regenerated_rows))

    fingerprint_diffs = _compare_fingerprints(baseline_plan, regenerated_plan)
    cause_candidates = _build_cause_candidates(fingerprint_diffs)
    diffs.extend(fingerprint_diffs)

    metadata_diff = _metadata_projection(baseline_plan) != _metadata_projection(regenerated_plan)
    if metadata_diff and not diffs:
        diffs.append(
            _diff_item(
                category=CATEGORY_METADATA_DIFF,
                severity=STATUS_PASS_WITH_METADATA_DIFF,
                message="Only metadata differs between baseline and regenerated Daily Plan JSON.",
            )
        )

    if not diffs:
        diffs.append(
            _diff_item(
                category=CATEGORY_NO_DIFF,
                severity=STATUS_PASS,
                message="Baseline and regenerated Daily Plan JSON match on compared fields.",
            )
        )

    return _build_report(
        account_id=resolved_account_id,
        plan_date=resolved_date,
        diffs=diffs,
        fingerprint_diffs=fingerprint_diffs,
        cause_candidates=cause_candidates,
        baseline_path=baseline_path,
        regenerated_path=regenerated_path,
        metadata_diff=metadata_diff,
    )


def write_daily_plan_diff_report(report: dict[str, Any], output_dir: str | Path | None = None) -> dict[str, str]:
    account_id = validate_account_id(str(report["account_id"]))
    plan_date = normalize_replay_diff_date(str(report["plan_date"]))
    if output_dir is None:
        target_dir = build_paper_account_paths(account_id, create=True).replay_diff_dir
    else:
        target_dir = Path(output_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

    date_key = compact_replay_diff_date(plan_date)
    json_path = target_dir / f"paper_daily_plan_diff_{date_key}.json"
    markdown_path = target_dir / f"paper_daily_plan_diff_{date_key}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_daily_plan_diff_markdown(report), encoding="utf-8")
    return {"json_path": str(json_path), "markdown_path": str(markdown_path)}


def render_daily_plan_diff_markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        f"# Daily Plan Replay Diff - {report.get('account_id')} - {report.get('plan_date')}",
        "",
        "## Summary",
        f"- Overall Status: `{report.get('overall_status')}`",
        f"- Diff Categories: `{', '.join(report.get('diff_categories', []))}`",
        f"- Added Symbols: {summary.get('added_symbols', 0)}",
        f"- Removed Symbols: {summary.get('removed_symbols', 0)}",
        f"- Action Diff Count: {summary.get('action_diff_count', 0)}",
        f"- Quantity Diff Count: {summary.get('quantity_diff_count', 0)}",
        f"- Price Diff Count: {summary.get('price_diff_count', 0)}",
        f"- Warning Diff Count: {summary.get('warning_diff_count', 0)}",
        "",
    ]
    _extend_markdown_items(lines, "Failures", report.get("diffs", []), STATUS_FAIL)
    _extend_markdown_items(lines, "Warnings", report.get("diffs", []), STATUS_WARNING)
    lines.extend(["## Metadata / Fingerprint Differences", ""])
    metadata_fingerprint = [
        item
        for item in report.get("diffs", [])
        if item.get("category")
        in {CATEGORY_METADATA_DIFF, CATEGORY_CONFIG_OR_UNIVERSE_DIFF, CATEGORY_STATE_OR_MARKET_FINGERPRINT_DIFF}
    ]
    if metadata_fingerprint:
        for item in metadata_fingerprint:
            lines.append(f"- `{item.get('category')}`: {item.get('message')}")
    else:
        lines.append("- None")
    lines.extend(["", "## Cause Candidates", ""])
    if report.get("cause_candidates"):
        lines.extend([f"- {candidate}" for candidate in report["cause_candidates"]])
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Input Files",
            f"- Baseline: `{report.get('input_files', {}).get('baseline_plan')}`",
            f"- Regenerated: `{report.get('input_files', {}).get('regenerated_plan')}`",
            "",
            "## Safety Notes",
            "- This report compares two provided JSON files only.",
            "- Daily Plan regeneration was not executed.",
            "- Notion API/write/export/sync was not executed.",
            "- Cause candidates are not confirmed root causes.",
        ]
    )
    return "\n".join(lines) + "\n"


def _extend_markdown_items(lines: list[str], title: str, items: list[dict[str, Any]], severity: str) -> None:
    lines.extend([f"## {title}", ""])
    matching = [item for item in items if item.get("severity") == severity]
    if not matching:
        lines.extend(["- None", ""])
        return
    for item in matching:
        lines.append(f"- `{item.get('category')}`: {item.get('message')}")
    lines.append("")


def _validate_account_date(
    payload: dict[str, Any],
    *,
    label: str,
    account_id: str,
    plan_date: str,
) -> list[dict[str, Any]]:
    diffs: list[dict[str, Any]] = []
    payload_account = str(payload.get("account_id") or payload.get("Account ID") or account_id)
    if payload_account != account_id:
        diffs.append(
            _diff_item(
                category=CATEGORY_ACCOUNT_DATE_MISMATCH,
                severity=STATUS_FAIL,
                message=f"{label} account_id={payload_account} does not match requested account_id={account_id}.",
                field="account_id",
                baseline=account_id if label == "regenerated" else payload_account,
                regenerated=payload_account if label == "regenerated" else account_id,
            )
        )
    payload_date = _normalize_optional_date(payload.get("plan_date") or payload.get("date") or payload.get("status_date"))
    if payload_date and payload_date != plan_date:
        diffs.append(
            _diff_item(
                category=CATEGORY_ACCOUNT_DATE_MISMATCH,
                severity=STATUS_FAIL,
                message=f"{label} plan_date={payload_date} does not match requested plan_date={plan_date}.",
                field="plan_date",
                baseline=plan_date if label == "regenerated" else payload_date,
                regenerated=payload_date if label == "regenerated" else plan_date,
            )
        )
    return diffs


def _extract_plan_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("items") or payload.get("action_items") or payload.get("actions") or payload.get("rows") or []
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _compare_rows(baseline_rows: list[dict[str, Any]], regenerated_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    diffs: list[dict[str, Any]] = []
    baseline_map, baseline_duplicates = _row_map(baseline_rows)
    regenerated_map, regenerated_duplicates = _row_map(regenerated_rows)
    duplicate_keys = sorted(set(baseline_duplicates) | set(regenerated_duplicates))
    for key in duplicate_keys:
        diffs.append(
            _diff_item(
                category=CATEGORY_DUPLICATE_ROW_KEY,
                severity=STATUS_WARNING,
                message=f"Duplicate symbol/action row key was found and was not auto-matched: {key}.",
                row_key=key,
            )
        )

    comparable_baseline = {key: value for key, value in baseline_map.items() if key not in duplicate_keys}
    comparable_regenerated = {key: value for key, value in regenerated_map.items() if key not in duplicate_keys}
    used_baseline: set[str] = set()
    used_regenerated: set[str] = set()

    baseline_by_symbol = _single_row_by_symbol(comparable_baseline)
    regenerated_by_symbol = _single_row_by_symbol(comparable_regenerated)
    for symbol in sorted(set(baseline_by_symbol) & set(regenerated_by_symbol)):
        baseline_key, baseline_row = baseline_by_symbol[symbol]
        regenerated_key, regenerated_row = regenerated_by_symbol[symbol]
        if baseline_key == regenerated_key:
            continue
        baseline_action = _string_field(baseline_row, "action")
        regenerated_action = _string_field(regenerated_row, "action")
        if baseline_action != regenerated_action:
            diffs.append(
                _diff_item(
                    category=CATEGORY_ACTION_DIFF,
                    severity=STATUS_FAIL,
                    message=f"Action changed for symbol {symbol}.",
                    row_key=symbol,
                    field="action",
                    baseline=baseline_action,
                    regenerated=regenerated_action,
                    symbol=symbol,
                )
            )
            used_baseline.add(baseline_key)
            used_regenerated.add(regenerated_key)

    for key in sorted(set(comparable_baseline) - set(comparable_regenerated) - used_baseline):
        diffs.append(
            _diff_item(
                category=CATEGORY_SYMBOL_SET_DIFF,
                severity=STATUS_FAIL,
                message=f"Baseline row is missing from regenerated plan: {key}.",
                row_key=key,
                baseline=_row_projection(comparable_baseline[key]),
                regenerated=None,
                symbol=_string_field(comparable_baseline[key], "symbol"),
            )
        )
    for key in sorted(set(comparable_regenerated) - set(comparable_baseline) - used_regenerated):
        diffs.append(
            _diff_item(
                category=CATEGORY_SYMBOL_SET_DIFF,
                severity=STATUS_FAIL,
                message=f"Regenerated row is missing from baseline plan: {key}.",
                row_key=key,
                baseline=None,
                regenerated=_row_projection(comparable_regenerated[key]),
                symbol=_string_field(comparable_regenerated[key], "symbol"),
            )
        )

    for key in sorted(set(comparable_baseline) & set(comparable_regenerated)):
        if key in used_baseline or key in used_regenerated:
            continue
        baseline_row = comparable_baseline[key]
        regenerated_row = comparable_regenerated[key]
        for field in CORE_FIELDS + OPTIONAL_FIELDS:
            if field not in baseline_row and field not in regenerated_row:
                continue
            baseline_value = _comparable_value(baseline_row.get(field))
            regenerated_value = _comparable_value(regenerated_row.get(field))
            if baseline_value == regenerated_value:
                continue
            category, severity = _field_diff_category(field)
            diffs.append(
                _diff_item(
                    category=category,
                    severity=severity,
                    message=f"{field} changed for row {key}.",
                    row_key=key,
                    field=field,
                    baseline=baseline_value,
                    regenerated=regenerated_value,
                    symbol=_string_field(baseline_row, "symbol") or _string_field(regenerated_row, "symbol"),
                )
            )
    return diffs


def _row_map(rows: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], set[str]]:
    keys = [_row_key(row) for row in rows]
    counts = Counter(keys)
    duplicates = {key for key, count in counts.items() if count > 1}
    return {key: row for key, row in zip(keys, rows) if key not in duplicates}, duplicates


def _row_key(row: dict[str, Any]) -> str:
    symbol = _string_field(row, "symbol")
    action = _string_field(row, "action")
    return f"{symbol}|{action}"


def _single_row_by_symbol(row_map: dict[str, dict[str, Any]]) -> dict[str, tuple[str, dict[str, Any]]]:
    symbols = [_string_field(row, "symbol") for row in row_map.values()]
    counts = Counter(symbols)
    result: dict[str, tuple[str, dict[str, Any]]] = {}
    for key, row in row_map.items():
        symbol = _string_field(row, "symbol")
        if symbol and counts[symbol] == 1:
            result[symbol] = (key, row)
    return result


def _field_diff_category(field: str) -> tuple[str, str]:
    if field == "quantity":
        return CATEGORY_QUANTITY_DIFF, STATUS_FAIL
    if field == "price":
        return CATEGORY_PRICE_DIFF, STATUS_WARNING
    if field in {"warning", "reason", "note"}:
        return CATEGORY_WARNING_DIFF, STATUS_WARNING
    if field == "action":
        return CATEGORY_ACTION_DIFF, STATUS_FAIL
    return CATEGORY_WARNING_DIFF, STATUS_WARNING


def _compare_fingerprints(baseline_plan: dict[str, Any], regenerated_plan: dict[str, Any]) -> list[dict[str, Any]]:
    baseline = _fingerprint_projection(baseline_plan)
    regenerated = _fingerprint_projection(regenerated_plan)
    diffs: list[dict[str, Any]] = []
    for field in FINGERPRINT_FIELDS:
        baseline_value = baseline.get(field)
        regenerated_value = regenerated.get(field)
        if baseline_value == regenerated_value:
            continue
        if baseline_value in (None, "") and regenerated_value in (None, ""):
            continue
        category = (
            CATEGORY_CONFIG_OR_UNIVERSE_DIFF
            if field in {"config_hash", "universe_hash"}
            else CATEGORY_STATE_OR_MARKET_FINGERPRINT_DIFF
        )
        diffs.append(
            _diff_item(
                category=category,
                severity=STATUS_WARNING,
                message=f"{field} differs; this is a cause candidate, not a confirmed root cause.",
                field=field,
                baseline=baseline_value,
                regenerated=regenerated_value,
            )
        )
    return diffs


def _build_cause_candidates(fingerprint_diffs: list[dict[str, Any]]) -> list[str]:
    candidates: list[str] = []
    for diff in fingerprint_diffs:
        field = diff.get("field")
        if field:
            candidates.append(f"{field} changed; this is a possible cause candidate.")
    return candidates


def _fingerprint_projection(payload: dict[str, Any]) -> dict[str, Any]:
    fingerprints = payload.get("fingerprints") if isinstance(payload.get("fingerprints"), dict) else {}
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    result: dict[str, Any] = {}
    for field in FINGERPRINT_FIELDS:
        result[field] = payload.get(field, fingerprints.get(field, metadata.get(field)))
    return result


def _metadata_projection(payload: dict[str, Any]) -> dict[str, Any]:
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    projection = dict(metadata)
    for key in ("generated_at", "report_id", "path", "source_path", "generator_version"):
        if key in payload:
            projection[key] = payload.get(key)
    return projection


def _build_report(
    *,
    account_id: str,
    plan_date: str,
    diffs: list[dict[str, Any]],
    fingerprint_diffs: list[dict[str, Any]],
    cause_candidates: list[str],
    baseline_path: str,
    regenerated_path: str,
    metadata_diff: bool,
) -> dict[str, Any]:
    categories = _diff_categories(diffs)
    overall_status = _overall_status(diffs, metadata_diff=metadata_diff)
    return {
        "schema_version": REPLAY_DIFF_SCHEMA_VERSION,
        "account_id": account_id,
        "plan_date": plan_date,
        "overall_status": overall_status,
        "diff_categories": categories,
        "summary": _summary(diffs),
        "diffs": diffs,
        "fingerprint_diffs": fingerprint_diffs,
        "cause_candidates": cause_candidates,
        "input_files": {
            "baseline_plan": baseline_path,
            "regenerated_plan": regenerated_path,
        },
        "write_executed": False,
        "notion_api_called": False,
        "notion_write_export_sync_executed": False,
    }


def _diff_categories(diffs: list[dict[str, Any]]) -> list[str]:
    categories = []
    for diff in diffs:
        category = str(diff.get("category") or "")
        if category and category not in categories:
            categories.append(category)
    return categories or [CATEGORY_NO_DIFF]


def _overall_status(diffs: list[dict[str, Any]], *, metadata_diff: bool) -> str:
    if any(diff.get("category") in FAIL_CATEGORIES or diff.get("severity") == STATUS_FAIL for diff in diffs):
        return STATUS_FAIL
    if any(diff.get("category") in WARNING_CATEGORIES or diff.get("severity") == STATUS_WARNING for diff in diffs):
        return STATUS_WARNING
    if any(diff.get("category") == CATEGORY_METADATA_DIFF for diff in diffs) or metadata_diff:
        return STATUS_PASS_WITH_METADATA_DIFF
    return STATUS_PASS


def _summary(diffs: list[dict[str, Any]]) -> dict[str, int]:
    categories = [diff.get("category") for diff in diffs]
    return {
        "added_symbols": sum(
            1
            for diff in diffs
            if diff.get("category") == CATEGORY_SYMBOL_SET_DIFF and diff.get("baseline") is None
        ),
        "removed_symbols": sum(
            1
            for diff in diffs
            if diff.get("category") == CATEGORY_SYMBOL_SET_DIFF and diff.get("regenerated") is None
        ),
        "action_diff_count": categories.count(CATEGORY_ACTION_DIFF),
        "quantity_diff_count": categories.count(CATEGORY_QUANTITY_DIFF),
        "price_diff_count": categories.count(CATEGORY_PRICE_DIFF),
        "warning_diff_count": categories.count(CATEGORY_WARNING_DIFF),
        "duplicate_row_key_count": categories.count(CATEGORY_DUPLICATE_ROW_KEY),
    }


def _diff_item(
    *,
    category: str,
    severity: str,
    message: str,
    row_key: str = "",
    field: str = "",
    baseline: Any = None,
    regenerated: Any = None,
    symbol: str = "",
    source_path: str = "",
) -> dict[str, Any]:
    return {
        "category": category,
        "severity": severity,
        "message": message,
        "row_key": row_key,
        "symbol": symbol,
        "field": field,
        "baseline": baseline,
        "regenerated": regenerated,
        "source_path": source_path,
    }


def _row_projection(row: dict[str, Any]) -> dict[str, Any]:
    return {field: row.get(field) for field in CORE_FIELDS + OPTIONAL_FIELDS if field in row}


def _string_field(row: dict[str, Any], key: str) -> str:
    return str(row.get(key) or "").strip().upper()


def _comparable_value(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    return value


def _normalize_optional_date(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        return normalize_replay_diff_date(str(value))
    except ValueError:
        return str(value).strip()
