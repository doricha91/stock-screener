from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.dev.capture_daily_plan_baseline as capture_cli


def _sidecar(**overrides) -> dict:
    payload = {
        "schema_version": "paper_daily_plan.v1",
        "account_id": "paper_sandbox",
        "plan_date": "2026-05-26",
        "run_mode": "baseline_capture",
        "official_run": False,
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
            "generator_version": "paper_daily_plan.v1",
            "config_hash": "sha256:abc",
            "config_hash_policy": "paper_config_hash.v1",
        },
    }
    payload.update(overrides)
    return payload


def test_capture_cli_help_exits_zero() -> None:
    with pytest.raises(SystemExit) as exc:
        capture_cli.main(["--help"])
    assert exc.value.code == 0


def test_capture_cli_requires_output_dir() -> None:
    with pytest.raises(SystemExit) as exc:
        capture_cli.main(["--account-id", "paper_sandbox", "--date", "2026-05-26"])
    assert exc.value.code == 2


def test_capture_writes_only_under_tmp_output_dir_and_reports_safety(monkeypatch, tmp_path: Path) -> None:
    captured: dict = {}
    output_dir = tmp_path / "capture"
    monkeypatch.setattr(
        capture_cli,
        "load_official_paper_state_for_daily_plan",
        lambda plan_date: {"cash": 100000},
    )

    def _fake_generate_daily_plan(**kwargs):
        captured.update(kwargs)
        output_path = Path(kwargs["output_path"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("# controlled plan\n", encoding="utf-8")
        Path(kwargs["config_snapshot_path"]).parent.mkdir(parents=True, exist_ok=True)
        Path(kwargs["config_snapshot_path"]).write_text(
            json.dumps({"schema_version": "paper_config_snapshot.test"}),
            encoding="utf-8",
        )
        Path(kwargs["json_sidecar_path"]).write_text(
            json.dumps(
                _sidecar(
                    account_id=kwargs["account_id"],
                    plan_date=kwargs["date_str"],
                    run_mode=kwargs["run_mode"],
                    official_run=kwargs["official_run"],
                )
            ),
            encoding="utf-8",
        )
        return str(output_path)

    monkeypatch.setattr(capture_cli, "generate_daily_plan", _fake_generate_daily_plan)

    summary, exit_code = capture_cli.run_capture_daily_plan_baseline(
        account_id="paper_sandbox",
        date="2026-05-26",
        output_dir=output_dir,
    )

    assert exit_code == 0
    assert Path(summary["markdown_path"]).is_relative_to(output_dir)
    assert Path(summary["sidecar_json_path"]).is_relative_to(output_dir)
    assert Path(summary["config_snapshot_path"]).is_relative_to(output_dir)
    assert Path(summary["markdown_path"]).exists()
    assert Path(summary["sidecar_json_path"]).exists()
    assert Path(summary["config_snapshot_path"]).exists()
    assert captured["account_id"] == "paper_sandbox"
    assert captured["date_str"] == "2026-05-26"
    assert captured["output_path"] == output_dir / "daily_action_plan_20260526.md"
    assert captured["run_mode"] == "baseline_capture"
    assert captured["official_run"] is False
    assert captured["market_state_write_log"] is False
    assert summary["sidecar_eligibility"]["eligible"] is True
    assert summary["write_executed"] is False
    assert summary["actual_executed"] is False
    assert summary["notion_api_called"] is False
    assert summary["notion_sync_executed"] is False
    assert summary["notion_write_export_sync_executed"] is False
    assert summary["commit_append_executed"] is False


def test_sidecar_eligibility_warns_when_config_hash_missing(tmp_path: Path) -> None:
    sidecar_path = tmp_path / "daily_action_plan_20260526.json"
    payload = _sidecar(fingerprints={"generator_version": "paper_daily_plan.v1"})
    sidecar_path.write_text(json.dumps(payload), encoding="utf-8")

    eligibility = capture_cli.inspect_sidecar_eligibility(
        sidecar_path,
        expected_account_id="paper_sandbox",
        expected_plan_date="2026-05-26",
    )

    assert eligibility["eligible"] is True
    assert "config_hash missing" in eligibility["warnings"]
    assert "config_hash_policy missing or not paper_config_hash.v1" in eligibility["warnings"]


def test_sidecar_eligibility_fails_for_missing_sidecar(tmp_path: Path) -> None:
    eligibility = capture_cli.inspect_sidecar_eligibility(
        tmp_path / "missing.json",
        expected_account_id="paper_sandbox",
        expected_plan_date="2026-05-26",
    )

    assert eligibility["eligible"] is False
    assert eligibility["status"] == "missing_sidecar"


def test_sidecar_eligibility_fails_for_malformed_sidecar(tmp_path: Path) -> None:
    sidecar_path = tmp_path / "daily_action_plan_20260526.json"
    sidecar_path.write_text("{bad json", encoding="utf-8")

    eligibility = capture_cli.inspect_sidecar_eligibility(
        sidecar_path,
        expected_account_id="paper_sandbox",
        expected_plan_date="2026-05-26",
    )

    assert eligibility["eligible"] is False
    assert eligibility["status"] == "malformed_sidecar"
