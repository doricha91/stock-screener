from __future__ import annotations

import csv
import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from core.notion_client import NotionClient
from core.notion_account_keys import (
    build_legacy_manual_execution_canonical_key,
    build_manual_execution_canonical_key,
    normalize_notion_account_id,
)
from core.notion_mapping import get_mapping_section, resolve_notion_property_name
from core.notion_settings import NotionSettings, get_notion_data_source_id
from core.long_position_policy import DEFAULT_MAX_LONG_POSITIONS, LongPositionAction
from core.manual_execution_long_position_cap import (
    ManualExecutionLongPositionValidation,
    get_configured_manual_execution_hedge_symbols,
    validate_manual_execution_long_position_actions,
)
from core.paper_account_paths import PaperAccountPaths
from core.paper_execution_log import build_paper_trade_id
from core.paths import (
    paper_account_snapshot_path,
    paper_position_snapshot_path,
    paper_reports_dir,
)


PASS = "PASS"
WARNING = "WARNING"
FAIL = "FAIL"

MANUAL_EXECUTION_SOURCE = "notion_manual_execution"
MANUAL_EXECUTION_REASON = "manual_execution_import"


class ManualExecutionImportError(RuntimeError):
    pass


@dataclass(frozen=True)
class ManualExecutionIssue:
    severity: str
    code: str
    message: str


@dataclass
class ManualExecutionCandidate:
    account_id: str
    page_id: str
    name: str
    execution_date: str
    plan_date: str | None
    symbol: str
    side: str
    quantity: int | float | None
    actual_price: float | None
    commission: float
    currency: str
    broker: str | None
    status: str
    note: str | None
    linked_daily_plan_key: str | None
    notion_external_key: str | None
    validation_status_raw: str | None
    validation_message_raw: str | None
    import_status_raw: str | None
    imported_at_raw: str | None
    synced_at_raw: str | None
    canonical_key: str = ""
    legacy_canonical_key: str | None = None
    legacy_key_compatible: bool = False
    projected_cash_delta: float = 0.0
    projected_position_delta: int = 0
    validation_issues: list[ManualExecutionIssue] = field(default_factory=list)

    @property
    def validation_status(self) -> str:
        severities = {issue.severity for issue in self.validation_issues}
        if FAIL in severities:
            return FAIL
        if WARNING in severities:
            return WARNING
        return PASS


@dataclass(frozen=True)
class ManualExecutionPreview:
    account_id: str
    execution_date: str
    candidate_count: int
    pass_count: int
    warning_count: int
    fail_count: int
    commit_allowed: str
    source_data_source_id: str
    json_path: str
    markdown_path: str
    projected_cash_start: float
    projected_cash_end: float
    projected_cash_impact: float
    projected_position_impact: dict[str, int]
    long_position_policy: dict[str, Any]
    candidates: list[ManualExecutionCandidate]

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_date": self.execution_date,
            "account_id": self.account_id,
            "candidate_count": self.candidate_count,
            "pass_count": self.pass_count,
            "warning_count": self.warning_count,
            "fail_count": self.fail_count,
            "commit_allowed": self.commit_allowed,
            "source_data_source_id": self.source_data_source_id,
            "json_path": self.json_path,
            "markdown_path": self.markdown_path,
            "projected_cash_start": self.projected_cash_start,
            "projected_cash_end": self.projected_cash_end,
            "projected_cash_impact": self.projected_cash_impact,
            "projected_position_impact": self.projected_position_impact,
            "long_position_policy": self.long_position_policy,
            "candidates": [
                {
                    **asdict(candidate),
                    "validation_status": candidate.validation_status,
                }
                for candidate in self.candidates
            ],
        }


