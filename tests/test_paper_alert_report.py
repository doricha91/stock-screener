from __future__ import annotations

import json

from core.paper_alert_report import (
    ALERT_REPORT_SCHEMA_VERSION,
    SEVERITY_BLOCKING,
    SEVERITY_INFO,
    SEVERITY_NEEDS_REVIEW,
    SEVERITY_SYNC_FAILED,
    build_paper_alert_report,
    render_paper_alert_report_markdown,
    write_paper_alert_report,
)
from scripts.dev.generate_paper_alert_report import main as alert_report_cli_main


def _preflight_payload(
    *,
    overall_status: str = "WARNING",
    schema_validation_result: str = "PASS",
    duplicate_classification: str = "update_candidate",
) -> dict:
    return {
        "target": "daily_ops_status",
        "account_id": "paper_sandbox",
        "status_date": "2026-05-20",
        "external_key": "daily_ops_status:paper_sandbox:2026-05-20",
        "overall_status": overall_status,
        "schema_validation_result": schema_validation_result,
        "recommended_action": "review_warnings_before_explicit_user_approval",
        "checks": [
            {
                "name": "command_gate_check",
                "status": "WARNING",
                "message": "expected_page_id was not provided; operator confirmation is required.",
            }
        ],
        "duplicate_audit": {
            "classification": duplicate_classification,
            "match_count": 1,
            "page_ids": ["1234567890abcdef1234567890abcdef"],
            "data_source_id": "abcdefabcdefabcdefabcdefabcdef12",
            "write_executed": False,
        },
        "write_executed": False,
    }


def _build_report(**kwargs) -> dict:
    return build_paper_alert_report(
        account_id="paper_sandbox",
        report_date="2026-05-20",
        phase="closeout",
        preflight=_preflight_payload(**kwargs),
    )


def test_preflight_fail_becomes_blocking() -> None:
    report = _build_report(overall_status="FAIL")
    assert report["summary"]["blocking_count"] == 1
    assert report["items"][0]["severity"] == SEVERITY_BLOCKING


def test_duplicate_blocker_becomes_blocking() -> None:
    report = _build_report(duplicate_classification="duplicate_blocker")
    assert report["summary"]["blocking_count"] == 1
    assert "Duplicate" in report["items"][0]["message"]


def test_actual_intent_warning_becomes_needs_review() -> None:
    report = build_paper_alert_report(
        account_id="paper_sandbox",
        report_date="2026-05-20",
        phase="closeout",
        actual_intent=True,
        preflight=_preflight_payload(),
    )
    assert report["summary"]["needs_review_count"] == 1
    assert report["items"][0]["severity"] == SEVERITY_NEEDS_REVIEW


def test_non_actual_expected_page_warning_is_info() -> None:
    report = _build_report()
    assert report["summary"]["info_count"] == 1
    assert report["summary"]["suppressed_info_count"] == 1
    assert report["items"][0]["severity"] == SEVERITY_INFO
    assert report["items"][0]["suppressed_in_markdown"] is True
    assert report["items"][0]["suppression_reason"] == "actual_intent=false"
    assert "actual_intent=false" in report["items"][0]["message"]


def test_update_candidate_is_info_when_no_actual_intent() -> None:
    report = build_paper_alert_report(
        account_id="paper_sandbox",
        report_date="2026-05-20",
        phase="closeout",
        preflight={
            **_preflight_payload(overall_status="PASS"),
            "checks": [],
        },
    )
    assert report["summary"]["info_count"] == 1
    assert report["items"][0]["severity"] == SEVERITY_INFO


def test_summary_counts_multiple_sources() -> None:
    report = build_paper_alert_report(
        account_id="paper_sandbox",
        report_date="2026-05-20",
        phase="closeout",
        daily_ops_status={"account_id": "paper_sandbox", "workflow_status": "UNKNOWN_OR_INCOMPLETE"},
        preflight=_preflight_payload(),
    )
    assert report["summary"] == {
        "blocking_count": 1,
        "needs_review_count": 0,
        "sync_failed_count": 0,
        "info_count": 1,
        "suppressed_info_count": 1,
    }


