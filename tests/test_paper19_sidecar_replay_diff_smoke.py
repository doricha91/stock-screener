from __future__ import annotations

import json

from core.paper_replay_diff import (
    CATEGORY_CONFIG_OR_UNIVERSE_DIFF,
    CATEGORY_NO_DIFF,
    CATEGORY_QUANTITY_DIFF,
    CATEGORY_STATE_OR_MARKET_FINGERPRINT_DIFF,
    CATEGORY_WARNING_DIFF,
    STATUS_FAIL,
    STATUS_PASS,
    STATUS_WARNING,
    compare_daily_plan_files,
)
from scripts.dev.diff_daily_plan import main as diff_daily_plan_cli_main


def _sidecar(**overrides) -> dict:
    payload = {
        "schema_version": "paper_daily_plan.v1",
        "account_id": "paper_sandbox",
        "plan_date": "2026-05-20",
        "run_mode": "official",
        "official_run": True,
        "generated_at": "2026-05-20T09:00:00Z",
        "items": [
            {
                "symbol": "AAPL",
                "action": "BUY",
                "quantity": 10,
                "price": 200.0,
                "warning": None,
                "reason": "STRATEGY_ENTRY",
                "note": None,
            }
        ],
        "fingerprints": {
            "config_hash": "config-a",
            "universe_hash": "universe-a",
            "state_snapshot_path": "outputs/paper_accounts/paper_sandbox/paper_current_state_20260520.json",
            "code_commit_sha": "abc123",
            "generator_version": "paper_daily_plan.v1",
        },
    }
    payload.update(overrides)
    return payload


def _write_json(path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_sidecar_same_plan_passes(tmp_path) -> None:
    baseline = tmp_path / "baseline_sidecar.json"
    regenerated = tmp_path / "regenerated_sidecar.json"
    _write_json(baseline, _sidecar())
    _write_json(regenerated, _sidecar())

    report = compare_daily_plan_files(
        account_id="paper_sandbox",
        plan_date="2026-05-20",
        baseline_plan_path=baseline,
        regenerated_plan_path=regenerated,
    )

    assert report["overall_status"] == STATUS_PASS
    assert report["diff_categories"] == [CATEGORY_NO_DIFF]
    assert report["write_executed"] is False
    assert report["notion_api_called"] is False


def test_sidecar_quantity_changed_fails(tmp_path) -> None:
    baseline = tmp_path / "baseline_sidecar.json"
    regenerated = tmp_path / "regenerated_sidecar.json"
    changed_item = {**_sidecar()["items"][0], "quantity": 11}
    _write_json(baseline, _sidecar())
    _write_json(regenerated, _sidecar(items=[changed_item]))

    report = compare_daily_plan_files(
        account_id="paper_sandbox",
        plan_date="2026-05-20",
        baseline_plan_path=baseline,
        regenerated_plan_path=regenerated,
    )

    assert report["overall_status"] == STATUS_FAIL
    assert CATEGORY_QUANTITY_DIFF in report["diff_categories"]


def test_sidecar_warning_changed_warns(tmp_path) -> None:
    baseline = tmp_path / "baseline_sidecar.json"
    regenerated = tmp_path / "regenerated_sidecar.json"
    changed_item = {**_sidecar()["items"][0], "warning": "manual review"}
    _write_json(baseline, _sidecar())
    _write_json(regenerated, _sidecar(items=[changed_item]))

    report = compare_daily_plan_files(
        account_id="paper_sandbox",
        plan_date="2026-05-20",
        baseline_plan_path=baseline,
        regenerated_plan_path=regenerated,
    )

    assert report["overall_status"] == STATUS_WARNING
    assert CATEGORY_WARNING_DIFF in report["diff_categories"]


def test_sidecar_fingerprint_changed_warns_with_cause_candidate(tmp_path) -> None:
    baseline = tmp_path / "baseline_sidecar.json"
    regenerated = tmp_path / "regenerated_sidecar.json"
    _write_json(baseline, _sidecar())
    _write_json(
        regenerated,
        _sidecar(
            fingerprints={
                **_sidecar()["fingerprints"],
                "config_hash": "config-b",
                "state_snapshot_path": "outputs/paper_accounts/paper_sandbox/paper_current_state_20260521.json",
            }
        ),
    )

    report = compare_daily_plan_files(
        account_id="paper_sandbox",
        plan_date="2026-05-20",
        baseline_plan_path=baseline,
        regenerated_plan_path=regenerated,
    )

    assert report["overall_status"] == STATUS_WARNING
    assert CATEGORY_CONFIG_OR_UNIVERSE_DIFF in report["diff_categories"]
    assert CATEGORY_STATE_OR_MARKET_FINGERPRINT_DIFF in report["diff_categories"]
    assert any("config_hash changed" in candidate for candidate in report["cause_candidates"])
    assert any("state_snapshot_path changed" in candidate for candidate in report["cause_candidates"])
    assert all(" because " not in candidate.lower() for candidate in report["cause_candidates"])


def test_sidecar_missing_optional_fields_still_compares(tmp_path) -> None:
    baseline = tmp_path / "baseline_sidecar.json"
    regenerated = tmp_path / "regenerated_sidecar.json"
    minimal_item = {"symbol": "AAPL", "action": "BUY", "quantity": 10}
    _write_json(baseline, _sidecar(items=[minimal_item], fingerprints={}))
    _write_json(regenerated, _sidecar(items=[minimal_item], fingerprints={}))

    report = compare_daily_plan_files(
        account_id="paper_sandbox",
        plan_date="2026-05-20",
        baseline_plan_path=baseline,
        regenerated_plan_path=regenerated,
    )

    assert report["overall_status"] == STATUS_PASS
    assert report["diff_categories"] == [CATEGORY_NO_DIFF]


def test_sidecar_cli_smoke_writes_json_and_markdown_reports(tmp_path, capsys) -> None:
    baseline = tmp_path / "baseline_sidecar.json"
    regenerated = tmp_path / "regenerated_sidecar.json"
    output_dir = tmp_path / "out"
    changed_item = {**_sidecar()["items"][0], "warning": "manual review"}
    _write_json(baseline, _sidecar())
    _write_json(regenerated, _sidecar(items=[changed_item]))

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

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["overall_status"] == STATUS_WARNING
    assert output["write_executed"] is False
    assert output["notion_api_called"] is False
    assert output["notion_write_export_sync_executed"] is False
    assert (output_dir / "paper_daily_plan_diff_20260520.json").exists()
    assert (output_dir / "paper_daily_plan_diff_20260520.md").exists()
