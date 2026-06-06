from __future__ import annotations

from pathlib import Path

import pytest

from scripts import paper


def test_commit_allows_non_default_account_and_passes_account_id(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        paper,
        "guard_paper_writer_account",
        lambda account_id=None, *, command_name, allow_non_default=False: {
            "account_id": "paper_growth",
            "account_root": str(Path("outputs/paper_accounts/paper_growth")),
            "legacy_default_used": False,
            "command_name": command_name,
            "write_allowed": allow_non_default,
            "message": "allowed",
        },
    )
    monkeypatch.setattr(paper, "format_writer_account_guard_message", lambda context: context["message"])
    monkeypatch.setattr(
        paper,
        "run_commit_shortcut",
        lambda date_str, replace, account_id=None: captured.update(
            {"date_str": date_str, "replace": replace, "account_id": account_id}
        )
        or 0,
    )

    exit_code = paper.main(["commit", "--date", "20260530", "--account-id", "paper_growth"])

    assert exit_code == 0
    assert captured == {
        "date_str": "20260530",
        "replace": False,
        "account_id": "paper_growth",
    }


def test_plan_builds_non_default_account_paths(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        paper,
        "guard_paper_writer_account",
        lambda account_id=None, *, command_name, allow_non_default=False: {
            "account_id": "paper_growth",
            "account_root": str(Path("outputs/paper_accounts/paper_growth")),
            "legacy_default_used": False,
            "command_name": command_name,
            "write_allowed": allow_non_default,
            "message": "allowed",
        },
    )
    monkeypatch.setattr(paper, "format_writer_account_guard_message", lambda context: context["message"])
    monkeypatch.setattr(
        paper,
        "run_preflight",
        lambda stage, date_str, strict, write_report: {"result": "PASS"},
    )
    account_paths = paper.build_paper_account_paths("paper_growth", account_root=Path("outputs/paper_accounts/paper_growth"))
    monkeypatch.setattr(paper, "build_paper_account_paths", lambda account_id, create=False: account_paths)

    def fake_run_paper_daily_plan(date_str, account_paths=None):
        captured["date_str"] = date_str
        captured["account_paths"] = account_paths
        return "x.md"

    monkeypatch.setattr(paper, "run_paper_daily_plan", fake_run_paper_daily_plan)

    exit_code = paper.main(["plan", "--date", "20260530", "--account-id", "paper_growth"])

    assert exit_code == 0
    assert captured["date_str"] == "20260530"
    assert captured["account_paths"] is account_paths


def test_plan_explicit_dates_pass_data_and_trade_dates(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        paper,
        "guard_paper_writer_account",
        lambda account_id=None, *, command_name, allow_non_default=False: {
            "account_id": "paper_growth",
            "account_root": str(Path("outputs/paper_accounts/paper_growth")),
            "legacy_default_used": False,
            "command_name": command_name,
            "write_allowed": allow_non_default,
            "message": "allowed",
        },
    )
    monkeypatch.setattr(paper, "format_writer_account_guard_message", lambda context: context["message"])
    monkeypatch.setattr(
        paper,
        "run_paper_data_freshness_check",
        lambda *, date_str, strict: {
            "target_date": date_str,
            "result": "PASS",
            "error_count": 0,
            "warning_count": 0,
        },
    )
    monkeypatch.setattr(
        paper,
        "run_preflight",
        lambda stage, date_str, strict, write_report: captured.update({"preflight_date": date_str})
        or {"result": "PASS"},
    )
    account_paths = paper.build_paper_account_paths("paper_growth", account_root=Path("outputs/paper_accounts/paper_growth"))
    monkeypatch.setattr(paper, "build_paper_account_paths", lambda account_id, create=False: account_paths)

    def fake_run_paper_daily_plan(date_str=None, account_paths=None, *, data_date=None, trade_date=None):
        captured.update(
            {
                "date_str": date_str,
                "account_paths": account_paths,
                "data_date": data_date,
                "trade_date": trade_date,
            }
        )
        return "x.md"

    monkeypatch.setattr(paper, "run_paper_daily_plan", fake_run_paper_daily_plan)

    exit_code = paper.main(
        [
            "plan",
            "--data-date",
            "2026-06-05",
            "--trade-date",
            "2026-06-08",
            "--account-id",
            "paper_growth",
        ]
    )

    assert exit_code == 0
    assert captured["preflight_date"] == "2026-06-08"
    assert captured["date_str"] is None
    assert captured["data_date"] == "2026-06-05"
    assert captured["trade_date"] == "2026-06-08"
    assert captured["account_paths"] is account_paths


