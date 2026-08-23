from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.paper_daily_review_scope import (
    DailyReviewScopeError,
    build_daily_manual_review_scope,
    validate_scope_manifest,
)
from core.paper_manual_review_log_template import build_paper_manual_review_log_template_from_scope


TRADE_DATE = "2026-08-10"
DATA_DATE = "2026-08-07"


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _build(
    tmp_path: Path,
    *,
    account_id: str = "paper_pilot_202606",
    open_symbols: list[str] | None = None,
    manual_symbols: list[str] | None = None,
    committed_symbols: list[str] | None = None,
    action_mode: str = "EXECUTION",
):
    open_symbols = open_symbols if open_symbols is not None else ["AMCR", "AON", "GPN", "INVH", "PAYX"]
    manual_symbols = manual_symbols if manual_symbols is not None else list(open_symbols)
    committed_symbols = committed_symbols if committed_symbols is not None else ["CMG", "EIX", "EQR", "KHC", "MAA", "UDR"]
    runbook_day_id = f"{account_id}_{DATA_DATE}_{TRADE_DATE}"
    plan = {
        "account_id": account_id,
        "data_date": DATA_DATE,
        "trade_date": TRADE_DATE,
        "execution_intent": {"action_mode": action_mode},
        "manual_review_items": [{"symbol": symbol, "state": "REVIEW_EXIT"} for symbol in manual_symbols],
        "items": [],
    }
    state = {"current_symbols": open_symbols, "shares": {symbol: 1 for symbol in open_symbols}}
    ids = [f"trade-{index}" for index, _ in enumerate(committed_symbols, start=1)]
    rows = [
        {
            "account_id": account_id,
            "canonical_key": f"manual_execution:{account_id}:{TRADE_DATE}:{symbol}:SELL:01",
            "symbol": symbol,
            "commit_status": "COMMITTED",
            "committed_trade_id": trade_id,
        }
        for symbol, trade_id in zip(committed_symbols, ids)
    ]
    report = {
        "status": "COMMITTED",
        "account_id": account_id,
        "execution_date": TRADE_DATE,
        "committed_row_count": len(rows),
        "committed_trade_ids": ids,
        "committed_rows": rows,
    }
    verification = {
        "schema_version": "stage_b_verification.v1",
        "runner_result": "PASS",
        "runbook_day_id": runbook_day_id,
        "account_id": account_id,
        "data_date": DATA_DATE,
        "trade_date": TRADE_DATE,
        "action_mode": action_mode,
        "verified_no_action": action_mode == "NO_ACTION",
        "committed_row_count": 0 if action_mode == "NO_ACTION" else len(rows),
        "failed_count": 0,
    }
    plan_path = _write_json(tmp_path / "daily_action_plan_20260810.json", plan)
    state_path = _write_json(tmp_path / "paper_current_state_20260810.json", state)
    verify_path = _write_json(tmp_path / "stage_b_verification.json", verification)
    commit_path = _write_json(tmp_path / "execution_commit_report.json", report)
    return build_daily_manual_review_scope(
        runbook_day_id=runbook_day_id,
        account_id=account_id,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
        daily_plan=plan,
        current_state=None if action_mode == "NO_ACTION" else state,
        stage_b_verification=verification,
        execution_commit_report=None if action_mode == "NO_ACTION" else report,
        daily_plan_path=plan_path,
        current_state_path=None if action_mode == "NO_ACTION" else state_path,
        stage_b_verification_path=verify_path,
        execution_commit_report_path=None if action_mode == "NO_ACTION" else commit_path,
        generated_at="2026-08-09T00:00:00",
    )


def test_incident_scope_is_position_5_execution_6_account_3(tmp_path: Path) -> None:
    manifest = _build(tmp_path)
    assert manifest["counts"] == {"position": 5, "execution": 6, "account": 3, "total": 14}
    assert manifest["position_symbols"] == ["AMCR", "AON", "GPN", "INVH", "PAYX"]
    assert manifest["execution_symbols"] == ["CMG", "EIX", "EQR", "KHC", "MAA", "UDR"]
    assert len(set(manifest["canonical_keys"])) == 14
    validate_scope_manifest(manifest)


def test_realized_only_and_open_without_manual_state_are_excluded(tmp_path: Path) -> None:
    manifest = _build(
        tmp_path,
        open_symbols=["OPEN_REVIEW", "OPEN_HOLD"],
        manual_symbols=["OPEN_REVIEW", "REALIZED_ONLY"],
        committed_symbols=["SOLD"],
    )
    assert manifest["position_symbols"] == ["OPEN_REVIEW"]
    assert "REALIZED_ONLY" not in {row["symbol"] for row in manifest["rows"]}
    assert "OPEN_HOLD" not in {row["symbol"] for row in manifest["rows"]}


def test_fully_sold_symbol_has_execution_review_but_no_position_review(tmp_path: Path) -> None:
    manifest = _build(tmp_path, open_symbols=[], manual_symbols=["SOLD"], committed_symbols=["SOLD"])
    sold_rows = [row for row in manifest["rows"] if row["symbol"] == "SOLD"]
    assert [row["question_id"] for row in sold_rows] == ["execution_review_1"]


