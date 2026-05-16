from __future__ import annotations

from pathlib import Path

from scripts.audit_paper_performance_inputs import (
    audit_account_snapshot,
    audit_position_snapshot,
    cross_validate_account_vs_position,
    run_audit,
)


def test_audit_account_snapshot_detects_missing_required_columns() -> None:
    rows = [
        {
            "snapshot_date": "2026-05-12",
            "cash": "100.00",
        }
    ]

    result = audit_account_snapshot(rows)

    assert any("Missing account snapshot columns" in issue for issue in result.issues)


def test_audit_account_snapshot_detects_duplicate_dates_and_invalid_numeric() -> None:
    rows = [
        {
            "snapshot_date": "2026-05-12",
            "cash": "bad",
            "positions_cost_value": "10.00",
            "total_equity_cost_basis": "110.00",
            "positions_market_value": "10.00",
            "total_equity_market_value": "110.00",
            "realized_pnl": "0.00",
            "unrealized_pnl": "0.00",
            "total_pnl": "0.00",
            "market_valuation_status": "success",
        },
        {
            "snapshot_date": "2026-05-12",
            "cash": "100.00",
            "positions_cost_value": "10.00",
            "total_equity_cost_basis": "110.00",
            "positions_market_value": "10.00",
            "total_equity_market_value": "110.00",
            "realized_pnl": "0.00",
            "unrealized_pnl": "0.00",
            "total_pnl": "0.00",
            "market_valuation_status": "success",
        },
    ]

    result = audit_account_snapshot(rows)

    assert any("Duplicate account snapshot_date values" in issue for issue in result.issues)
    assert any("column cash has 1 invalid numeric rows" in issue for issue in result.issues)


def test_audit_account_snapshot_detects_identity_mismatch() -> None:
    rows = [
        {
            "snapshot_date": "2026-05-12",
            "cash": "100.00",
            "positions_cost_value": "10.00",
            "total_equity_cost_basis": "120.00",
            "positions_market_value": "10.00",
            "total_equity_market_value": "110.00",
            "realized_pnl": "1.00",
            "unrealized_pnl": "2.00",
            "total_pnl": "5.00",
            "market_valuation_status": "success",
        }
    ]

    result = audit_account_snapshot(rows)

    assert any("Cost-basis identity mismatch" in issue for issue in result.issues)
    assert any("PnL identity mismatch" in issue for issue in result.issues)


def test_cross_validate_account_vs_position_detects_mismatch() -> None:
    account_rows = [
        {
            "snapshot_date": "2026-05-12",
            "cash": "100.00",
            "positions_cost_value": "50.00",
            "total_equity_cost_basis": "150.00",
            "positions_market_value": "55.00",
            "total_equity_market_value": "155.00",
            "realized_pnl": "0.00",
            "unrealized_pnl": "5.00",
            "total_pnl": "5.00",
            "market_valuation_status": "success",
        }
    ]
    position_rows = [
        {
            "snapshot_date": "2026-05-12",
            "symbol": "AAA",
            "shares": "1",
            "avg_price": "10.00",
            "cost_value": "10.00",
            "close_price": "11.00",
            "market_value": "11.00",
            "unrealized_pnl": "1.00",
            "unrealized_pnl_pct": "0.1",
            "position_status": "OPEN",
        }
    ]

    position_result = audit_position_snapshot(position_rows)
    cross = cross_validate_account_vs_position(
        account_rows,
        position_rows,
        position_result.summary["resolved_columns"],
    )

    assert any("cost sum mismatch" in issue for issue in cross.issues)
    assert any("market sum mismatch" in issue for issue in cross.issues)


def test_run_audit_on_healthy_fixture_has_no_issues() -> None:
    temp_path = Path("outputs/paper_test/reports/_test_audit_fixture")
    temp_path.mkdir(parents=True, exist_ok=True)
    try:
        account_path = temp_path / "paper_account_snapshot.csv"
        position_path = temp_path / "paper_position_snapshot.csv"
        execution_path = temp_path / "paper_execution_log.csv"
        report_path = temp_path / "paper_performance_input_audit.md"

        account_path.write_text(
            "\n".join(
                [
                    "snapshot_date,cash,positions_cost_value,total_equity_cost_basis,positions_market_value,total_equity_market_value,realized_pnl,unrealized_pnl,total_pnl,market_valuation_status",
                    "2026-05-12,99990.00,10.00,100000.00,12.00,100002.00,1.00,1.00,2.00,success",
                ]
            ),
            encoding="utf-8",
        )
        position_path.write_text(
            "\n".join(
                [
                    "snapshot_date,symbol,shares,avg_price,cost_value,close_price,market_value,unrealized_pnl,unrealized_pnl_pct,position_status",
                    "2026-05-12,AAA,1,10.00,10.00,12.00,12.00,1.00,0.1000000,OPEN",
                ]
            ),
            encoding="utf-8",
        )
        execution_path.write_text(
            "\n".join(
                [
                    "trade_id,date,regime,symbol,side,shares,price,gross_amount,source,status,reason,notes,rec_shares,rec_price,created_at",
                    "t1,2026-05-12,BULL,AAA,BUY,1,10.00,10.00,test,FILLED,,,1,10.00,2026-05-12T16:00:00",
                ]
            ),
            encoding="utf-8",
        )

        result = run_audit(
            account_snapshot_path=account_path,
            position_snapshot_path=position_path,
            execution_log_path=execution_path,
            report_path=report_path,
        )

        assert result["issues"] == []
        assert report_path.exists()
        assert "Proceed to PAPER8-2: Yes" in report_path.read_text(encoding="utf-8")
    finally:
        for path in temp_path.glob("*"):
            path.unlink()
        temp_path.rmdir()
