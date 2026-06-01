from __future__ import annotations

import json
from pathlib import Path

from core.paper_weekly_status import build_paper_weekly_status_summary, generate_paper_weekly_status


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_root(tmp_path: Path) -> Path:
    root = tmp_path / "paper_test"
    (root / "reports").mkdir(parents=True, exist_ok=True)
    (root / "reviews").mkdir(parents=True, exist_ok=True)
    return root


def _seed_base_dataset(root: Path) -> None:
    _write(
        root / "paper_account_snapshot.csv",
        "snapshot_date,cash,total_equity_market_value,cash_ratio_market_value,unrealized_pnl,position_count,total_equity_cost_basis\n"
        "2026-05-09,100,1000,0.10,10,2,1000\n"
        "2026-05-12,110,1010,0.11,20,2,1010\n"
        "2026-05-13,120,1020,0.12,15,2,1020\n"
        "2026-05-14,130,1030,0.13,18,3,1030\n"
        "2026-05-15,140,1040,0.14,25,3,1040\n"
        "2026-05-16,150,1050,0.15,30,3,1050\n",
    )
    _write(
        root / "paper_position_snapshot.csv",
        "snapshot_date,symbol,shares,market_value,unrealized_pnl,close_price\n"
        "2026-05-15,AAPL,10,500,30,50\n"
        "2026-05-15,MSFT,5,300,-10,60\n"
        "2026-05-15,NVDA,2,240,5,120\n"
        "2026-05-16,AAPL,10,520,40,52\n"
        "2026-05-16,MSFT,5,290,-20,58\n"
        "2026-05-16,TSLA,3,240,10,80\n",
    )
    _write(
        root / "paper_execution_log.csv",
        "date,symbol,side\n"
        "2026-05-15,AAPL,BUY\n"
        "2026-05-15,MSFT,SELL\n",
    )
    _write(root / "daily_action_plan_20260515.md", "# plan\n")
    _write(root / "daily_action_plan_20260516.md", "# plan\n")
    _write(root / "paper_current_state_20260515.json", "{}\n")
    _write(root / "paper_current_state_20260516.json", "{}\n")
    _write(root / "reports" / "paper_daily_review_summary.md", "# summary\n")
    _write(root / "reports" / "paper_performance_summary.md", "# perf\n")
    _write(
        root / "reports" / "paper_symbol_review_buckets.csv",
        "symbol,review_priority,review_bucket\nAAPL,high,monitor_open_gain\nTSLA,medium,neutral\n",
    )
    _write(
        root / "reviews" / "paper_manual_review_log_template.csv",
        "review_date,symbol,review_status\n2026-05-16,AAPL,pending\n",
    )
    _write(
        root / "reviews" / "paper_manual_review_log_validation_report.md",
        "# report\n\n- Validation result: PASS\n",
    )
    _write(
        root / "reviews" / "paper_manual_review_log.csv",
        "review_date,symbol,review_status\n2026-05-16,AAPL,reviewed\n",
    )


def test_selects_latest_five_snapshot_dates_by_default(tmp_path):
    root = _build_root(tmp_path)
    _seed_base_dataset(root)
    summary = build_paper_weekly_status_summary(paper_root=root)
    coverage_dates = [row["date"] for row in summary["operation_coverage"]]
    assert coverage_dates == ["2026-05-12", "2026-05-13", "2026-05-14", "2026-05-15", "2026-05-16"]


def test_days_option_limits_snapshot_count(tmp_path):
    root = _build_root(tmp_path)
    _seed_base_dataset(root)
    summary = build_paper_weekly_status_summary(days=2, paper_root=root)
    assert summary["period"]["snapshot_count"] == 2
    assert summary["period"]["actual_start"] == "2026-05-15"
    assert summary["period"]["actual_end"] == "2026-05-16"
    assert summary["period"]["coverage_status"] == "FULL"


def test_start_end_filters_snapshot_dates(tmp_path):
    root = _build_root(tmp_path)
    _seed_base_dataset(root)
    summary = build_paper_weekly_status_summary(start="20260513", end="20260515", paper_root=root)
    assert [row["date"] for row in summary["operation_coverage"]] == ["2026-05-13", "2026-05-14", "2026-05-15"]
    assert summary["period"]["basis"] == "snapshot_date"
    assert summary["period"]["requested_start"] == "2026-05-13"
    assert summary["period"]["requested_end"] == "2026-05-15"
    assert summary["period"]["included_snapshot_dates"] == ["2026-05-13", "2026-05-14", "2026-05-15"]
    assert summary["period"]["coverage_status"] == "FULL"


def test_no_trade_day_is_not_high_gap(tmp_path):
    root = _build_root(tmp_path)
    _seed_base_dataset(root)
    summary = build_paper_weekly_status_summary(days=2, paper_root=root)
    coverage = {row["date"]: row for row in summary["operation_coverage"]}
    assert coverage["2026-05-16"]["execution_log_rows"] == 0
    assert coverage["2026-05-16"]["operation_gap_severity"] != "HIGH"
    assert "2026-05-16" in summary["trade_summary"]["no_trade_days"]