def build_manual_execution_preview(
    *,
    client: NotionClient,
    settings: NotionSettings,
    mapping_root: dict[str, dict[str, str]],
    execution_date: str,
    account_id: str | None = None,
    account_paths: PaperAccountPaths | None = None,
    env: dict[str, str] | None = None,
    reports_dir: Path | None = None,
    max_long_positions: int = DEFAULT_MAX_LONG_POSITIONS,
) -> ManualExecutionPreview:
    resolved_account_id = normalize_notion_account_id(account_id)
    if account_paths is not None and account_paths.account_id != resolved_account_id:
        raise ManualExecutionImportError("Provided account_paths.account_id does not match requested account_id.")
    mapping = get_mapping_section(mapping_root, "manual_executions")
    data_source_id = get_notion_data_source_id(
        settings,
        "manual_executions",
        env=env,
        env_override="NOTION_MANUAL_EXECUTIONS_DATA_SOURCE_ID",
    )
    pages = fetch_manual_execution_pages(
        client=client,
        data_source_id=data_source_id,
        mapping=mapping,
        execution_date=execution_date,
        account_id=resolved_account_id,
    )
    candidates = normalize_manual_execution_pages(
        pages=pages,
        mapping=mapping,
        account_id=resolved_account_id,
    )
    existing_trade_ids = _load_existing_trade_ids(account_paths=account_paths)
    available_cash = _load_latest_cash_balance(account_paths=account_paths)
    holdings = _load_latest_position_shares(account_paths=account_paths)
    hedge_symbols = get_configured_manual_execution_hedge_symbols()
    projected_position_impact: dict[str, int] = {}

    for candidate in candidates:
        _validate_candidate_shape(candidate)
    _assign_canonical_keys(candidates, account_id=resolved_account_id)
    _validate_duplicate_trade_ids(candidates, existing_trade_ids)

    running_cash = available_cash
    running_holdings = dict(holdings)
    for candidate in candidates:
        if (
            candidate.quantity is None
            or not float(candidate.quantity).is_integer()
            or not math.isfinite(float(candidate.quantity))
            or candidate.quantity <= 0
            or candidate.actual_price is None
            or not math.isfinite(float(candidate.actual_price))
            or candidate.actual_price <= 0
        ):
            continue
        cash_delta = _calculate_cash_delta(candidate)
        position_delta = candidate.quantity if candidate.side == "BUY" else -candidate.quantity
        candidate.projected_cash_delta = cash_delta
        candidate.projected_position_delta = position_delta
        projected_position_impact[candidate.symbol] = projected_position_impact.get(candidate.symbol, 0) + position_delta

        if candidate.side == "SELL":
            current_holding = running_holdings.get(candidate.symbol, 0)
            if candidate.quantity > current_holding:
                candidate.validation_issues.append(
                    ManualExecutionIssue(
                        severity=FAIL,
                        code="sell_exceeds_holding",
                        message=(
                            f"SELL quantity {candidate.quantity} exceeds current holding "
                            f"{current_holding} for {candidate.symbol}."
                        ),
                    )
                )
            else:
                running_holdings[candidate.symbol] = current_holding - candidate.quantity
                running_cash += cash_delta
        else:
            projected_cash = running_cash + cash_delta
            if projected_cash < 0:
                candidate.validation_issues.append(
                    ManualExecutionIssue(
                        severity=FAIL,
                        code="insufficient_cash",
                        message=(
                            f"BUY would reduce projected cash below zero: "
                            f"{projected_cash:.2f} after {candidate.symbol}."
                        ),
                    )
                )
            else:
                running_cash = projected_cash
                running_holdings[candidate.symbol] = running_holdings.get(candidate.symbol, 0) + candidate.quantity

    long_position_validation = validate_manual_execution_long_position_actions(
        holdings,
        [
            LongPositionAction(
                symbol=candidate.symbol,
                action_type=candidate.side,
                quantity=candidate.quantity,
            )
            for candidate in candidates
            if candidate.quantity is not None
            and math.isfinite(float(candidate.quantity))
            and float(candidate.quantity).is_integer()
            and candidate.quantity > 0
        ],
        max_long_positions=max_long_positions,
        hedge_symbols=hedge_symbols,
    )
    if candidates and not long_position_validation.allowed:
        issue = _long_position_cap_issue(long_position_validation)
        for candidate in candidates:
            candidate.validation_issues.append(issue)

    commit_allowed = _derive_commit_allowed(candidates)
    output_dir = _resolve_preview_reports_dir(account_paths=account_paths, reports_dir=reports_dir)
    compact_date = execution_date.replace("-", "")
    json_path = output_dir / f"manual_execution_import_preview_{compact_date}.json"
    markdown_path = output_dir / f"manual_execution_import_preview_{compact_date}.md"

    preview = ManualExecutionPreview(
        account_id=resolved_account_id,
        execution_date=execution_date,
        candidate_count=len(candidates),
        pass_count=sum(1 for item in candidates if item.validation_status == PASS),
        warning_count=sum(1 for item in candidates if item.validation_status == WARNING),
        fail_count=sum(1 for item in candidates if item.validation_status == FAIL),
        commit_allowed=commit_allowed,
        source_data_source_id=data_source_id,
        json_path=str(json_path),
        markdown_path=str(markdown_path),
        projected_cash_start=available_cash,
        projected_cash_end=running_cash,
        projected_cash_impact=running_cash - available_cash,
        projected_position_impact=dict(sorted(projected_position_impact.items())),
        long_position_policy=long_position_validation.to_dict(),
        candidates=candidates,
    )
    _write_preview_files(preview, json_path=json_path, markdown_path=markdown_path)
    return preview


