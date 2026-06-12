from __future__ import annotations

from pathlib import Path
import sys

import pytest

from scripts import paper


def test_help_shows_subcommands(capsys):
    exit_code = paper.main([])
    output = capsys.readouterr().out
    assert exit_code == 0
    assert "prepare" in output
    assert "prepare-data" in output
    assert "preview" in output
    assert "commit" in output
    assert "data-freshness" in output
    assert "status" in output
    assert "weekly-status" in output
    assert "benchmark" in output
    assert "preflight" in output
    assert "plan" in output
    assert "eod" in output
    assert "review" in output
    assert "reports" in output
    assert "review-template" in output
    assert "review-validate" in output
    assert "review-append" in output


def test_prepare_data_calls_existing_runner(monkeypatch):
    captured: dict[str, object] = {}

    def fake_run_paper_prepare_data(
        date_str: str,
        *,
        skip_prices: bool,
        skip_indicators: bool,
        include_universe: bool,
    ) -> dict:
        captured.update(
            {
                "date_str": date_str,
                "skip_prices": skip_prices,
                "skip_indicators": skip_indicators,
                "include_universe": include_universe,
            }
        )
        return {
            "date": "2026-05-13",
            "ticker_count": 10,
            "market_db_path": "outputs/market_data.db",
            "price_update_status": "success",
            "indicators_update_status": "success",
            "universe_update_status": "skipped",
            "universe_snapshot_path": None,
            "warnings": [],
            "errors": [],
        }

    monkeypatch.setattr(paper, "run_paper_prepare_data", fake_run_paper_prepare_data)
    exit_code = paper.main(["prepare-data", "--date", "20260513"])
    assert exit_code == 0
    assert captured == {
        "date_str": "20260513",
        "skip_prices": False,
        "skip_indicators": False,
        "include_universe": False,
    }


def test_prepare_data_passes_skip_and_universe_flags(monkeypatch):
    captured: dict[str, object] = {}

    def fake_run_paper_prepare_data(
        date_str: str,
        *,
        skip_prices: bool,
        skip_indicators: bool,
        include_universe: bool,
    ) -> dict:
        captured.update(
            {
                "date_str": date_str,
                "skip_prices": skip_prices,
                "skip_indicators": skip_indicators,
                "include_universe": include_universe,
            }
        )
        return {
            "date": "2026-05-13",
            "ticker_count": 10,
            "market_db_path": "outputs/market_data.db",
            "price_update_status": "skipped",
            "indicators_update_status": "skipped",
            "universe_update_status": "success",
            "universe_snapshot_path": "outputs/universe/universe_snapshot_20260513.json",
            "warnings": [],
            "errors": [],
        }

    monkeypatch.setattr(paper, "run_paper_prepare_data", fake_run_paper_prepare_data)
    exit_code = paper.main(
        ["prepare-data", "--date", "20260513", "--skip-prices", "--skip-indicators", "--universe"]
    )
    assert exit_code == 0
    assert captured == {
        "date_str": "20260513",
        "skip_prices": True,
        "skip_indicators": True,
        "include_universe": True,
    }


def test_data_freshness_calls_existing_checker(monkeypatch):
    captured: dict[str, object] = {}

    def fake_run_paper_data_freshness_check(*, date_str: str, strict: bool) -> dict:
        captured.update({"date_str": date_str, "strict": strict})
        return {
            "target_date": "2026-05-13",
            "market_db_path": "outputs/market_data.db",
            "result": "PASS_WITH_WARNINGS",
            "error_count": 0,
            "warning_count": 1,
            "checks": [],
        }

    monkeypatch.setattr(paper, "run_paper_data_freshness_check", fake_run_paper_data_freshness_check)
    exit_code = paper.main(["data-freshness", "--date", "20260513", "--strict"])
    assert exit_code == 0
    assert captured == {"date_str": "20260513", "strict": True}


def test_data_freshness_returns_one_on_fail(monkeypatch):
    def fake_run_paper_data_freshness_check(*, date_str: str, strict: bool) -> dict:
        return {
            "target_date": "2026-05-13",
            "market_db_path": "outputs/market_data.db",
            "result": "FAIL",
            "error_count": 1,
            "warning_count": 0,
            "checks": [],
        }

    monkeypatch.setattr(paper, "run_paper_data_freshness_check", fake_run_paper_data_freshness_check)
    exit_code = paper.main(["data-freshness", "--date", "20260513"])
    assert exit_code == 1


def test_data_freshness_without_write_report_does_not_create_report(monkeypatch):
    called = {"report": False}

    def fake_run_paper_data_freshness_check(*, date_str: str, strict: bool) -> dict:
        return {
            "target_date": "2026-05-13",
            "market_db_path": "outputs/market_data.db",
            "result": "PASS",
            "error_count": 0,
            "warning_count": 0,
            "checks": [],
        }

    def fake_write_report(summary: dict) -> tuple[str, str]:
        called["report"] = True
        return ("report.md", "issues.csv")

    monkeypatch.setattr(paper, "run_paper_data_freshness_check", fake_run_paper_data_freshness_check)
    monkeypatch.setattr(paper, "write_paper_data_freshness_report", fake_write_report)
    exit_code = paper.main(["data-freshness", "--date", "20260513"])
    assert exit_code == 0
    assert called["report"] is False


def test_data_freshness_does_not_call_prepare_data(monkeypatch):
    called = {"prepare": False}

    def fake_run_paper_data_freshness_check(*, date_str: str, strict: bool) -> dict:
        return {
            "target_date": "2026-05-13",
            "market_db_path": "outputs/market_data.db",
            "result": "PASS",
            "error_count": 0,
            "warning_count": 0,
            "checks": [],
        }

    def fake_run_paper_prepare_data(
        date_str: str,
        *,
        skip_prices: bool,
        skip_indicators: bool,
        include_universe: bool,
    ) -> dict:
        called["prepare"] = True
        return {}

    monkeypatch.setattr(paper, "run_paper_data_freshness_check", fake_run_paper_data_freshness_check)
    monkeypatch.setattr(paper, "run_paper_prepare_data", fake_run_paper_prepare_data)
    exit_code = paper.main(["data-freshness", "--date", "20260513"])
    assert exit_code == 0
    assert called["prepare"] is False


def test_status_calls_core_status_reader(monkeypatch):
    captured: list[str | None] = []

    def fake_run_paper_status(date_str: str | None = None):
        captured.append(date_str)
        return {
            "date": "2026-05-20",
            "workflow_status": "COMMITTED",
            "latest_account_snapshot_date": "2026-05-20",
            "latest_current_state_date": "2026-05-20",
            "daily_action_plan_exists": True,
            "current_state_exists": True,
            "account_snapshot_exists": True,
            "position_snapshot_exists": True,
            "same_date_snapshot_exists": True,
            "execution_log_rows_for_date": 0,
            "reports_exists": True,
            "review_template_exists": True,
            "review_validation_exists": True,
            "review_validation_result": "PASS",
            "next_recommended_command": "paper.py review",
            "errors": [],
        }

    monkeypatch.setattr(paper, "run_paper_status", fake_run_paper_status)
    exit_code = paper.main(["status", "--date", "20260520"])
    assert exit_code == 0
    assert captured == ["20260520"]