def test_missing_position_snapshot_is_high_gap(tmp_path):
    root = _build_root(tmp_path)
    _write(
        root / "paper_account_snapshot.csv",
        "snapshot_date,cash,total_equity_market_value,cash_ratio_market_value,unrealized_pnl,position_count,total_equity_cost_basis\n"
        "2026-05-20,100,1000,0.1,10,2,1000\n",
    )
    _write(root / "daily_action_plan_20260520.md", "# plan\n")
    _write(root / "paper_current_state_20260520.json", "{}\n")
    summary = build_paper_weekly_status_summary(days=1, paper_root=root)
    assert summary["operation_coverage"][0]["operation_gap_severity"] == "HIGH"
    assert summary["operation_gaps"][0]["code"] in {"MISSING_POSITION_SNAPSHOT", "INCOMPLETE_COMMIT_SNAPSHOT"}


def test_missing_plan_is_shown_in_coverage(tmp_path):
    root = _build_root(tmp_path)
    _seed_base_dataset(root)
    (root / "daily_action_plan_20260516.md").unlink()
    summary = build_paper_weekly_status_summary(days=2, paper_root=root)
    coverage = {row["date"]: row for row in summary["operation_coverage"]}
    assert "MISSING_PLAN" in coverage["2026-05-16"]["missing_steps"]


def test_equity_and_cash_ratio_changes_are_computed(tmp_path):
    root = _build_root(tmp_path)
    _seed_base_dataset(root)
    summary = build_paper_weekly_status_summary(days=2, paper_root=root)
    account = summary["account_summary"]
    assert account["equity_change"] == 10.0
    assert round(account["equity_change_pct"], 6) == round(10.0 / 1040.0, 6)
    assert round(account["cash_ratio_change"], 6) == 0.01
    assert isinstance(account["end_equity_market_value"], float)
    assert isinstance(account["end_cash_ratio_market_value"], float)


def test_added_and_removed_symbols_are_computed(tmp_path):
    root = _build_root(tmp_path)
    _seed_base_dataset(root)
    summary = build_paper_weekly_status_summary(days=2, paper_root=root)
    position = summary["position_summary"]
    assert position["added_symbols"] == ["TSLA"]
    assert position["removed_symbols"] == ["NVDA"]
    assert position["held_symbols"] == ["AAPL", "MSFT"]


def test_markdown_and_json_files_are_generated(tmp_path):
    root = _build_root(tmp_path)
    _seed_base_dataset(root)
    result = generate_paper_weekly_status(days=2, paper_root=root)
    assert result["markdown_path"].exists()
    assert result["json_path"].exists()
    payload = json.loads(result["json_path"].read_text(encoding="utf-8"))
    assert payload["schema_version"] == "paper_weekly_status.v1"
    assert payload["period"]["actual_start"] == "2026-05-15"
    assert payload["period"]["actual_end"] == "2026-05-16"
    assert "source_files" in payload
    assert "limitations" in payload


def test_top_level_json_schema_is_stable(tmp_path):
    root = _build_root(tmp_path)
    _seed_base_dataset(root)
    payload = build_paper_weekly_status_summary(days=2, paper_root=root)
    assert set(payload.keys()) == {
        "account_id",
        "account_root",
        "legacy_default_used",
        "schema_version",
        "generated_at",
        "period",
        "latest_snapshot_date",
        "overall_status",
        "operation_coverage",
        "account_summary",
        "position_summary",
        "trade_summary",
        "review_summary",
        "operation_gaps",
        "recommended_next_actions",
        "source_files",
        "limitations",
    }


def test_source_files_metadata_is_present(tmp_path):
    root = _build_root(tmp_path)
    _seed_base_dataset(root)
    summary = build_paper_weekly_status_summary(days=2, paper_root=root)
    assert summary["source_files"]["account_snapshot"]["exists"] is True
    assert summary["source_files"]["execution_log"]["row_count"] == 2
    assert summary["source_files"]["position_snapshot"]["latest_date"] == "2026-05-16"


def test_markdown_mentions_schema_version_and_coverage_status(tmp_path):
    root = _build_root(tmp_path)
    _seed_base_dataset(root)
    result = generate_paper_weekly_status(days=2, paper_root=root)
    text = result["markdown_path"].read_text(encoding="utf-8")
    assert "Schema version: paper_weekly_status.v1" in text
    assert "Coverage status: FULL" in text


def test_operation_gaps_include_code_severity_and_message(tmp_path):
    root = _build_root(tmp_path)
    _seed_base_dataset(root)
    (root / "daily_action_plan_20260516.md").unlink()
    summary = build_paper_weekly_status_summary(days=2, paper_root=root)
    assert summary["operation_gaps"]
    for gap in summary["operation_gaps"]:
        assert gap["severity"] in {"HIGH", "MEDIUM", "LOW"}
        assert set(gap.keys()) >= {"date", "code", "severity", "message"}


def test_empty_requested_range_sets_empty_coverage(tmp_path):
    root = _build_root(tmp_path)
    _seed_base_dataset(root)
    summary = build_paper_weekly_status_summary(start="20260501", end="20260502", paper_root=root)
    assert summary["period"]["coverage_status"] == "EMPTY"
    assert summary["period"]["snapshot_count"] == 0
    assert summary["overall_status"] == "FAIL"
