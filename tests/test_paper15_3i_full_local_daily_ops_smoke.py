from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

import core.paper_manual_execution_commit as commit_module
import scripts.run_paper_daily_plan as plan_script
import scripts.run_paper_eod_update as eod_script
from core.paper_account_guard import assert_non_default_writer_target
from core.paper_account_paths import build_paper_account_paths
from core.paper_execution_log import PAPER_EXECUTION_LOG_COLUMNS
from core.paper_market_valuation import PaperAccountValuation, PaperPositionValuation
from core.paper_manual_execution_commit import commit_manual_execution_preview
from core.paper_status import WORKFLOW_REVIEW_PARTIAL, run_paper_status
from scripts.append_paper_manual_review_log import append_paper_manual_review_log_from_template
from scripts.generate_paper_daily_review_summary import generate_paper_daily_review_summary
from scripts.generate_paper_drawdown import generate_paper_drawdown_for_account
from scripts.generate_paper_equity_curve import generate_paper_equity_curve_for_account
from scripts.generate_paper_manual_review_log_template import generate_paper_manual_review_log_template
from scripts.generate_paper_performance_summary import generate_paper_performance_summary
from scripts.generate_paper_realized_ranking_report import generate_paper_realized_ranking_report
from scripts.generate_paper_realized_trade_journal import generate_paper_realized_trade_journal
from scripts.generate_paper_symbol_realized_performance import generate_paper_symbol_realized_performance
from scripts.generate_paper_symbol_review_buckets import generate_paper_symbol_review_buckets
from scripts.generate_paper_symbol_review_worksheet import generate_paper_symbol_review_worksheet
from scripts.generate_paper_symbol_side_by_side_performance import generate_paper_symbol_side_by_side_performance
from scripts.generate_paper_symbol_unrealized_performance import generate_paper_symbol_unrealized_performance
from scripts.run_paper_daily_plan import run_paper_daily_plan
from scripts.run_paper_eod_update import run_paper_eod_dry_run
from scripts.validate_paper_manual_review_log import validate_paper_manual_review_log


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _account_row(*, snapshot_date: str = "2026-05-29") -> dict[str, str]:
    return {
        "snapshot_date": snapshot_date,
        "currency": "USD",
        "initial_cash": "1000.00",
        "cash": "1000.00",
        "positions_cost_value": "0.00",
        "total_equity_cost_basis": "1000.00",
        "cash_ratio_cost_basis": "1.0000000",
        "position_count": "0",
        "symbols": "",
        "applied_trade_count": "0",
        "valuation_method": "cost_basis",
        "source_execution_log": "",
        "source_current_state": "",
        "created_at": "2026-05-29T10:00:00",
        "positions_market_value": "0.00",
        "total_equity_market_value": "1000.00",
        "cash_ratio_market_value": "1.0000000",
        "unrealized_pnl": "0.00",
        "unrealized_pnl_pct": "0.0000000",
        "realized_pnl": "0.00",
        "realized_pnl_by_symbol": "{}",
        "total_pnl": "0.00",
        "total_pnl_pct": "0.0000000",
        "market_valuation_status": "success",
        "market_valuation_error": "",
        "valuation_price_date": snapshot_date,
        "valuation_price_dates": "{}",
        "price_staleness_days": "{}",
        "max_price_staleness_days": "0",
    }


def _preview_payload(account_id: str) -> dict[str, object]:
    return {
        "execution_date": "2026-05-30",
        "account_id": account_id,
        "candidate_count": 1,
        "pass_count": 1,
        "warning_count": 0,
        "fail_count": 0,
        "commit_allowed": "true",
        "source_data_source_id": "ds-manual-execution",
        "projected_cash_start": 1000.0,
        "projected_cash_end": 900.0,
        "projected_cash_impact": -100.0,
        "projected_position_impact": {"AAPL": 1},
        "candidates": [
            {
                "page_id": "page-execution-1",
                "account_id": account_id,
                "name": "AAPL BUY",
                "execution_date": "2026-05-30",
                "plan_date": "2026-05-30",
                "symbol": "AAPL",
                "side": "BUY",
                "quantity": 1,
                "actual_price": 100.0,
                "commission": 0.0,
                "currency": "USD",
                "broker": "IBKR",
                "status": "READY",
                "note": "Smoke commit",
                "linked_daily_plan_key": f"daily_plan:{account_id}:2026-05-30",
                "notion_external_key": None,
                "validation_status_raw": None,
                "validation_message_raw": None,
                "import_status_raw": None,
                "imported_at_raw": None,
                "synced_at_raw": None,
                "canonical_key": f"manual_execution:{account_id}:2026-05-30:AAPL:BUY:01",
                "projected_cash_delta": -100.0,
                "projected_position_delta": 1,
                "validation_issues": [],
                "validation_status": "PASS",
            }
        ],
    }