def test_status_json_output_is_valid(monkeypatch, capsys):
    monkeypatch.setattr(
        paper,
        "run_paper_status",
        lambda date_str=None: {
            "date": "2026-05-20",
            "workflow_status": "PLAN_READY",
            "latest_account_snapshot_date": "2026-05-20",
            "latest_current_state_date": None,
            "daily_action_plan_exists": True,
            "current_state_exists": False,
            "account_snapshot_exists": False,
            "position_snapshot_exists": False,
            "same_date_snapshot_exists": False,
            "execution_log_rows_for_date": 0,
            "reports_exists": False,
            "review_template_exists": False,
            "review_validation_exists": False,
            "review_validation_result": None,
            "next_recommended_command": "paper.py commit --date 20260520",
            "errors": [],
        },
    )
    exit_code = paper.main(["status", "--date", "20260520", "--json"])
    output = capsys.readouterr().out
    assert exit_code == 0
    assert '"workflow_status": "PLAN_READY"' in output


def test_status_does_not_call_writers(monkeypatch):
    called = {"prepare": False, "plan": False, "eod": False, "reports": False, "review_append": False}

    monkeypatch.setattr(
        paper,
        "run_paper_status",
        lambda date_str=None: {
            "date": "2026-05-20",
            "workflow_status": "NO_PLAN",
            "latest_account_snapshot_date": None,
            "latest_current_state_date": None,
            "daily_action_plan_exists": False,
            "current_state_exists": False,
            "account_snapshot_exists": False,
            "position_snapshot_exists": False,
            "same_date_snapshot_exists": False,
            "execution_log_rows_for_date": 0,
            "reports_exists": False,
            "review_template_exists": False,
            "review_validation_exists": False,
            "review_validation_result": None,
            "next_recommended_command": "paper.py preview --date 20260520",
            "errors": [],
        },
    )
    monkeypatch.setattr(paper, "run_paper_prepare_data", lambda *args, **kwargs: called.__setitem__("prepare", True) or {})
    monkeypatch.setattr(paper, "run_paper_daily_plan", lambda *args, **kwargs: called.__setitem__("plan", True) or "")
    monkeypatch.setattr(paper, "run_paper_eod_dry_run", lambda *args, **kwargs: called.__setitem__("eod", True) or 0)
    monkeypatch.setattr(paper, "run_report_chain", lambda: called.__setitem__("reports", True) or [])
    monkeypatch.setattr(paper, "append_paper_manual_review_log_from_template", lambda: called.__setitem__("review_append", True) or {})
    exit_code = paper.main(["status"])
    assert exit_code == 0
    assert called == {"prepare": False, "plan": False, "eod": False, "reports": False, "review_append": False}


def test_weekly_status_calls_generator(monkeypatch):
    captured: dict[str, object] = {}

    def fake_generate_paper_weekly_status(*, days: int, start: str | None, end: str | None) -> dict:
        captured.update({"days": days, "start": start, "end": end})
        return {
            "markdown_path": "outputs/paper_test/reports/paper_weekly_status_summary.md",
            "json_path": "outputs/paper_test/reports/paper_weekly_status_summary.json",
            "summary": {
                "schema_version": "paper_weekly_status.v1",
                "period": {"actual_start": "2026-05-15", "actual_end": "2026-05-20", "snapshot_count": 2, "coverage_status": "FULL"},
                "overall_status": "PASS",
            },
        }

    monkeypatch.setattr(paper, "generate_paper_weekly_status", fake_generate_paper_weekly_status)
    exit_code = paper.main(["weekly-status", "--days", "2"])
    assert exit_code == 0
    assert captured == {"days": 2, "start": None, "end": None}


def test_weekly_status_does_not_call_writers(monkeypatch):
    called = {"prepare": False, "plan": False, "eod": False, "reports": False, "review_append": False}

    monkeypatch.setattr(
        paper,
        "generate_paper_weekly_status",
        lambda **kwargs: {
            "markdown_path": "outputs/paper_test/reports/paper_weekly_status_summary.md",
            "json_path": "outputs/paper_test/reports/paper_weekly_status_summary.json",
            "summary": {
                "schema_version": "paper_weekly_status.v1",
                "period": {"actual_start": "2026-05-15", "actual_end": "2026-05-20", "snapshot_count": 2, "coverage_status": "FULL"},
                "overall_status": "PASS_WITH_WARNINGS",
            },
        },
    )
    monkeypatch.setattr(paper, "run_paper_prepare_data", lambda *args, **kwargs: called.__setitem__("prepare", True) or {})
    monkeypatch.setattr(paper, "run_paper_daily_plan", lambda *args, **kwargs: called.__setitem__("plan", True) or "")
    monkeypatch.setattr(paper, "run_paper_eod_dry_run", lambda *args, **kwargs: called.__setitem__("eod", True) or 0)
    monkeypatch.setattr(paper, "run_report_chain", lambda: called.__setitem__("reports", True) or [])
    monkeypatch.setattr(paper, "append_paper_manual_review_log_from_template", lambda: called.__setitem__("review_append", True) or {})
    exit_code = paper.main(["weekly-status"])
    assert exit_code == 0
    assert called == {"prepare": False, "plan": False, "eod": False, "reports": False, "review_append": False}


def test_benchmark_calls_generator(monkeypatch):
    called = {"benchmark": False}

    def fake_generate_paper_benchmark_comparison() -> dict:
        called["benchmark"] = True
        return {
            "markdown_path": "outputs/paper_test/reports/paper_benchmark_comparison.md",
            "json_path": "outputs/paper_test/reports/paper_benchmark_comparison.json",
            "summary": {
                "schema_version": "paper_benchmark_comparison.v1",
                "run_mode": "exploratory",
                "official_run": False,
                "latest_snapshot_date": "2026-05-20",
                "availability_status": "AVAILABLE",
            },
        }

    monkeypatch.setattr(paper, "generate_paper_benchmark_comparison", fake_generate_paper_benchmark_comparison)
    exit_code = paper.main(["benchmark"])
    assert exit_code == 0
    assert called["benchmark"] is True


def test_benchmark_json_prints_payload(monkeypatch, capsys):
    monkeypatch.setattr(
        paper,
        "generate_paper_benchmark_comparison",
        lambda: {
            "markdown_path": "outputs/paper_test/reports/paper_benchmark_comparison.md",
            "json_path": "outputs/paper_test/reports/paper_benchmark_comparison.json",
            "summary": {
                "schema_version": "paper_benchmark_comparison.v1",
                "run_mode": "exploratory",
                "official_run": False,
                "latest_snapshot_date": "2026-05-20",
                "availability_status": "AVAILABLE",
            },
        },
    )
    exit_code = paper.main(["benchmark", "--json"])
    output = capsys.readouterr().out
    assert exit_code == 0
    assert '"schema_version": "paper_benchmark_comparison.v1"' in output