def test_plan_explicit_dates_require_pair(monkeypatch):
    monkeypatch.setattr(paper, "_guard_writer_account", lambda *args, **kwargs: 0)

    exit_code = paper.main(["plan", "--data-date", "2026-06-05"])

    assert exit_code == 1


def test_plan_explicit_dates_block_freshness_warnings(monkeypatch):
    monkeypatch.setattr(paper, "_guard_writer_account", lambda *args, **kwargs: 0)
    monkeypatch.setattr(
        paper,
        "run_paper_data_freshness_check",
        lambda *, date_str, strict: {
            "target_date": date_str,
            "result": "PASS_WITH_WARNINGS",
            "error_count": 0,
            "warning_count": 1,
        },
    )

    exit_code = paper.main(
        ["plan", "--data-date", "2026-06-05", "--trade-date", "2026-06-08"]
    )

    assert exit_code == 1


def test_review_append_builds_non_default_account_paths(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        paper,
        "guard_paper_writer_account",
        lambda account_id=None, *, command_name, allow_non_default=False: {
            "account_id": "paper_growth",
            "account_root": str(Path("outputs/paper_accounts/paper_growth")),
            "legacy_default_used": False,
            "command_name": command_name,
            "write_allowed": allow_non_default,
            "message": "allowed",
        },
    )
    monkeypatch.setattr(paper, "format_writer_account_guard_message", lambda context: context["message"])
    monkeypatch.setattr(
        paper,
        "run_preflight",
        lambda stage, date_str, strict, write_report: {"result": "PASS"},
    )
    account_paths = paper.build_paper_account_paths("paper_growth", account_root=Path("outputs/paper_accounts/paper_growth"))
    monkeypatch.setattr(paper, "build_paper_account_paths", lambda account_id, create=False: account_paths)
    monkeypatch.setattr(
        paper,
        "append_paper_manual_review_log_from_template",
        lambda account_paths=None: captured.update({"account_paths": account_paths})
        or {
            "target_log_path": "x.csv",
            "append_report_path": "x.md",
            "append_issues_path": "x_issues.csv",
            "summary": {
                "validation_result": "PASS",
                "rows_appended": 1,
                "rows_skipped_pending": 0,
                "rows_skipped_duplicate": 0,
            },
        },
    )

    exit_code = paper.main(["review-append", "--account-id", "paper_growth"])

    assert exit_code == 0
    assert captured["account_paths"] is account_paths


def test_commit_defaults_to_paper_default_and_passes_guard(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        paper,
        "guard_paper_writer_account",
        lambda account_id=None, *, command_name, allow_non_default=False: {
            "account_id": "paper_default",
            "account_root": str(Path("outputs/paper_test")),
            "legacy_default_used": True,
            "command_name": command_name,
            "write_allowed": True,
            "message": "allowed",
        },
    )
    monkeypatch.setattr(paper, "format_writer_account_guard_message", lambda context: context["message"])
    monkeypatch.setattr(
        paper,
        "run_commit_shortcut",
        lambda date_str, replace, account_id=None: captured.update(
            {"date_str": date_str, "replace": replace, "account_id": account_id}
        )
        or 0,
    )

    exit_code = paper.main(["commit", "--date", "20260530"])

    assert exit_code == 0
    assert captured == {
        "date_str": "20260530",
        "replace": False,
        "account_id": None,
    }


def test_eod_allows_paper_default_and_preserves_writer_path_behavior(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        paper,
        "guard_paper_writer_account",
        lambda account_id=None, *, command_name, allow_non_default=False: {
            "account_id": "paper_default",
            "account_root": str(Path("outputs/paper_test")),
            "legacy_default_used": True,
            "command_name": command_name,
            "write_allowed": True,
            "message": "allowed",
        },
    )
    monkeypatch.setattr(paper, "format_writer_account_guard_message", lambda context: context["message"])
    monkeypatch.setattr(
        paper,
        "run_preflight",
        lambda stage, date_str, strict, write_report: {"result": "PASS"},
    )

    def fake_run_paper_eod_dry_run(date_str: str, allow_empty_journal: bool, commit: bool, plan_path, account_paths=None):
        captured["date_str"] = date_str
        captured["commit"] = commit
        captured["plan_path"] = plan_path
        captured["account_paths"] = account_paths
        return 0

    monkeypatch.setattr(paper, "run_paper_eod_dry_run", fake_run_paper_eod_dry_run)

    exit_code = paper.main(["eod", "--date", "20260530", "--commit"])

    assert exit_code == 0
    assert captured == {
        "date_str": "20260530",
        "commit": True,
        "plan_path": None,
        "account_paths": None,
    }