def test_overlap_symbol_gets_both_questions(tmp_path: Path) -> None:
    manifest = _build(tmp_path, open_symbols=["BOTH"], manual_symbols=["BOTH"], committed_symbols=["BOTH"])
    assert [row["question_id"] for row in manifest["rows"] if row["symbol"] == "BOTH"] == [
        "position_review_1",
        "execution_review_1",
    ]


def test_execution_symbols_are_unique_in_first_commit_order(tmp_path: Path) -> None:
    manifest = _build(tmp_path, open_symbols=[], manual_symbols=[], committed_symbols=["B", "A", "B", "C"])
    assert manifest["execution_symbols"] == ["B", "A", "C"]


def test_not_executed_symbol_is_not_resurrected_as_execution_review(tmp_path: Path) -> None:
    manifest = _build(
        tmp_path,
        open_symbols=[],
        manual_symbols=["NOT_EXECUTED"],
        committed_symbols=[],
    )

    assert manifest["execution_symbols"] == []
    assert "NOT_EXECUTED" not in {row["symbol"] for row in manifest["rows"]}


@pytest.mark.parametrize("account_id", ["paper_default", "paper_growth"])
def test_default_and_non_default_account_keys_are_account_aware(tmp_path: Path, account_id: str) -> None:
    manifest = _build(tmp_path, account_id=account_id, open_symbols=[], manual_symbols=[], committed_symbols=["AAPL"])
    assert all(key.startswith(f"manual_review:{account_id}:{TRADE_DATE}:") for key in manifest["canonical_keys"])


def test_no_action_contract_remains_zero_review(tmp_path: Path) -> None:
    manifest = _build(tmp_path, action_mode="NO_ACTION")
    assert manifest["rows"] == []
    assert manifest["counts"] == {"position": 0, "execution": 0, "account": 0, "total": 0}


def test_template_uses_scope_categories_and_new_position_question_only(tmp_path: Path) -> None:
    manifest = _build(tmp_path, open_symbols=["BOTH"], manual_symbols=["BOTH"], committed_symbols=["BOTH"])
    scope_path = _write_json(tmp_path / "scope.json", manifest)
    rows, summary, warnings = build_paper_manual_review_log_template_from_scope(
        manifest, scope_path, created_at="2026-08-09T00:00:00"
    )
    assert [row["question_id"] for row in rows] == [
        "position_review_1", "execution_review_1", "account_review_1", "account_review_2", "account_review_3"
    ]
    assert rows[0]["review_tag"] == "position_follow_up"
    assert all(row["manual_answer"] == "" and row["review_status"] == "pending" for row in rows)
    assert summary["scope_sha256"] == manifest["scope_sha256"]
    assert warnings == []


def test_missing_commit_report_and_context_mismatch_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(DailyReviewScopeError, match="required"):
        manifest = _build(tmp_path)
        build_daily_manual_review_scope(
            runbook_day_id=manifest["frozen_context"]["runbook_day_id"],
            account_id=manifest["frozen_context"]["account_id"],
            data_date=DATA_DATE,
            trade_date=TRADE_DATE,
            daily_plan=json.loads((tmp_path / "daily_action_plan_20260810.json").read_text()),
            current_state=json.loads((tmp_path / "paper_current_state_20260810.json").read_text()),
            stage_b_verification=json.loads((tmp_path / "stage_b_verification.json").read_text()),
            execution_commit_report=None,
            daily_plan_path=tmp_path / "daily_action_plan_20260810.json",
            current_state_path=tmp_path / "paper_current_state_20260810.json",
            stage_b_verification_path=tmp_path / "stage_b_verification.json",
            execution_commit_report_path=None,
        )


def test_wrong_account_and_changed_source_hash_fail_closed(tmp_path: Path) -> None:
    manifest = _build(tmp_path)
    changed_path = Path(manifest["sources"]["daily_plan_json"]["path"])
    changed_path.write_text("{}", encoding="utf-8")
    with pytest.raises(DailyReviewScopeError, match="source hash mismatch"):
        validate_scope_manifest(manifest)

    plan = {"account_id": "paper_other", "data_date": DATA_DATE, "trade_date": TRADE_DATE,
            "execution_intent": {"action_mode": "EXECUTION"}, "items": []}
    plan_path = _write_json(tmp_path / "other" / "daily_action_plan_20260810.json", plan)
    state = {"current_symbols": [], "shares": {}}
    state_path = _write_json(tmp_path / "other" / "paper_current_state_20260810.json", state)
    verification = {"schema_version": "stage_b_verification.v1", "runner_result": "PASS",
                    "runbook_day_id": "x", "account_id": "paper_pilot_202606", "data_date": DATA_DATE,
                    "trade_date": TRADE_DATE, "action_mode": "EXECUTION", "failed_count": 0}
    verification_path = _write_json(tmp_path / "other" / "verification.json", verification)
    with pytest.raises(DailyReviewScopeError, match="Daily Plan account_id mismatch"):
        build_daily_manual_review_scope(
            runbook_day_id="x", account_id="paper_pilot_202606", data_date=DATA_DATE, trade_date=TRADE_DATE,
            daily_plan=plan, current_state=state, stage_b_verification=verification,
            execution_commit_report={}, daily_plan_path=plan_path, current_state_path=state_path,
            stage_b_verification_path=verification_path, execution_commit_report_path=verification_path,
        )
