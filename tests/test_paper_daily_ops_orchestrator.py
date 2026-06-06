from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.paper_daily_ops_orchestrator import build_daily_ops_status
from scripts import paper_daily_ops


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    _write(path, json.dumps(payload, indent=2))


def _stage(payload: dict, name: str) -> dict:
    return next(stage for stage in payload["stages"] if stage["stage_name"] == name)


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "paper_accounts" / "paper_ops"
    (root / "reports").mkdir(parents=True)
    (root / "reviews").mkdir()
    (root / "config_snapshots").mkdir()
    return root


def _legacy_root(tmp_path: Path) -> Path:
    root = tmp_path / "paper_test"
    (root / "reports").mkdir(parents=True)
    (root / "reviews").mkdir()
    (root / "config_snapshots").mkdir()
    return root


def _base_kwargs(root: Path, legacy: Path) -> dict:
    return {
        "account_id": "paper_ops",
        "data_date": "2026-06-05",
        "trade_date": "2026-06-08",
        "account_root": root,
        "legacy_root": legacy,
    }


def _write_plan(root: Path) -> None:
    _write(root / "daily_action_plan_20260608.md", "# plan\n")
    _write_json(
        root / "daily_action_plan_20260608.json",
        {
            "account_id": "paper_ops",
            "data_date": "2026-06-05",
            "trade_date": "2026-06-08",
            "plan_date": "2026-06-08",
        },
    )
    _write_json(root / "config_snapshots" / "paper_config_snapshot_20260608.json", {"ok": True})


def _write_execution_preview(root: Path) -> None:
    _write_json(
        root / "reports" / "manual_execution_import_preview_20260608.json",
        {
            "account_id": "paper_ops",
            "execution_date": "2026-06-08",
            "candidate_count": 1,
            "fail_count": 0,
            "commit_allowed": "true",
            "candidates": [],
        },
    )


def _write_execution_commit(root: Path) -> None:
    _write_json(
        root / "reports" / "manual_execution_import_commit_20260608.json",
        {
            "account_id": "paper_ops",
            "execution_date": "2026-06-08",
            "committed_rows": [],
        },
    )
    _write(root / "paper_current_state_20260608.json", "{}\n")
    _write(
        root / "paper_account_snapshot.csv",
        "snapshot_date,cash,total_equity_market_value,unrealized_pnl,position_count,symbols\n"
        "2026-06-08,100,100,0,0,\n",
    )
    _write(root / "paper_position_snapshot.csv", "snapshot_date,symbol\n2026-06-08,AAPL\n")
    _write(
        root / "paper_execution_log.csv",
        "date,source,symbol\n2026-06-08,notion_manual_execution,AAPL\n",
    )


def _write_review_ready(root: Path) -> None:
    _write(root / "reports" / "paper_daily_review_summary.md", "# summary\n")
    _write(root / "reports" / "paper_performance_summary.md", "# perf\n")
    _write(
        root / "reviews" / "paper_manual_review_log_template.csv",
        "review_date,symbol,question_id,manual_answer,review_status\n"
        "2026-06-08,AAPL,Q1,,pending\n",
    )
    _write(
        root / "reviews" / "paper_manual_review_log_validation_report.md",
        "# validation\n\n- Validation result: PASS\n",
    )


def _write_review_preview(root: Path) -> None:
    _write_json(
        root / "reports" / "manual_review_import_preview_20260608.json",
        {
            "account_id": "paper_ops",
            "review_date": "2026-06-08",
            "candidate_count": 1,
            "fail_count": 0,
            "append_allowed": "true",
            "duplicate_candidates": [],
            "candidates": [],
        },
    )


def _write_review_commit(root: Path) -> None:
    _write_json(
        root / "reports" / "manual_review_import_commit_20260608.json",
        {
            "account_id": "paper_ops",
            "review_date": "2026-06-08",
            "rows": [],
        },
    )
    _write(
        root / "reviews" / "paper_manual_review_log.csv",
        "review_date,symbol,question_id,manual_answer,review_status\n"
        "2026-06-08,AAPL,Q1,done,reviewed\n",
    )


def test_account_id_missing_is_blocked():
    with pytest.raises(ValueError, match="account_id is required"):
        build_daily_ops_status(account_id="", data_date="2026-06-05", trade_date="2026-06-08")


