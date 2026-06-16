from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from datetime import date
from pathlib import Path

from scripts import n8n_paper_ops_runner as runner


def _write_context(workspace: Path) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "context.json").write_text(
        json.dumps(
            {
                "account_id": "paper_ops",
                "data_date": "2026-06-12",
                "trade_date": "2026-06-15",
            }
        ),
        encoding="utf-8",
    )


def test_context_command_writes_context_json_and_telegram_text(tmp_path: Path) -> None:
    exit_code = runner.main(
        [
            "context",
            "--workspace",
            str(tmp_path),
            "--account-id",
            "paper_ops",
            "--data-date",
            "20260612",
            "--trade-date",
            "2026-06-15",
        ]
    )

    assert exit_code == 0
    assert json.loads((tmp_path / "context.json").read_text(encoding="utf-8")) == {
        "account_id": "paper_ops",
        "data_date": "2026-06-12",
        "trade_date": "2026-06-15",
    }
    text = (tmp_path / "context_latest.txt").read_text(encoding="utf-8")
    assert "runner_result: PASS" in text
    assert "account_id: paper_ops" in text


def test_status_runs_only_allowlisted_python_argv_and_writes_summary(tmp_path: Path, monkeypatch) -> None:
    _write_context(tmp_path)
    captured: dict[str, object] = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=json.dumps(
                {
                    "overall_status": "PASS",
                    "workflow_status": "REVIEW_DONE",
                    "operator_summary": {
                        "current_step": "FINAL_STATUS",
                        "current_step_status": "DONE",
                        "recommended_operator_action": "NONE",
                        "risk_level": "SAFE",
                        "requires_manual_approval": False,
                        "terminal": True,
                        "next_command": None,
                        "warnings": [],
                        "blockers": [],
                    },
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    exit_code = runner.main(["status", "--workspace", str(tmp_path)])

    assert exit_code == 0
    assert captured["argv"] == [
        sys.executable,
        "scripts\\paper_daily_ops.py",
        "status",
        "--account-id",
        "paper_ops",
        "--data-date",
        "2026-06-12",
        "--trade-date",
        "2026-06-15",
        "--json",
        "--include-notion-read",
    ]
    assert captured["kwargs"]["shell"] is False
    assert (tmp_path / "status_latest.json").exists()
    text = (tmp_path / "status_latest.txt").read_text(encoding="utf-8")
    assert "Paper Daily Ops Status" in text
    assert "current_step: FINAL_STATUS" in text


def test_eod_dryrun_pass_requires_accounting_close_write_intent(tmp_path: Path, monkeypatch) -> None:
    _write_context(tmp_path)
    stdout = "\n".join(
        [
            "EOD roll-forward intent:",
            "  eod_mode: accounting_close",
            "  execution_candidate_count: 0",
            "  execution_log_rows_for_date: 0",
            "  ready_preview_count: 0",
            "  no_action_day: true",
            "  would_append_execution_log: false",
            "  would_write_current_state: true",
            "  would_write_account_snapshot: true",
            "  would_write_position_snapshot: true",
            "  source_snapshot_date: 2026-06-14",
            "  target_snapshot_date: 2026-06-15",
        ]
    )

    def fake_run(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    exit_code = runner.main(["eod_dryrun", "--workspace", str(tmp_path)])

    assert exit_code == 0
    assert (tmp_path / "eod_dryrun_latest.raw.txt").read_text(encoding="utf-8") == stdout
    text = (tmp_path / "eod_dryrun_latest.txt").read_text(encoding="utf-8")
    assert "runner_result: PASS" in text
    assert "would_write_position_snapshot: true" in text


def test_eod_dryrun_failure_still_writes_telegram_error_text(tmp_path: Path, monkeypatch) -> None:
    _write_context(tmp_path)

    def fake_run(argv, **kwargs):
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout="\n".join(
                [
                    "  eod_mode: accounting_close",
                    "  would_append_execution_log: true",
                    "  would_write_current_state: true",
                    "  would_write_account_snapshot: true",
                    "  would_write_position_snapshot: true",
                ]
            ),
            stderr="",
        )

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    exit_code = runner.main(["eod_dryrun", "--workspace", str(tmp_path)])

    assert exit_code == 1
    text = (tmp_path / "eod_dryrun_latest.txt").read_text(encoding="utf-8")
    assert "runner_result: FAIL" in text
    assert "would_append_execution_log expected false, got true" in text


def test_missing_context_writes_status_error_text(tmp_path: Path) -> None:
    exit_code = runner.main(["status", "--workspace", str(tmp_path)])

    assert exit_code == 1
    text = (tmp_path / "status_latest.txt").read_text(encoding="utf-8")
    assert "Paper Ops Runner Error" in text
    assert "command_key: status" in text
    assert "context file not found" in text


def _create_market_db(
    path: Path,
    *,
    daily_price_dates: list[str] | None = None,
    spy_dates: list[str] | None = None,
    indicator_dates: list[str] | None = None,
) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE daily_price (symbol TEXT, date TEXT)")
        conn.execute("CREATE TABLE market_index (symbol TEXT, date TEXT)")
        conn.execute("CREATE TABLE daily_indicators (symbol TEXT, date TEXT)")
        for item_date in daily_price_dates or []:
            conn.execute("INSERT INTO daily_price (symbol, date) VALUES (?, ?)", ("AAPL", item_date))
        for item_date in spy_dates or []:
            conn.execute("INSERT INTO market_index (symbol, date) VALUES (?, ?)", ("SPY", item_date))
        for item_date in indicator_dates or []:
            conn.execute("INSERT INTO daily_indicators (symbol, date) VALUES (?, ?)", ("AAPL", item_date))


def test_resolve_daily_refresh_dates_pass_when_sources_aligned(tmp_path: Path) -> None:
    db_path = tmp_path / "market.db"
    _create_market_db(
        db_path,
        daily_price_dates=["2026-06-12"],
        spy_dates=["2026-06-12"],
        indicator_dates=["2026-06-12"],
    )

    result = runner.resolve_daily_refresh_dates(
        account_id="paper_ops",
        db_path=db_path,
        as_of_date=date(2026, 6, 13),
    )

    assert result.runner_result == "PASS"
    assert result.data_date == "2026-06-12"
    assert result.source_data_max_date == "2026-06-12"
    assert result.trade_date == "2026-06-15"
    assert result.stale is False


def test_resolve_daily_refresh_dates_uses_lagging_complete_date(tmp_path: Path) -> None:
    db_path = tmp_path / "market.db"
    _create_market_db(
        db_path,
        daily_price_dates=["2026-06-16"],
        spy_dates=["2026-06-16"],
        indicator_dates=["2026-06-15"],
    )

    result = runner.resolve_daily_refresh_dates(
        account_id="paper_ops",
        db_path=db_path,
        as_of_date="2026-06-16",
    )

    assert result.runner_result == "WARNING"
    assert result.data_date == "2026-06-15"
    assert result.trade_date == "2026-06-16"
    assert result.daily_price_max_date == "2026-06-16"
    assert result.daily_indicators_max_date == "2026-06-15"
    assert "not aligned" in result.reason


def test_resolve_daily_refresh_dates_fails_when_required_data_empty(tmp_path: Path) -> None:
    db_path = tmp_path / "market.db"
    _create_market_db(db_path, daily_price_dates=[], spy_dates=["2026-06-12"], indicator_dates=["2026-06-12"])

    result = runner.resolve_daily_refresh_dates(
        account_id="paper_ops",
        db_path=db_path,
        as_of_date="2026-06-13",
    )

    assert result.runner_result == "FAIL"
    assert result.data_date is None
    assert "daily_price has no date rows" in result.reason


def test_resolve_daily_refresh_dates_fails_without_spy_market_index(tmp_path: Path) -> None:
    db_path = tmp_path / "market.db"
    _create_market_db(
        db_path,
        daily_price_dates=["2026-06-12"],
        spy_dates=[],
        indicator_dates=["2026-06-12"],
    )
    with sqlite3.connect(db_path) as conn:
        conn.execute("INSERT INTO market_index (symbol, date) VALUES (?, ?)", ("QQQ", "2026-06-12"))

    result = runner.resolve_daily_refresh_dates(
        account_id="paper_ops",
        db_path=db_path,
        as_of_date="2026-06-13",
    )

    assert result.runner_result == "FAIL"
    assert "market_index has no date rows for SPY" in result.reason


def test_resolve_daily_refresh_dates_friday_trade_date_is_next_monday(tmp_path: Path) -> None:
    db_path = tmp_path / "market.db"
    _create_market_db(
        db_path,
        daily_price_dates=["2026-06-12"],
        spy_dates=["2026-06-12"],
        indicator_dates=["2026-06-12"],
    )

    result = runner.resolve_daily_refresh_dates(
        account_id="paper_ops",
        db_path=db_path,
        as_of_date="2026-06-12",
    )

    assert result.data_date == "2026-06-12"
    assert result.trade_date == "2026-06-15"


def test_resolve_daily_refresh_dates_marks_stale_as_warning(tmp_path: Path) -> None:
    db_path = tmp_path / "market.db"
    _create_market_db(
        db_path,
        daily_price_dates=["2026-06-01"],
        spy_dates=["2026-06-01"],
        indicator_dates=["2026-06-01"],
    )

    result = runner.resolve_daily_refresh_dates(
        account_id="paper_ops",
        db_path=db_path,
        as_of_date="2026-06-10",
        stale_threshold_days=3,
    )

    assert result.runner_result == "WARNING"
    assert result.stale is True
    assert result.stale_days == 9
    assert "stale" in result.reason


def test_resolve_daily_refresh_dates_fails_without_account_id(tmp_path: Path) -> None:
    db_path = tmp_path / "market.db"
    _create_market_db(
        db_path,
        daily_price_dates=["2026-06-12"],
        spy_dates=["2026-06-12"],
        indicator_dates=["2026-06-12"],
    )

    result = runner.resolve_daily_refresh_dates(
        account_id="",
        db_path=db_path,
        as_of_date="2026-06-13",
    )

    assert result.runner_result == "FAIL"
    assert result.reason == "account_id is required"


def test_resolve_daily_refresh_dates_does_not_write_runner_files(tmp_path: Path) -> None:
    db_path = tmp_path / "market.db"
    _create_market_db(
        db_path,
        daily_price_dates=["2026-06-12"],
        spy_dates=["2026-06-12"],
        indicator_dates=["2026-06-12"],
    )

    result = runner.resolve_daily_refresh_dates(
        account_id="paper_ops",
        db_path=db_path,
        as_of_date="2026-06-13",
    )

    assert result.runner_result == "PASS"
    assert not (tmp_path / "context.json").exists()
    assert not (tmp_path / "context_latest.txt").exists()
    assert not (tmp_path / "status_latest.txt").exists()
    assert not (tmp_path / "eod_dryrun_latest.txt").exists()