def test_daily_ops_sync_failure_becomes_sync_failed() -> None:
    report = build_paper_alert_report(
        account_id="paper_sandbox",
        report_date="2026-05-20",
        phase="closeout",
        daily_ops_status={"account_id": "paper_sandbox", "sync_status": "SYNC_FAILED"},
    )
    assert report["summary"]["sync_failed_count"] == 1
    assert report["items"][0]["severity"] == SEVERITY_SYNC_FAILED


def test_daily_ops_review_partial_becomes_needs_review() -> None:
    report = build_paper_alert_report(
        account_id="paper_sandbox",
        report_date="2026-05-20",
        phase="closeout",
        daily_ops_status={
            "account_id": "paper_sandbox",
            "workflow_status": "REVIEW_PARTIAL",
            "review_progress_status": "PARTIAL",
            "review_pending_row_count": 3,
        },
    )
    assert report["summary"]["needs_review_count"] == 1
    assert report["items"][0]["severity"] == SEVERITY_NEEDS_REVIEW


def test_manual_execution_preview_fail_becomes_blocking() -> None:
    report = build_paper_alert_report(
        account_id="paper_sandbox",
        report_date="2026-05-20",
        phase="closeout",
        manual_execution={"account_id": "paper_sandbox", "execution_preview_result": "FAIL"},
    )
    assert report["summary"]["blocking_count"] == 1
    assert report["items"][0]["category"] == "MANUAL_EXECUTION"


def test_manual_execution_sync_failed_becomes_sync_failed() -> None:
    report = build_paper_alert_report(
        account_id="paper_sandbox",
        report_date="2026-05-20",
        phase="closeout",
        manual_execution={"account_id": "paper_sandbox", "execution_sync_status": "SYNC_FAILED"},
    )
    assert report["summary"]["sync_failed_count"] == 1
    assert report["items"][0]["severity"] == SEVERITY_SYNC_FAILED


def test_manual_execution_pending_rows_becomes_needs_review() -> None:
    report = build_paper_alert_report(
        account_id="paper_sandbox",
        report_date="2026-05-20",
        phase="closeout",
        manual_execution={"account_id": "paper_sandbox", "execution_pending_row_count": 2},
    )
    assert report["summary"]["needs_review_count"] == 1


def test_manual_review_validation_fail_becomes_blocking() -> None:
    report = build_paper_alert_report(
        account_id="paper_sandbox",
        report_date="2026-05-20",
        phase="closeout",
        manual_review={"account_id": "paper_sandbox", "review_validation_result": "FAIL"},
    )
    assert report["summary"]["blocking_count"] == 1
    assert report["items"][0]["category"] == "MANUAL_REVIEW"


def test_manual_review_sync_failed_becomes_sync_failed() -> None:
    report = build_paper_alert_report(
        account_id="paper_sandbox",
        report_date="2026-05-20",
        phase="closeout",
        manual_review={"account_id": "paper_sandbox", "review_sync_status": "SYNC_FAILED"},
    )
    assert report["summary"]["sync_failed_count"] == 1


def test_manual_review_pending_rows_becomes_needs_review() -> None:
    report = build_paper_alert_report(
        account_id="paper_sandbox",
        report_date="2026-05-20",
        phase="closeout",
        manual_review={"account_id": "paper_sandbox", "review_pending_row_count": 4},
    )
    assert report["summary"]["needs_review_count"] == 1


def test_daily_ops_review_signal_suppresses_manual_review_duplicate_pending() -> None:
    report = build_paper_alert_report(
        account_id="paper_sandbox",
        report_date="2026-05-20",
        phase="closeout",
        daily_ops_status={
            "account_id": "paper_sandbox",
            "review_progress_status": "PARTIAL",
            "review_pending_row_count": 4,
        },
        manual_review={"account_id": "paper_sandbox", "review_pending_row_count": 4},
    )
    titles = [item["title"] for item in report["items"]]
    assert titles.count("Daily Ops review is incomplete") == 1
    assert "Manual Review is incomplete" not in titles


def test_daily_ops_missing_source_at_closeout_becomes_needs_review() -> None:
    report = build_paper_alert_report(
        account_id="paper_sandbox",
        report_date="2026-05-20",
        phase="closeout",
        source_events=[
            {
                "source": "daily_ops_status",
                "status": "missing",
                "message": "daily_ops_status JSON source was not provided.",
            }
        ],
    )
    assert report["summary"]["needs_review_count"] == 1
    assert report["items"][0]["category"] == "ALERT_SOURCE"


