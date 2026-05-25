from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.notion_client import NotionClient
from core.notion_mapping import get_mapping_section, resolve_notion_property_name
from core.notion_settings import NotionSettings, NotionSettingsError, get_notion_data_source_id


PASS = "PASS"
FAIL = "FAIL"
WARNING = "WARNING"


@dataclass(frozen=True)
class ExpectedProperty:
    source_key: str
    notion_type: str | tuple[str, ...]
    required: bool = True
    select_options: tuple[str, ...] = ()
    check_options: bool = False


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    property_name: str | None
    code: str
    message: str


@dataclass(frozen=True)
class DataSourceValidationResult:
    target: str
    data_source_id: str
    status: str
    issues: list[ValidationIssue]
    checked_property_count: int


def build_expected_schema(mapping_root: dict[str, dict[str, str]]) -> dict[str, list[ExpectedProperty]]:
    schemas: dict[str, list[ExpectedProperty]] = {}
    if "weekly_reports" in mapping_root:
        weekly = get_mapping_section(mapping_root, "weekly_reports")
        schemas["weekly_reports"] = [
            _expected(weekly, "name", "title"),
            _expected(weekly, "external_key", "rich_text"),
            _expected(weekly, "period.actual_start", "date"),
            _expected(weekly, "period.actual_end", "date"),
            _expected(weekly, "latest_snapshot_date", "date"),
            _expected(weekly, "period.coverage_status", "select", select_options=("FULL", "PARTIAL", "EMPTY"), check_options=True),
            _expected(weekly, "overall_status", "select", select_options=("PASS", "PASS_WITH_WARNINGS", "FAIL"), check_options=True),
            _expected(weekly, "period.snapshot_count", "number"),
            _expected(weekly, "account_summary.end_equity_market_value", "number"),
            _expected(weekly, "account_summary.equity_change_pct", "number"),
            _expected(weekly, "account_summary.end_cash_ratio_market_value", "number"),
            _expected(weekly, "trade_summary.trade_count", "number"),
            _expected(weekly, "operation_gaps.count", "number"),
            _expected(weekly, "operation_gaps.high_count", "number"),
            _expected(weekly, "markdown_path", "rich_text"),
            _expected(weekly, "json_path", "rich_text"),
            _expected(weekly, "schema_version", "rich_text"),
            _expected(weekly, "synced_at", "rich_text"),
            _expected(weekly, "sync_status", "select", select_options=("SYNCED",), check_options=True),
        ]
    if "benchmark_reports" in mapping_root:
        benchmark = get_mapping_section(mapping_root, "benchmark_reports")
        schemas["benchmark_reports"] = [
            _expected(benchmark, "name", "title"),
            _expected(benchmark, "external_key", "rich_text"),
            _expected(benchmark, "latest_snapshot_date", "date"),
            _expected(benchmark, "run_mode", "select", select_options=("EXPLORATORY",), check_options=False),
            _expected(benchmark, "official_run", "select", select_options=("TRUE", "FALSE"), check_options=True),
            _expected(benchmark, "availability_status", "select", select_options=("AVAILABLE", "INSUFFICIENT_DATA", "UNKNOWN"), check_options=True),
            _expected(benchmark, "summary.paper.paper_return", "number"),
            _expected(benchmark, "summary.benchmarks.SPY.benchmark_return", "number"),
            _expected(benchmark, "summary.benchmarks.QQQ.benchmark_return", "number"),
            _expected(benchmark, "summary.benchmarks.CASH.benchmark_return", "number"),
            _expected(benchmark, "summary.benchmarks.SPY.excess_return", "number"),
            _expected(benchmark, "summary.benchmarks.QQQ.excess_return", "number"),
            _expected(benchmark, "summary.benchmarks.CASH.excess_return", "number"),
            _expected(benchmark, "summary.paper.paper_max_drawdown", "number"),
            _expected(benchmark, "summary.benchmarks.SPY.benchmark_max_drawdown", "number"),
            _expected(benchmark, "summary.benchmarks.QQQ.benchmark_max_drawdown", "number"),
            _expected(benchmark, "markdown_path", "rich_text"),
            _expected(benchmark, "json_path", "rich_text"),
            _expected(benchmark, "schema_version", "rich_text"),
            _expected(benchmark, "synced_at", "rich_text"),
            _expected(benchmark, "sync_status", "select", select_options=("SYNCED",), check_options=True),
        ]
    if "account_snapshots" in mapping_root:
        account = get_mapping_section(mapping_root, "account_snapshots")
        schemas["account_snapshots"] = [
            _expected(account, "name", "title"),
            _expected(account, "external_key", "rich_text"),
            _expected(account, "snapshot_date", "date"),
            _expected(account, "initial_cash", "number"),
            _expected(account, "cash", "number"),
            _expected(account, "total_equity_market_value", "number"),
            _expected(account, "total_equity_cost_basis", "number"),
            _expected(account, "unrealized_pnl", "number"),
            _expected(account, "cash_ratio_market_value", "number"),
            _expected(account, "cash_ratio_cost_basis", "number"),
            _expected(account, "position_count", "number"),
            _expected(account, "symbols", "rich_text"),
            _expected(account, "market_valuation_status", "select", select_options=("SUCCESS", "FAILED", "NOT_RUN", "UNKNOWN", "PARTIAL"), check_options=True),
            _expected(account, "valuation_price_date", "date"),
            _expected(account, "synced_at", "rich_text"),
            _expected(account, "sync_status", "select", select_options=("SYNCED",), check_options=True),
        ]
    if "daily_plans" in mapping_root:
        daily_plan = get_mapping_section(mapping_root, "daily_plans")
        schemas["daily_plans"] = [
            _expected(daily_plan, "name", "title"),
            _expected(daily_plan, "external_key", "rich_text"),
            _expected(daily_plan, "plan_date", "date"),
            _expected(daily_plan, "regime", "select", select_options=("BULL", "BEAR", "PANIC"), check_options=False),
            _expected(daily_plan, "confirmed_trade_count", "number"),
            _expected(daily_plan, "review_item_count", "number"),
            _expected(daily_plan, "warning_count", "number"),
            _expected(daily_plan, "markdown_path", "rich_text"),
            _expected(daily_plan, "json_path", "rich_text"),
            _expected(daily_plan, "schema_version", "rich_text"),
            _expected(daily_plan, "synced_at", "rich_text"),
            _expected(daily_plan, "sync_status", "select", select_options=("SYNCED",), check_options=True),
        ]
    if "manual_executions" in mapping_root:
        manual_execution = get_mapping_section(mapping_root, "manual_executions")
        schemas["manual_executions"] = [
            _expected(manual_execution, "name", "title"),
            _expected(manual_execution, "execution_date", "date"),
            _expected(manual_execution, "symbol", "rich_text"),
            _expected(manual_execution, "side", "select", select_options=("BUY", "SELL"), check_options=True),
            _expected(manual_execution, "quantity", "number"),
            _expected(manual_execution, "actual_price", "number"),
            _expected(
                manual_execution,
                "status",
                "select",
                select_options=("DRAFT", "READY", "IMPORTED", "REJECTED"),
                check_options=True,
            ),
            _expected(manual_execution, "external_key", "rich_text", required=False),
            _expected(manual_execution, "plan_date", "date", required=False),
            _expected(manual_execution, "commission", "number", required=False),
            _expected(manual_execution, "currency", "select", required=False, select_options=("USD", "KRW"), check_options=True),
            _expected(manual_execution, "broker", ("select", "rich_text"), required=False),
            _expected(manual_execution, "note", "rich_text", required=False),
            _expected(manual_execution, "linked_daily_plan_key", "rich_text", required=False),
            _expected(
                manual_execution,
                "validation_status",
                "select",
                required=False,
                select_options=("NOT_CHECKED", "PASS", "WARNING", "FAIL"),
                check_options=True,
            ),
            _expected(manual_execution, "validation_message", "rich_text", required=False),
            _expected(
                manual_execution,
                "import_status",
                "select",
                required=False,
                select_options=("NOT_IMPORTED", "PREVIEWED", "COMMITTED", "SKIPPED"),
                check_options=True,
            ),
            _expected(manual_execution, "imported_at", "rich_text", required=False),
            _expected(manual_execution, "synced_at", "rich_text", required=False),
        ]
    if "daily_review_summaries" in mapping_root:
        daily_review = get_mapping_section(mapping_root, "daily_review_summaries")
        schemas["daily_review_summaries"] = [
            _expected(daily_review, "name", "title"),
            _expected(daily_review, "external_key", "rich_text"),
            _expected(daily_review, "review_date", "date"),
            _expected(
                daily_review,
                "review_status",
                "select",
                select_options=("PASS", "PASS_WITH_WARNINGS", "FAIL", "NO_ACTIVITY"),
                check_options=True,
            ),
            _expected(
                daily_review,
                "availability_status",
                "select",
                select_options=("AVAILABLE", "NO_COMMIT_REPORT", "NO_MANUAL_EXECUTIONS", "PARTIAL", "UNKNOWN"),
                check_options=True,
            ),
            _expected(daily_review, "committed_trade_count", "number"),
            _expected(daily_review, "warning_count", "number"),
            _expected(daily_review, "fail_count", "number"),
            _expected(daily_review, "cash_start", "number"),
            _expected(daily_review, "cash_end", "number"),
            _expected(daily_review, "cash_impact", "number"),
            _expected(daily_review, "position_impact_summary", "rich_text"),
            _expected(daily_review, "commit_report_path", "rich_text"),
            _expected(daily_review, "preview_report_path", "rich_text"),
            _expected(daily_review, "latest_snapshot_date", "date"),
            _expected(daily_review, "schema_version", "rich_text"),
            _expected(daily_review, "synced_at", "rich_text"),
            _expected(daily_review, "sync_status", "select", select_options=("SYNCED",), check_options=True),
        ]
    return schemas


