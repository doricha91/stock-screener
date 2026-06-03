from __future__ import annotations

import json

from core.paper_replay_diff import (
    CATEGORY_ACTION_DIFF,
    CATEGORY_CONFIG_OR_UNIVERSE_DIFF,
    CATEGORY_DUPLICATE_ROW_KEY,
    CATEGORY_MALFORMED_INPUT,
    CATEGORY_MISSING_INPUT,
    CATEGORY_NO_DIFF,
    CATEGORY_PRICE_DIFF,
    CATEGORY_QUANTITY_DIFF,
    CATEGORY_SYMBOL_SET_DIFF,
    CATEGORY_WARNING_DIFF,
    STATUS_FAIL,
    STATUS_PASS,
    STATUS_PASS_WITH_METADATA_DIFF,
    STATUS_WARNING,
    compare_daily_plan_files,
    compare_daily_plan_payloads,
    render_daily_plan_diff_markdown,
    write_daily_plan_diff_report,
)
from scripts.dev.diff_daily_plan import main as diff_daily_plan_cli_main


def _plan(**overrides) -> dict:
    payload = {
        "account_id": "paper_sandbox",
        "plan_date": "2026-05-20",
        "items": [
            {
                "symbol": "AAPL",
                "action": "BUY",
                "quantity": 10,
                "price": 100.0,
                "warning": "",
                "reason": "entry",
                "note": "",
            }
        ],
        "metadata": {"generated_at": "2026-05-20T09:00:00Z"},
        "fingerprints": {
            "config_hash": "config-a",
            "universe_hash": "universe-a",
        },
    }
    payload.update(overrides)
    return payload


def _report(baseline: dict | None = None, regenerated: dict | None = None) -> dict:
    return compare_daily_plan_payloads(
        account_id="paper_sandbox",
        plan_date="2026-05-20",
        baseline_plan=baseline if baseline is not None else _plan(),
        regenerated_plan=regenerated if regenerated is not None else _plan(),
    )


def test_same_plan_passes_with_no_diff() -> None:
    report = _report()
    assert report["overall_status"] == STATUS_PASS
    assert report["diff_categories"] == [CATEGORY_NO_DIFF]
    assert report["write_executed"] is False
    assert report["notion_api_called"] is False


def test_metadata_only_diff_is_pass_with_metadata_diff() -> None:
    regenerated = _plan(metadata={"generated_at": "2026-05-20T10:00:00Z"})
    report = _report(regenerated=regenerated)
    assert report["overall_status"] == STATUS_PASS_WITH_METADATA_DIFF
    assert "METADATA_DIFF" in report["diff_categories"]


def test_symbol_added_or_removed_fails() -> None:
    regenerated = _plan(items=[])
    report = _report(regenerated=regenerated)
    assert report["overall_status"] == STATUS_FAIL
    assert CATEGORY_SYMBOL_SET_DIFF in report["diff_categories"]


def test_action_changed_fails() -> None:
    regenerated = _plan(items=[{**_plan()["items"][0], "action": "SELL"}])
    report = _report(regenerated=regenerated)
    assert report["overall_status"] == STATUS_FAIL
    assert CATEGORY_ACTION_DIFF in report["diff_categories"]


def test_quantity_changed_fails() -> None:
    regenerated = _plan(items=[{**_plan()["items"][0], "quantity": 11}])
    report = _report(regenerated=regenerated)
    assert report["overall_status"] == STATUS_FAIL
    assert CATEGORY_QUANTITY_DIFF in report["diff_categories"]


def test_price_changed_warns() -> None:
    regenerated = _plan(items=[{**_plan()["items"][0], "price": 101.0}])
    report = _report(regenerated=regenerated)
    assert report["overall_status"] == STATUS_WARNING
    assert CATEGORY_PRICE_DIFF in report["diff_categories"]


def test_warning_reason_changed_warns() -> None:
    regenerated = _plan(items=[{**_plan()["items"][0], "reason": "changed"}])
    report = _report(regenerated=regenerated)
    assert report["overall_status"] == STATUS_WARNING
    assert CATEGORY_WARNING_DIFF in report["diff_categories"]


def test_config_hash_change_records_cause_candidate() -> None:
    regenerated = _plan(fingerprints={"config_hash": "config-b", "universe_hash": "universe-a"})
    report = _report(regenerated=regenerated)
    assert report["overall_status"] == STATUS_WARNING
    assert CATEGORY_CONFIG_OR_UNIVERSE_DIFF in report["diff_categories"]
    assert any("config_hash changed" in candidate for candidate in report["cause_candidates"])