def _fake_valuation(state, snapshot_date: str, db_path: Path) -> PaperAccountValuation:
    positions = []
    valuation_price_dates: dict[str, str] = {}
    staleness: dict[str, int] = {}
    positions_cost_value = 0.0
    positions_market_value = 0.0
    for symbol, position in sorted(state.positions.items()):
        close_price = position.avg_price
        cost_value = position.shares * position.avg_price
        market_value = position.shares * close_price
        positions_cost_value += cost_value
        positions_market_value += market_value
        positions.append(
            PaperPositionValuation(
                symbol=symbol,
                shares=position.shares,
                avg_price=position.avg_price,
                close_price=close_price,
                market_value=market_value,
                cost_value=cost_value,
                unrealized_pnl=0.0,
                unrealized_pnl_pct=0.0 if cost_value else None,
                valuation_price_date=snapshot_date,
                price_staleness_days=0,
            )
        )
        valuation_price_dates[symbol] = snapshot_date
        staleness[symbol] = 0
    total_equity_cost_basis = float(state.cash) + positions_cost_value
    total_equity_market_value = float(state.cash) + positions_market_value
    return PaperAccountValuation(
        snapshot_date=snapshot_date,
        cash=float(state.cash),
        positions_cost_value=positions_cost_value,
        positions_market_value=positions_market_value,
        total_equity_cost_basis=total_equity_cost_basis,
        total_equity_market_value=total_equity_market_value,
        cash_ratio_market_value=1.0 if total_equity_market_value == 0 else float(state.cash) / total_equity_market_value,
        unrealized_pnl=0.0,
        unrealized_pnl_pct=0.0 if positions_cost_value else None,
        valuation_method="db_daily_price_close",
        valuation_price_date=snapshot_date,
        valuation_price_dates=valuation_price_dates,
        price_staleness_days=staleness,
        positions=positions,
    )