def validate_data_source_schema(
    *,
    target: str,
    data_source_id: str,
    actual_schema: dict[str, Any],
    mapping_root: dict[str, dict[str, str]],
) -> DataSourceValidationResult:
    expected_schema = build_expected_schema(mapping_root)
    if target not in expected_schema:
        raise ValueError(f"Unsupported target: {target}")

    actual_properties = _extract_actual_properties(actual_schema)
    issues: list[ValidationIssue] = []

    for expected in expected_schema[target]:
        property_name = expected.source_key
        actual = actual_properties.get(property_name)
        if actual is None:
            if expected.required:
                issues.append(
                    ValidationIssue(
                        severity=FAIL,
                        property_name=property_name,
                        code="missing_property",
                        message=f"{property_name} is missing.",
                    )
                )
            continue
        actual_type = str(actual.get("type") or "").strip()
        expected_types = _expected_types(expected.notion_type)
        if actual_type not in expected_types:
            issues.append(
                ValidationIssue(
                    severity=FAIL,
                    property_name=property_name,
                    code="type_mismatch",
                    message=(
                        f"{property_name} expected {_format_expected_types(expected_types)}, "
                        f"got {actual_type or 'unknown'}."
                    ),
                )
            )
            continue
        if actual_type == "select" and expected.check_options and expected.select_options:
            available = _extract_select_options(actual)
            missing = [option for option in expected.select_options if option not in available]
            if missing:
                issues.append(
                    ValidationIssue(
                        severity=WARNING,
                        property_name=property_name,
                        code="missing_select_options",
                        message=(
                            f"{property_name} is a select property but missing recommended options: "
                            + ", ".join(missing)
                        ),
                    )
                )

    status = _derive_status(issues)
    return DataSourceValidationResult(
        target=target,
        data_source_id=data_source_id,
        status=status,
        issues=issues,
        checked_property_count=len(expected_schema[target]),
    )