def test_data_or_trade_date_missing_is_blocked():
    with pytest.raises(ValueError, match="data_date is required"):
        build_daily_ops_status(account_id="paper_ops", data_date="", trade_date="2026-06-08")
    with pytest.raises(ValueError, match="trade_date is required"):
        build_daily_ops_status(account_id="paper_ops", data_date="2026-06-05", trade_date="")


def test_trade_date_must_be_after_data_date(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    payload = build_daily_ops_status(
        account_id="paper_ops",
        data_date="2026-06-08",
        trade_date="2026-06-08",
        account_root=root,
        legacy_root=legacy,
    )
    assert payload["overall_status"] == "BLOCKED"
    assert payload["guards"]["trade_date_after_data_date"] is False


def test_normal_input_generates_stage_list_and_read_only_flags(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    payload = build_daily_ops_status(**_base_kwargs(root, legacy))

    assert [stage["stage_name"] for stage in payload["stages"]]
    assert len(payload["stages"]) == 13
    assert payload["read_only"] is True
    assert payload["write_executed"] is False
    assert payload["notion_api_called"] is False
    assert payload["commit_append_executed"] is False


def test_non_default_legacy_paper_test_plan_blocks_daily_plan_evidence(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write(legacy / "daily_action_plan_20260608.md", "# legacy\n")
    _write_json(legacy / "daily_action_plan_20260608.json", {"account_id": "paper_default"})
    _write_json(legacy / "config_snapshots" / "paper_config_snapshot_20260608.json", {})

    payload = build_daily_ops_status(**_base_kwargs(root, legacy))

    assert payload["paper_test_artifacts_detected"] is True
    assert _stage(payload, "DAILY_PLAN")["status"] == "BLOCKED"
    assert _stage(payload, "DAILY_PLAN")["existing_artifacts"] == []


def test_paper_test_artifact_is_not_done_evidence_for_non_default(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write(legacy / "reports" / "manual_execution_import_preview_20260608.json", "{}")

    payload = build_daily_ops_status(**_base_kwargs(root, legacy))

    preview_stage = _stage(payload, "MANUAL_EXECUTION_PREVIEW")
    assert preview_stage["status"] == "BLOCKED"
    assert preview_stage["existing_artifacts"] == []


def test_preview_without_commit_does_not_recommend_commit_when_preview_missing(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write_plan(root)

    payload = build_daily_ops_status(**_base_kwargs(root, legacy))

    commit_stage = _stage(payload, "MANUAL_EXECUTION_COMMIT")
    assert commit_stage["status"] == "BLOCKED"
    assert commit_stage["next_command"] is None


def test_existing_execution_commit_suppresses_commit_recommendation(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write_plan(root)
    _write_execution_preview(root)
    _write_execution_commit(root)

    payload = build_daily_ops_status(**_base_kwargs(root, legacy))

    commit_stage = _stage(payload, "MANUAL_EXECUTION_COMMIT")
    assert commit_stage["status"] == "DONE"
    assert commit_stage["next_command"] is None


def test_existing_review_append_suppresses_append_recommendation(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write_plan(root)
    _write_execution_preview(root)
    _write_execution_commit(root)
    _write_review_ready(root)
    _write_review_preview(root)
    _write_review_commit(root)

    payload = build_daily_ops_status(**_base_kwargs(root, legacy))

    append_stage = _stage(payload, "MANUAL_REVIEW_APPEND")
    assert append_stage["status"] == "DONE"
    assert append_stage["next_command"] is None


def test_review_done_has_no_commit_or_append_next_command(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write_plan(root)
    _write_execution_preview(root)
    _write_execution_commit(root)
    _write_review_ready(root)
    _write_review_preview(root)
    _write_review_commit(root)

    payload = build_daily_ops_status(**_base_kwargs(root, legacy))

    assert payload["workflow_status"] == "REVIEW_DONE"
    assert payload["next_command"] is None
    commands = [stage["next_command"] or "" for stage in payload["stages"]]
    assert all(command == "" for command in commands)
    assert not any(" --commit " in command for command in commands)
    assert not any("review-append" in command for command in commands)


def test_cli_json_output_is_parseable(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)

    exit_code = paper_daily_ops.main(
        [
            "status",
            "--account-id",
            "paper_ops",
            "--data-date",
            "2026-06-05",
            "--trade-date",
            "2026-06-08",
            "--account-root",
            str(root),
            "--legacy-root",
            str(legacy),
            "--json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["account_id"] == "paper_ops"
    assert payload["read_only"] is True