def fetch_manual_execution_pages(
    *,
    client: NotionClient,
    data_source_id: str,
    mapping: dict[str, str],
    execution_date: str,
    account_id: str | None = None,
) -> list[dict[str, Any]]:
    resolved_account_id = normalize_notion_account_id(account_id)
    account_id_property = resolve_notion_property_name(mapping, "account_id")
    if resolved_account_id == "paper_default":
        account_filter = {
            "or": [
                {
                    "property": account_id_property,
                    "select": {"equals": resolved_account_id},
                },
                {
                    "property": account_id_property,
                    "select": {"is_empty": True},
                },
            ]
        }
    else:
        account_filter = {
            "property": account_id_property,
            "select": {"equals": resolved_account_id},
        }
    filter_payload = {
        "and": [
            {
                "property": resolve_notion_property_name(mapping, "execution_date"),
                "date": {"equals": execution_date},
            },
            {
                "property": resolve_notion_property_name(mapping, "status"),
                "select": {"equals": "READY"},
            },
            account_filter,
        ]
    }
    sorts = [
        {
            "property": resolve_notion_property_name(mapping, "execution_date"),
            "direction": "ascending",
        }
    ]
    return client.query_data_source(
        data_source_id,
        filter_payload=filter_payload,
        sorts=sorts,
    )