def validate_selected_data_sources(
    *,
    client: NotionClient,
    settings: NotionSettings,
    mapping_root: dict[str, dict[str, str]],
    targets: list[str],
    env: dict[str, str] | None = None,
) -> list[DataSourceValidationResult]:
    env_override_map = {
        "weekly_reports": "NOTION_WEEKLY_REPORTS_DATA_SOURCE_ID",
        "benchmark_reports": "NOTION_BENCHMARK_REPORTS_DATA_SOURCE_ID",
        "account_snapshots": "NOTION_ACCOUNT_SNAPSHOTS_DATA_SOURCE_ID",
        "daily_plans": "NOTION_DAILY_PLANS_DATA_SOURCE_ID",
        "manual_executions": "NOTION_MANUAL_EXECUTIONS_DATA_SOURCE_ID",
        "daily_review_summaries": "NOTION_DAILY_REVIEW_SUMMARIES_DATA_SOURCE_ID",
    }
    results: list[DataSourceValidationResult] = []
    for target in targets:
        try:
            data_source_id = get_notion_data_source_id(
                settings,
                target,
                env=env,
                env_override=env_override_map[target],
            )
        except NotionSettingsError as exc:
            if target not in {"daily_plans", "manual_executions", "daily_review_summaries"}:
                raise
            expected_schema = build_expected_schema(mapping_root)
            results.append(
                DataSourceValidationResult(
                    target=target,
                    data_source_id="",
                    status=WARNING,
                    issues=[
                        ValidationIssue(
                            severity=WARNING,
                            property_name=None,
                            code="missing_data_source_id",
                            message=f"{exc} Skipping read-only schema validation for {target}.",
                        )
                    ],
                    checked_property_count=len(expected_schema[target]),
                )
            )
            continue
        actual_schema = client.get_data_source_schema(data_source_id)
        results.append(
            validate_data_source_schema(
                target=target,
                data_source_id=data_source_id,
                actual_schema=actual_schema,
                mapping_root=mapping_root,
            )
        )
    return results


