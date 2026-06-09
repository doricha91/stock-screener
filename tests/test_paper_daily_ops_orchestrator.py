from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.paper_daily_ops_evidence import (
    EVIDENCE_DAILY_PLAN_NOTION_EXPORT,
    EVIDENCE_MANUAL_EXECUTION_STATUS_SYNC,
    EVIDENCE_MANUAL_EXECUTION_TEMPLATE,
    EVIDENCE_MANUAL_REVIEW_STATUS_SYNC,
    EVIDENCE_MANUAL_REVIEW_TEMPLATE,
    notion_evidence_path,
)
from core.notion_client import NotionAPIError
from core.notion_settings import NotionSettings
from core.paper_daily_ops_notion_status import build_notion_live_read_status
from core.paper_daily_ops_orchestrator import build_daily_ops_status
from scripts import paper_daily_ops


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    _write(path, json.dumps(payload, indent=2))


def _stage(payload: dict, name: str) -> dict:
    return next(stage for stage in payload["stages"] if stage["stage_name"] == name)


def _assert_operator_next(payload: dict, stage_name: str, command_fragment: str | None) -> None:
    assert payload["operator_summary"]["current_step"] == stage_name
    assert payload["operator_summary"]["next_command"] == payload["next_command"]
    if command_fragment is None:
        assert payload["next_command"] is None
    else:
        assert command_fragment in payload["next_command"]


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


def _write_notion_evidence(
    root: Path,
    evidence_type: str,
    *,
    status: str = "PASS",
    account_id: str = "paper_ops",
    trade_date: str = "2026-06-08",
    data_date: str | None = "2026-06-05",
    failed_count: int = 0,
) -> Path:
    path = notion_evidence_path(root, evidence_type, trade_date)
    operation = "sync" if evidence_type.endswith("STATUS_SYNC") else "export"
    _write_json(
        path,
        {
            "schema_version": "paper_notion_evidence.v1",
            "evidence_type": evidence_type,
            "account_id": account_id,
            "trade_date": trade_date,
            "data_date": data_date,
            "source_command": "python scripts\\example.py --json",
            "source_artifacts": [],
            "target_system": "notion",
            "operation": operation,
            "dry_run": False,
            "actual_executed": True,
            "notion_api_called": True,
            "write_executed": True,
            "status": status,
            "page_count": 1,
            "created_count": 0,
            "updated_count": 1,
            "skipped_count": 0,
            "failed_count": failed_count,
            "warnings": ["operator should review"] if status == "WARNING" else [],
            "errors": ["notion write failed"] if status == "FAILED" or failed_count else [],
            "created_at": "2026-06-08T09:00:00+09:00",
            "producer": "test",
        },
    )
    return path


def _notion_stage_report(
    status: str,
    *,
    row_count: int = 1,
    status_counts: dict[str, int] | None = None,
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
    details: dict | None = None,
) -> dict:
    return {
        "status": status,
        "row_count": row_count,
        "status_counts": status_counts or {},
        "errors": errors or [],
        "warnings": warnings or [],
        "details": details or {},
    }


def _notion_report(stages: dict[str, dict], *, status: str = "PASS") -> dict:
    return {
        "enabled": True,
        "called": True,
        "status": status,
        "errors": [],
        "warnings": [],
        "summary": {"stage_status_counts": {status: len(stages)}, "total_row_count": len(stages)},
        "stages": stages,
    }


def _notion_property(value: str, kind: str) -> dict:
    if kind == "select":
        return {"type": "select", "select": {"name": value}}
    if kind == "date":
        return {"type": "date", "date": {"start": value}}
    if kind == "number":
        return {"type": "number", "number": float(value)}
    return {"type": "rich_text", "rich_text": [{"plain_text": value}]}


def _fake_notion_page(*, account_id: str = "paper_ops", date_key: str, date_value: str, status: str = "SYNCED") -> dict:
    return {
        "id": f"page-{date_key}",
        "properties": {
            "Account ID": _notion_property(account_id, "select"),
            "Plan Date": _notion_property(date_value, "date"),
            "Execution Date": _notion_property(date_value, "date"),
            "Review Date": _notion_property(date_value, "date"),
            "Status": _notion_property(status, "select"),
            "Import Status": _notion_property(status, "select"),
            "Review Status": _notion_property(status.lower(), "select"),
            "Sync Status": _notion_property(status, "select"),
            "Actual Price": _notion_property("100", "number"),
        },
    }


class _FakeNotionClient:
    def __init__(self, pages: list[dict] | None = None, exc: Exception | None = None) -> None:
        self.pages = pages or []
        self.exc = exc
        self.calls: list[tuple[str, dict | None]] = []
        self.external_key_calls: list[tuple[str, str, str]] = []

    def query_by_external_key(
        self,
        data_source_id: str,
        external_key: str,
        external_key_property: str,
    ) -> list[dict]:
        self.external_key_calls.append((data_source_id, external_key, external_key_property))
        if self.exc:
            raise self.exc
        return list(self.pages)

    def query_data_source(self, data_source_id: str, *, filter_payload: dict | None = None, **_: object) -> list[dict]:
        self.calls.append((data_source_id, filter_payload))
        if self.exc:
            raise self.exc
        return list(self.pages)


def _notion_settings() -> NotionSettings:
    return NotionSettings(
        enabled=True,
        token_env="NOTION_TOKEN",
        data_sources={
            "daily_plans": "daily-plans",
            "manual_executions": "manual-executions",
            "manual_reviews": "manual-reviews",
        },
    )


def _notion_mapping() -> dict[str, dict[str, str]]:
    return {
        "daily_plans": {
            "external_key": "External Key",
            "account_id": "Account ID",
            "plan_date": "Plan Date",
            "sync_status": "Sync Status",
        },
        "manual_executions": {
            "account_id": "Account ID",
            "execution_date": "Execution Date",
            "status": "Status",
            "import_status": "Import Status",
            "actual_price": "Actual Price",
        },
        "manual_reviews": {
            "account_id": "Account ID",
            "review_date": "Review Date",
            "review_status": "Review Status",
            "import_status": "Import Status",
            "manual_answer": "Manual Answer",
        },
    }


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
    assert payload["operation_write_executed"] is False
    assert payload["notion_api_called"] is False
    assert payload["notion_live_read_enabled"] is False
    assert payload["notion_live_read_called"] is False
    assert payload["notion_live_read_status"] == "SKIPPED"
    assert payload["commit_append_executed"] is False
    assert payload["status_report_written"] is False
    assert payload["status_report_path"] is None
    assert "next_action" in payload
    assert "summary" in payload
    assert "stage_counts" in payload
    assert "operator_summary" in payload
    assert payload["reconciliation_summary"]["checked"] is False
    assert all("notion_checked" in stage for stage in payload["stages"])
    assert all("reconciliation_checked" in stage for stage in payload["stages"])

    operator_summary = payload["operator_summary"]
    assert operator_summary["current_step"] == "DATA_FRESHNESS"
    assert operator_summary["current_step_status"] == "READY"
    assert operator_summary["next_command"] == payload["next_command"]
    assert operator_summary["command_type"] == payload["next_action"]["command_type"]
    assert operator_summary["risk_level"] == payload["next_action"]["risk_level"]
    assert operator_summary["requires_manual_approval"] == payload["next_action"]["requires_manual_approval"]
    assert operator_summary["warnings"] == payload["warnings"]
    assert operator_summary["blockers"] == payload["blockers"]
    assert operator_summary["ready_count"] == payload["stage_counts"]["READY"]
    assert operator_summary["blocked_count"] == payload["stage_counts"]["BLOCKED"]
    assert operator_summary["warning_count"] == payload["stage_counts"]["WARNING"]
    assert operator_summary["done_count"] == payload["stage_counts"]["DONE"]
    assert operator_summary["unknown_count"] == payload["stage_counts"]["UNKNOWN"]