def test_malformed_source_becomes_blocking() -> None:
    report = build_paper_alert_report(
        account_id="paper_sandbox",
        report_date="2026-05-20",
        phase="closeout",
        source_events=[
            {
                "source": "daily_ops_status",
                "status": "malformed",
                "source_path": r"C:\secret\broken.json",
                "message": "daily_ops_status JSON source could not be parsed.",
            }
        ],
    )
    assert report["summary"]["blocking_count"] == 1
    assert report["items"][0]["source_path"] == "<redacted_path>"


def test_malformed_manual_source_becomes_blocking() -> None:
    report = build_paper_alert_report(
        account_id="paper_sandbox",
        report_date="2026-05-20",
        phase="closeout",
        source_events=[
            {
                "source": "manual_execution",
                "status": "malformed",
                "message": "manual execution JSON source could not be parsed.",
            }
        ],
    )
    assert report["summary"]["blocking_count"] == 1


def test_preflight_missing_without_actual_intent_is_suppressed_info() -> None:
    report = build_paper_alert_report(
        account_id="paper_sandbox",
        report_date="2026-05-20",
        phase="closeout",
        actual_intent=False,
        source_events=[{"source": "daily_ops_actual_preflight", "status": "missing"}],
    )
    assert report["summary"]["info_count"] == 1
    assert report["summary"]["suppressed_info_count"] == 1
    assert report["items"][0]["suppressed_in_markdown"] is True


def test_preflight_missing_with_actual_intent_is_needs_review() -> None:
    report = build_paper_alert_report(
        account_id="paper_sandbox",
        report_date="2026-05-20",
        phase="closeout",
        actual_intent=True,
        source_events=[{"source": "daily_ops_actual_preflight", "status": "missing"}],
    )
    assert report["summary"]["needs_review_count"] == 1


def test_report_schema_version_and_markdown() -> None:
    report = _build_report()
    assert report["schema_version"] == ALERT_REPORT_SCHEMA_VERSION
    assert report["items"][0]["schema_version"] == ALERT_REPORT_SCHEMA_VERSION
    markdown = render_paper_alert_report_markdown(report)
    assert "Paper Ops Exception Report" in markdown
    assert "## Info / Suppressed Summary" in markdown
    assert "- Suppressed INFO: 1" in markdown


def test_write_report_uses_account_output_filenames(tmp_path) -> None:
    report = _build_report()
    paths = write_paper_alert_report(report, output_dir=tmp_path)
    assert paths["json_path"].endswith("paper_alert_report_20260520.json")
    assert paths["markdown_path"].endswith("paper_alert_report_20260520.md")
    loaded = json.loads((tmp_path / "paper_alert_report_20260520.json").read_text(encoding="utf-8"))
    assert loaded["account_id"] == "paper_sandbox"


def test_sensitive_values_are_redacted() -> None:
    report = _build_report()
    evidence = report["items"][0]["evidence"]
    assert evidence["duplicate_audit"]["page_ids"] == ["****cdef"]
    assert evidence["duplicate_audit"]["data_source_id"] == "****ef12"
    serialized = json.dumps(report, ensure_ascii=False)
    assert "1234567890abcdef1234567890abcdef" not in serialized
    assert "abcdefabcdefabcdefabcdefabcdef12" not in serialized


def test_delivery_is_not_executed() -> None:
    report = _build_report()
    assert report["delivery"]["delivery_executed"] is False
    assert report["delivery"]["delivery_adapter"] is None
    assert all(item["sendable"] is False for item in report["items"])


def test_actual_intent_warning_is_not_suppressed_in_markdown() -> None:
    report = build_paper_alert_report(
        account_id="paper_sandbox",
        report_date="2026-05-20",
        phase="closeout",
        actual_intent=True,
        preflight=_preflight_payload(),
    )
    item = report["items"][0]
    assert item["severity"] == SEVERITY_NEEDS_REVIEW
    assert item["suppressed_in_markdown"] is False
    markdown = render_paper_alert_report_markdown(report)
    assert "Daily Ops actual preflight returned WARNING" in markdown