def normalize_manual_execution_pages(
    *,
    pages: list[dict[str, Any]],
    mapping: dict[str, str],
    account_id: str | None = None,
) -> list[ManualExecutionCandidate]:
    resolved_account_id = normalize_notion_account_id(account_id)
    normalized: list[ManualExecutionCandidate] = []
    for page in sorted(
        pages,
        key=lambda item: _page_sort_key(
            item,
            execution_date_property=resolve_notion_property_name(mapping, "execution_date"),
            symbol_property=resolve_notion_property_name(mapping, "symbol"),
            side_property=resolve_notion_property_name(mapping, "side"),
        ),
    ):
        properties = page.get("properties") or {}
        execution_date = _extract_date(properties, resolve_notion_property_name(mapping, "execution_date"))
        symbol = _extract_rich_text(properties, resolve_notion_property_name(mapping, "symbol")).upper().strip()
        side = _extract_select(properties, resolve_notion_property_name(mapping, "side")).upper().strip()
        quantity_value = _extract_number(properties, resolve_notion_property_name(mapping, "quantity"))
        actual_price = _extract_number(properties, resolve_notion_property_name(mapping, "actual_price"))
        quantity = int(quantity_value) if quantity_value is not None and float(quantity_value).is_integer() else quantity_value
        candidate = ManualExecutionCandidate(
            account_id=resolved_account_id,
            page_id=str(page.get("id") or "").strip(),
            name=_extract_title(properties, resolve_notion_property_name(mapping, "name")),
            execution_date=execution_date,
            plan_date=_extract_optional_date(properties, mapping.get("plan_date")),
            symbol=symbol,
            side=side,
            quantity=quantity,
            actual_price=actual_price,
            commission=0.0,
            currency="USD",
            broker=_extract_optional_text(properties, mapping.get("broker")),
            status=_extract_select(properties, resolve_notion_property_name(mapping, "status")).upper().strip(),
            note=_extract_optional_text(properties, mapping.get("note")),
            linked_daily_plan_key=_extract_optional_text(properties, mapping.get("linked_daily_plan_key")),
            notion_external_key=_extract_optional_text(properties, mapping.get("external_key")),
            validation_status_raw=_extract_optional_select(properties, mapping.get("validation_status")),
            validation_message_raw=_extract_optional_text(properties, mapping.get("validation_message")),
            import_status_raw=_extract_optional_select(properties, mapping.get("import_status")),
            imported_at_raw=_extract_optional_text(properties, mapping.get("imported_at")),
            synced_at_raw=_extract_optional_text(properties, mapping.get("synced_at")),
        )

        commission_text = _extract_optional_number(properties, mapping.get("commission"))
        if commission_text is None:
            candidate.validation_issues.append(
                ManualExecutionIssue(
                    severity=WARNING,
                    code="missing_commission",
                    message="Commission is blank; normalized to 0.",
                )
            )
        else:
            candidate.commission = commission_text

        currency = _extract_optional_select(properties, mapping.get("currency"))
        if not currency:
            candidate.validation_issues.append(
                ManualExecutionIssue(
                    severity=WARNING,
                    code="missing_currency",
                    message="Currency is blank; normalized to USD.",
                )
            )
        else:
            candidate.currency = currency.upper().strip()

        if not candidate.plan_date:
            candidate.validation_issues.append(
                ManualExecutionIssue(
                    severity=WARNING,
                    code="missing_plan_date",
                    message="Plan Date is blank.",
                )
            )
        if not candidate.linked_daily_plan_key:
            candidate.validation_issues.append(
                ManualExecutionIssue(
                    severity=WARNING,
                    code="missing_linked_daily_plan_key",
                    message="Linked Daily Plan Key is blank.",
                )
            )
        if not candidate.broker:
            candidate.validation_issues.append(
                ManualExecutionIssue(
                    severity=WARNING,
                    code="missing_broker",
                    message="Broker is blank.",
                )
            )
        normalized.append(candidate)
    return normalized


def _validate_candidate_shape(candidate: ManualExecutionCandidate) -> None:
    if not candidate.execution_date:
        candidate.validation_issues.append(
            ManualExecutionIssue(FAIL, "missing_execution_date", "Execution Date is required.")
        )
    if not candidate.symbol:
        candidate.validation_issues.append(
            ManualExecutionIssue(FAIL, "missing_symbol", "Symbol is required.")
        )
    if candidate.side not in {"BUY", "SELL"}:
        candidate.validation_issues.append(
            ManualExecutionIssue(FAIL, "invalid_side", f"Side must be BUY or SELL, got {candidate.side or 'blank'}.")
        )
    if (
        candidate.quantity is None
        or not math.isfinite(float(candidate.quantity))
        or not float(candidate.quantity).is_integer()
        or candidate.quantity <= 0
    ):
        candidate.validation_issues.append(
            ManualExecutionIssue(FAIL, "invalid_quantity", f"Quantity must be a positive whole number, got {candidate.quantity}.")
        )
    if (
        candidate.actual_price is None
        or not math.isfinite(float(candidate.actual_price))
        or candidate.actual_price <= 0
    ):
        candidate.validation_issues.append(
            ManualExecutionIssue(FAIL, "invalid_actual_price", f"Actual Price must be > 0, got {candidate.actual_price}.")
        )