def test_benchmark_does_not_call_writers(monkeypatch):
    called = {"prepare": False, "plan": False, "eod": False, "reports": False, "review_append": False}

    monkeypatch.setattr(
        paper,
        "generate_paper_benchmark_comparison",
        lambda: {
            "markdown_path": "outputs/paper_test/reports/paper_benchmark_comparison.md",
            "json_path": "outputs/paper_test/reports/paper_benchmark_comparison.json",
            "summary": {
                "schema_version": "paper_benchmark_comparison.v1",
                "run_mode": "exploratory",
                "official_run": False,
                "latest_snapshot_date": "2026-05-20",
                "availability_status": "AVAILABLE",
            },
        },
    )
    monkeypatch.setattr(paper, "run_paper_prepare_data", lambda *args, **kwargs: called.__setitem__("prepare", True) or {})
    monkeypatch.setattr(paper, "run_paper_daily_plan", lambda *args, **kwargs: called.__setitem__("plan", True) or "")
    monkeypatch.setattr(paper, "run_paper_eod_dry_run", lambda *args, **kwargs: called.__setitem__("eod", True) or 0)
    monkeypatch.setattr(paper, "run_report_chain", lambda: called.__setitem__("reports", True) or [])
    monkeypatch.setattr(paper, "append_paper_manual_review_log_from_template", lambda: called.__setitem__("review_append", True) or {})
    exit_code = paper.main(["benchmark"])
    assert exit_code == 0
    assert called == {"prepare": False, "plan": False, "eod": False, "reports": False, "review_append": False}


def test_prepare_shortcut_runs_prepare_data_then_data_freshness(monkeypatch):
    order: list[str] = []

    def fake_run_paper_prepare_data(
        date_str: str,
        *,
        skip_prices: bool,
        skip_indicators: bool,
        include_universe: bool,
    ) -> dict:
        order.append("prepare-data")
        return {
            "date": "2026-05-13",
            "ticker_count": 10,
            "market_db_path": "outputs/market_data.db",
            "price_update_status": "success",
            "indicators_update_status": "success",
            "universe_update_status": "skipped",
            "universe_snapshot_path": None,
            "warnings": [],
            "errors": [],
        }

    def fake_run_paper_data_freshness_check(*, date_str: str, strict: bool) -> dict:
        order.append("data-freshness")
        return {
            "target_date": "2026-05-13",
            "market_db_path": "outputs/market_data.db",
            "result": "PASS",
            "error_count": 0,
            "warning_count": 0,
            "checks": [],
        }

    monkeypatch.setattr(paper, "run_paper_prepare_data", fake_run_paper_prepare_data)
    monkeypatch.setattr(paper, "run_paper_data_freshness_check", fake_run_paper_data_freshness_check)
    exit_code = paper.main(["prepare", "--date", "20260513"])
    assert exit_code == 0
    assert order == ["prepare-data", "data-freshness"]


def test_prepare_shortcut_blocks_on_warnings_by_default(monkeypatch):
    monkeypatch.setattr(
        paper,
        "run_paper_prepare_data",
        lambda date_str, **kwargs: {
            "date": "2026-05-13",
            "ticker_count": 10,
            "market_db_path": "outputs/market_data.db",
            "price_update_status": "success",
            "indicators_update_status": "success",
            "universe_update_status": "skipped",
            "universe_snapshot_path": None,
            "warnings": [],
            "errors": [],
        },
    )
    monkeypatch.setattr(
        paper,
        "run_paper_data_freshness_check",
        lambda *, date_str, strict: {
            "target_date": "2026-05-13",
            "market_db_path": "outputs/market_data.db",
            "result": "PASS_WITH_WARNINGS",
            "error_count": 0,
            "warning_count": 1,
            "checks": [],
        },
    )
    exit_code = paper.main(["prepare", "--date", "20260513"])
    assert exit_code == 1


def test_prepare_shortcut_allows_warnings_when_explicit(monkeypatch):
    monkeypatch.setattr(
        paper,
        "run_paper_prepare_data",
        lambda date_str, **kwargs: {
            "date": "2026-05-13",
            "ticker_count": 10,
            "market_db_path": "outputs/market_data.db",
            "price_update_status": "success",
            "indicators_update_status": "success",
            "universe_update_status": "skipped",
            "universe_snapshot_path": None,
            "warnings": [],
            "errors": [],
        },
    )
    monkeypatch.setattr(
        paper,
        "run_paper_data_freshness_check",
        lambda *, date_str, strict: {
            "target_date": "2026-05-13",
            "market_db_path": "outputs/market_data.db",
            "result": "PASS_WITH_WARNINGS",
            "error_count": 0,
            "warning_count": 1,
            "checks": [],
        },
    )
    exit_code = paper.main(["prepare", "--date", "20260513", "--allow-warnings"])
    assert exit_code == 0


def test_prepare_shortcut_passes_universe_flag(monkeypatch):
    captured: dict[str, object] = {}

    def fake_run_paper_prepare_data(
        date_str: str,
        *,
        skip_prices: bool,
        skip_indicators: bool,
        include_universe: bool,
    ) -> dict:
        captured["include_universe"] = include_universe
        return {
            "date": "2026-05-13",
            "ticker_count": 10,
            "market_db_path": "outputs/market_data.db",
            "price_update_status": "success",
            "indicators_update_status": "success",
            "universe_update_status": "success",
            "universe_snapshot_path": "outputs/universe/universe_snapshot_20260513.json",
            "warnings": [],
            "errors": [],
        }

    monkeypatch.setattr(paper, "run_paper_prepare_data", fake_run_paper_prepare_data)
    monkeypatch.setattr(
        paper,
        "run_paper_data_freshness_check",
        lambda *, date_str, strict: {
            "target_date": "2026-05-13",
            "market_db_path": "outputs/market_data.db",
            "result": "PASS",
            "error_count": 0,
            "warning_count": 0,
            "checks": [],
        },
    )
    exit_code = paper.main(["prepare", "--date", "20260513", "--universe"])
    assert exit_code == 0
    assert captured["include_universe"] is True


