from __future__ import annotations

import json
import csv
import hashlib
from pathlib import Path

from core.paper_execution_intent import build_execution_intent
from core.notion_account_keys import build_manual_review_canonical_key
from core.paper_manual_review_log_template import PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS
from scripts import runbook_gate_checker
from scripts import runbook_stage_runner
from scripts import runbook_state
from scripts.runbook_no_action import sha256_file


ACCOUNT_ID = "paper_pilot_202606"
DATA_DATE = "2026-07-01"
TRADE_DATE = "2026-07-02"


def _write_json(path: Path, payload: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _seed_stage_c_pass_state(
    tmp_path: Path,
    *,
    stage_c_pass: bool = True,
    scope_rows: list[tuple[str, str]] | None = None,
) -> runbook_state.RunbookState:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    state = runbook_state.complete_stage(state, "A")
    state = runbook_state.complete_stage(state, "GATE1")
    state = runbook_state.complete_stage(state, "B")
    items = [{"symbol": "TDY", "action": "BUY", "quantity": 1}]
    daily_plan = _write_json(
        tmp_path / "artifacts" / state.runbook_day_id / "daily_plan.json",
        {
            "schema_version": "paper_daily_plan.v1",
            "account_id": ACCOUNT_ID,
            "data_date": DATA_DATE,
            "trade_date": TRADE_DATE,
            "plan_date": TRADE_DATE,
            "run_mode": "official",
            "official_run": True,
            "generated_at": f"{TRADE_DATE}T00:00:00Z",
            "items": items,
            "execution_intent": build_execution_intent(items),
            "fingerprints": {},
        },
    )
    verification = _write_json(
        tmp_path / "verification_runs" / state.runbook_day_id / "latest_stage_b_verification.json",
        {
            "schema_version": "stage_b_verification.v1",
            "runner_result": "PASS",
            "runbook_day_id": state.runbook_day_id,
            "account_id": ACCOUNT_ID,
            "data_date": DATA_DATE,
            "trade_date": TRADE_DATE,
            "action_mode": "EXECUTION",
            "verified_no_action": False,
            "committed_row_count": 5,
            "updated_count": 5,
            "failed_count": 0,
        },
    )
    template_csv = tmp_path / "artifacts" / state.runbook_day_id / "review_prep" / "paper_manual_review_log_template.csv"
    template_csv.parent.mkdir(parents=True, exist_ok=True)
    template_csv.write_text("review_date,symbol,question_id,manual_answer,review_status\n", encoding="utf-8")
    state = runbook_state.record_artifact(state, "daily_plan_json", daily_plan, tmp_path)
    state = runbook_state.record_artifact(state, "stage_b_verification_json", verification, tmp_path)
    state = runbook_state.record_artifact(state, "manual_review_template_csv", str(template_csv), tmp_path)
    scope_pairs = scope_rows if scope_rows is not None else [("TDY", "execution_review_1")]
    scope_data_rows = [
        {
            "account_id": ACCOUNT_ID,
            "review_date": TRADE_DATE,
            "symbol": symbol,
            "question_id": question_id,
            "question_text": "Review execution.",
            "question_category": "execution_review",
            "review_tag": "execution_quality",
            "canonical_key": build_manual_review_canonical_key(ACCOUNT_ID, TRADE_DATE, symbol, question_id),
        }
        for symbol, question_id in scope_pairs
    ]
    basis = {
        "schema_version": "paper_daily_manual_review_scope.v1",
        "frozen_context": {
            "runbook_day_id": state.runbook_day_id,
            "account_id": ACCOUNT_ID,
            "data_date": DATA_DATE,
            "trade_date": TRADE_DATE,
        },
        "action_mode": "EXECUTION",
        "sources": {},
        "manual_review_symbols": [],
        "current_open_symbols": [],
        "position_symbols": [],
        "execution_symbols": [symbol for symbol, _ in scope_pairs],
        "canonical_keys": [row["canonical_key"] for row in scope_data_rows],
        "rows": scope_data_rows,
    }
    scope_sha = hashlib.sha256(
        json.dumps(basis, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    scope_path = _write_json(
        tmp_path / "artifacts" / state.runbook_day_id / "stage_c" / "manual_review_scope.json",
        {**basis, "generated_at": "2026-07-02T00:00:00", "counts": {"total": len(scope_data_rows)}, "scope_sha256": scope_sha},
    )
    state = runbook_state.record_artifact(state, "manual_review_scope_json", scope_path, tmp_path)
    if stage_c_pass:
        state = runbook_state.complete_stage(state, "C")
        stage_c_summary = _write_json(
            tmp_path / "stage_runs" / state.runbook_day_id / "stage_c.json",
            {
                "schema_version": "runbook_stage_summary.v1",
                "runner_result": "PASS",
                "stage_id": "C",
                "runbook_day_id": state.runbook_day_id,
                "frozen_context": {
                    "account_id": ACCOUNT_ID,
                    "data_date": DATA_DATE,
                    "trade_date": TRADE_DATE,
                },
                "raw_payload": {
                    "action_mode": "EXECUTION",
                    "verified_no_action": False,
                    "manual_review_scope_sha256": scope_sha,
                    "manual_review_scope_count": len(scope_data_rows),
                },
            },
        )
        state = runbook_state.record_artifact(state, "stage_c_summary_json", stage_c_summary, tmp_path)
    path = runbook_state.get_state_path_for_context(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    runbook_state.save_state(state, path)
    return state


def _seed_no_action_stage_c_state(tmp_path: Path) -> runbook_state.RunbookState:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    for stage_id in ("A", "GATE1", "B", "C"):
        state = runbook_state.complete_stage(state, stage_id)
    items: list[dict] = []
    daily_plan_path = Path(
        _write_json(
            tmp_path / "artifacts" / state.runbook_day_id / "daily_plan.json",
            {
                "schema_version": "paper_daily_plan.v1",
                "account_id": ACCOUNT_ID,
                "data_date": DATA_DATE,
                "trade_date": TRADE_DATE,
                "plan_date": TRADE_DATE,
                "run_mode": "official",
                "official_run": True,
                "generated_at": f"{TRADE_DATE}T00:00:00Z",
                "items": items,
                "execution_intent": build_execution_intent(items),
                "fingerprints": {},
            },
        )
    )
    state = runbook_state.record_artifact(state, "daily_plan_json", str(daily_plan_path), tmp_path)
    gate1_path = _write_json(tmp_path / "gate_runs" / state.runbook_day_id / "gate1.json", {"runner_result": "PASS"})
    state = runbook_state.record_artifact(state, "gate1_readiness_json", gate1_path, tmp_path)
    no_action_path = _write_json(
        tmp_path / "no_action_runs" / state.runbook_day_id / "stage_b_no_action.json",
        {
            "schema_version": "stage_b_no_action.v1",
            "runner_result": "PASS",
            "runbook_day_id": state.runbook_day_id,
            "account_id": ACCOUNT_ID,
            "data_date": DATA_DATE,
            "trade_date": TRADE_DATE,
            "action_mode": "NO_ACTION",
            "execution_required": False,
            "candidate_execution_count": 0,
            "manual_execution_row_count": 0,
            "daily_plan_json": state.artifacts["daily_plan_json"],
            "daily_plan_sha256": sha256_file(daily_plan_path),
            "gate1_readiness_json": state.artifacts["gate1_readiness_json"],
            "skipped_command_keys": [
                "execution_preview",
                "execution_reconciliation_preview",
                "execution_commit",
                "sync_execution_status",
            ],
            "ledger_write_performed": False,
            "notion_write_performed": False,
            "idempotency_record_created": False,
        },
    )
    verification_path = _write_json(
        tmp_path / "verification_runs" / state.runbook_day_id / "stage_b.json",
        {
            "schema_version": "stage_b_verification.v1",
            "runner_result": "PASS",
            "runbook_day_id": state.runbook_day_id,
            "account_id": ACCOUNT_ID,
            "data_date": DATA_DATE,
            "trade_date": TRADE_DATE,
            "action_mode": "NO_ACTION",
            "verified_no_action": True,
            "committed_row_count": 0,
            "updated_count": 0,
            "failed_count": 0,
        },
    )
    stage_c_path = _write_json(
        tmp_path / "stage_runs" / state.runbook_day_id / "stage_c.json",
        {
            "schema_version": "runbook_stage_summary.v1",
            "runner_result": "PASS",
            "stage_id": "C",
            "runbook_day_id": state.runbook_day_id,
            "frozen_context": {
                "account_id": ACCOUNT_ID,
                "data_date": DATA_DATE,
                "trade_date": TRADE_DATE,
            },
            "raw_payload": {
                "action_mode": "NO_ACTION",
                "verified_no_action": True,
                "candidate_execution_count": 0,
                "execution_commit_report_json": None,
            },
        },
    )
    template_path = tmp_path / "artifacts" / state.runbook_day_id / "review_prep" / "template.csv"
    template_path.parent.mkdir(parents=True, exist_ok=True)
    with template_path.open("w", encoding="utf-8-sig", newline="") as handle:
        csv.DictWriter(handle, fieldnames=PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS).writeheader()
    for key, value in (
        ("stage_b_no_action_json", no_action_path),
        ("stage_b_verification_json", verification_path),
        ("stage_c_summary_json", stage_c_path),
        ("manual_review_template_csv", str(template_path)),
    ):
        state = runbook_state.record_artifact(state, key, value, tmp_path)
    state_path = runbook_state.get_state_path_for_context(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    runbook_state.save_state(state, state_path)
    return state


def _row(
    symbol: str = "TDY",
    question_id: str = "execution_review_1",
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
    state = _seed_stage_c_pass_state(
        tmp_path,
        scope_rows=[("TDY", "execution_review_1"), ("CMG", "execution_review_1")],
    )

    result = runbook_gate_checker.check_gate2_readiness(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        row_fetcher=lambda state: [_row("TDY"), _row("CMG")],
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


def test_gate2_execution_without_review_rows_blocks_on_missing_scope(tmp_path: Path) -> None:
    _seed_stage_c_pass_state(tmp_path)

    result = runbook_gate_checker.check_gate2_readiness(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, row_fetcher=lambda state: []
    )

    assert result["runner_result"] == "BLOCKED"
    assert result["action_mode"] == "EXECUTION"


def test_gate2_no_action_without_review_rows_passes_and_completes_step_12(tmp_path: Path) -> None:
    _seed_no_action_stage_c_state(tmp_path)

    result = runbook_gate_checker.check_gate2_readiness(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, row_fetcher=lambda state: []
    )

    assert result["runner_result"] == "PASS"
    assert result["action_mode"] == "NO_ACTION"
    assert result["review_required"] is False
    assert result["manual_review_row_count"] == 0
    assert result["candidate_count"] == 0
    assert result["ready_count"] == 0
    assert result["message"] == "No Manual Review input is required."
    assert result["next_required_action"] == "Run Stage D preview."
    loaded = runbook_state.load_state(
        runbook_state.get_state_path_for_context(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    )
    assert loaded.stage_status["GATE2"] == "PASS"
    assert loaded.last_completed_step == 12
    assert loaded.last_completed_stage == "GATE2"
    assert loaded.last_error is None
    gate_payload = json.loads(Path(result["gate_result_json"]).read_text(encoding="utf-8"))
    latest_payload = json.loads(Path(result["latest_gate_result_json"]).read_text(encoding="utf-8"))
    assert gate_payload == latest_payload
    assert gate_payload["action_mode"] == "NO_ACTION"
    gate_text = Path(result["gate_result_txt"]).read_text(encoding="utf-8")
    assert "Action mode: NO_ACTION" in gate_text
    assert "Review required: False" in gate_text
    assert "Manual review rows: 0" in gate_text


def test_gate2_no_action_with_unexpected_review_row_is_blocked(tmp_path: Path) -> None:
    _seed_no_action_stage_c_state(tmp_path)

    result = runbook_gate_checker.check_gate2_readiness(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, row_fetcher=lambda state: [_row()]
    )

    assert result["runner_result"] == "BLOCKED"
    loaded = runbook_state.load_state(
        runbook_state.get_state_path_for_context(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    )
    assert loaded.last_error["reason"] == "unexpected_manual_review_rows_for_no_action"


def test_gate2_no_action_query_failure_is_blocked(tmp_path: Path) -> None:
    _seed_no_action_stage_c_state(tmp_path)

    def fail_query(state):
        raise RuntimeError("fixture query failure")

    result = runbook_gate_checker.check_gate2_readiness(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, row_fetcher=fail_query
    )

    assert result["runner_result"] == "BLOCKED"
    assert "fixture query failure" in result["message"]


def test_gate2_no_action_blocks_stage_c_action_mode_mismatch(tmp_path: Path) -> None:
    state = _seed_no_action_stage_c_state(tmp_path)
    stage_c_path = tmp_path / state.artifacts["stage_c_summary_json"]
    payload = json.loads(stage_c_path.read_text(encoding="utf-8"))
    payload["raw_payload"]["action_mode"] = "EXECUTION"
    stage_c_path.write_text(json.dumps(payload), encoding="utf-8")

    result = runbook_gate_checker.check_gate2_readiness(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, row_fetcher=lambda state: []
    )

    assert result["runner_result"] == "BLOCKED"
    assert runbook_state.load_state(Path(result["state_path"])).last_error["reason"] == "action_mode_mismatch"


def test_gate2_no_action_blocks_unverified_stage_b(tmp_path: Path) -> None:
    state = _seed_no_action_stage_c_state(tmp_path)
    verification_path = tmp_path / state.artifacts["stage_b_verification_json"]
    payload = json.loads(verification_path.read_text(encoding="utf-8"))
    payload["verified_no_action"] = False
    verification_path.write_text(json.dumps(payload), encoding="utf-8")

    result = runbook_gate_checker.check_gate2_readiness(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, row_fetcher=lambda state: []
    )

    assert result["runner_result"] == "BLOCKED"
    assert runbook_state.load_state(Path(result["state_path"])).last_error["reason"] == "stage_b_no_action_verification_required"


def test_gate2_no_action_blocks_template_data_rows(tmp_path: Path) -> None:
    state = _seed_no_action_stage_c_state(tmp_path)
    template_path = tmp_path / state.artifacts["manual_review_template_csv"]
    row = {column: "" for column in PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS}
    row.update({"review_date": TRADE_DATE, "symbol": "ACCOUNT", "question_id": "Q1"})
    with template_path.open("a", encoding="utf-8-sig", newline="") as handle:
        csv.DictWriter(handle, fieldnames=PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS).writerow(row)

    result = runbook_gate_checker.check_gate2_readiness(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, row_fetcher=lambda state: []
    )

    assert result["runner_result"] == "BLOCKED"
    assert runbook_state.load_state(Path(result["state_path"])).last_error["reason"] == "unexpected_manual_review_template_rows_for_no_action"


def test_gate2_no_action_blocks_daily_plan_hash_mismatch(tmp_path: Path) -> None:
    state = _seed_no_action_stage_c_state(tmp_path)
    daily_plan_path = tmp_path / state.artifacts["daily_plan_json"]
    payload = json.loads(daily_plan_path.read_text(encoding="utf-8"))
    payload["generated_at"] = f"{TRADE_DATE}T01:00:00Z"
    daily_plan_path.write_text(json.dumps(payload), encoding="utf-8")

    result = runbook_gate_checker.check_gate2_readiness(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, row_fetcher=lambda state: []
    )

    assert result["runner_result"] == "BLOCKED"
    assert runbook_state.load_state(Path(result["state_path"])).last_error["reason"] == "daily_plan_hash_mismatch"


def test_gate2_no_action_blocks_verification_context_mismatch(tmp_path: Path) -> None:
    state = _seed_no_action_stage_c_state(tmp_path)
    verification_path = tmp_path / state.artifacts["stage_b_verification_json"]
    payload = json.loads(verification_path.read_text(encoding="utf-8"))
    payload["account_id"] = "paper_other"
    verification_path.write_text(json.dumps(payload), encoding="utf-8")

    result = runbook_gate_checker.check_gate2_readiness(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, row_fetcher=lambda state: []
    )

    assert result["runner_result"] == "BLOCKED"
    assert runbook_state.load_state(Path(result["state_path"])).last_error["reason"] == "stage_b_verification_context_mismatch"


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
    assert all("canonical_scope_mismatch" in row["missing"] for row in payload["rows"])


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
