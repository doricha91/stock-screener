from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from datetime import date
from pathlib import Path

from scripts import n8n_paper_ops_runner as runner


def test_runner_script_can_be_invoked_directly() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts\\n8n_paper_ops_runner.py", "--help"],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )

    assert completed.returncode == 0
    assert "daily_refresh" in completed.stdout


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


def _fake_status_stdout() -> str:
    return json.dumps(
        {
            "overall_status": "PASS",
            "workflow_status": "FINAL_STATUS",
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
    )


def _fake_eod_stdout(append_execution_log: str = "false") -> str:
    return "\n".join(
        [
            "EOD roll-forward intent:",
            "  eod_mode: accounting_close",
            "  execution_candidate_count: 0",
            "  execution_log_rows_for_date: 0",
            "  ready_preview_count: 0",
            "  no_action_day: true",
            f"  would_append_execution_log: {append_execution_log}",
            "  would_write_current_state: true",
            "  would_write_account_snapshot: true",
            "  would_write_position_snapshot: true",
            "  source_snapshot_date: 2026-06-12",
            "  target_snapshot_date: 2026-06-15",
        ]
    )


def test_daily_refresh_pass_writes_all_latest_files(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "market.db"
    workspace = tmp_path / "workspace"
    _create_market_db(
        db_path,
        daily_price_dates=["2026-06-12"],
        spy_dates=["2026-06-12"],
        indicator_dates=["2026-06-12"],
    )
    calls: list[list[str]] = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        if "scripts\\paper_daily_ops.py" in argv:
            return subprocess.CompletedProcess(argv, 0, stdout=_fake_status_stdout(), stderr="")
        if "scripts\\paper.py" in argv:
            return subprocess.CompletedProcess(argv, 0, stdout=_fake_eod_stdout(), stderr="")
        raise AssertionError(f"unexpected argv: {argv}")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    exit_code = runner.main(
        [
            "daily_refresh",
            "--workspace",
            str(workspace),
            "--account-id",
            "paper_ops",
            "--db-path",
            str(db_path),
            "--as-of-date",
            "2026-06-13",
        ]
    )

    assert exit_code == 0
    assert [call[1] for call in calls] == ["scripts\\paper_daily_ops.py", "scripts\\paper.py"]
    assert json.loads((workspace / "context.json").read_text(encoding="utf-8")) == {
        "account_id": "paper_ops",
        "data_date": "2026-06-12",
        "trade_date": "2026-06-15",
    }
    payload = json.loads((workspace / "daily_refresh_latest.json").read_text(encoding="utf-8"))
    assert payload["runner_result"] == "PASS"
    assert payload["stages"]["resolve_dates"]["result"] == "PASS"
    assert payload["stages"]["context"]["result"] == "PASS"
    assert payload["stages"]["status"]["result"] == "PASS"
    assert payload["stages"]["eod_dryrun"]["result"] == "PASS"
    text = (workspace / "daily_refresh_latest.txt").read_text(encoding="utf-8")
    assert "Daily Runner Refresh" in text
    assert "runner_result: PASS" in text
    assert "context_result: PASS" in text
    assert (workspace / "status_latest.txt").exists()
    assert (workspace / "eod_dryrun_latest.txt").exists()


def test_daily_refresh_date_resolution_fail_does_not_overwrite_existing_latest_files(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    for name in ["context_latest.txt", "status_latest.txt", "eod_dryrun_latest.txt"]:
        (workspace / name).write_text(f"old {name}", encoding="utf-8")

    def fail_run(*args, **kwargs):
        raise AssertionError("downstream command must not run")

    monkeypatch.setattr(runner.subprocess, "run", fail_run)

    exit_code = runner.main(
        [
            "daily_refresh",
            "--workspace",
            str(workspace),
            "--account-id",
            "paper_ops",
            "--db-path",
            str(tmp_path / "missing.db"),
            "--as-of-date",
            "2026-06-13",
        ]
    )

    assert exit_code == 1
    for name in ["context_latest.txt", "status_latest.txt", "eod_dryrun_latest.txt"]:
        assert (workspace / name).read_text(encoding="utf-8") == f"old {name}"
    payload = json.loads((workspace / "daily_refresh_latest.json").read_text(encoding="utf-8"))
    assert payload["runner_result"] == "FAIL"
    assert payload["failed_stage"] == "resolve_dates"
    assert payload["stages"]["resolve_dates"]["result"] == "FAIL"


def test_daily_refresh_warning_runs_subcommands_and_preserves_warning(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "market.db"
    workspace = tmp_path / "workspace"
    _create_market_db(
        db_path,
        daily_price_dates=["2026-06-16"],
        spy_dates=["2026-06-16"],
        indicator_dates=["2026-06-15"],
    )

    def fake_run(argv, **kwargs):
        if "scripts\\paper_daily_ops.py" in argv:
            return subprocess.CompletedProcess(argv, 0, stdout=_fake_status_stdout(), stderr="")
        if "scripts\\paper.py" in argv:
            return subprocess.CompletedProcess(argv, 0, stdout=_fake_eod_stdout(), stderr="")
        raise AssertionError(f"unexpected argv: {argv}")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    exit_code = runner.main(
        [
            "daily_refresh",
            "--workspace",
            str(workspace),
            "--account-id",
            "paper_ops",
            "--db-path",
            str(db_path),
            "--as-of-date",
            "2026-06-16",
        ]
    )

    assert exit_code == 0
    payload = json.loads((workspace / "daily_refresh_latest.json").read_text(encoding="utf-8"))
    assert payload["runner_result"] == "WARNING"
    assert payload["data_date"] == "2026-06-15"
    assert payload["stages"]["eod_dryrun"]["result"] == "PASS"
    assert "not aligned" in payload["date_reason"]


def test_daily_refresh_status_failure_skips_eod_dryrun(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "market.db"
    workspace = tmp_path / "workspace"
    _create_market_db(
        db_path,
        daily_price_dates=["2026-06-12"],
        spy_dates=["2026-06-12"],
        indicator_dates=["2026-06-12"],
    )
    calls: list[list[str]] = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        if "scripts\\paper_daily_ops.py" in argv:
            return subprocess.CompletedProcess(argv, 1, stdout=_fake_status_stdout(), stderr="status failed")
        if "scripts\\paper.py" in argv:
            raise AssertionError("eod_dryrun must not run after status failure")
        raise AssertionError(f"unexpected argv: {argv}")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    exit_code = runner.main(
        [
            "daily_refresh",
            "--workspace",
            str(workspace),
            "--account-id",
            "paper_ops",
            "--db-path",
            str(db_path),
            "--as-of-date",
            "2026-06-13",
        ]
    )

    assert exit_code == 1
    assert [call[1] for call in calls] == ["scripts\\paper_daily_ops.py"]
    payload = json.loads((workspace / "daily_refresh_latest.json").read_text(encoding="utf-8"))
    assert payload["runner_result"] == "FAIL"
    assert payload["failed_stage"] == "status"
    assert payload["stages"]["status"]["result"] == "FAIL"
    assert "eod_dryrun" not in payload["stages"]


def test_daily_refresh_eod_failure_marks_final_fail(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "market.db"
    workspace = tmp_path / "workspace"
    _create_market_db(
        db_path,
        daily_price_dates=["2026-06-12"],
        spy_dates=["2026-06-12"],
        indicator_dates=["2026-06-12"],
    )

    def fake_run(argv, **kwargs):
        if "scripts\\paper_daily_ops.py" in argv:
            return subprocess.CompletedProcess(argv, 0, stdout=_fake_status_stdout(), stderr="")
        if "scripts\\paper.py" in argv:
            return subprocess.CompletedProcess(argv, 0, stdout=_fake_eod_stdout(append_execution_log="true"), stderr="")
        raise AssertionError(f"unexpected argv: {argv}")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    exit_code = runner.main(
        [
            "daily_refresh",
            "--workspace",
            str(workspace),
            "--account-id",
            "paper_ops",
            "--db-path",
            str(db_path),
            "--as-of-date",
            "2026-06-13",
        ]
    )

    assert exit_code == 1
    payload = json.loads((workspace / "daily_refresh_latest.json").read_text(encoding="utf-8"))
    assert payload["runner_result"] == "FAIL"
    assert payload["failed_stage"] == "eod_dryrun"
    assert payload["stages"]["context"]["result"] == "PASS"
    assert payload["stages"]["status"]["result"] == "PASS"
    assert payload["stages"]["eod_dryrun"]["result"] == "FAIL"