def test_preview_runs_data_freshness_then_plan_then_eod_dry_run(monkeypatch):
    order: list[str] = []

    def fake_run_paper_data_freshness_check(*, date_str: str, strict: bool) -> dict:
        order.append("data-freshness")
        return {
            "target_date": "2026-05-13",
            "market_db_path": "outputs/market_data.db",
            "result": "PASS",
            "error_count": 0,
            "warning_count": 0,
            "checks": [],
        }

    def fake_handle_plan(args):
        order.append("plan")
        return 0

    def fake_handle_eod(args):
        order.append("eod-dry-run")
        assert args.commit is False
        assert args.dry_run is True
        return 0

    monkeypatch.setattr(paper, "run_paper_data_freshness_check", fake_run_paper_data_freshness_check)
    monkeypatch.setattr(paper, "handle_plan", fake_handle_plan)
    monkeypatch.setattr(paper, "handle_eod", fake_handle_eod)
    exit_code = paper.main(["preview", "--date", "20260513"])
    assert exit_code == 0
    assert order == ["data-freshness", "plan", "eod-dry-run"]


def test_preview_does_not_call_prepare_data(monkeypatch):
    called = {"prepare": False}

    monkeypatch.setattr(
        paper,
        "run_paper_data_freshness_check",
        lambda *, date_str, strict: {
            "target_date": "2026-05-13",
            "market_db_path": "outputs/market_data.db",
            "result": "PASS",
            "error_count": 0,
            "warning_count": 0,
            "checks": [],
        },
    )
    monkeypatch.setattr(paper, "handle_plan", lambda args: 0)
    monkeypatch.setattr(paper, "handle_eod", lambda args: 0)

    def fake_run_paper_prepare_data(date_str: str, **kwargs) -> dict:
        called["prepare"] = True
        return {}

    monkeypatch.setattr(paper, "run_paper_prepare_data", fake_run_paper_prepare_data)
    exit_code = paper.main(["preview", "--date", "20260513"])
    assert exit_code == 0
    assert called["prepare"] is False


def test_preview_does_not_call_eod_commit(monkeypatch):
    monkeypatch.setattr(
        paper,
        "run_paper_data_freshness_check",
        lambda *, date_str, strict: {
            "target_date": "2026-05-13",
            "market_db_path": "outputs/market_data.db",
            "result": "PASS",
            "error_count": 0,
            "warning_count": 0,
            "checks": [],
        },
    )
    monkeypatch.setattr(paper, "handle_plan", lambda args: 0)

    def fake_handle_eod(args):
        assert args.commit is False
        return 0

    monkeypatch.setattr(paper, "handle_eod", fake_handle_eod)
    exit_code = paper.main(["preview", "--date", "20260513"])
    assert exit_code == 0


def test_preview_blocks_on_warnings_by_default(monkeypatch):
    monkeypatch.setattr(
        paper,
        "run_paper_data_freshness_check",
        lambda *, date_str, strict: {
            "target_date": "2026-05-13",
            "market_db_path": "outputs/market_data.db",
            "result": "PASS_WITH_WARNINGS",
            "error_count": 0,
            "warning_count": 1,
            "checks": [],
        },
    )
    exit_code = paper.main(["preview", "--date", "20260513"])
    assert exit_code == 1


def test_preview_allows_warnings_when_explicit(monkeypatch):
    calls: list[str] = []

    monkeypatch.setattr(
        paper,
        "run_paper_data_freshness_check",
        lambda *, date_str, strict: {
            "target_date": "2026-05-13",
            "market_db_path": "outputs/market_data.db",
            "result": "PASS_WITH_WARNINGS",
            "error_count": 0,
            "warning_count": 1,
            "checks": [],
        },
    )
    monkeypatch.setattr(paper, "handle_plan", lambda args: calls.append("plan") or 0)
    monkeypatch.setattr(paper, "handle_eod", lambda args: calls.append("eod") or 0)
    exit_code = paper.main(["preview", "--date", "20260513", "--allow-warnings"])
    assert exit_code == 0
    assert calls == ["plan", "eod"]


def test_commit_calls_eod_commit_only(monkeypatch):
    captured: list[tuple[bool, bool, str]] = []

    monkeypatch.setattr(
        paper,
        "check_same_date_commit_guard",
        lambda date_str: {
            "allowed": True,
            "error": None,
            "normalized_date": "2026-05-13",
            "existing_sources": [],
            "paths": None,
        },
    )

    def fake_handle_eod(args):
        captured.append((args.dry_run, args.commit, args.date))
        return 0

    monkeypatch.setattr(paper, "handle_eod", fake_handle_eod)
    exit_code = paper.main(["commit", "--date", "20260513"])
    assert exit_code == 0
    assert captured == [(False, True, "20260513")]


def test_commit_blocks_when_current_state_snapshot_exists(monkeypatch):
    monkeypatch.setattr(
        paper,
        "check_same_date_commit_guard",
        lambda date_str: {
            "allowed": False,
            "error": None,
            "normalized_date": "2026-05-13",
            "existing_sources": ["paper_current_state_20260513.json"],
            "paths": None,
        },
    )
    called = {"eod": False}

    def fake_handle_eod(args):
        called["eod"] = True
        return 0

    monkeypatch.setattr(paper, "handle_eod", fake_handle_eod)
    exit_code = paper.main(["commit", "--date", "20260513"])
    assert exit_code == 1
    assert called["eod"] is False


def test_commit_blocks_when_account_snapshot_has_same_date(monkeypatch):
    monkeypatch.setattr(
        paper,
        "check_same_date_commit_guard",
        lambda date_str: {
            "allowed": False,
            "error": None,
            "normalized_date": "2026-05-13",
            "existing_sources": ["paper_account_snapshot.csv"],
            "paths": None,
        },
    )
    monkeypatch.setattr(paper, "handle_eod", lambda args: 0)
    exit_code = paper.main(["commit", "--date", "20260513"])
    assert exit_code == 1


def test_commit_blocks_when_position_snapshot_has_same_date(monkeypatch):
    monkeypatch.setattr(
        paper,
        "check_same_date_commit_guard",
        lambda date_str: {
            "allowed": False,
            "error": None,
            "normalized_date": "2026-05-13",
            "existing_sources": ["paper_position_snapshot.csv"],
            "paths": None,
        },
    )
    monkeypatch.setattr(paper, "handle_eod", lambda args: 0)
    exit_code = paper.main(["commit", "--date", "20260513"])
    assert exit_code == 1


def test_commit_allows_replace_on_same_date(monkeypatch):
    captured: list[tuple[bool, bool, str]] = []

    monkeypatch.setattr(
        paper,
        "check_same_date_commit_guard",
        lambda date_str: {
            "allowed": False,
            "error": None,
            "normalized_date": "2026-05-13",
            "existing_sources": ["paper_account_snapshot.csv"],
            "paths": None,
        },
    )

    def fake_handle_eod(args):
        captured.append((args.dry_run, args.commit, args.date))
        return 7

    monkeypatch.setattr(paper, "handle_eod", fake_handle_eod)
    exit_code = paper.main(["commit", "--date", "20260513", "--replace"])
    assert exit_code == 7
    assert captured == [(False, True, "20260513")]