def test_universe_hash_change_records_cause_candidate() -> None:
    regenerated = _plan(fingerprints={"config_hash": "config-a", "universe_hash": "universe-b"})
    report = _report(regenerated=regenerated)
    assert CATEGORY_CONFIG_OR_UNIVERSE_DIFF in report["diff_categories"]
    assert any("universe_hash changed" in candidate for candidate in report["cause_candidates"])


def test_account_date_mismatch_fails() -> None:
    regenerated = _plan(account_id="other_account")
    report = _report(regenerated=regenerated)
    assert report["overall_status"] == STATUS_FAIL
    assert "ACCOUNT_DATE_MISMATCH" in report["diff_categories"]


def test_duplicate_symbol_action_key_warns_without_auto_matching() -> None:
    duplicate_row = {**_plan()["items"][0], "quantity": 99}
    baseline = _plan(items=[_plan()["items"][0], duplicate_row])
    report = _report(baseline=baseline)
    assert report["overall_status"] == STATUS_WARNING
    assert CATEGORY_DUPLICATE_ROW_KEY in report["diff_categories"]


def test_missing_input_fails(tmp_path) -> None:
    baseline = tmp_path / "missing.json"
    regenerated = tmp_path / "regenerated.json"
    regenerated.write_text(json.dumps(_plan()), encoding="utf-8")
    report = compare_daily_plan_files(
        account_id="paper_sandbox",
        plan_date="2026-05-20",
        baseline_plan_path=baseline,
        regenerated_plan_path=regenerated,
    )
    assert report["overall_status"] == STATUS_FAIL
    assert CATEGORY_MISSING_INPUT in report["diff_categories"]


def test_malformed_input_fails(tmp_path) -> None:
    baseline = tmp_path / "baseline.json"
    regenerated = tmp_path / "regenerated.json"
    baseline.write_text("{bad json", encoding="utf-8")
    regenerated.write_text(json.dumps(_plan()), encoding="utf-8")
    report = compare_daily_plan_files(
        account_id="paper_sandbox",
        plan_date="2026-05-20",
        baseline_plan_path=baseline,
        regenerated_plan_path=regenerated,
    )
    assert report["overall_status"] == STATUS_FAIL
    assert CATEGORY_MALFORMED_INPUT in report["diff_categories"]


def test_json_and_markdown_report_are_written(tmp_path) -> None:
    report = _report(regenerated=_plan(items=[{**_plan()["items"][0], "price": 101.0}]))
    paths = write_daily_plan_diff_report(report, output_dir=tmp_path)
    assert (tmp_path / "paper_daily_plan_diff_20260520.json").exists()
    assert (tmp_path / "paper_daily_plan_diff_20260520.md").exists()
    markdown = render_daily_plan_diff_markdown(report)
    assert "Daily Plan Replay Diff" in markdown
    assert "Daily Plan regeneration was not executed." in markdown
    assert "because" not in " ".join(report["cause_candidates"]).lower()
    assert paths["json_path"].endswith("paper_daily_plan_diff_20260520.json")


def test_cli_compares_files_and_writes_to_output_dir(tmp_path, capsys) -> None:
    baseline = tmp_path / "baseline.json"
    regenerated = tmp_path / "regenerated.json"
    output_dir = tmp_path / "out"
    baseline.write_text(json.dumps(_plan()), encoding="utf-8")
    regenerated.write_text(json.dumps(_plan(items=[{**_plan()["items"][0], "price": 101.0}])), encoding="utf-8")

    exit_code = diff_daily_plan_cli_main(
        [
            "--account-id",
            "paper_sandbox",
            "--date",
            "2026-05-20",
            "--baseline-plan",
            str(baseline),
            "--regenerated-plan",
            str(regenerated),
            "--output-dir",
            str(output_dir),
            "--json",
        ]
    )

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["overall_status"] == STATUS_WARNING
    assert output["write_executed"] is False
    assert output["notion_api_called"] is False
    assert output["notion_write_export_sync_executed"] is False
    assert (output_dir / "paper_daily_plan_diff_20260520.json").exists()
    assert (output_dir / "paper_daily_plan_diff_20260520.md").exists()