def format_validation_results(results: list[DataSourceValidationResult]) -> str:
    lines: list[str] = []
    for result in results:
        lines.append(f"{result.target}: {result.status}")
        for issue in result.issues:
            prefix = issue.property_name or "-"
            lines.append(f"- {prefix} {issue.message}")
    return "\n".join(lines)


def validation_results_to_json(results: list[DataSourceValidationResult]) -> dict[str, Any]:
    return {
        "overall_status": FAIL if any(result.status == FAIL for result in results) else (
            WARNING if any(result.status == WARNING for result in results) else PASS
        ),
        "results": [
            {
                "target": result.target,
                "data_source_id": result.data_source_id,
                "status": result.status,
                "checked_property_count": result.checked_property_count,
                "issues": [
                    {
                        "severity": issue.severity,
                        "property_name": issue.property_name,
                        "code": issue.code,
                        "message": issue.message,
                    }
                    for issue in result.issues
                ],
            }
            for result in results
        ],
    }


def _expected(
    mapping_section: dict[str, str],
    source_key: str,
    notion_type: str | tuple[str, ...],
    *,
    required: bool = True,
    select_options: tuple[str, ...] = (),
    check_options: bool = False,
) -> ExpectedProperty:
    return ExpectedProperty(
        source_key=resolve_notion_property_name(mapping_section, source_key),
        notion_type=notion_type,
        required=required,
        select_options=select_options,
        check_options=check_options,
    )


def _extract_actual_properties(actual_schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    properties = actual_schema.get("properties") or {}
    if isinstance(properties, dict):
        return {
            str(name): value
            for name, value in properties.items()
            if isinstance(value, dict)
        }
    if isinstance(properties, list):
        extracted: dict[str, dict[str, Any]] = {}
        for item in properties:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("property") or "").strip()
            if name:
                extracted[name] = item
        return extracted
    return {}


def _extract_select_options(property_schema: dict[str, Any]) -> set[str]:
    select_payload = property_schema.get("select") or {}
    options = select_payload.get("options") or []
    extracted: set[str] = set()
    for option in options:
        if not isinstance(option, dict):
            continue
        name = str(option.get("name") or "").strip()
        if name:
            extracted.add(name)
    return extracted


def _derive_status(issues: list[ValidationIssue]) -> str:
    severities = {issue.severity for issue in issues}
    if FAIL in severities:
        return FAIL
    if WARNING in severities:
        return WARNING
    return PASS


def _expected_types(value: str | tuple[str, ...]) -> tuple[str, ...]:
    if isinstance(value, tuple):
        return value
    return (value,)


def _format_expected_types(expected_types: tuple[str, ...]) -> str:
    if len(expected_types) == 1:
        return expected_types[0]
    return " or ".join(expected_types)