def test_commit_guard_error_returns_one(monkeypatch):
    monkeypatch.setattr(
        paper,
        "check_same_date_commit_guard",
        lambda date_str: {
            "allowed": False,
            "error": "failed to parse paper_account_snapshot.csv",
            "normalized_date": "2026-05-13",
            "existing_sources": [],
            "paths": None,
        },
    )
    monkeypatch.setattr(paper, "handle_eod", lambda args: 0)
    exit_code = paper.main(["commit", "--date", "20260513"])
    assert exit_code == 1


def test_commit_guard_does_not_call_prepare_reports_or_review(monkeypatch):
    called = {"prepare": False, "reports": False, "review_template": False, "review_validate": False}

    monkeypatch.setattr(
        paper,
        "check_same_date_commit_guard",
        lambda date_str: {
            "allowed": True,
            "error": None,
            "normalized_date": "2026-05-13",
            "existing_sources": [],
            "paths": None,
        },
    )
    monkeypatch.setattr(paper, "handle_eod", lambda args: 0)
    monkeypatch.setattr(paper, "run_paper_prepare_data", lambda *args, **kwargs: called.__setitem__("prepare", True) or {})
    monkeypatch.setattr(paper, "handle_reports", lambda args: called.__setitem__("reports", True) or 0)
    monkeypatch.setattr(paper, "handle_review_template", lambda args: called.__setitem__("review_template", True) or 0)
    monkeypatch.setattr(paper, "handle_review_validate", lambda args: called.__setitem__("review_validate", True) or 0)
    exit_code = paper.main(["commit", "--date", "20260513"])
    assert exit_code == 0
    assert called == {"prepare": False, "reports": False, "review_template": False, "review_validate": False}


def test_review_shortcut_runs_reports_then_template_then_validate(monkeypatch):
    order: list[str] = []
    captured_dates: list[str | None] = []

    def fake_handle_reports(args):
        order.append("reports")
        return 0

    def fake_handle_review_template(args):
        order.append("review-template")
        captured_dates.append(args.date)
        return 0

    def fake_handle_review_validate(args):
        order.append("review-validate")
        return 0

    monkeypatch.setattr(paper, "handle_reports", fake_handle_reports)
    monkeypatch.setattr(paper, "handle_review_template", fake_handle_review_template)
    monkeypatch.setattr(paper, "handle_review_validate", fake_handle_review_validate)
    exit_code = paper.main(["review"])
    assert exit_code == 0
    assert order == ["reports", "review-template", "review-validate"]
    assert captured_dates == [None]


def test_review_shortcut_passes_explicit_review_date_to_template(monkeypatch):
    captured_dates: list[str | None] = []

    monkeypatch.setattr(paper, "handle_reports", lambda args: 0)
    monkeypatch.setattr(
        paper,
        "handle_review_template",
        lambda args: captured_dates.append(args.date) or 0,
    )
    monkeypatch.setattr(paper, "handle_review_validate", lambda args: 0)

    exit_code = paper.main(["review", "--date", "2026-06-08"])

    assert exit_code == 0
    assert captured_dates == ["2026-06-08"]


def test_review_shortcut_does_not_call_review_append(monkeypatch):
    called = {"append": False}

    monkeypatch.setattr(paper, "handle_reports", lambda args: 0)
    monkeypatch.setattr(paper, "handle_review_template", lambda args: 0)
    monkeypatch.setattr(paper, "handle_review_validate", lambda args: 0)

    def fake_handle_review_append(args):
        called["append"] = True
        return 0

    monkeypatch.setattr(paper, "handle_review_append", fake_handle_review_append)
    exit_code = paper.main(["review"])
    assert exit_code == 0
    assert called["append"] is False


def test_review_shortcut_blocks_on_reports_warnings_by_default(monkeypatch):
    captured: list[bool] = []

    def fake_handle_reports(args):
        captured.append(args.strict)
        return 1

    monkeypatch.setattr(paper, "handle_reports", fake_handle_reports)
    exit_code = paper.main(["review"])
    assert exit_code == 1
    assert captured == [True]


def test_review_shortcut_allows_reports_warnings_when_explicit(monkeypatch):
    captured: list[bool] = []

    def fake_handle_reports(args):
        captured.append(args.strict)
        return 0

    monkeypatch.setattr(paper, "handle_reports", fake_handle_reports)
    monkeypatch.setattr(paper, "handle_review_template", lambda args: 0)
    monkeypatch.setattr(paper, "handle_review_validate", lambda args: 0)
    exit_code = paper.main(["review", "--allow-warnings"])
    assert exit_code == 0
    assert captured == [False]


def test_preflight_subcommand_calls_paper_preflight(monkeypatch):
    calls: list[tuple[str, str | None, bool]] = []

    def fake_run_preflight_check(stage: str, date_str: str | None, strict: bool) -> dict:
        calls.append((stage, date_str, strict))
        return {
            "stage": stage,
            "date": date_str or "",
            "strict": strict,
            "result": "PASS",
            "error_count": 0,
            "warning_count": 0,
            "issues": [],
        }

    monkeypatch.setattr(paper, "run_paper_preflight_check", fake_run_preflight_check)
    exit_code = paper.main(["preflight", "--date", "20260513", "--stage", "plan"])
    assert exit_code == 0
    assert calls == [("plan", "20260513", False)]


def test_plan_subcommand_runs_preflight_first(monkeypatch):
    order: list[str] = []

    def fake_run_preflight_check(stage: str, date_str: str | None, strict: bool) -> dict:
        order.append("preflight")
        return {
            "stage": stage,
            "date": date_str or "",
            "strict": strict,
            "result": "PASS",
            "error_count": 0,
            "warning_count": 0,
            "issues": [],
        }

    def fake_run_paper_daily_plan(date_str: str) -> str:
        order.append("plan")
        return f"outputs/paper_test/daily_action_plan_{date_str}.md"

    monkeypatch.setattr(paper, "run_paper_preflight_check", fake_run_preflight_check)
    monkeypatch.setattr(paper, "run_paper_daily_plan", fake_run_paper_daily_plan)
    exit_code = paper.main(["plan", "--date", "20260513"])
    assert exit_code == 0
    assert order == ["preflight", "plan"]


def test_plan_aborts_when_preflight_fails(monkeypatch):
    called = {"plan": False}

    def fake_run_preflight_check(stage: str, date_str: str | None, strict: bool) -> dict:
        return {
            "stage": stage,
            "date": date_str or "",
            "strict": strict,
            "result": "FAIL",
            "error_count": 1,
            "warning_count": 0,
            "issues": [{"severity": "error", "stage": stage, "check_name": "x", "message": "x"}],
        }

    def fake_run_paper_daily_plan(date_str: str) -> str:
        called["plan"] = True
        return ""

    monkeypatch.setattr(paper, "run_paper_preflight_check", fake_run_preflight_check)
    monkeypatch.setattr(paper, "run_paper_daily_plan", fake_run_paper_daily_plan)
    exit_code = paper.main(["plan", "--date", "20260513"])
    assert exit_code == 1
    assert called["plan"] is False