def _assign_canonical_keys(
    candidates: list[ManualExecutionCandidate],
    *,
    account_id: str | None = None,
) -> None:
    sequence_by_group: dict[tuple[str, str, str], int] = {}
    seen_keys: set[str] = set()
    for candidate in sorted(candidates, key=lambda item: (item.execution_date, item.symbol, item.side, item.page_id)):
        group = (candidate.execution_date, candidate.symbol, candidate.side)
        sequence_by_group[group] = sequence_by_group.get(group, 0) + 1
        sequence = sequence_by_group[group]
        candidate.canonical_key = build_manual_execution_canonical_key(
            account_id,
            candidate.execution_date,
            candidate.symbol,
            candidate.side,
            sequence,
        )
        if candidate.account_id == "paper_default":
            candidate.legacy_canonical_key = build_legacy_manual_execution_canonical_key(
                candidate.execution_date,
                candidate.symbol,
                candidate.side,
                sequence,
            )
            candidate.legacy_key_compatible = True
        if candidate.canonical_key in seen_keys:
            candidate.validation_issues.append(
                ManualExecutionIssue(
                    severity=FAIL,
                    code="duplicate_canonical_key",
                    message=f"Duplicate canonical key generated: {candidate.canonical_key}.",
                )
            )
        seen_keys.add(candidate.canonical_key)


def _validate_duplicate_trade_ids(
    candidates: list[ManualExecutionCandidate],
    existing_trade_ids: set[str],
) -> None:
    batch_trade_ids: set[str] = set()
    for candidate in candidates:
        prospective_trade_id = _build_prospective_trade_id(candidate)
        if prospective_trade_id in existing_trade_ids:
            candidate.validation_issues.append(
                ManualExecutionIssue(
                    severity=FAIL,
                    code="duplicate_existing_trade",
                    message="Prospective manual execution already exists in paper_execution_log.csv.",
                )
            )
        if prospective_trade_id in batch_trade_ids:
            candidate.validation_issues.append(
                ManualExecutionIssue(
                    severity=FAIL,
                    code="duplicate_batch_trade",
                    message="Prospective manual execution is duplicated within the preview batch.",
                )
            )
        batch_trade_ids.add(prospective_trade_id)


def _build_prospective_trade_id(candidate: ManualExecutionCandidate) -> str:
    quantity = candidate.quantity or 0
    signed_shares = quantity if candidate.side == "BUY" else -quantity
    return build_paper_trade_id(
        {
            "date": candidate.execution_date,
            "symbol": candidate.symbol,
            "side": candidate.side,
            "shares": signed_shares,
            "price": candidate.actual_price,
            "reason": MANUAL_EXECUTION_REASON,
            "source": MANUAL_EXECUTION_SOURCE,
        }
    )


def _resolve_preview_reports_dir(
    *,
    account_paths: PaperAccountPaths | None = None,
    reports_dir: Path | None = None,
) -> Path:
    if account_paths is not None and account_paths.account_id != "paper_default":
        return account_paths.reports_dir
    return reports_dir if reports_dir is not None else paper_reports_dir()


def _load_existing_trade_ids(*, account_paths: PaperAccountPaths | None = None) -> set[str]:
    path = (
        account_paths.execution_log_path
        if account_paths is not None and account_paths.account_id != "paper_default"
        else paper_account_snapshot_path().parent / "paper_execution_log.csv"
    )
    if not path.exists():
        return set()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {
            str(row.get("trade_id") or "").strip()
            for row in csv.DictReader(handle)
            if str(row.get("trade_id") or "").strip()
        }