def test_notion_live_read_module_uses_read_only_client():
    page = _fake_notion_page(date_key="plan_date", date_value="2026-06-08")
    client = _FakeNotionClient([page])

    report = build_notion_live_read_status(
        account_id="paper_ops",
        data_date="2026-06-05",
        trade_date="2026-06-08",
        client=client,
        settings=_notion_settings(),
        mapping_root=_notion_mapping(),
        env={},
    )

    assert report["called"] is True
    assert client.calls
    assert client.external_key_calls == [("daily-plans", "daily_plan:paper_ops:2026-06-08", "External Key")]
    assert len(client.calls) == 6
    assert report["stages"]["DAILY_PLAN_NOTION_EXPORT"]["row_count"] == 1


def test_notion_live_read_env_only_settings_are_allowed_when_overrides_exist():
    page = _fake_notion_page(date_key="plan_date", date_value="2026-06-08")
    client = _FakeNotionClient([page])
    env = {
        "NOTION_TOKEN": "test-token",
        "NOTION_DAILY_PLANS_DATA_SOURCE_ID": "env-daily-plans",
        "NOTION_MANUAL_EXECUTIONS_DATA_SOURCE_ID": "env-manual-executions",
        "NOTION_MANUAL_REVIEWS_DATA_SOURCE_ID": "env-manual-reviews",
    }

    report = build_notion_live_read_status(
        account_id="paper_ops",
        data_date="2026-06-05",
        trade_date="2026-06-08",
        client=client,
        settings=NotionSettings(enabled=False, token_env="NOTION_TOKEN", data_sources={}),
        mapping_root=_notion_mapping(),
        env=env,
    )

    assert report["called"] is True
    assert report["status"] in {"PASS", "WARNING", "UNKNOWN"}
    assert report["errors"] == []
    assert client.external_key_calls == [("env-daily-plans", "daily_plan:paper_ops:2026-06-08", "External Key")]
    assert {call[0] for call in client.calls} == {
        "env-manual-executions",
        "env-manual-reviews",
    }


def test_notion_live_read_disabled_settings_is_blocked():
    report = build_notion_live_read_status(
        account_id="paper_ops",
        data_date="2026-06-05",
        trade_date="2026-06-08",
        client=_FakeNotionClient(),
        settings=NotionSettings(enabled=False, token_env="NOTION_TOKEN", data_sources={}),
        mapping_root=_notion_mapping(),
        env={},
    )

    assert report["called"] is True
    assert report["status"] == "BLOCKED"
    assert report["errors"]
    assert "Missing Notion token in environment variable: NOTION_TOKEN." in report["errors"][0]


def test_notion_live_read_env_only_missing_token_is_blocked():
    report = build_notion_live_read_status(
        account_id="paper_ops",
        data_date="2026-06-05",
        trade_date="2026-06-08",
        client=_FakeNotionClient(),
        settings=NotionSettings(enabled=False, token_env="NOTION_TOKEN", data_sources={}),
        mapping_root=_notion_mapping(),
        env={
            "NOTION_DAILY_PLANS_DATA_SOURCE_ID": "env-daily-plans",
            "NOTION_MANUAL_EXECUTIONS_DATA_SOURCE_ID": "env-manual-executions",
            "NOTION_MANUAL_REVIEWS_DATA_SOURCE_ID": "env-manual-reviews",
        },
    )

    assert report["status"] == "BLOCKED"
    assert report["errors"] == ["Missing Notion token in environment variable: NOTION_TOKEN."]


def test_notion_live_read_env_only_missing_data_source_names_key():
    report = build_notion_live_read_status(
        account_id="paper_ops",
        data_date="2026-06-05",
        trade_date="2026-06-08",
        client=_FakeNotionClient(),
        settings=NotionSettings(enabled=False, token_env="NOTION_TOKEN", data_sources={}),
        mapping_root=_notion_mapping(),
        env={
            "NOTION_TOKEN": "test-token",
            "NOTION_DAILY_PLANS_DATA_SOURCE_ID": "env-daily-plans",
            "NOTION_MANUAL_EXECUTIONS_DATA_SOURCE_ID": "env-manual-executions",
        },
    )

    assert report["status"] == "BLOCKED"
    assert "Missing required Notion env override: NOTION_MANUAL_REVIEWS_DATA_SOURCE_ID." in report["errors"][0]


def test_status_cli_loads_root_dotenv_for_notion_read(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture):
    calls: list[str] = []

    def fake_load_dotenv() -> None:
        calls.append("loaded")

    def fake_build_status(**kwargs: object) -> dict:
        assert kwargs["include_notion_read"] is True
        return {
            "schema_version": "mfu_oper9_daily_ops_status.v1",
            "overall_status": "PASS",
            "account_id": kwargs["account_id"],
            "data_date": "2026-06-05",
            "trade_date": "2026-06-08",
            "next_command": None,
            "stages": [],
        }

    monkeypatch.setattr(paper_daily_ops, "_load_root_dotenv", fake_load_dotenv)
    monkeypatch.setattr(paper_daily_ops, "build_daily_ops_status", fake_build_status)

    exit_code = paper_daily_ops.main(
        [
            "status",
            "--account-id",
            "paper_ops",
            "--data-date",
            "2026-06-05",
            "--trade-date",
            "2026-06-08",
            "--include-notion-read",
            "--json",
        ]
    )

    assert exit_code == 0
    assert calls == ["loaded"]
    assert json.loads(capsys.readouterr().out)["overall_status"] == "PASS"


def test_notion_live_read_api_exception_is_json_safe():
    report = build_notion_live_read_status(
        account_id="paper_ops",
        data_date="2026-06-05",
        trade_date="2026-06-08",
        client=_FakeNotionClient(exc=NotionAPIError("read failed")),
        settings=_notion_settings(),
        mapping_root=_notion_mapping(),
    )

    assert report["called"] is True
    assert report["status"] == "WARNING"
    assert report["errors"] == []
    assert "Notion live read failed with an API warning; check Notion connectivity and schema configuration." in report["warnings"]


def test_notion_account_select_option_missing_warning_is_structured():
    exc = NotionAPIError(
        "POST /data_sources/<redacted>/query failed -> HTTP 400",
        status_code=400,
        response_body='{"message":"Option \\"paper_ops\\" not found for property \\"Account ID\\" select."}',
    )

    report = build_notion_live_read_status(
        account_id="paper_ops",
        data_date="2026-06-05",
        trade_date="2026-06-08",
        client=_FakeNotionClient(exc=exc),
        settings=_notion_settings(),
        mapping_root=_notion_mapping(),
        env={"NOTION_TOKEN": "token"},
    )

    stage = report["stages"]["MANUAL_EXECUTION_TEMPLATE"]
    assert report["status"] == "WARNING"
    assert stage["status"] == "WARNING"
    assert stage["errors"] == []
    assert stage["warnings"] == [
        "Notion Account ID select option may be missing for this account; account-filtered live read returned HTTP 400."
    ]
    assert stage["details"]["warning_code"] == "NOTION_ACCOUNT_ID_SELECT_OPTION_MISSING"


