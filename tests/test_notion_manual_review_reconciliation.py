from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.notion_exporters import (
    build_manual_review_template_properties,
    build_manual_review_template_update_properties,
)
from core.notion_manual_review_reconciliation import (
    ManualReviewReconciliationError,
    apply_manual_review_reconciliation,
    assess_manual_review_reconciliation,
)
from core.paper_daily_review_scope import build_daily_manual_review_scope


ACCOUNT = "paper_pilot_202606"
DATE = "2026-08-10"


def _manifest(tmp_path: Path) -> dict:
    plan = {
        "account_id": ACCOUNT,
        "data_date": "2026-08-07",
        "trade_date": DATE,
        "execution_intent": {"action_mode": "EXECUTION"},
        "manual_review_items": [
            {"symbol": symbol, "state": "REVIEW_EXIT"}
            for symbol in ["AMCR", "AON", "GPN", "INVH", "PAYX"]
        ],
        "items": [],
    }
    current = {
        "current_symbols": ["AMCR", "AON", "GPN", "INVH", "PAYX"],
        "shares": {symbol: 1 for symbol in ["AMCR", "AON", "GPN", "INVH", "PAYX"]},
    }
    execution = ["CMG", "EIX", "EQR", "KHC", "MAA", "UDR"]
    rows = [
        {
            "account_id": ACCOUNT,
            "canonical_key": f"manual_execution:{ACCOUNT}:{DATE}:{symbol}:SELL:01",
            "symbol": symbol,
            "commit_status": "COMMITTED",
            "committed_trade_id": f"id-{index}",
        }
        for index, symbol in enumerate(execution)
    ]
    report = {
        "status": "COMMITTED",
        "account_id": ACCOUNT,
        "execution_date": DATE,
        "committed_row_count": 6,
        "committed_trade_ids": [f"id-{index}" for index in range(6)],
        "committed_rows": rows,
    }
    verification = {
        "schema_version": "stage_b_verification.v1",
        "runner_result": "PASS",
        "runbook_day_id": f"{ACCOUNT}_2026-08-07_{DATE}",
        "account_id": ACCOUNT,
        "data_date": "2026-08-07",
        "trade_date": DATE,
        "action_mode": "EXECUTION",
        "verified_no_action": False,
        "committed_row_count": 6,
        "failed_count": 0,
    }
    paths = []
    for name, payload in (("daily_action_plan_20260810.json", plan), ("paper_current_state_20260810.json", current),
                          ("verification.json", verification), ("commit.json", report)):
        path = tmp_path / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        paths.append(path)
    return build_daily_manual_review_scope(
        runbook_day_id=verification["runbook_day_id"], account_id=ACCOUNT, data_date="2026-08-07",
        trade_date=DATE, daily_plan=plan, current_state=current, stage_b_verification=verification,
        execution_commit_report=report, daily_plan_path=paths[0], current_state_path=paths[1],
        stage_b_verification_path=paths[2], execution_commit_report_path=paths[3],
        generated_at="2026-08-09T00:00:00",
    )


def _row_from_key(key: str, index: int) -> dict:
    _, account, date, symbol, question_id = key.split(":", 4)
    return {
        "page_id": f"page-{index}", "external_key": key, "account_id": account, "review_date": date,
        "symbol": symbol, "question_id": question_id,
    }


