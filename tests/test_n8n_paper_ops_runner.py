from __future__ import annotations

import json
import subprocess
import sys
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