def test_account_select_option_warning_does_not_block_current_actionable_stage(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write_plan(root)

    payload = build_daily_ops_status(
        **_base_kwargs(root, legacy),
        include_notion_read=True,
        notion_status_report=_notion_report(
            {
                "MANUAL_EXECUTION_TEMPLATE": _notion_stage_report(
                    "WARNING",
                    row_count=0,
                    warnings=[
                        "Notion Account ID select option may be missing for this account; account-filtered live read returned HTTP 400."
                    ],
                    details={"warning_code": "NOTION_ACCOUNT_ID_SELECT_OPTION_MISSING"},
                )
            },
            status="WARNING",
        ),
    )

    assert payload["operator_summary"]["current_step"] == "DAILY_PLAN_NOTION_EXPORT"
    assert payload["operator_summary"]["recommended_operator_action"] == "RUN_NEXT_COMMAND"
    assert payload["operator_summary"]["has_reconciliation_conflicts"] is False
    assert "Notion Account ID select option may be missing for this account." in payload["operator_summary"]["warnings"]


def test_include_notion_read_improves_daily_plan_export_stage(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write_plan(root)

    payload = build_daily_ops_status(
        **_base_kwargs(root, legacy),
        include_notion_read=True,
        notion_status_report=_notion_report(
            {"DAILY_PLAN_NOTION_EXPORT": _notion_stage_report("PASS", status_counts={"SYNCED": 1})}
        ),
    )
    stage = _stage(payload, "DAILY_PLAN_NOTION_EXPORT")

    assert payload["notion_live_read_enabled"] is True
    assert payload["notion_live_read_called"] is True
    assert stage["status"] == "DONE"
    assert stage["notion_checked"] is True
    assert stage["notion_row_count"] == 1
    assert stage["local_stage_status"] == "UNKNOWN"
    assert stage["reconciliation_status"] == "DONE"
    assert stage["reconciliation_rule_id"] == "OPER9_6_DAILY_PLAN_LOCAL_AND_NOTION_PRESENT"


def test_notion_ready_manual_execution_preserves_preview_recommendation(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write_plan(root)

    payload = build_daily_ops_status(
        **_base_kwargs(root, legacy),
        include_notion_read=True,
        notion_status_report=_notion_report(
            {"MANUAL_EXECUTION_PREVIEW": _notion_stage_report("PASS", status_counts={"READY": 1})}
        ),
    )
    stage = _stage(payload, "MANUAL_EXECUTION_PREVIEW")

    assert stage["status"] == "READY"
    assert stage["next_action"]["command_type"] == "READ_ONLY"
    assert stage["notion_checked"] is True
    assert stage["reconciliation_status"] == "READY"
    assert payload["reconciliation_summary"]["recommended_operator_action"] == "RUN_PREVIEW"
    assert payload["operator_summary"]["recommended_operator_action"] == "RUN_NEXT_COMMAND"
    assert payload["operator_summary"]["current_step"] == "DAILY_PLAN_NOTION_EXPORT"


def test_plan_ready_advances_past_data_freshness_for_top_level_next_command(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write_plan(root)

    payload = build_daily_ops_status(**_base_kwargs(root, legacy))

    assert payload["workflow_status"] == "PLAN_READY"
    assert _stage(payload, "DATA_FRESHNESS")["status"] == "READY"
    assert _stage(payload, "DAILY_PLAN")["status"] == "DONE"
    assert payload["next_command"] != _stage(payload, "DATA_FRESHNESS")["next_command"]
    assert "data-freshness" not in payload["next_command"]
    assert payload["operator_summary"]["current_step"] != "DATA_FRESHNESS"
    assert payload["operator_summary"]["operator_message"] != (
        "Data freshness check is ready. Run the read-only freshness command first."
    )
    assert payload["operator_summary"]["next_command"] == payload["next_command"]
    assert payload["operator_summary"]["current_step"] == "DAILY_PLAN_NOTION_EXPORT"
    assert "export_paper_to_notion.py" in payload["next_command"]


def test_plan_ready_does_not_skip_to_downstream_preview_when_plan_export_is_pending(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write_plan(root)

    payload = build_daily_ops_status(**_base_kwargs(root, legacy))

    assert _stage(payload, "MANUAL_EXECUTION_PREVIEW")["status"] == "READY"
    assert payload["operator_summary"]["current_step"] == "DAILY_PLAN_NOTION_EXPORT"
    assert "import_notion_executions.py" not in payload["next_command"]


def test_plan_ready_legacy_warning_does_not_rewind_to_data_freshness(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write_plan(root)
    _write(legacy / "reports" / "manual_execution_import_preview_20260608.json", "{}")

    payload = build_daily_ops_status(**_base_kwargs(root, legacy))

    assert payload["paper_test_artifacts_detected"] is True
    assert payload["warnings"]
    assert payload["operator_summary"]["current_step"] == "DAILY_PLAN_NOTION_EXPORT"
    assert "data-freshness" not in payload["operator_summary"]["next_command"]


def test_stage_advancement_matrix_initial_no_plan_uses_initial_step(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)

    payload = build_daily_ops_status(**_base_kwargs(root, legacy))

    _assert_operator_next(payload, "DATA_FRESHNESS", "data-freshness")
    assert payload["operator_summary"]["recommended_operator_action"] == "RUN_NEXT_COMMAND"
    assert payload["operator_summary"]["risk_level"] == "SAFE"


def test_stage_advancement_matrix_plan_export_then_execution_template(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write_plan(root)

    plan_ready = build_daily_ops_status(**_base_kwargs(root, legacy))
    _assert_operator_next(plan_ready, "DAILY_PLAN_NOTION_EXPORT", "export_paper_to_notion.py --daily-plan")
    assert "data-freshness" not in plan_ready["next_command"]

    _write_notion_evidence(root, EVIDENCE_DAILY_PLAN_NOTION_EXPORT)
    export_done = build_daily_ops_status(**_base_kwargs(root, legacy))
    _assert_operator_next(export_done, "MANUAL_EXECUTION_TEMPLATE", "--manual-execution-template")


def test_stage_advancement_matrix_execution_template_gates_preview(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write_plan(root)
    _write_notion_evidence(root, EVIDENCE_DAILY_PLAN_NOTION_EXPORT)
    _write_execution_preview(root)

    template_missing = build_daily_ops_status(**_base_kwargs(root, legacy))
    _assert_operator_next(template_missing, "MANUAL_EXECUTION_TEMPLATE", "--manual-execution-template")
    assert "import_notion_executions.py" not in template_missing["next_command"]

    _write_notion_evidence(root, EVIDENCE_MANUAL_EXECUTION_TEMPLATE)
    template_done = build_daily_ops_status(**_base_kwargs(root, legacy))
    _assert_operator_next(template_done, "MANUAL_EXECUTION_COMMIT", "import_notion_executions.py")
    assert "--commit" in template_done["next_command"]


def test_stage_advancement_matrix_execution_preview_to_commit_to_sync_to_review(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write_plan(root)
    _write_notion_evidence(root, EVIDENCE_DAILY_PLAN_NOTION_EXPORT)
    _write_notion_evidence(root, EVIDENCE_MANUAL_EXECUTION_TEMPLATE)

    ready_for_preview = build_daily_ops_status(
        **_base_kwargs(root, legacy),
        include_notion_read=True,
        notion_status_report=_notion_report(
            {"MANUAL_EXECUTION_PREVIEW": _notion_stage_report("PASS", status_counts={"READY": 1})}
        ),
    )
    _assert_operator_next(ready_for_preview, "MANUAL_EXECUTION_PREVIEW", "import_notion_executions.py")
    assert "--preview" in ready_for_preview["next_command"]

    _write_execution_preview(root)
    preview_done = build_daily_ops_status(**_base_kwargs(root, legacy))
    _assert_operator_next(preview_done, "MANUAL_EXECUTION_COMMIT", "import_notion_executions.py")
    assert "--commit" in preview_done["next_command"]

    _write_execution_commit(root)
    commit_done = build_daily_ops_status(**_base_kwargs(root, legacy))
    _assert_operator_next(commit_done, "MANUAL_EXECUTION_STATUS_SYNC", "sync_notion_execution_status.py")
    assert commit_done["operator_summary"]["requires_manual_approval"] is True

    _write_notion_evidence(root, EVIDENCE_MANUAL_EXECUTION_STATUS_SYNC)
    sync_done = build_daily_ops_status(**_base_kwargs(root, legacy))
    _assert_operator_next(sync_done, "DAILY_REVIEW", "paper.py review")


def test_manual_execution_draft_rows_wait_for_notion_input(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write_plan(root)
    _write_notion_evidence(root, EVIDENCE_DAILY_PLAN_NOTION_EXPORT)
    _write_notion_evidence(root, EVIDENCE_MANUAL_EXECUTION_TEMPLATE)

    payload = build_daily_ops_status(
        **_base_kwargs(root, legacy),
        include_notion_read=True,
        notion_status_report=_notion_report(
            {
                "MANUAL_EXECUTION_TEMPLATE": _notion_stage_report(
                    "PASS",
                    row_count=3,
                    status_counts={"DRAFT": 3, "NOT_IMPORTED": 3},
                    details={"missing_actual_price_count": 3},
                )
            }
        ),
    )

    assert payload["next_command"] is None
    assert payload["operator_summary"]["current_step"] == "MANUAL_EXECUTION_TEMPLATE"
    assert payload["operator_summary"]["current_step"] != "FINAL_STATUS"
    assert payload["operator_summary"]["recommended_operator_action"] == "WAIT_FOR_INPUT"
    assert payload["operator_summary"]["next_command"] is None
    assert payload["operator_summary"]["operator_message"] == (
        "Enter Actual Price and set Status to READY in Notion before running the execution preview."
    )


def test_manual_execution_post_sync_ready_absence_is_not_conflict(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write_plan(root)
    _write_notion_evidence(root, EVIDENCE_DAILY_PLAN_NOTION_EXPORT)
    _write_notion_evidence(root, EVIDENCE_MANUAL_EXECUTION_TEMPLATE)
    _write_execution_preview(root)
    _write_execution_commit(root)
    _write_notion_evidence(root, EVIDENCE_MANUAL_EXECUTION_STATUS_SYNC)

    payload = build_daily_ops_status(
        **_base_kwargs(root, legacy),
        include_notion_read=True,
        notion_status_report=_notion_report(
            {
                "MANUAL_EXECUTION_PREVIEW": _notion_stage_report(
                    "PASS",
                    row_count=7,
                    status_counts={"IMPORTED": 7, "COMMITTED": 7},
                ),
                "MANUAL_EXECUTION_STATUS_SYNC": _notion_stage_report(
                    "PASS",
                    row_count=7,
                    status_counts={"IMPORTED": 7, "COMMITTED": 7},
                ),
            }
        ),
    )

    preview_stage = _stage(payload, "MANUAL_EXECUTION_PREVIEW")
    assert preview_stage["status"] == "DONE"
    assert preview_stage["reconciliation_rule_id"] == "OPER9_13_EXEC_PREVIEW_POST_COMMIT_NO_READY_ROWS"
    assert preview_stage["_reconciliation_conflict"] is False
    assert payload["reconciliation_summary"]["has_conflicts"] is False
    assert payload["operator_summary"]["has_reconciliation_conflicts"] is False
    _assert_operator_next(payload, "DAILY_REVIEW", "paper.py review")
    assert payload["operator_summary"]["recommended_operator_action"] == "RUN_NEXT_COMMAND"


def test_stage_advancement_matrix_daily_review_to_manual_review_template(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write_plan(root)
    _write_notion_evidence(root, EVIDENCE_DAILY_PLAN_NOTION_EXPORT)
    _write_notion_evidence(root, EVIDENCE_MANUAL_EXECUTION_TEMPLATE)
    _write_execution_preview(root)
    _write_execution_commit(root)
    _write_notion_evidence(root, EVIDENCE_MANUAL_EXECUTION_STATUS_SYNC)

    before_review = build_daily_ops_status(**_base_kwargs(root, legacy))
    _assert_operator_next(before_review, "DAILY_REVIEW", "paper.py review")

    _write_review_ready(root)
    review_ready = build_daily_ops_status(**_base_kwargs(root, legacy))
    _assert_operator_next(review_ready, "MANUAL_REVIEW_TEMPLATE", "--manual-review-template")
    assert "paper.py review" not in review_ready["next_command"]


def test_stage_advancement_matrix_manual_review_preview_append_and_sync(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write_plan(root)
    _write_notion_evidence(root, EVIDENCE_DAILY_PLAN_NOTION_EXPORT)
    _write_notion_evidence(root, EVIDENCE_MANUAL_EXECUTION_TEMPLATE)
    _write_execution_preview(root)
    _write_execution_commit(root)
    _write_notion_evidence(root, EVIDENCE_MANUAL_EXECUTION_STATUS_SYNC)
    _write_review_ready(root)

    template_missing = build_daily_ops_status(**_base_kwargs(root, legacy))
    _assert_operator_next(template_missing, "MANUAL_REVIEW_TEMPLATE", "--manual-review-template")

    _write_notion_evidence(root, EVIDENCE_MANUAL_REVIEW_TEMPLATE)
    template_done = build_daily_ops_status(
        **_base_kwargs(root, legacy),
        include_notion_read=True,
        notion_status_report=_notion_report(
            {"MANUAL_REVIEW_PREVIEW": _notion_stage_report("PASS", status_counts={"READY": 1})}
        ),
    )
    _assert_operator_next(template_done, "MANUAL_REVIEW_PREVIEW", "import_notion_reviews.py")
    assert "--preview" in template_done["next_command"]

    _write_review_preview(root)
    preview_done = build_daily_ops_status(**_base_kwargs(root, legacy))
    _assert_operator_next(preview_done, "MANUAL_REVIEW_APPEND", "import_notion_reviews.py")
    assert "--commit" in preview_done["next_command"]

    _write_json(
        root / "reports" / "manual_review_import_commit_20260608.json",
        {
            "account_id": "paper_ops",
            "review_date": "2026-06-08",
            "rows": [],
        },
    )
    append_done = build_daily_ops_status(**_base_kwargs(root, legacy))
    _assert_operator_next(append_done, "MANUAL_REVIEW_STATUS_SYNC", "sync_notion_review_status.py")


def test_manual_review_pending_rows_wait_for_notion_input(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write_plan(root)
    _write_notion_evidence(root, EVIDENCE_DAILY_PLAN_NOTION_EXPORT)
    _write_notion_evidence(root, EVIDENCE_MANUAL_EXECUTION_TEMPLATE)
    _write_execution_preview(root)
    _write_execution_commit(root)
    _write_notion_evidence(root, EVIDENCE_MANUAL_EXECUTION_STATUS_SYNC)
    _write_review_ready(root)
    _write_notion_evidence(root, EVIDENCE_MANUAL_REVIEW_TEMPLATE)

    payload = build_daily_ops_status(
        **_base_kwargs(root, legacy),
        include_notion_read=True,
        notion_status_report=_notion_report(
            {
                "MANUAL_REVIEW_TEMPLATE": _notion_stage_report(
                    "PASS",
                    row_count=10,
                    status_counts={"PENDING": 10, "DRAFT": 10},
                    details={"pending_review_count": 10, "draft_import_status_count": 10},
                ),
                "MANUAL_REVIEW_PREVIEW": _notion_stage_report(
                    "PASS",
                    row_count=10,
                    status_counts={"PENDING": 10, "DRAFT": 10},
                    details={"pending_review_count": 10, "draft_import_status_count": 10},
                ),
            }
        ),
    )

    assert payload["next_command"] is None
    assert payload["operator_summary"]["current_step"] in {"MANUAL_REVIEW_TEMPLATE", "MANUAL_REVIEW_PREVIEW"}
    assert payload["operator_summary"]["current_step"] != "FINAL_STATUS"
    assert payload["operator_summary"]["recommended_operator_action"] == "WAIT_FOR_INPUT"
    assert payload["operator_summary"]["next_command"] is None
    assert payload["operator_summary"]["operator_message"] == (
        "Manual Review rows are pending. Enter Manual Answer and set Review Status to READY/REVIEWED in Notion before running review preview."
    )


def test_manual_review_ready_rows_recommend_preview_not_final_status(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write_plan(root)
    _write_notion_evidence(root, EVIDENCE_DAILY_PLAN_NOTION_EXPORT)
    _write_notion_evidence(root, EVIDENCE_MANUAL_EXECUTION_TEMPLATE)
    _write_execution_preview(root)
    _write_execution_commit(root)
    _write_notion_evidence(root, EVIDENCE_MANUAL_EXECUTION_STATUS_SYNC)
    _write_review_ready(root)
    _write_notion_evidence(root, EVIDENCE_MANUAL_REVIEW_TEMPLATE)

    payload = build_daily_ops_status(
        **_base_kwargs(root, legacy),
        include_notion_read=True,
        notion_status_report=_notion_report(
            {"MANUAL_REVIEW_PREVIEW": _notion_stage_report("PASS", row_count=2, status_counts={"READY": 2})}
        ),
    )

    _assert_operator_next(payload, "MANUAL_REVIEW_PREVIEW", "import_notion_reviews.py")
    assert "--preview" in payload["next_command"]
    assert payload["operator_summary"]["recommended_operator_action"] == "RUN_NEXT_COMMAND"
    assert payload["operator_summary"]["current_step"] != "FINAL_STATUS"


def test_manual_review_preview_artifact_recommends_append_with_manual_approval(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write_plan(root)
    _write_notion_evidence(root, EVIDENCE_DAILY_PLAN_NOTION_EXPORT)
    _write_notion_evidence(root, EVIDENCE_MANUAL_EXECUTION_TEMPLATE)
    _write_execution_preview(root)
    _write_execution_commit(root)
    _write_notion_evidence(root, EVIDENCE_MANUAL_EXECUTION_STATUS_SYNC)
    _write_review_ready(root)
    _write_notion_evidence(root, EVIDENCE_MANUAL_REVIEW_TEMPLATE)
    _write_review_preview(root)

    payload = build_daily_ops_status(**_base_kwargs(root, legacy))

    _assert_operator_next(payload, "MANUAL_REVIEW_APPEND", "import_notion_reviews.py")
    assert "--commit" in payload["next_command"]
    assert "--preview-json" in payload["next_command"]
    assert payload["operator_summary"]["requires_manual_approval"] is True


def test_stage_advancement_matrix_review_done_terminal_suppresses_all_commands(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write_plan(root)
    _write_notion_evidence(root, EVIDENCE_DAILY_PLAN_NOTION_EXPORT)
    _write_notion_evidence(root, EVIDENCE_MANUAL_EXECUTION_TEMPLATE)
    _write_execution_preview(root)
    _write_execution_commit(root)
    _write_notion_evidence(root, EVIDENCE_MANUAL_EXECUTION_STATUS_SYNC)
    _write_review_ready(root)
    _write_notion_evidence(root, EVIDENCE_MANUAL_REVIEW_TEMPLATE)
    _write_review_preview(root)
    _write_review_commit(root)
    _write_notion_evidence(root, EVIDENCE_MANUAL_REVIEW_STATUS_SYNC)

    payload = build_daily_ops_status(**_base_kwargs(root, legacy))

    assert payload["workflow_status"] == "REVIEW_DONE"
    _assert_operator_next(payload, "FINAL_STATUS", None)
    assert payload["operator_summary"]["terminal"] is True
    assert all(stage["next_command"] is None for stage in payload["stages"])


def test_local_commit_with_unsynced_notion_status_keeps_sync_recommendation(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write_plan(root)
    _write_execution_preview(root)
    _write_execution_commit(root)

    payload = build_daily_ops_status(
        **_base_kwargs(root, legacy),
        include_notion_read=True,
        notion_status_report=_notion_report(
            {
                "MANUAL_EXECUTION_STATUS_SYNC": _notion_stage_report(
                    "WARNING",
                    status_counts={"READY": 1},
                    warnings=["No Notion rows are COMMITTED/SYNCED."],
                )
            },
            status="WARNING",
        ),
    )
    stage = _stage(payload, "MANUAL_EXECUTION_STATUS_SYNC")

    assert stage["status"] == "READY"
    assert "sync_notion_execution_status.py" in stage["next_command"]
    assert stage["notion_warnings"]
    assert stage["reconciliation_rule_id"] == "OPER9_6_EXEC_SYNC_LOCAL_COMMIT_UNSYNCED"
    assert payload["reconciliation_summary"]["recommended_operator_action"] == "RUN_SYNC"


def test_notion_mismatch_blocks_stage(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write_plan(root)

    payload = build_daily_ops_status(
        **_base_kwargs(root, legacy),
        include_notion_read=True,
        notion_status_report=_notion_report(
            {
                "DAILY_PLAN_NOTION_EXPORT": _notion_stage_report(
                    "BLOCKED",
                    errors=["Notion account_id mismatch: other != paper_ops."],
                )
            },
            status="BLOCKED",
        ),
    )
    stage = _stage(payload, "DAILY_PLAN_NOTION_EXPORT")

    assert stage["status"] == "BLOCKED"
    assert stage["notion_errors"]
    assert stage["next_command"] is None
    assert payload["reconciliation_summary"]["blocking_conflict_count"] == 1
    assert payload["operator_summary"]["has_reconciliation_conflicts"] is True
    assert payload["operator_summary"]["conflict_count"] == 1
    assert payload["operator_summary"]["recommended_operator_action"] == "RESOLVE_CONFLICT"
    assert payload["operator_summary"]["current_step"] == "DAILY_PLAN_NOTION_EXPORT"


def test_local_plan_without_notion_plan_reconciles_export_ready(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write_plan(root)

    payload = build_daily_ops_status(
        **_base_kwargs(root, legacy),
        include_notion_read=True,
        notion_status_report=_notion_report(
            {"DAILY_PLAN_NOTION_EXPORT": _notion_stage_report("UNKNOWN", row_count=0)}
        ),
    )
    stage = _stage(payload, "DAILY_PLAN_NOTION_EXPORT")

    assert stage["local_stage_status"] == "UNKNOWN"
    assert stage["status"] == "READY"
    assert stage["reconciliation_status"] == "READY"
    assert "export_paper_to_notion.py" in stage["next_command"]


def test_notion_plan_without_local_plan_is_reconciliation_warning(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)

    payload = build_daily_ops_status(
        **_base_kwargs(root, legacy),
        include_notion_read=True,
        notion_status_report=_notion_report(
            {"DAILY_PLAN_NOTION_EXPORT": _notion_stage_report("PASS", status_counts={"SYNCED": 1})}
        ),
    )
    stage = _stage(payload, "DAILY_PLAN_NOTION_EXPORT")

    assert stage["status"] == "WARNING"
    assert stage["next_command"] is None
    assert stage["reconciliation_rule_id"] == "OPER9_6_DAILY_PLAN_NOTION_WITHOUT_LOCAL"
    assert payload["reconciliation_summary"]["warning_conflict_count"] == 1


def test_notion_execution_ready_missing_actual_price_is_warning(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write_plan(root)

    payload = build_daily_ops_status(
        **_base_kwargs(root, legacy),
        include_notion_read=True,
        notion_status_report=_notion_report(
            {
                "MANUAL_EXECUTION_PREVIEW": _notion_stage_report(
                    "WARNING",
                    status_counts={"READY": 1},
                    warnings=["Manual Execution READY rows include blank Actual Price values."],
                    details={"missing_actual_price_count": 1},
                )
            },
            status="WARNING",
        ),
    )
    stage = _stage(payload, "MANUAL_EXECUTION_PREVIEW")

    assert stage["status"] == "WARNING"
    assert stage["reconciliation_rule_id"] == "OPER9_6_EXEC_PREVIEW_READY_MISSING_PRICE"
    assert payload["reconciliation_summary"]["recommended_operator_action"] == "RESOLVE_CONFLICT"
    assert payload["operator_summary"]["operator_message"] == (
        "Local and Notion states conflict. Resolve the conflict before running risky commands."
    )


def test_notion_committed_without_local_commit_blocks_commit_recommendation(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write_plan(root)
    _write_execution_preview(root)

    payload = build_daily_ops_status(
        **_base_kwargs(root, legacy),
        include_notion_read=True,
        notion_status_report=_notion_report(
            {"MANUAL_EXECUTION_COMMIT": _notion_stage_report("PASS", status_counts={"COMMITTED": 1})}
        ),
    )
    stage = _stage(payload, "MANUAL_EXECUTION_COMMIT")

    assert stage["status"] == "BLOCKED"
    assert stage["next_command"] is None
    assert stage["reconciliation_rule_id"] == "OPER9_6_EXEC_COMMIT_NOTION_COMMITTED_WITHOUT_LOCAL"


def test_review_template_local_without_notion_rows_is_ready(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write_plan(root)
    _write_execution_preview(root)
    _write_execution_commit(root)
    _write_review_ready(root)

    payload = build_daily_ops_status(
        **_base_kwargs(root, legacy),
        include_notion_read=True,
        notion_status_report=_notion_report(
            {"MANUAL_REVIEW_TEMPLATE": _notion_stage_report("UNKNOWN", row_count=0)}
        ),
    )
    stage = _stage(payload, "MANUAL_REVIEW_TEMPLATE")

    assert stage["status"] == "READY"
    assert "export_paper_to_notion.py" in stage["next_command"]
    assert stage["reconciliation_rule_id"] == "OPER9_6_REVIEW_TEMPLATE_LOCAL_ONLY"


def test_notion_review_ready_without_local_preview_is_ready(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write_plan(root)
    _write_execution_preview(root)
    _write_execution_commit(root)
    _write_review_ready(root)

    payload = build_daily_ops_status(
        **_base_kwargs(root, legacy),
        include_notion_read=True,
        notion_status_report=_notion_report(
            {"MANUAL_REVIEW_PREVIEW": _notion_stage_report("PASS", status_counts={"READY": 1})}
        ),
    )
    stage = _stage(payload, "MANUAL_REVIEW_PREVIEW")

    assert stage["status"] == "READY"
    assert "import_notion_reviews.py" in stage["next_command"]
    assert payload["reconciliation_summary"]["recommended_operator_action"] == "RUN_PREVIEW"


def test_review_commit_with_unsynced_notion_status_reconciles_sync_ready(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write_plan(root)
    _write_execution_preview(root)
    _write_execution_commit(root)
    _write_review_ready(root)
    _write_review_preview(root)
    _write_json(
        root / "reports" / "manual_review_import_commit_20260608.json",
        {
            "account_id": "paper_ops",
            "review_date": "2026-06-08",
            "rows": [],
        },
    )

    payload = build_daily_ops_status(
        **_base_kwargs(root, legacy),
        include_notion_read=True,
        notion_status_report=_notion_report(
            {"MANUAL_REVIEW_STATUS_SYNC": _notion_stage_report("WARNING", status_counts={"REVIEWED": 1})},
            status="WARNING",
        ),
    )
    stage = _stage(payload, "MANUAL_REVIEW_STATUS_SYNC")

    assert stage["status"] == "READY"
    assert "sync_notion_review_status.py" in stage["next_command"]
    assert stage["reconciliation_rule_id"] == "OPER9_6_REVIEW_SYNC_LOCAL_COMMIT_UNSYNCED"


def test_review_done_with_unsynced_notion_recommends_review_status_sync(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write_plan(root)
    _write_execution_preview(root)
    _write_execution_commit(root)
    _write_review_ready(root)
    _write_review_preview(root)
    _write_review_commit(root)

    payload = build_daily_ops_status(
        **_base_kwargs(root, legacy),
        include_notion_read=True,
        notion_status_report=_notion_report(
            {"MANUAL_REVIEW_STATUS_SYNC": _notion_stage_report("WARNING", status_counts={"REVIEWED": 1})},
            status="WARNING",
        ),
    )

    assert payload["workflow_status"] == "REVIEW_DONE"
    assert payload["operator_summary"]["terminal"] is False
    assert payload["operator_summary"]["current_step"] == "MANUAL_REVIEW_STATUS_SYNC"
    assert payload["operator_summary"]["recommended_operator_action"] == "RUN_SYNC"
    assert "sync_notion_review_status.py" in payload["operator_summary"]["next_command"]
    assert payload["operator_summary"]["has_reconciliation_conflicts"] is False
    assert payload["reconciliation_summary"]["conflict_count"] == 0
    assert payload["reconciliation_summary"]["recommended_operator_action"] == "RUN_SYNC"
    assert _stage(payload, "MANUAL_REVIEW_STATUS_SYNC")["status"] == "READY"
    assert _stage(payload, "MANUAL_REVIEW_STATUS_SYNC")["reconciliation_rule_id"] == (
        "OPER9_15_REVIEW_SYNC_REVIEW_DONE_NOTION_UNSYNCED"
    )


def test_review_done_with_synced_notion_remains_terminal_without_conflicts(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write_plan(root)
    _write_execution_preview(root)
    _write_execution_commit(root)
    _write_review_ready(root)
    _write_review_preview(root)
    _write_review_commit(root)

    payload = build_daily_ops_status(
        **_base_kwargs(root, legacy),
        include_notion_read=True,
        notion_status_report=_notion_report(
            {"MANUAL_REVIEW_STATUS_SYNC": _notion_stage_report("PASS", status_counts={"IMPORTED": 1})}
        ),
    )

    assert payload["workflow_status"] == "REVIEW_DONE"
    assert payload["next_command"] is None
    assert payload["next_action"] is None
    assert payload["operator_summary"]["terminal"] is True
    assert payload["operator_summary"]["current_step"] == "FINAL_STATUS"
    assert payload["operator_summary"]["recommended_operator_action"] == "NONE"
    assert payload["operator_summary"]["has_reconciliation_conflicts"] is False
    assert payload["reconciliation_summary"]["conflict_count"] == 0


def test_operator_summary_exists_when_notion_read_is_blocked(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)

    payload = build_daily_ops_status(
        **_base_kwargs(root, legacy),
        include_notion_read=True,
        notion_status_report={
            "enabled": True,
            "called": True,
            "status": "BLOCKED",
            "errors": ["Notion settings are disabled or missing."],
            "warnings": [],
            "summary": {"stage_status_counts": {}, "total_row_count": 0},
            "stages": {},
        },
    )

    operator_summary = payload["operator_summary"]
    assert operator_summary["notion_live_read_enabled"] is True
    assert operator_summary["notion_live_read_status"] == "BLOCKED"
    assert operator_summary["current_step"] == "DATA_FRESHNESS"
    assert operator_summary["next_command"] == payload["next_command"]


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
    assert payload["next_action"] is None
    assert payload["summary"]["terminal"] is True
    assert payload["summary"]["needs_attention"] is False
    assert payload["summary"]["recommended_operator_action"] == "NONE"
    commands = [stage["next_command"] or "" for stage in payload["stages"]]
    assert all(command == "" for command in commands)
    assert all(stage["next_action"] is None for stage in payload["stages"])
    assert not any(" --commit " in command for command in commands)
    assert not any("review-append" in command for command in commands)


def test_next_action_classifies_read_only_notion_and_ledger_commands(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    payload = build_daily_ops_status(**_base_kwargs(root, legacy))
    assert _stage(payload, "DATA_FRESHNESS")["next_action"]["command_type"] == "READ_ONLY"
    assert _stage(payload, "DATA_FRESHNESS")["next_action"]["risk_level"] == "SAFE"

    _write_plan(root)
    payload = build_daily_ops_status(**_base_kwargs(root, legacy))
    notion_export_action = _stage(payload, "DAILY_PLAN_NOTION_EXPORT")["next_action"]
    assert notion_export_action["command_type"] == "NOTION_WRITE"
    assert notion_export_action["risk_level"] == "REQUIRES_MANUAL_REVIEW"
    assert notion_export_action["writes_notion"] is True

    _write_execution_preview(root)
    payload = build_daily_ops_status(**_base_kwargs(root, legacy))
    ledger_action = _stage(payload, "MANUAL_EXECUTION_COMMIT")["next_action"]
    assert ledger_action["command_type"] == "LEDGER_WRITE"
    assert ledger_action["risk_level"] == "REQUIRES_MANUAL_REVIEW"
    assert ledger_action["writes_ledger"] is True

    _write_execution_commit(root)
    payload = build_daily_ops_status(**_base_kwargs(root, legacy))
    sync_action = _stage(payload, "MANUAL_EXECUTION_STATUS_SYNC")["next_action"]
    assert sync_action["command_type"] == "NOTION_WRITE"
    assert sync_action["risk_level"] == "REQUIRES_MANUAL_REVIEW"
    assert sync_action["writes_notion"] is True


def test_notion_stage_without_evidence_stays_unknown(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write_plan(root)

    payload = build_daily_ops_status(**_base_kwargs(root, legacy))
    stage = _stage(payload, "DAILY_PLAN_NOTION_EXPORT")

    assert stage["status"] == "UNKNOWN"
    assert stage["evidence_checked"] is False
    assert stage["evidence_status"] is None
    assert stage["evidence_path"].endswith("daily_plan_notion_export_20260608.json")


def test_notion_evidence_path_uses_compact_filename_date(tmp_path: Path):
    path = notion_evidence_path(tmp_path, EVIDENCE_DAILY_PLAN_NOTION_EXPORT, "2026-06-08")

    assert path.name == "daily_plan_notion_export_20260608.json"


@pytest.mark.parametrize(
    ("evidence_type", "stage_name"),
    [
        (EVIDENCE_DAILY_PLAN_NOTION_EXPORT, "DAILY_PLAN_NOTION_EXPORT"),
        (EVIDENCE_MANUAL_EXECUTION_TEMPLATE, "MANUAL_EXECUTION_TEMPLATE"),
        (EVIDENCE_MANUAL_EXECUTION_STATUS_SYNC, "MANUAL_EXECUTION_STATUS_SYNC"),
        (EVIDENCE_MANUAL_REVIEW_TEMPLATE, "MANUAL_REVIEW_TEMPLATE"),
        (EVIDENCE_MANUAL_REVIEW_STATUS_SYNC, "MANUAL_REVIEW_STATUS_SYNC"),
    ],
)
def test_pass_evidence_marks_target_notion_stage_done(tmp_path: Path, evidence_type: str, stage_name: str):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write_plan(root)
    if stage_name in {"MANUAL_EXECUTION_STATUS_SYNC", "MANUAL_REVIEW_STATUS_SYNC"}:
        _write_execution_preview(root)
        _write_execution_commit(root)
    if stage_name in {"MANUAL_REVIEW_TEMPLATE", "MANUAL_REVIEW_STATUS_SYNC"}:
        _write_review_ready(root)
    if stage_name == "MANUAL_REVIEW_STATUS_SYNC":
        _write_review_preview(root)
        _write_review_commit(root)
    _write_notion_evidence(root, evidence_type)

    payload = build_daily_ops_status(**_base_kwargs(root, legacy))
    stage = _stage(payload, stage_name)

    assert stage["status"] == "DONE"
    assert stage["evidence_checked"] is True
    assert stage["evidence_status"] == "PASS"


def test_compact_filename_with_hyphenated_payload_trade_date_is_valid(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write_plan(root)
    evidence_path = _write_notion_evidence(root, EVIDENCE_DAILY_PLAN_NOTION_EXPORT)

    payload = build_daily_ops_status(**_base_kwargs(root, legacy))
    stage = _stage(payload, "DAILY_PLAN_NOTION_EXPORT")

    assert evidence_path.name == "daily_plan_notion_export_20260608.json"
    assert json.loads(evidence_path.read_text(encoding="utf-8"))["trade_date"] == "2026-06-08"
    assert stage["status"] == "DONE"


def test_warning_evidence_marks_notion_stage_warning(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write_plan(root)
    _write_notion_evidence(root, EVIDENCE_DAILY_PLAN_NOTION_EXPORT, status="WARNING")

    payload = build_daily_ops_status(**_base_kwargs(root, legacy))
    stage = _stage(payload, "DAILY_PLAN_NOTION_EXPORT")

    assert stage["status"] == "WARNING"
    assert stage["evidence_checked"] is True
    assert stage["evidence_status"] == "WARNING"
    assert stage["warnings"]


@pytest.mark.parametrize("status,failed_count", [("FAILED", 0), ("PASS", 1)])
def test_failed_evidence_or_failed_count_blocks_notion_stage(tmp_path: Path, status: str, failed_count: int):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write_plan(root)
    _write_notion_evidence(
        root,
        EVIDENCE_DAILY_PLAN_NOTION_EXPORT,
        status=status,
        failed_count=failed_count,
    )

    payload = build_daily_ops_status(**_base_kwargs(root, legacy))
    stage = _stage(payload, "DAILY_PLAN_NOTION_EXPORT")

    assert stage["status"] == "BLOCKED"
    assert stage["evidence_checked"] is True
    assert stage["evidence_errors"]


@pytest.mark.parametrize(
    ("field", "value", "expected_error"),
    [
        ("account_id", "other_account", "account_id"),
        ("trade_date", "2026-06-09", "trade_date"),
        ("evidence_type", EVIDENCE_MANUAL_EXECUTION_TEMPLATE, "evidence_type"),
    ],
)
def test_mismatched_evidence_blocks_notion_stage(
    tmp_path: Path,
    field: str,
    value: str,
    expected_error: str,
):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write_plan(root)
    path = _write_notion_evidence(root, EVIDENCE_DAILY_PLAN_NOTION_EXPORT)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload[field] = value
    _write_json(path, payload)

    status = build_daily_ops_status(**_base_kwargs(root, legacy))
    stage = _stage(status, "DAILY_PLAN_NOTION_EXPORT")

    assert stage["status"] == "BLOCKED"
    assert stage["evidence_checked"] is True
    assert any(expected_error in error for error in stage["evidence_errors"])


def test_malformed_evidence_is_not_done_evidence(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write_plan(root)
    path = notion_evidence_path(root, EVIDENCE_DAILY_PLAN_NOTION_EXPORT, "2026-06-08")
    _write(path, "{not-json")

    payload = build_daily_ops_status(**_base_kwargs(root, legacy))
    stage = _stage(payload, "DAILY_PLAN_NOTION_EXPORT")

    assert stage["status"] == "WARNING"
    assert stage["evidence_checked"] is True
    assert stage["evidence_status"] is None
    assert not stage["evidence_errors"]


def test_hyphenated_filename_evidence_is_not_used_when_compact_file_is_absent(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write_plan(root)
    _write_json(
        root / "reports" / "daily_plan_notion_export_2026-06-08.json",
        {
            "schema_version": "paper_notion_evidence.v1",
            "evidence_type": EVIDENCE_DAILY_PLAN_NOTION_EXPORT,
            "account_id": "paper_ops",
            "trade_date": "2026-06-08",
            "data_date": "2026-06-05",
            "target_system": "notion",
            "status": "PASS",
            "failed_count": 0,
        },
    )

    payload = build_daily_ops_status(**_base_kwargs(root, legacy))
    stage = _stage(payload, "DAILY_PLAN_NOTION_EXPORT")

    assert stage["status"] == "UNKNOWN"
    assert stage["evidence_checked"] is False
    assert stage["evidence_path"].endswith("daily_plan_notion_export_20260608.json")


def test_legacy_paper_test_notion_evidence_is_not_done_for_non_default_account(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    _write_plan(root)
    _write_notion_evidence(legacy, EVIDENCE_DAILY_PLAN_NOTION_EXPORT)

    payload = build_daily_ops_status(**_base_kwargs(root, legacy))
    stage = _stage(payload, "DAILY_PLAN_NOTION_EXPORT")

    assert stage["status"] == "BLOCKED"
    assert stage["evidence_checked"] is True
    assert stage["evidence_status"] is None
    assert "Legacy paper_test evidence" in stage["evidence_errors"][0]


def test_summary_flags_blockers_warnings_unknowns_and_stage_counts(tmp_path: Path):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)
    blocked_payload = build_daily_ops_status(
        account_id="paper_ops",
        data_date="2026-06-08",
        trade_date="2026-06-08",
        account_root=root,
        legacy_root=legacy,
    )
    assert blocked_payload["summary"]["has_blockers"] is True
    assert blocked_payload["summary"]["recommended_operator_action"] == "RESOLVE_BLOCKERS"

    _write_plan(root)
    _write_json(
        root / "reports" / "manual_execution_import_preview_20260608.json",
        {
            "account_id": "paper_ops",
            "execution_date": "2026-06-08",
            "fail_count": 0,
            "commit_allowed": "true_with_warnings",
        },
    )
    warning_payload = build_daily_ops_status(**_base_kwargs(root, legacy))
    assert warning_payload["summary"]["has_warnings"] is True
    assert warning_payload["summary"]["has_unknowns"] is True
    assert sum(warning_payload["stage_counts"].values()) == len(warning_payload["stages"]) == 13
    assert warning_payload["stage_counts"]["WARNING"] >= 1
    assert warning_payload["stage_counts"]["UNKNOWN"] >= 1


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


def test_cli_does_not_write_status_report_by_default(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
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
    assert payload["status_report_written"] is False
    assert payload["status_report_path"] is None
    assert not (root / "reports" / "daily_ops_status_2026-06-08.json").exists()


def test_cli_writes_status_report_only_when_requested(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
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
            "--write-status-report",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    report_path = root / "reports" / "daily_ops_status_2026-06-08.json"
    assert report_path.exists()
    written = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["status_report_written"] is True
    assert written["status_report_written"] is True
    assert payload["write_executed"] is False
    assert payload["operation_write_executed"] is False


def test_cli_strict_exit_policy_and_validation_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    root = _root(tmp_path)
    legacy = _legacy_root(tmp_path)

    default_exit = paper_daily_ops.main(
        [
            "status",
            "--account-id",
            "paper_ops",
            "--data-date",
            "2026-06-08",
            "--trade-date",
            "2026-06-08",
            "--account-root",
            str(root),
            "--legacy-root",
            str(legacy),
            "--json",
        ]
    )
    assert default_exit == 0
    capsys.readouterr()

    strict_exit = paper_daily_ops.main(
        [
            "status",
            "--account-id",
            "paper_ops",
            "--data-date",
            "2026-06-08",
            "--trade-date",
            "2026-06-08",
            "--account-root",
            str(root),
            "--legacy-root",
            str(legacy),
            "--json",
            "--strict-exit",
        ]
    )
    assert strict_exit == 2
    capsys.readouterr()

    validation_exit = paper_daily_ops.main(
        [
            "status",
            "--account-id",
            "",
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
    assert validation_exit == 2


def test_cli_unexpected_exception_returns_3(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    def raise_unexpected(**_: object) -> dict:
        raise RuntimeError("boom")

    monkeypatch.setattr(paper_daily_ops, "build_daily_ops_status", raise_unexpected)

    exit_code = paper_daily_ops.main(
        [
            "status",
            "--account-id",
            "paper_ops",
            "--data-date",
            "2026-06-05",
            "--trade-date",
            "2026-06-08",
            "--json",
        ]
    )

    assert exit_code == 3
    payload = json.loads(capsys.readouterr().out)
    assert payload["overall_status"] == "ERROR"