def test_plan_calls_existing_wrapper_on_pass(monkeypatch):
    called: list[str] = []

    def fake_run_preflight_check(stage: str, date_str: str | None, strict: bool) -> dict:
        return {
            "stage": stage,
            "date": date_str or "",
            "strict": strict,
            "result": "PASS_WITH_WARNINGS",
            "error_count": 0,
            "warning_count": 1,
            "issues": [{"severity": "warning", "stage": stage, "check_name": "x", "message": "x"}],
        }

    def fake_run_paper_daily_plan(date_str: str) -> str:
        called.append(date_str)
        return "outputs/paper_test/daily_action_plan_20260513.md"

    monkeypatch.setattr(paper, "run_paper_preflight_check", fake_run_preflight_check)
    monkeypatch.setattr(paper, "run_paper_daily_plan", fake_run_paper_daily_plan)
    exit_code = paper.main(["plan", "--date", "20260513"])
    assert exit_code == 0
    assert called == ["20260513"]


def test_eod_dry_run_runs_preflight_first(monkeypatch):
    order: list[str] = []

    def fake_run_preflight_check(stage: str, date_str: str | None, strict: bool) -> dict:
        order.append("preflight")
        return {
            "stage": stage,
            "date": date_str or "",
            "strict": strict,
            "result": "PASS",
            "error_count": 0,
            "warning_count": 0,
            "issues": [],
        }

    def fake_run_paper_eod_dry_run(date_str: str, allow_empty_journal: bool, commit: bool, plan_path: str | None) -> int:
        order.append("eod")
        assert date_str == "20260513"
        assert allow_empty_journal is True
        assert commit is False
        assert plan_path is None
        return 0

    monkeypatch.setattr(paper, "run_paper_preflight_check", fake_run_preflight_check)
    monkeypatch.setattr(paper, "run_paper_eod_dry_run", fake_run_paper_eod_dry_run)
    exit_code = paper.main(["eod", "--date", "20260513", "--dry-run"])
    assert exit_code == 0
    assert order == ["preflight", "eod"]


def test_eod_dry_run_calls_existing_wrapper(monkeypatch):
    captured: dict[str, object] = {}

    def fake_run_preflight_check(stage: str, date_str: str | None, strict: bool) -> dict:
        return {
            "stage": stage,
            "date": date_str or "",
            "strict": strict,
            "result": "PASS",
            "error_count": 0,
            "warning_count": 0,
            "issues": [],
        }

    def fake_run_paper_eod_dry_run(date_str: str, allow_empty_journal: bool, commit: bool, plan_path: str | None) -> int:
        captured.update(
            {
                "date_str": date_str,
                "allow_empty_journal": allow_empty_journal,
                "commit": commit,
                "plan_path": plan_path,
            }
        )
        return 0

    monkeypatch.setattr(paper, "run_paper_preflight_check", fake_run_preflight_check)
    monkeypatch.setattr(paper, "run_paper_eod_dry_run", fake_run_paper_eod_dry_run)
    exit_code = paper.main(["eod", "--date", "20260513", "--dry-run"])
    assert exit_code == 0
    assert captured == {
        "date_str": "20260513",
        "allow_empty_journal": True,
        "commit": False,
        "plan_path": None,
    }


def test_eod_commit_runs_only_when_explicit(monkeypatch):
    captured: list[bool] = []

    def fake_run_preflight_check(stage: str, date_str: str | None, strict: bool) -> dict:
        return {
            "stage": stage,
            "date": date_str or "",
            "strict": strict,
            "result": "PASS",
            "error_count": 0,
            "warning_count": 0,
            "issues": [],
        }

    def fake_run_paper_eod_dry_run(date_str: str, allow_empty_journal: bool, commit: bool, plan_path: str | None) -> int:
        captured.append(commit)
        return 0

    monkeypatch.setattr(paper, "run_paper_preflight_check", fake_run_preflight_check)
    monkeypatch.setattr(paper, "run_paper_eod_dry_run", fake_run_paper_eod_dry_run)
    exit_code = paper.main(["eod", "--date", "20260513", "--commit"])
    assert exit_code == 0
    assert captured == [True]


def test_eod_requires_one_mode():
    with pytest.raises(SystemExit) as exc_info:
        paper.main(["eod", "--date", "20260513"])
    assert exc_info.value.code == 2


def test_eod_rejects_both_modes():
    with pytest.raises(SystemExit) as exc_info:
        paper.main(["eod", "--date", "20260513", "--dry-run", "--commit"])
    assert exc_info.value.code == 2


def test_missing_future_commands_from_help(capsys):
    paper.main([])
    output = capsys.readouterr().out
    assert "{prepare-data,prepare,data-freshness,status,init-account,weekly-status,benchmark,preview,commit,preflight,plan,eod,reports,review,review-template,review-validate,review-append}" in output
    assert "run-all" not in output
    assert "prepare-data" in output
    assert "data-freshness" in output
    assert "review-append" in output


def test_script_does_not_directly_call_generate_daily_plan():
    script_text = Path("scripts/paper.py").read_text(encoding="utf-8")
    assert "from core.daily_plan_generator import generate_daily_plan" not in script_text


def test_prepare_data_does_not_call_eod_commit(monkeypatch):
    called = {"eod": False}

    def fake_run_paper_prepare_data(
        date_str: str,
        *,
        skip_prices: bool,
        skip_indicators: bool,
        include_universe: bool,
    ) -> dict:
        return {
            "date": "2026-05-13",
            "ticker_count": 10,
            "market_db_path": "outputs/market_data.db",
            "price_update_status": "success",
            "indicators_update_status": "success",
            "universe_update_status": "skipped",
            "universe_snapshot_path": None,
            "warnings": [],
            "errors": [],
        }

    def fake_run_paper_eod_dry_run(*args, **kwargs):
        called["eod"] = True
        return 0

    monkeypatch.setattr(paper, "run_paper_prepare_data", fake_run_paper_prepare_data)
    monkeypatch.setattr(paper, "run_paper_eod_dry_run", fake_run_paper_eod_dry_run)
    exit_code = paper.main(["prepare-data", "--date", "20260513"])
    assert exit_code == 0
    assert called["eod"] is False


def test_reports_runs_preflight_first(monkeypatch):
    order: list[str] = []

    def fake_run_preflight_check(stage: str, date_str: str | None, strict: bool) -> dict:
        order.append("preflight")
        return {
            "stage": stage,
            "date": date_str or "",
            "strict": strict,
            "result": "PASS",
            "error_count": 0,
            "warning_count": 0,
            "issues": [],
        }

    def fake_run_report_chain() -> list[dict[str, object]]:
        order.append("reports")
        return [{"step_name": "equity_curve", "status": "success", "exit_code": 0, "message": "ok"}]

    monkeypatch.setattr(paper, "run_paper_preflight_check", fake_run_preflight_check)
    monkeypatch.setattr(paper, "run_report_chain", fake_run_report_chain)
    exit_code = paper.main(["reports"])
    assert exit_code == 0
    assert order == ["preflight", "reports"]


