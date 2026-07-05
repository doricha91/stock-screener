from __future__ import annotations

import json
from pathlib import Path

from scripts import runbook_gate_checker
from scripts import runbook_stage_runner
from scripts import runbook_state


ACCOUNT_ID = "paper_pilot_202606"
DATA_DATE = "2026-07-01"
TRADE_DATE = "2026-07-02"


def _write_json(path: Path, payload: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _seed_stage_c_pass_state(tmp_path: Path, *, stage_c_pass: bool = True) -> runbook_state.RunbookState:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    state = runbook_state.complete_stage(state, "A")
    state = runbook_state.complete_stage(state, "GATE1")
    state = runbook_state.complete_stage(state, "B")
    verification = _write_json(
        tmp_path / "verification_runs" / state.runbook_day_id / "latest_stage_b_verification.json",
        {
            "schema_version": "stage_b_verification.v1",
            "runner_result": "PASS",
            "committed_row_count": 5,
            "failed_count": 0,
        },
    )
    template_csv = tmp_path / "artifacts" / state.runbook_day_id / "review_prep" / "paper_manual_review_log_template.csv"
    template_csv.parent.mkdir(parents=True, exist_ok=True)
    template_csv.write_text("review_date,symbol,question_id,manual_answer,review_status\n", encoding="utf-8")
    state = runbook_state.record_artifact(state, "stage_b_verification_json", verification, tmp_path)
    state = runbook_state.record_artifact(state, "manual_review_template_csv", str(template_csv), tmp_path)
    if stage_c_pass:
        state = runbook_state.complete_stage(state, "C")
    path = runbook_state.get_state_path_for_context(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    runbook_state.save_state(state, path)
    return state


def _row(
    symbol: str = "TDY",
    question_id: str = "review_entry_rule",
    *,
    account_id: str = ACCOUNT_ID,
    review_date: str = TRADE_DATE,
    manual_answer: str = "Reviewed.",
    review_status: str = "reviewed",
    import_status: str = "READY",
    external_key: str | None = None,
) -> dict[str, object]:
    return {
        "page_id": f"page-{symbol}-{question_id}",
        "external_key": external_key or f"manual_review:{ACCOUNT_ID}:{TRADE_DATE}:{symbol}:{question_id}",
        "account_id": account_id,
        "review_date": review_date,
        "symbol": symbol,
        "question_id": question_id,
        "manual_answer": manual_answer,
        "review_status": review_status,
        "import_status": import_status,
        "source_template_key": "template-key",
    }


def test_gate2_passes_when_manual_review_rows_are_ready(tmp_path: Path) -> None:
    state = _seed_stage_c_pass_state(tmp_path)

    result = runbook_gate_checker.check_gate2_readiness(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        row_fetcher=lambda state: [_row("TDY"), _row("CMG", "review_exit_rule")],
    )

    assert result["runner_result"] == "PASS"
    assert result["next_stage"] == "D"
    loaded = runbook_state.load_state(runbook_state.get_state_path_for_context(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE))
    assert loaded.stage_status["GATE2"] == "PASS"
    assert loaded.current_stage == "GATE2"
    assert loaded.current_status == "PASS"
    assert loaded.last_completed_step == 12
    assert loaded.last_completed_stage == "GATE2"
    assert loaded.artifacts["gate2_readiness_json"].startswith(f"gate_runs/{state.runbook_day_id}/")
    payload = json.loads(Path(result["gate_result_json"]).read_text(encoding="utf-8"))
    assert payload["schema_version"] == "gate2_review_readiness.v1"
    assert payload["candidate_count"] == 2
    assert payload["ready_count"] == 2


def test_gate2_blocks_when_stage_c_not_pass(tmp_path: Path) -> None:
    _seed_stage_c_pass_state(tmp_path, stage_c_pass=False)

    result = runbook_gate_checker.check_gate2_readiness(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        row_fetcher=lambda state: [_row()],
    )

    assert result["runner_result"] == "BLOCKED"
    payload = json.loads(Path(result["gate_result_json"]).read_text(encoding="utf-8"))
    assert payload["summary"]["message"] == "stage_c_required"


def test_gate2_waits_when_manual_answer_empty(tmp_path: Path) -> None:
    _seed_stage_c_pass_state(tmp_path)

    result = runbook_gate_checker.check_gate2_readiness(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        row_fetcher=lambda state: [_row(manual_answer="")],
    )

    assert result["runner_result"] == "WAIT"
    payload = json.loads(Path(result["gate_result_json"]).read_text(encoding="utf-8"))
    assert payload["not_ready_count"] == 1
    assert "manual_answer" in payload["rows"][0]["missing"]
    loaded = runbook_state.load_state(runbook_state.get_state_path_for_context(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE))
    assert loaded.stage_status["GATE2"] == "WAIT"
    assert loaded.last_completed_step is None


def test_gate2_waits_when_review_status_not_reviewed(tmp_path: Path) -> None:
    _seed_stage_c_pass_state(tmp_path)

    result = runbook_gate_checker.check_gate2_readiness(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        row_fetcher=lambda state: [_row(review_status="pending")],
    )

    payload = json.loads(Path(result["gate_result_json"]).read_text(encoding="utf-8"))
    assert result["runner_result"] == "WAIT"
    assert "review_status_reviewed" in payload["rows"][0]["missing"]


def test_gate2_waits_when_import_status_not_ready(tmp_path: Path) -> None:
    _seed_stage_c_pass_state(tmp_path)

    result = runbook_gate_checker.check_gate2_readiness(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        row_fetcher=lambda state: [_row(import_status="DRAFT")],
    )

    payload = json.loads(Path(result["gate_result_json"]).read_text(encoding="utf-8"))
    assert result["runner_result"] == "WAIT"
    assert "import_status_READY" in payload["rows"][0]["missing"]


def test_gate2_blocks_on_account_id_mismatch(tmp_path: Path) -> None:
    _seed_stage_c_pass_state(tmp_path)

    result = runbook_gate_checker.check_gate2_readiness(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        row_fetcher=lambda state: [_row(account_id="paper_other")],
    )

    payload = json.loads(Path(result["gate_result_json"]).read_text(encoding="utf-8"))
    assert result["runner_result"] == "BLOCKED"
    assert payload["blocked_count"] == 1
    assert "account_id" in payload["rows"][0]["missing"]


def test_gate2_blocks_on_review_date_mismatch(tmp_path: Path) -> None:
    _seed_stage_c_pass_state(tmp_path)

    result = runbook_gate_checker.check_gate2_readiness(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        row_fetcher=lambda state: [_row(review_date="2026-07-03")],
    )

    payload = json.loads(Path(result["gate_result_json"]).read_text(encoding="utf-8"))
    assert result["runner_result"] == "BLOCKED"
    assert "review_date" in payload["rows"][0]["missing"]


def test_gate2_blocks_on_duplicate_ready_rows(tmp_path: Path) -> None:
    _seed_stage_c_pass_state(tmp_path)
    duplicate_key = f"manual_review:{ACCOUNT_ID}:{TRADE_DATE}:TDY:review_entry_rule"

    result = runbook_gate_checker.check_gate2_readiness(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        row_fetcher=lambda state: [
            _row("TDY", "review_entry_rule", external_key=duplicate_key),
            _row("TDY", "review_entry_rule", external_key=duplicate_key),
        ],
    )

    payload = json.loads(Path(result["gate_result_json"]).read_text(encoding="utf-8"))
    assert result["runner_result"] == "BLOCKED"
    assert payload["blocked_count"] == 2
    assert all("duplicate_ready_row" in row["missing"] for row in payload["rows"])


def test_stage_runner_gate2_requires_paper_confirmation(tmp_path: Path) -> None:
    result = runbook_stage_runner.check_gate2(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=False,
    )

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "paper_test_confirmation_required"
