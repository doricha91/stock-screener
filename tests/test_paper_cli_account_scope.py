from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from core.paper_execution_log import PAPER_EXECUTION_LOG_COLUMNS
from core.paper_market_valuation import PaperAccountValuation, PaperPositionValuation
from core.paper_status import WORKFLOW_REVIEW_DONE, run_paper_status
from core.paper_account_paths import PaperAccountPaths
from scripts import paper
from scripts import run_paper_eod_update


def _account_paths(account_id: str, root: Path, *, legacy_default_used: bool = False) -> PaperAccountPaths:
    return PaperAccountPaths(
        account_id=account_id,
        root=root,
        legacy_default_used=legacy_default_used,
        execution_log_path=root / "paper_execution_log.csv",
        account_snapshot_path=root / "paper_account_snapshot.csv",
        position_snapshot_path=root / "paper_position_snapshot.csv",
        reports_dir=root / "reports",
        reviews_dir=root / "reviews",
        config_snapshots_dir=root / "config_snapshots",
        config_snapshot_archive_dir=root / "archive" / "config_snapshots",
        replay_diff_dir=root / "replay_diff",
        replay_diff_config_snapshot_archive_dir=root / "replay_diff" / "archive" / "config_snapshots",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _seed_no_action_eod_account(root: Path) -> PaperAccountPaths:
    paths = _account_paths("paper_growth", root)
    root.mkdir(parents=True, exist_ok=True)
    paths.reports_dir.mkdir(parents=True, exist_ok=True)
    paths.reviews_dir.mkdir(parents=True, exist_ok=True)
    paths.config_snapshots_dir.mkdir(parents=True, exist_ok=True)
    _write_text(root / "daily_action_plan_20260609.md", "# No action plan\n\nHold existing positions.\n")
    _write_text(root / "daily_action_plan_20260609.json", json.dumps({"items": []}, indent=2))
    _write_text(root / "paper_current_state_20260608.json", "{}\n")
    _write_csv(
        paths.execution_log_path,
        PAPER_EXECUTION_LOG_COLUMNS,
        [
            {
                "trade_id": "seed-buy-aapl",
                "date": "2026-06-08",
                "regime": "normal",
                "symbol": "AAPL",
                "side": "BUY",
                "shares": 10,
                "price": 100,
                "gross_amount": 1000,
                "source": "fixture",
                "status": "COMMITTED",
                "reason": "seed previous day",
                "notes": "",
                "rec_shares": 10,
                "rec_price": 100,
                "created_at": "2026-06-08T16:00:00",
            }
        ],
    )
    _write_text(
        paths.account_snapshot_path,
        "snapshot_date,currency,initial_cash,cash,positions_cost_value,total_equity_cost_basis,"
        "cash_ratio_cost_basis,position_count,symbols,applied_trade_count,valuation_method,"
        "source_execution_log,source_current_state,created_at,positions_market_value,"
        "total_equity_market_value,cash_ratio_market_value,unrealized_pnl,unrealized_pnl_pct,"
        "realized_pnl,realized_pnl_by_symbol,total_pnl,total_pnl_pct,market_valuation_status,"
        "market_valuation_error,valuation_price_date,valuation_price_dates,price_staleness_days,"
        "max_price_staleness_days\n"
        "2026-06-08,USD,100000.00,99000.00,1000.00,100000.00,0.9900000,1,AAPL,1,"
        "db_daily_price_close,,,,1000.00,100000.00,0.9900000,0.00,0.0000000,0.00,{},0.00,"
        "0.0000000,success,,2026-06-08,{\"AAPL\":\"2026-06-08\"},{\"AAPL\":0},0\n",
    )
    _write_text(
        paths.position_snapshot_path,
        "snapshot_date,symbol,shares,avg_price,cost_value,close_price,market_value,unrealized_pnl,"
        "unrealized_pnl_pct,realized_pnl,total_pnl,total_pnl_pct_on_current_cost,valuation_method,"
        "valuation_price_date,price_staleness_days,position_status,created_at\n"
        "2026-06-08,AAPL,10,100.00,1000.00,100.00,1000.00,0.00,0.0000000,0.00,0.00,"
        "0.0000000,db_daily_price_close,2026-06-08,0,OPEN,2026-06-08T16:00:00\n",
    )
    return paths


def _fake_valuation(state, snapshot_date: str, db_path: Path) -> PaperAccountValuation:
    position = state.positions["AAPL"]
    cost_value = position.shares * position.avg_price
    market_value = position.shares * 101.0
    return PaperAccountValuation(
        snapshot_date="2026-06-09",
        cash=float(state.cash),
        positions_cost_value=cost_value,
        positions_market_value=market_value,
        total_equity_cost_basis=float(state.cash) + cost_value,
        total_equity_market_value=float(state.cash) + market_value,
        cash_ratio_market_value=float(state.cash) / (float(state.cash) + market_value),
        unrealized_pnl=market_value - cost_value,
        unrealized_pnl_pct=(market_value - cost_value) / cost_value,
        valuation_method="fixture_close",
        valuation_price_date="2026-06-09",
        valuation_price_dates={"AAPL": "2026-06-09"},
        price_staleness_days={"AAPL": 0},
        positions=[
            PaperPositionValuation(
                symbol="AAPL",
                shares=position.shares,
                avg_price=position.avg_price,
                close_price=101.0,
                market_value=market_value,
                cost_value=cost_value,
                unrealized_pnl=market_value - cost_value,
                unrealized_pnl_pct=(market_value - cost_value) / cost_value,
                valuation_price_date="2026-06-09",
                price_staleness_days=0,
            )
        ],
    )


def test_status_uses_account_paths_and_defaults_to_paper_default(monkeypatch):
    captured: dict[str, object] = {}
    paths = _account_paths("paper_default", Path("outputs/paper_test"), legacy_default_used=True)

    def fake_build_paper_account_paths(account_id=None, *, create: bool = False):
        captured["account_id"] = account_id
        captured["create"] = create
        return paths

    def fake_run_paper_status(date_str=None, *, account_paths=None, paper_root=None):
        captured["status_account_id"] = account_paths.account_id
        captured["paper_root"] = paper_root
        return {
            "account_id": account_paths.account_id,
            "account_root": str(account_paths.root),
            "legacy_default_used": account_paths.legacy_default_used,
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

    monkeypatch.setattr(paper, "build_paper_account_paths", fake_build_paper_account_paths)
    monkeypatch.setattr(paper, "run_paper_status", fake_run_paper_status)

    exit_code = paper.main(["status", "--json"])
    assert exit_code == 0
    assert captured["account_id"] is None
    assert captured["create"] is False
    assert captured["status_account_id"] == "paper_default"
    assert captured["paper_root"] is None


def test_status_invalid_account_id_raises():
    with pytest.raises(ValueError):
        paper.main(["status", "--account-id", "Paper Default"])


def test_weekly_status_passes_account_paths(monkeypatch):
    captured: dict[str, object] = {}
    root = Path("outputs/paper_accounts/paper_growth")
    paths = _account_paths("paper_growth", root)

    monkeypatch.setattr(paper, "build_paper_account_paths", lambda account_id=None, *, create=False: paths)
    monkeypatch.setattr(Path, "exists", lambda self: True if self == root else Path.__dict__["exists"](self))

    def fake_generate_paper_weekly_status(*, days, start, end, account_paths=None, paper_root=None):
        captured["days"] = days
        captured["account_id"] = account_paths.account_id
        captured["paper_root"] = paper_root
        return {
            "markdown_path": root / "reports" / "paper_weekly_status_summary.md",
            "json_path": root / "reports" / "paper_weekly_status_summary.json",
            "summary": {
                "account_id": account_paths.account_id,
                "account_root": str(account_paths.root),
                "legacy_default_used": False,
                "schema_version": "paper_weekly_status.v1",
                "period": {"actual_start": "2026-05-15", "actual_end": "2026-05-20", "snapshot_count": 2, "coverage_status": "FULL"},
                "overall_status": "PASS",
            },
        }

    monkeypatch.setattr(paper, "generate_paper_weekly_status", fake_generate_paper_weekly_status)
    exit_code = paper.main(["weekly-status", "--account-id", "paper_growth", "--days", "2"])
    assert exit_code == 0
    assert captured == {"days": 2, "account_id": "paper_growth", "paper_root": None}


def test_benchmark_passes_account_paths(monkeypatch):
    captured: dict[str, object] = {}
    root = Path("outputs/paper_accounts/paper_growth")
    paths = _account_paths("paper_growth", root)

    monkeypatch.setattr(paper, "build_paper_account_paths", lambda account_id=None, *, create=False: paths)
    monkeypatch.setattr(Path, "exists", lambda self: True if self == root else Path.__dict__["exists"](self))

    def fake_generate_paper_benchmark_comparison(*, account_paths=None, paper_root=None, market_db=None):
        captured["account_id"] = account_paths.account_id
        captured["paper_root"] = paper_root
        return {
            "markdown_path": root / "reports" / "paper_benchmark_comparison.md",
            "json_path": root / "reports" / "paper_benchmark_comparison.json",
            "summary": {
                "account_id": account_paths.account_id,
                "account_root": str(account_paths.root),
                "legacy_default_used": False,
                "schema_version": "paper_benchmark_comparison.v1",
                "run_mode": "exploratory",
                "official_run": False,
                "latest_snapshot_date": "2026-05-20",
                "availability_status": "AVAILABLE",
            },
        }

    monkeypatch.setattr(paper, "generate_paper_benchmark_comparison", fake_generate_paper_benchmark_comparison)
    exit_code = paper.main(["benchmark", "--account-id", "paper_growth"])
    assert exit_code == 0
    assert captured == {"account_id": "paper_growth", "paper_root": None}


def test_missing_non_default_root_returns_no_data_without_creation(monkeypatch, capsys):
    root = Path("outputs/paper_accounts/paper_growth")
    paths = _account_paths("paper_growth", root)
    monkeypatch.setattr(paper, "build_paper_account_paths", lambda account_id=None, *, create=False: paths)
    monkeypatch.setattr(Path, "exists", lambda self: False if self == root else Path.__dict__["exists"](self))

    exit_code = paper.main(["benchmark", "--account-id", "paper_growth", "--json"])
    output = capsys.readouterr().out
    assert exit_code == 1
    assert '"availability_status": "NO_DATA"' in output


def test_eod_dry_run_preflight_uses_non_default_account_paths(tmp_path, monkeypatch):
    captured: dict[str, object] = {}
    account_root = tmp_path / "paper_accounts" / "paper_pilot_202606"
    fallback_root = tmp_path / "paper_test"
    paths = _account_paths("paper_pilot_202606", account_root)
    account_root.mkdir(parents=True)
    fallback_root.mkdir(parents=True)
    paths.daily_action_plan_path("2026-06-08").write_text("# account plan\n", encoding="utf-8")

    def fake_build_paper_account_paths(account_id=None, *, create=False):
        captured["build_account_id"] = account_id
        captured["build_create"] = create
        return paths

    def fake_call_preflight(*, stage, date_str, strict, write_report, account_paths):
        captured["preflight_account_root"] = account_paths.root
        captured["fallback_plan_exists"] = (fallback_root / "daily_action_plan_20260608.md").exists()
        assert account_paths.daily_action_plan_path(date_str).exists()
        return {"result": "PASS"}

    def fake_run_paper_eod_dry_run(date_str, *, allow_empty_journal, commit, plan_path, account_paths):
        captured["eod_account_root"] = account_paths.root
        captured["eod_commit"] = commit
        return 0

    monkeypatch.setattr(paper, "build_paper_account_paths", fake_build_paper_account_paths)
    monkeypatch.setattr(paper, "_call_preflight", fake_call_preflight)
    monkeypatch.setattr(paper, "run_paper_eod_dry_run", fake_run_paper_eod_dry_run)

    exit_code = paper.main(["eod", "--date", "2026-06-08", "--account-id", "paper_pilot_202606", "--dry-run"])

    assert exit_code == 0
    assert captured["build_account_id"] == "paper_pilot_202606"
    assert captured["build_create"] is False
    assert captured["preflight_account_root"] == account_root
    assert captured["eod_account_root"] == account_root
    assert captured["eod_commit"] is False
    assert captured["fallback_plan_exists"] is False


def test_eod_dry_run_preflight_still_fails_when_account_plan_missing(tmp_path, monkeypatch, capsys):
    account_root = tmp_path / "paper_accounts" / "paper_pilot_202606"
    paths = _account_paths("paper_pilot_202606", account_root)
    account_root.mkdir(parents=True)

    monkeypatch.setattr(paper, "build_paper_account_paths", lambda account_id=None, *, create=False: paths)

    def fake_call_preflight(*, stage, date_str, strict, write_report, account_paths):
        assert not account_paths.daily_action_plan_path(date_str).exists()
        return {"result": "FAIL"}

    called = {"eod": False}

    def fake_run_paper_eod_dry_run(*args, **kwargs):
        called["eod"] = True
        return 0

    monkeypatch.setattr(paper, "_call_preflight", fake_call_preflight)
    monkeypatch.setattr(paper, "run_paper_eod_dry_run", fake_run_paper_eod_dry_run)

    exit_code = paper.main(["eod", "--date", "2026-06-08", "--account-id", "paper_pilot_202606", "--dry-run"])

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "Paper EOD aborted because preflight failed." in output
    assert called["eod"] is False


def test_eod_commit_path_builds_account_paths_before_preflight_with_create_true(monkeypatch):
    captured: dict[str, object] = {}
    paths = _account_paths("paper_growth", Path("outputs/paper_accounts/paper_growth"))

    def fake_build_paper_account_paths(account_id=None, *, create=False):
        captured["build_account_id"] = account_id
        captured["build_create"] = create
        return paths

    def fake_call_preflight(*, stage, date_str, strict, write_report, account_paths):
        captured["preflight_account_id"] = account_paths.account_id
        return {"result": "PASS"}

    def fake_run_paper_eod_dry_run(date_str, *, allow_empty_journal, commit, plan_path, account_paths):
        captured["eod_commit"] = commit
        captured["eod_account_id"] = account_paths.account_id
        return 0

    monkeypatch.setattr(paper, "build_paper_account_paths", fake_build_paper_account_paths)
    monkeypatch.setattr(paper, "_call_preflight", fake_call_preflight)
    monkeypatch.setattr(paper, "run_paper_eod_dry_run", fake_run_paper_eod_dry_run)

    exit_code = paper.handle_eod(
        paper.argparse.Namespace(
            date="2026-06-08",
            dry_run=False,
            commit=True,
            account_id="paper_growth",
            guard_checked=True,
        )
    )

    assert exit_code == 0
    assert captured == {
        "build_account_id": "paper_growth",
        "build_create": True,
        "preflight_account_id": "paper_growth",
        "eod_commit": True,
        "eod_account_id": "paper_growth",
    }


def test_no_action_eod_dry_run_shows_roll_forward_intent_without_writes(tmp_path, monkeypatch, capsys):
    paths = _seed_no_action_eod_account(tmp_path / "paper_accounts" / "paper_growth")
    monkeypatch.setattr(run_paper_eod_update, "value_paper_account_state", _fake_valuation)

    exit_code = run_paper_eod_update.run_paper_eod_dry_run(
        "2026-06-09",
        allow_empty_journal=True,
        commit=False,
        account_paths=paths,
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "no_action_day: true" in output
    assert "execution_candidate_count: 0" in output
    assert "ready_preview_count: 0" in output
    assert "would_append_execution_log: false" in output
    assert "would_write_current_state: true" in output
    assert "would_write_account_snapshot: true" in output
    assert "would_write_position_snapshot: true" in output
    assert "source_snapshot_date: 2026-06-08" in output
    assert "target_snapshot_date: 2026-06-09" in output
    assert not paths.current_state_snapshot_path("2026-06-09").exists()
    assert "2026-06-09" not in paths.account_snapshot_path.read_text(encoding="utf-8-sig")
    assert "2026-06-09" not in paths.position_snapshot_path.read_text(encoding="utf-8-sig")


def test_no_action_eod_commit_fixture_rolls_forward_snapshots_without_execution_rows(tmp_path, monkeypatch):
    paths = _seed_no_action_eod_account(tmp_path / "paper_accounts" / "paper_growth")
    monkeypatch.setattr(run_paper_eod_update, "value_paper_account_state", _fake_valuation)
    before_log_rows = list(csv.DictReader(paths.execution_log_path.open("r", encoding="utf-8-sig", newline="")))

    exit_code = run_paper_eod_update.run_paper_eod_dry_run(
        "2026-06-09",
        allow_empty_journal=True,
        commit=True,
        account_paths=paths,
    )

    after_log_rows = list(csv.DictReader(paths.execution_log_path.open("r", encoding="utf-8-sig", newline="")))
    account_rows = list(csv.DictReader(paths.account_snapshot_path.open("r", encoding="utf-8-sig", newline="")))
    position_rows = list(csv.DictReader(paths.position_snapshot_path.open("r", encoding="utf-8-sig", newline="")))
    current_state = json.loads(paths.current_state_snapshot_path("2026-06-09").read_text(encoding="utf-8"))

    assert exit_code == 0
    assert len(after_log_rows) == len(before_log_rows)
    assert not [row for row in after_log_rows if row["date"] == "2026-06-09"]
    assert paths.current_state_snapshot_path("2026-06-09").exists()
    assert any(row["snapshot_date"] == "2026-06-09" for row in account_rows)
    assert any(row["snapshot_date"] == "2026-06-09" and row["symbol"] == "AAPL" for row in position_rows)
    target_account = next(row for row in account_rows if row["snapshot_date"] == "2026-06-09")
    previous_account = next(row for row in account_rows if row["snapshot_date"] == "2026-06-08")
    assert target_account["cash"] == previous_account["cash"]
    assert target_account["position_count"] == previous_account["position_count"]
    assert target_account["symbols"] == previous_account["symbols"]
    assert current_state["absolute_cash"] == 99000.0
    assert current_state["shares"]["AAPL"] == 10


def test_no_action_roll_forward_allows_status_review_done_without_commit_recommendation(tmp_path, monkeypatch):
    paths = _seed_no_action_eod_account(tmp_path / "paper_accounts" / "paper_growth")
    monkeypatch.setattr(run_paper_eod_update, "value_paper_account_state", _fake_valuation)
    _write_text(paths.reports_dir / "paper_daily_review_summary.md", "# summary\nLatest snapshot date: 2026-06-09\n")
    _write_text(paths.reports_dir / "paper_performance_summary.md", "# perf\nLatest Snapshot Date: 2026-06-09\n")
    _write_text(
        paths.reviews_dir / "paper_manual_review_log_template.csv",
        "review_date,symbol,question_id,manual_answer,review_status\n"
        "2026-06-09,AAPL,Q1,,pending\n",
    )
    _write_text(
        paths.reviews_dir / "paper_manual_review_log.csv",
        "review_date,symbol,question_id,manual_answer,review_status\n"
        "2026-06-09,AAPL,Q1,done,reviewed\n",
    )
    _write_text(
        paths.reviews_dir / "paper_manual_review_log_validation_report.md",
        "# validation\n\n- Validation result: PASS\n",
    )

    assert run_paper_eod_update.run_paper_eod_dry_run(
        "2026-06-09",
        allow_empty_journal=True,
        commit=True,
        account_paths=paths,
    ) == 0

    status = run_paper_status("2026-06-09", account_paths=paths)
    assert status["same_date_snapshot_exists"] is True
    assert status["current_state_exists"] is True
    assert status["account_snapshot_exists"] is True
    assert status["position_snapshot_exists"] is True
    assert status["execution_log_rows_for_date"] == 0
    assert status["review_progress_status"] == "DONE"
    assert status["workflow_status"] == WORKFLOW_REVIEW_DONE
    assert status["next_recommended_command"] == "no immediate action"