def _load_latest_cash_balance(*, account_paths: PaperAccountPaths | None = None) -> float:
    path = (
        account_paths.account_snapshot_path
        if account_paths is not None and account_paths.account_id != "paper_default"
        else paper_account_snapshot_path()
    )
    rows = _read_csv_rows(path)
    if not rows:
        raise ManualExecutionImportError(f"{path.name} has no rows.")
    latest_row = max(rows, key=lambda row: row.get("snapshot_date", ""))
    return float(latest_row.get("cash") or 0.0)


def _load_latest_position_shares(*, account_paths: PaperAccountPaths | None = None) -> dict[str, int]:
    path = (
        account_paths.position_snapshot_path
        if account_paths is not None and account_paths.account_id != "paper_default"
        else paper_position_snapshot_path()
    )
    if not path.exists():
        return {}
    rows = _read_csv_rows(path)
    if not rows:
        return {}
    latest_date = max(row.get("snapshot_date", "") for row in rows)
    holdings: dict[str, int] = {}
    for row in rows:
        if row.get("snapshot_date") != latest_date:
            continue
        symbol = str(row.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        holdings[symbol] = int(float(row.get("shares") or 0))
    return holdings


def _long_position_cap_issue(
    validation: ManualExecutionLongPositionValidation,
) -> ManualExecutionIssue:
    policy = validation.policy
    return ManualExecutionIssue(
        severity=FAIL,
        code="long_position_cap_blocked",
        message=(
            "Long-position hard-cap validation blocked the entire batch: "
            f"mode={validation.mode}, current={policy.current_count}, "
            f"projected={policy.projected_count}, max={validation.max_long_positions}, "
            f"error_codes={','.join(validation.error_codes) or 'none'}."
        ),
    )


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows: list[dict[str, str]] = []
        for row in csv.DictReader(handle):
            normalized: dict[str, str] = {}
            for key, value in row.items():
                normalized[(key or "").replace("\ufeff", "").strip()] = value or ""
            rows.append(normalized)
        return rows


def _calculate_cash_delta(candidate: ManualExecutionCandidate) -> float:
    if candidate.quantity is None or candidate.actual_price is None:
        raise ManualExecutionImportError("Cash delta requires non-blank quantity and actual price.")
    gross = candidate.quantity * candidate.actual_price
    if candidate.side == "BUY":
        return -(gross + candidate.commission)
    return gross - candidate.commission


def _derive_commit_allowed(candidates: list[ManualExecutionCandidate]) -> str:
    statuses = {candidate.validation_status for candidate in candidates}
    if FAIL in statuses:
        return "false"
    if WARNING in statuses:
        return "true_with_warnings"
    return "true"


def _write_preview_files(
    preview: ManualExecutionPreview,
    *,
    json_path: Path,
    markdown_path: Path,
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(preview.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_render_preview_markdown(preview), encoding="utf-8")


def _render_preview_markdown(preview: ManualExecutionPreview) -> str:
    lines = [
        f"# Manual Execution Import Preview [{preview.execution_date}]",
        "",
        "## Summary",
        f"- Account ID: {preview.account_id}",
        f"- Candidate Rows: {preview.candidate_count}",
        f"- PASS: {preview.pass_count}",
        f"- WARNING: {preview.warning_count}",
        f"- FAIL: {preview.fail_count}",
        f"- Commit Allowed: {preview.commit_allowed}",
        f"- Projected Cash Start: {preview.projected_cash_start:.2f}",
        f"- Projected Cash End: {preview.projected_cash_end:.2f}",
        f"- Projected Cash Impact: {preview.projected_cash_impact:.2f}",
        f"- Long Position Mode: {preview.long_position_policy['mode']}",
        f"- Long Position Count: {preview.long_position_policy['current_count']} -> {preview.long_position_policy['projected_count']}",
        f"- Max Long Positions: {preview.long_position_policy['max_long_positions']}",
        f"- Long Position Policy Errors: {preview.long_position_policy['error_codes'] or []}",
        "",
        "## Position Impact",
    ]
    if preview.projected_position_impact:
        for symbol, delta in preview.projected_position_impact.items():
            lines.append(f"- {symbol}: {delta:+d}")
    else:
        lines.append("- No candidate rows")
    lines.extend(["", "## Candidates"])
    if not preview.candidates:
        lines.append("- No READY rows found for the selected Execution Date.")
        return "\n".join(lines)

    for candidate in preview.candidates:
        lines.extend(
            [
                f"### {candidate.symbol} {candidate.side} {candidate.quantity}",
                f"- Account ID: {candidate.account_id}",
                f"- Canonical Key: {candidate.canonical_key}",
                f"- Legacy Canonical Key: {candidate.legacy_canonical_key or '-'}",
                f"- Validation Status: {candidate.validation_status}",
                f"- Actual Price: {candidate.actual_price:.4f}",
                f"- Commission: {candidate.commission:.4f}",
                f"- Currency: {candidate.currency}",
                f"- Projected Cash Delta: {candidate.projected_cash_delta:.2f}",
                f"- Projected Position Delta: {candidate.projected_position_delta:+d}",
            ]
        )
        if candidate.validation_issues:
            lines.append("- Messages:")
            for issue in candidate.validation_issues:
                lines.append(f"  - [{issue.severity}] {issue.message}")
        else:
            lines.append("- Messages: none")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _page_sort_key(
    page: dict[str, Any],
    *,
    execution_date_property: str,
    symbol_property: str,
    side_property: str,
) -> tuple[str, str, str, str]:
    properties = page.get("properties") or {}
    return (
        _extract_date(properties, execution_date_property),
        _extract_rich_text(properties, symbol_property).upper().strip(),
        _extract_select(properties, side_property).upper().strip(),
        str(page.get("created_time") or page.get("id") or ""),
    )


def _extract_title(properties: dict[str, Any], property_name: str) -> str:
    return _join_rich_text((properties.get(property_name) or {}).get("title") or [])


def _extract_rich_text(properties: dict[str, Any], property_name: str) -> str:
    return _join_rich_text((properties.get(property_name) or {}).get("rich_text") or [])


def _extract_select(properties: dict[str, Any], property_name: str) -> str:
    select_payload = (properties.get(property_name) or {}).get("select") or {}
    return str(select_payload.get("name") or "").strip()


def _extract_optional_select(properties: dict[str, Any], property_name: str | None) -> str | None:
    if not property_name:
        return None
    value = _extract_select(properties, property_name)
    return value or None


def _extract_date(properties: dict[str, Any], property_name: str) -> str:
    return _extract_optional_date(properties, property_name) or ""


def _extract_optional_date(properties: dict[str, Any], property_name: str | None) -> str | None:
    if not property_name:
        return None
    date_payload = (properties.get(property_name) or {}).get("date") or {}
    value = str(date_payload.get("start") or "").strip()
    return value or None


def _extract_number(properties: dict[str, Any], property_name: str) -> float | None:
    return _extract_optional_number(properties, property_name)


def _extract_optional_number(properties: dict[str, Any], property_name: str | None) -> float | None:
    if not property_name:
        return None
    payload = properties.get(property_name) or {}
    value = payload.get("number")
    if value is None:
        return None
    return float(value)


def _extract_optional_text(properties: dict[str, Any], property_name: str | None) -> str | None:
    if not property_name:
        return None
    payload = properties.get(property_name) or {}
    property_type = str(payload.get("type") or "").strip()
    if property_type == "rich_text":
        value = _join_rich_text(payload.get("rich_text") or [])
    elif property_type == "select":
        value = str((payload.get("select") or {}).get("name") or "").strip()
    elif property_type == "title":
        value = _join_rich_text(payload.get("title") or [])
    else:
        value = ""
    return value or None


def _join_rich_text(items: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for item in items:
        plain = str(item.get("plain_text") or "").strip()
        if plain:
            parts.append(plain)
            continue
        text_payload = item.get("text") or {}
        content = str(text_payload.get("content") or "").strip()
        if content:
            parts.append(content)
    return "".join(parts).strip()