def test_markdown_suppresses_info_details_but_json_preserves_item() -> None:
    report = _build_report()
    assert report["items"][0]["title"] == "Daily Ops actual preflight warning suppressed for non-actual run"
    markdown = render_paper_alert_report_markdown(report)
    assert "Daily Ops actual preflight warning suppressed for non-actual run" not in markdown
    assert "INFO details are preserved in JSON." in markdown


def test_blocking_needs_review_and_sync_failed_details_remain_in_markdown() -> None:
    blocking = build_paper_alert_report(
        account_id="paper_sandbox",
        report_date="2026-05-20",
        phase="closeout",
        daily_ops_status={"account_id": "paper_sandbox", "sync_status": "SYNC_FAILED"},
        preflight=_preflight_payload(overall_status="FAIL"),
    )
    needs_review = build_paper_alert_report(
        account_id="paper_sandbox",
        report_date="2026-05-20",
        phase="closeout",
        actual_intent=True,
        preflight=_preflight_payload(),
    )
    markdown = render_paper_alert_report_markdown(blocking) + render_paper_alert_report_markdown(needs_review)
    assert "Daily Ops actual preflight returned blocking result" in markdown
    assert "Daily Ops actual preflight returned WARNING" in markdown
    assert "Daily Ops Status sync failed" in markdown


def test_cli_smoke_generates_reports_in_tmp_path(tmp_path, capsys) -> None:
    preflight_path = tmp_path / "preflight.json"
    preflight_path.write_text(json.dumps(_preflight_payload()), encoding="utf-8")

    exit_code = alert_report_cli_main(
        [
            "--account-id",
            "paper_sandbox",
            "--date",
            "2026-05-20",
            "--phase",
            "closeout",
            "--preflight-json",
            str(preflight_path),
            "--output-dir",
            str(tmp_path),
            "--json",
        ]
    )

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["delivery_executed"] is False
    assert output["notion_api_called"] is False
    assert output["notion_write_export_sync_executed"] is False
    assert (tmp_path / "paper_alert_report_20260520.json").exists()
    assert (tmp_path / "paper_alert_report_20260520.md").exists()
    assert "outputs/paper_accounts" not in output["json_path"].replace("\\", "/")


def test_cli_source_root_resolves_tmp_path_sources(tmp_path, capsys) -> None:
    daily_ops_path = tmp_path / "daily_ops_status_20260520.json"
    preflight_path = tmp_path / "daily_ops_actual_preflight_20260520.json"
    daily_ops_path.write_text(
        json.dumps({"account_id": "paper_sandbox", "sync_status": "SYNC_FAILED"}),
        encoding="utf-8",
    )
    preflight_path.write_text(json.dumps(_preflight_payload()), encoding="utf-8")
    output_dir = tmp_path / "alerts"

    exit_code = alert_report_cli_main(
        [
            "--account-id",
            "paper_sandbox",
            "--date",
            "2026-05-20",
            "--phase",
            "closeout",
            "--source-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
            "--json",
        ]
    )

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["summary"]["sync_failed_count"] == 1
    assert (output_dir / "paper_alert_report_20260520.json").exists()
    assert (output_dir / "paper_alert_report_20260520.md").exists()


def test_cli_explicit_manual_json_overrides_source_root(tmp_path, capsys) -> None:
    source_root_manual = tmp_path / "manual_execution_20260520.json"
    explicit_manual = tmp_path / "explicit_manual_execution.json"
    source_root_manual.write_text(
        json.dumps({"account_id": "paper_sandbox", "execution_sync_status": "SYNC_FAILED"}),
        encoding="utf-8",
    )
    explicit_manual.write_text(
        json.dumps({"account_id": "paper_sandbox", "execution_preview_result": "FAIL"}),
        encoding="utf-8",
    )
    output_dir = tmp_path / "alerts"

    exit_code = alert_report_cli_main(
        [
            "--account-id",
            "paper_sandbox",
            "--date",
            "2026-05-20",
            "--phase",
            "closeout",
            "--source-root",
            str(tmp_path),
            "--manual-execution-json",
            str(explicit_manual),
            "--output-dir",
            str(output_dir),
            "--json",
        ]
    )

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["summary"]["blocking_count"] == 1
    assert output["summary"]["sync_failed_count"] == 0