def test_reports_aborts_when_preflight_fails(monkeypatch):
    called = {"reports": False}

    def fake_run_preflight_check(stage: str, date_str: str | None, strict: bool) -> dict:
        return {
            "stage": stage,
            "date": date_str or "",
            "strict": strict,
            "result": "FAIL",
            "error_count": 1,
            "warning_count": 0,
            "issues": [{"severity": "error", "stage": stage, "check_name": "x", "message": "x"}],
        }

    def fake_run_report_chain() -> list[dict[str, object]]:
        called["reports"] = True
        return []

    monkeypatch.setattr(paper, "run_paper_preflight_check", fake_run_preflight_check)
    monkeypatch.setattr(paper, "run_report_chain", fake_run_report_chain)
    exit_code = paper.main(["reports"])
    assert exit_code == 1
    assert called["reports"] is False


def test_reports_runs_on_pass_with_warnings_in_non_strict(monkeypatch):
    called = {"reports": False}

    def fake_run_preflight_check(stage: str, date_str: str | None, strict: bool) -> dict:
        return {
            "stage": stage,
            "date": date_str or "",
            "strict": strict,
            "result": "PASS_WITH_WARNINGS",
            "error_count": 0,
            "warning_count": 1,
            "issues": [{"severity": "warning", "stage": stage, "check_name": "x", "message": "x"}],
        }

    def fake_run_report_chain() -> list[dict[str, object]]:
        called["reports"] = True
        return [{"step_name": "equity_curve", "status": "success", "exit_code": 0, "message": "ok"}]

    monkeypatch.setattr(paper, "run_paper_preflight_check", fake_run_preflight_check)
    monkeypatch.setattr(paper, "run_report_chain", fake_run_report_chain)
    exit_code = paper.main(["reports"])
    assert exit_code == 0
    assert called["reports"] is True


def test_reports_strict_blocks_on_warnings(monkeypatch):
    called = {"reports": False}

    def fake_run_preflight_check(stage: str, date_str: str | None, strict: bool) -> dict:
        return {
            "stage": stage,
            "date": date_str or "",
            "strict": strict,
            "result": "FAIL" if strict else "PASS_WITH_WARNINGS",
            "error_count": 1 if strict else 0,
            "warning_count": 0 if strict else 1,
            "issues": [{"severity": "error" if strict else "warning", "stage": stage, "check_name": "x", "message": "x"}],
        }

    def fake_run_report_chain() -> list[dict[str, object]]:
        called["reports"] = True
        return []

    monkeypatch.setattr(paper, "run_paper_preflight_check", fake_run_preflight_check)
    monkeypatch.setattr(paper, "run_report_chain", fake_run_report_chain)
    exit_code = paper.main(["reports", "--strict"])
    assert exit_code == 1
    assert called["reports"] is False


def test_report_step_failure_stops_chain(monkeypatch):
    def fake_run_preflight_check(stage: str, date_str: str | None, strict: bool) -> dict:
        return {
            "stage": stage,
            "date": date_str or "",
            "strict": strict,
            "result": "PASS",
            "error_count": 0,
            "warning_count": 0,
            "issues": [],
        }

    monkeypatch.setattr(paper, "run_paper_preflight_check", fake_run_preflight_check)
    monkeypatch.setattr(
        paper,
        "run_report_chain",
        lambda: [
            {"step_name": "equity_curve", "status": "success", "exit_code": 0, "message": "ok"},
            {"step_name": "drawdown", "status": "failed", "exit_code": 1, "message": "boom"},
        ],
    )
    exit_code = paper.main(["reports"])
    assert exit_code == 1


def test_report_steps_run_in_defined_order():
    step_names = [step_name for step_name, _ in paper.REPORT_STEPS]
    assert step_names == [
        "equity_curve",
        "drawdown",
        "performance_summary",
        "realized_trade_journal",
        "symbol_realized_performance",
        "realized_ranking_report",
        "symbol_unrealized_performance",
        "symbol_side_by_side_performance",
        "symbol_review_buckets",
        "symbol_review_worksheet",
        "daily_review_summary",
    ]


def test_reports_does_not_call_eod_commit(monkeypatch):
    called = {"eod": False}

    def fake_run_preflight_check(stage: str, date_str: str | None, strict: bool) -> dict:
        return {
            "stage": stage,
            "date": date_str or "",
            "strict": strict,
            "result": "PASS",
            "error_count": 0,
            "warning_count": 0,
            "issues": [],
        }

    def fake_run_report_chain() -> list[dict[str, object]]:
        return [{"step_name": "equity_curve", "status": "success", "exit_code": 0, "message": "ok"}]

    def fake_run_paper_eod_dry_run(*args, **kwargs):
        called["eod"] = True
        return 0

    monkeypatch.setattr(paper, "run_paper_preflight_check", fake_run_preflight_check)
    monkeypatch.setattr(paper, "run_report_chain", fake_run_report_chain)
    monkeypatch.setattr(paper, "run_paper_eod_dry_run", fake_run_paper_eod_dry_run)
    exit_code = paper.main(["reports"])
    assert exit_code == 0
    assert called["eod"] is False


def test_reports_does_not_call_review_append(monkeypatch):
    called = {"append": False}

    def fake_run_preflight_check(stage: str, date_str: str | None, strict: bool) -> dict:
        return {
            "stage": stage,
            "date": date_str or "",
            "strict": strict,
            "result": "PASS",
            "error_count": 0,
            "warning_count": 0,
            "issues": [],
        }

    def fake_run_report_chain() -> list[dict[str, object]]:
        return [{"step_name": "equity_curve", "status": "success", "exit_code": 0, "message": "ok"}]

    def fake_append() -> dict:
        called["append"] = True
        return {}

    monkeypatch.setattr(paper, "run_paper_preflight_check", fake_run_preflight_check)
    monkeypatch.setattr(paper, "run_report_chain", fake_run_report_chain)
    monkeypatch.setattr(paper, "append_paper_manual_review_log_from_template", fake_append)
    exit_code = paper.main(["reports"])
    assert exit_code == 0
    assert called["append"] is False


def test_review_template_runs_preflight_first(monkeypatch):
    order: list[str] = []

    def fake_run_preflight_check(stage: str, date_str: str | None, strict: bool) -> dict:
        order.append("preflight")
        return {
            "stage": stage,
            "date": date_str or "",
            "strict": strict,
            "result": "PASS",
            "error_count": 0,
            "warning_count": 0,
            "issues": [],
        }

    def fake_generate_template(**kwargs) -> dict:
        order.append("template")
        return {
            "csv_output_path": "outputs/paper_test/reviews/paper_manual_review_log_template.csv",
            "markdown_output_path": "outputs/paper_test/reviews/paper_manual_review_log_template.md",
            "summary": {"review_template_row_count": 28},
        }

    monkeypatch.setattr(paper, "run_paper_preflight_check", fake_run_preflight_check)
    monkeypatch.setattr(paper, "generate_paper_manual_review_log_template", fake_generate_template)
    exit_code = paper.main(["review-template"])
    assert exit_code == 0
    assert order == ["preflight", "template"]