def test_non_default_full_local_daily_ops_smoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    account_paths = build_paper_account_paths(
        "paper_smoke",
        account_root=tmp_path / "outputs" / "paper_accounts" / "paper_smoke",
        allow_legacy_default=False,
        create=True,
    )
    compact_date = "20260530"
    target_date = "2026-05-30"

    _write_csv(account_paths.execution_log_path, PAPER_EXECUTION_LOG_COLUMNS, [])
    _write_csv(account_paths.account_snapshot_path, list(_account_row().keys()), [_account_row()])
    _write_csv(
        account_paths.position_snapshot_path,
        [
            "snapshot_date",
            "symbol",
            "shares",
            "avg_price",
            "cost_value",
            "close_price",
            "market_value",
            "unrealized_pnl",
            "unrealized_pnl_pct",
            "realized_pnl",
            "total_pnl",
            "total_pnl_pct_on_current_cost",
            "valuation_method",
            "valuation_price_date",
            "price_staleness_days",
            "position_status",
            "created_at",
        ],
        [],
    )

    def _fake_load_official_paper_state_for_daily_plan(date_str: str, **kwargs):
        return {"date": date_str, "account_id": account_paths.account_id}

    def _fake_generate_daily_plan(
        *,
        date_str: str,
        current_state,
        output_path: Path,
        market_state_write_log: bool,
        config_snapshot_path: Path,
        config_snapshot_archive_dir: Path,
        config_snapshot_source: str,
        **kwargs,
    ) -> str:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            "\n".join(
                [
                    "# Daily Action Plan",
                    "",
                    "## 5. Execution Journal",
                    "| Date | Regime | Symbol | Type | Rec_Shares | Rec_Price | Act_Shares | Act_Price | Reason | Notes |",
                    "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        config_snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        config_snapshot_path.write_text(
            json.dumps(
                {
                    "date": date_str,
                    "account_id": current_state["account_id"],
                    "source": config_snapshot_source,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        config_snapshot_archive_dir.mkdir(parents=True, exist_ok=True)
        return str(output_path)

    monkeypatch.setattr(
        plan_script,
        "load_official_paper_state_for_daily_plan",
        _fake_load_official_paper_state_for_daily_plan,
    )
    monkeypatch.setattr(plan_script, "generate_daily_plan", _fake_generate_daily_plan)
    monkeypatch.setattr(eod_script, "market_db_path", lambda: str(tmp_path / "unused_market.db"))
    monkeypatch.setattr(eod_script, "value_paper_account_state", _fake_valuation)
    monkeypatch.setattr(commit_module, "market_db_path", lambda: str(tmp_path / "unused_market.db"))
    monkeypatch.setattr(commit_module, "value_paper_account_state", _fake_valuation)

    plan_path = Path(run_paper_daily_plan(compact_date, account_paths=account_paths))
    assert plan_path == account_paths.daily_action_plan_path(compact_date)
    assert plan_path.is_relative_to(account_paths.root.resolve())
    assert account_paths.config_snapshot_path(compact_date).exists()

    eod_result = run_paper_eod_dry_run(
        compact_date,
        allow_empty_journal=True,
        commit=False,
        account_paths=account_paths,
    )
    assert eod_result == 0
    assert not account_paths.current_state_snapshot_path(compact_date).exists()

    preview_path = account_paths.reports_dir / "manual_execution_preview_20260530.json"
    preview_path.write_text(json.dumps(_preview_payload(account_paths.account_id)), encoding="utf-8")
    commit_result = commit_manual_execution_preview(
        execution_date=target_date,
        preview_json_path=preview_path,
        account_paths=account_paths,
    )
    assert commit_result.account_id == account_paths.account_id
    assert account_paths.execution_log_path.exists()
    assert account_paths.current_state_snapshot_path(compact_date).exists()
    assert account_paths.account_snapshot_path.exists()
    assert account_paths.position_snapshot_path.exists()

    report_results = [
        generate_paper_equity_curve_for_account(account_paths=account_paths),
        generate_paper_drawdown_for_account(account_paths=account_paths),
        generate_paper_performance_summary(account_paths=account_paths),
        generate_paper_realized_trade_journal(account_paths=account_paths),
        generate_paper_symbol_realized_performance(account_paths=account_paths),
        generate_paper_realized_ranking_report(account_paths=account_paths),
        generate_paper_symbol_unrealized_performance(account_paths=account_paths),
        generate_paper_symbol_side_by_side_performance(account_paths=account_paths),
        generate_paper_symbol_review_buckets(account_paths=account_paths),
        generate_paper_symbol_review_worksheet(account_paths=account_paths),
        generate_paper_daily_review_summary(account_paths=account_paths),
    ]
    template_result = generate_paper_manual_review_log_template(account_paths=account_paths)
    validation_before = validate_paper_manual_review_log(account_paths=account_paths)
    assert validation_before["summary"]["validation_result"] == "PASS"

    template_path = template_result["csv_output_path"]
    with template_path.open("r", encoding="utf-8-sig", newline="") as handle:
        template_rows = list(csv.DictReader(handle))
    assert template_rows
    template_rows[0]["manual_answer"] = "Smoke reviewed"
    template_rows[0]["review_status"] = "reviewed"
    with template_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=template_rows[0].keys())
        writer.writeheader()
        writer.writerows(template_rows)

    validation_after = validate_paper_manual_review_log(account_paths=account_paths)
    append_result = append_paper_manual_review_log_from_template(account_paths=account_paths)
    final_status = run_paper_status(compact_date, account_paths=account_paths)

    assert validation_after["summary"]["validation_result"] == "PASS"
    assert append_result["summary"]["rows_appended"] == 1
    assert final_status["workflow_status"] == WORKFLOW_REVIEW_PARTIAL
    assert final_status["next_recommended_command"].endswith("--account-id paper_smoke")
    assert final_status["account_id"] == account_paths.account_id
    assert final_status["account_root"] == str(account_paths.root)
    assert final_status["reports_exists"] is True
    assert final_status["review_template_exists"] is True
    assert final_status["review_validation_result"] == "PASS"
    assert final_status["manual_review_log_exists"] is True
    assert final_status["manual_review_log_row_count"] == 1

    important_paths = [
        plan_path,
        account_paths.config_snapshot_path(compact_date),
        Path(commit_result.commit_json_path),
        Path(commit_result.commit_markdown_path),
        report_results[0]["output_path"],
        report_results[1]["output_path"],
        report_results[2]["output_path"],
        template_result["csv_output_path"],
        validation_after["report_output_path"],
        validation_after["issues_output_path"],
        append_result["target_log_path"],
        append_result["append_report_path"],
        append_result["append_issues_path"],
    ]
    for path in important_paths:
        assert path.is_relative_to(account_paths.root.resolve())

    with pytest.raises(ValueError, match="account root"):
        assert_non_default_writer_target(
            tmp_path / "outputs" / "paper_test" / "paper_execution_log.csv",
            account_id=account_paths.account_id,
            account_root=account_paths.root,
        )

    assert not (tmp_path / "outputs" / "paper_test").exists()


def test_paper_default_legacy_policy_unchanged_for_full_smoke(tmp_path: Path):
    account_paths = build_paper_account_paths(
        "paper_default",
        account_root=tmp_path / "outputs" / "paper_test",
        allow_legacy_default=False,
        create=True,
    )
    assert account_paths.account_id == "paper_default"
    assert account_paths.root == tmp_path / "outputs" / "paper_test"
    assert account_paths.reports_dir == account_paths.root / "reports"
    assert account_paths.reviews_dir == account_paths.root / "reviews"
