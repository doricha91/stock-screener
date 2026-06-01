from __future__ import annotations

from core.paper_account_profile import (
    default_paper_account_profile,
    validate_account_id,
)


def normalize_notion_account_id(account_id: str | None = None) -> str:
    if account_id is None:
        return default_paper_account_profile().account_id
    return validate_account_id(account_id)


def build_weekly_report_external_key(
    account_id: str | None,
    period_start: str,
    period_end: str,
) -> str:
    return f"weekly_report:{normalize_notion_account_id(account_id)}:{period_start}:{period_end}"


def build_legacy_weekly_report_external_key(period_start: str, period_end: str) -> str:
    return f"weekly_report:{period_start}:{period_end}"


def build_benchmark_report_external_key(
    account_id: str | None,
    latest_snapshot_date: str,
    run_mode: str,
) -> str:
    return f"benchmark:{normalize_notion_account_id(account_id)}:{latest_snapshot_date}:{run_mode}"


def build_legacy_benchmark_report_external_key(latest_snapshot_date: str, run_mode: str) -> str:
    return f"benchmark:{latest_snapshot_date}:{run_mode}"


def build_account_snapshot_external_key(account_id: str | None, snapshot_date: str) -> str:
    return f"account_snapshot:{normalize_notion_account_id(account_id)}:{snapshot_date}"


def build_legacy_account_snapshot_external_key(snapshot_date: str) -> str:
    return f"account_snapshot:{snapshot_date}"


def build_daily_plan_external_key(account_id: str | None, plan_date: str) -> str:
    return f"daily_plan:{normalize_notion_account_id(account_id)}:{plan_date}"


def build_legacy_daily_plan_external_key(plan_date: str) -> str:
    return f"daily_plan:{plan_date}"


def build_daily_review_summary_external_key(account_id: str | None, review_date: str) -> str:
    return f"daily_review_summary:{normalize_notion_account_id(account_id)}:{review_date}"


def build_legacy_daily_review_summary_external_key(review_date: str) -> str:
    return f"daily_review_summary:{review_date}"


def build_manual_execution_canonical_key(
    account_id: str | None,
    execution_date: str,
    symbol: str,
    side: str,
    sequence: int,
) -> str:
    return (
        f"manual_execution:{normalize_notion_account_id(account_id)}:"
        f"{execution_date}:{symbol.upper()}:{side.upper()}:{sequence:02d}"
    )


def build_legacy_manual_execution_canonical_key(
    execution_date: str,
    symbol: str,
    side: str,
    sequence: int,
) -> str:
    return f"manual_execution:{execution_date}:{symbol.upper()}:{side.upper()}:{sequence:02d}"


def build_manual_review_canonical_key(
    account_id: str | None,
    review_date: str,
    symbol: str,
    question_id: str,
) -> str:
    return (
        f"manual_review:{normalize_notion_account_id(account_id)}:"
        f"{review_date}:{symbol.upper()}:{question_id}"
    )


def build_legacy_manual_review_canonical_key(
    review_date: str,
    symbol: str,
    question_id: str,
) -> str:
    return f"manual_review:{review_date}:{symbol.upper()}:{question_id}"