def test_review_template_aborts_when_preflight_fails(monkeypatch):
    called = {"template": False}

    def fake_run_preflight_check(stage: str, date_str: str | None, strict: bool) -> dict:
        return {
            "stage": stage,
            "date": date_str or "",
            "strict": strict,
            "result": "FAIL",
            "error_count": 1,
            "warning_count": 0,
            "issues": [{"severity": "error", "stage": stage, "check_name": "x", "message": "x"}],
        }

    def fake_generate_template(**kwargs) -> dict:
        called["template"] = True
        return {}

    monkeypatch.setattr(paper, "run_paper_preflight_check", fake_run_preflight_check)
    monkeypatch.setattr(paper, "generate_paper_manual_review_log_template", fake_generate_template)
    exit_code = paper.main(["review-template"])
    assert exit_code == 1
    assert called["template"] is False


def test_review_template_calls_existing_generator_on_pass(monkeypatch):
    called = {"template": False}

    def fake_run_preflight_check(stage: str, date_str: str | None, strict: bool) -> dict:
        return {
            "stage": stage,
            "date": date_str or "",
            "strict": strict,
            "result": "PASS_WITH_WARNINGS",
            "error_count": 0,
            "warning_count": 1,
            "issues": [{"severity": "warning", "stage": stage, "check_name": "x", "message": "x"}],
        }

    def fake_generate_template(**kwargs) -> dict:
        called["template"] = True
        return {
            "csv_output_path": "outputs/paper_test/reviews/paper_manual_review_log_template.csv",
            "markdown_output_path": "outputs/paper_test/reviews/paper_manual_review_log_template.md",
            "summary": {"review_template_row_count": 28},
        }

    monkeypatch.setattr(paper, "run_paper_preflight_check", fake_run_preflight_check)
    monkeypatch.setattr(paper, "generate_paper_manual_review_log_template", fake_generate_template)
    exit_code = paper.main(["review-template"])
    assert exit_code == 0
    assert called["template"] is True


def test_review_validate_calls_existing_validator(monkeypatch):
    called = {"validate": False}

    def fake_validate() -> dict:
        called["validate"] = True
        return {
            "input_path": "in.csv",
            "report_output_path": "report.md",
            "issues_output_path": "issues.csv",
            "summary": {
                "validation_result": "PASS",
                "error_count": 0,
                "warning_count": 1,
            },
        }

    monkeypatch.setattr(paper, "validate_paper_manual_review_log", fake_validate)
    exit_code = paper.main(["review-validate"])
    assert exit_code == 0
    assert called["validate"] is True


def test_review_validate_returns_one_on_errors(monkeypatch):
    def fake_validate() -> dict:
        return {
            "input_path": "in.csv",
            "report_output_path": "report.md",
            "issues_output_path": "issues.csv",
            "summary": {
                "validation_result": "FAIL",
                "error_count": 2,
                "warning_count": 0,
            },
        }

    monkeypatch.setattr(paper, "validate_paper_manual_review_log", fake_validate)
    exit_code = paper.main(["review-validate"])
    assert exit_code == 1


def test_review_append_runs_preflight_first(monkeypatch):
    order: list[str] = []

    def fake_run_preflight_check(stage: str, date_str: str | None, strict: bool) -> dict:
        order.append("preflight")
        return {
            "stage": stage,
            "date": date_str or "",
            "strict": strict,
            "result": "PASS",
            "error_count": 0,
            "warning_count": 0,
            "issues": [],
        }

    def fake_append() -> dict:
        order.append("append")
        return {
            "target_log_path": "log.csv",
            "append_report_path": "append_report.md",
            "append_issues_path": "append_issues.csv",
            "summary": {
                "validation_result": "PASS",
                "rows_appended": 1,
                "rows_skipped_pending": 0,
                "rows_skipped_duplicate": 0,
            },
        }

    monkeypatch.setattr(paper, "run_paper_preflight_check", fake_run_preflight_check)
    monkeypatch.setattr(paper, "append_paper_manual_review_log_from_template", fake_append)
    exit_code = paper.main(["review-append"])
    assert exit_code == 0
    assert order == ["preflight", "append"]


def test_review_append_aborts_when_preflight_fails(monkeypatch):
    called = {"append": False}

    def fake_run_preflight_check(stage: str, date_str: str | None, strict: bool) -> dict:
        return {
            "stage": stage,
            "date": date_str or "",
            "strict": strict,
            "result": "FAIL",
            "error_count": 1,
            "warning_count": 0,
            "issues": [{"severity": "error", "stage": stage, "check_name": "x", "message": "x"}],
        }

    def fake_append() -> dict:
        called["append"] = True
        return {}

    monkeypatch.setattr(paper, "run_paper_preflight_check", fake_run_preflight_check)
    monkeypatch.setattr(paper, "append_paper_manual_review_log_from_template", fake_append)
    exit_code = paper.main(["review-append"])
    assert exit_code == 1
    assert called["append"] is False


def test_review_append_calls_existing_append_on_pass(monkeypatch):
    called = {"append": False}

    def fake_run_preflight_check(stage: str, date_str: str | None, strict: bool) -> dict:
        return {
            "stage": stage,
            "date": date_str or "",
            "strict": strict,
            "result": "PASS_WITH_WARNINGS",
            "error_count": 0,
            "warning_count": 1,
            "issues": [{"severity": "warning", "stage": stage, "check_name": "x", "message": "x"}],
        }

    def fake_append() -> dict:
        called["append"] = True
        return {
            "target_log_path": "log.csv",
            "append_report_path": "append_report.md",
            "append_issues_path": "append_issues.csv",
            "summary": {
                "validation_result": "PASS",
                "rows_appended": 1,
                "rows_skipped_pending": 0,
                "rows_skipped_duplicate": 0,
            },
        }

    monkeypatch.setattr(paper, "run_paper_preflight_check", fake_run_preflight_check)
    monkeypatch.setattr(paper, "append_paper_manual_review_log_from_template", fake_append)
    exit_code = paper.main(["review-append"])
    assert exit_code == 0
    assert called["append"] is True


def test_review_append_does_not_implement_overwrite():
    script_text = Path("scripts/paper.py").read_text(encoding="utf-8")
    assert 'review_append_parser.add_argument("--overwrite"' not in script_text


def test_review_shortcut_exists_in_help(capsys):
    paper.main([])
    output = capsys.readouterr().out
    assert "\n    review " in output or "\n    review\n" in output
