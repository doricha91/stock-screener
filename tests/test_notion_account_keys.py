from __future__ import annotations

import pytest

from core.notion_account_keys import (
    build_account_snapshot_external_key,
    build_benchmark_report_external_key,
    build_daily_plan_external_key,
    build_daily_review_summary_external_key,
    build_legacy_account_snapshot_external_key,
    build_legacy_benchmark_report_external_key,
    build_legacy_daily_plan_external_key,
    build_legacy_daily_review_summary_external_key,
    build_legacy_weekly_report_external_key,
    build_weekly_report_external_key,
)


def test_default_account_is_used_when_account_id_is_omitted():
    assert build_daily_plan_external_key(None, "2026-05-20") == "daily_plan:paper_default:2026-05-20"


def test_account_aware_external_keys_are_built_for_read_only_targets():
    assert build_daily_plan_external_key("paper_growth", "2026-05-20") == "daily_plan:paper_growth:2026-05-20"
    assert build_account_snapshot_external_key("paper_growth", "2026-05-20") == (
        "account_snapshot:paper_growth:2026-05-20"
    )
    assert build_weekly_report_external_key("paper_growth", "2026-05-09", "2026-05-20") == (
        "weekly_report:paper_growth:2026-05-09:2026-05-20"
    )
    assert build_benchmark_report_external_key("paper_growth", "2026-05-20", "exploratory") == (
        "benchmark:paper_growth:2026-05-20:exploratory"
    )
    assert build_daily_review_summary_external_key("paper_growth", "2026-05-25") == (
        "daily_review_summary:paper_growth:2026-05-25"
    )


def test_legacy_external_keys_remain_account_less():
    assert build_legacy_daily_plan_external_key("2026-05-20") == "daily_plan:2026-05-20"
    assert build_legacy_account_snapshot_external_key("2026-05-20") == "account_snapshot:2026-05-20"
    assert build_legacy_weekly_report_external_key("2026-05-09", "2026-05-20") == (
        "weekly_report:2026-05-09:2026-05-20"
    )
    assert build_legacy_benchmark_report_external_key("2026-05-20", "exploratory") == (
        "benchmark:2026-05-20:exploratory"
    )
    assert build_legacy_daily_review_summary_external_key("2026-05-25") == (
        "daily_review_summary:2026-05-25"
    )


def test_invalid_account_id_fails():
    with pytest.raises(ValueError):
        build_daily_plan_external_key("Paper Default", "2026-05-20")