def test_incident_assessment_reports_22_14_9_5_13(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    overlap = manifest["canonical_keys"][5:]
    stale_symbols = ["AMCR", "AON", "GPN", "INVH", "PAYX", "AMT", "AVB", "BF-B", "CCI", "CCL", "PLD", "SW", "TDY"]
    stale = [f"manual_review:{ACCOUNT}:{DATE}:{symbol}:execution_review_1" for symbol in stale_symbols]
    existing = [_row_from_key(key, index) for index, key in enumerate([*overlap, *stale])]
    result = assess_manual_review_reconciliation(existing, manifest)
    assert (result["active_existing_count"], result["desired_count"]) == (22, 14)
    assert (result["overlap_count"], result["missing_count"], result["stale_count"]) == (9, 5, 13)
    assert result["duplicate_count"] == 0


def test_normal_update_properties_preserve_all_human_progress_fields() -> None:
    mapping = {name: name for name in (
        "name", "external_key", "account_id", "review_date", "symbol", "question_id", "question",
        "manual_answer", "review_status", "follow_up_needed", "review_tag", "reviewer_note", "source_template_key", "import_status",
    )}
    row = {"symbol": "AAPL", "question_id": "execution_review_1", "question_text": "Q", "review_tag": "execution_quality", "source_worksheet_path": "scope"}
    create = build_manual_review_template_properties(
        row, mapping, account_id=ACCOUNT, review_date=DATE, external_key="key"
    )
    update = build_manual_review_template_update_properties(
        row, mapping, account_id=ACCOUNT, review_date=DATE, external_key="key"
    )
    human_fields = {"manual_answer", "review_status", "follow_up_needed", "review_tag", "reviewer_note", "import_status"}
    assert human_fields.isdisjoint(update)
    assert human_fields.issubset(create)
    assert create["review_tag"] == {"multi_select": [{"name": "execution_quality"}]}


def test_explicit_apply_creates_before_archive_and_never_hard_deletes(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    desired = manifest["canonical_keys"]
    stale_key = f"manual_review:{ACCOUNT}:{DATE}:STALE:execution_review_1"
    rows = [_row_from_key(key, index) for index, key in enumerate(desired[:-1])]
    rows.append(_row_from_key(stale_key, 99))
    events: list[str] = []

    def create(row):
        events.append(f"create:{row['canonical_key']}")
        rows.append(_row_from_key(row["canonical_key"], 100))
        return "page-100"

    def archive(page_id):
        events.append(f"archive:{page_id}")

    result = apply_manual_review_reconciliation(
        existing_rows=list(rows), scope_manifest=manifest, confirmed_scope_sha256=manifest["scope_sha256"],
        create_row=create, archive_page=archive, fetch_rows=lambda: list(rows),
    )
    assert result["runner_result"] == "PASS"
    assert events[0].startswith("create:") and events[1].startswith("archive:")
    assert result["hard_deleted_count"] == 0


def test_canonical_create_failure_prevents_archive(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    rows = [_row_from_key(manifest["canonical_keys"][0], 1)]
    archived: list[str] = []
    result = apply_manual_review_reconciliation(
        existing_rows=rows, scope_manifest=manifest, confirmed_scope_sha256=manifest["scope_sha256"],
        create_row=lambda row: (_ for _ in ()).throw(RuntimeError("create failed")),
        archive_page=archived.append, fetch_rows=lambda: rows,
    )
    assert result["runner_result"] == "FAILED"
    assert result["archive_started"] is False and archived == []


def test_duplicate_or_scope_sha_mismatch_fails_closed(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    duplicate = _row_from_key(manifest["canonical_keys"][0], 1)
    with pytest.raises(ManualReviewReconciliationError, match="Duplicate"):
        apply_manual_review_reconciliation(
            existing_rows=[duplicate, {**duplicate, "page_id": "page-2"}], scope_manifest=manifest,
            confirmed_scope_sha256=manifest["scope_sha256"], create_row=lambda row: "", archive_page=lambda page: None,
            fetch_rows=lambda: [],
        )
    with pytest.raises(ManualReviewReconciliationError, match="SHA"):
        apply_manual_review_reconciliation(
            existing_rows=[], scope_manifest=manifest, confirmed_scope_sha256="wrong", create_row=lambda row: "",
            archive_page=lambda page: None, fetch_rows=lambda: [],
        )


def test_partial_archive_failure_is_reported(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    stale1 = _row_from_key(f"manual_review:{ACCOUNT}:{DATE}:STALE1:execution_review_1", 90)
    stale2 = _row_from_key(f"manual_review:{ACCOUNT}:{DATE}:STALE2:execution_review_1", 91)
    rows = [_row_from_key(key, index) for index, key in enumerate(manifest["canonical_keys"])] + [stale1, stale2]

    def archive(page_id):
        if page_id == "page-91":
            raise RuntimeError("archive failed")

    result = apply_manual_review_reconciliation(
        existing_rows=rows, scope_manifest=manifest, confirmed_scope_sha256=manifest["scope_sha256"],
        create_row=lambda row: "", archive_page=archive, fetch_rows=lambda: rows,
    )
    assert result["runner_result"] == "FAILED"
    assert result["archived_count"] == 1 and result["archive_failed_count"] == 1
