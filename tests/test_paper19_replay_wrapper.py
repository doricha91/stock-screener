from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.dev.replay_daily_plan_diff as replay_wrapper
from core.paper_replay_diff import (
    CATEGORY_ACCOUNT_DATE_MISMATCH,
    CATEGORY_CONFIG_OR_UNIVERSE_DIFF,
    CATEGORY_MISSING_INPUT,
    CATEGORY_QUANTITY_DIFF,
    STATUS_FAIL,
    STATUS_PASS,
    STATUS_WARNING,
)


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
            "generator_version": "paper_daily_plan.v1",
            "config_hash": "sha256:aaa",
            "config_hash_policy": "paper_config_hash.v1",
        },
    }
    payload.update(overrides)
    return payload


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _patch_replay_generation(monkeypatch: pytest.MonkeyPatch, regenerated_payload: dict) -> None:
    monkeypatch.setattr(
        replay_wrapper,
        "load_official_paper_state_for_daily_plan",
        lambda plan_date: {"cash": 100000},
    )

    def _fake_generate_daily_plan(**kwargs):
        output_path = Path(kwargs["output_path"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("# regenerated\n", encoding="utf-8")
        sidecar = {
            **regenerated_payload,
            "account_id": kwargs["account_id"],
            "plan_date": kwargs["date_str"],
            "run_mode": kwargs["run_mode"],
            "official_run": kwargs["official_run"],
        }
        output_path.with_suffix(".json").write_text(json.dumps(sidecar), encoding="utf-8")
        return str(output_path)

    monkeypatch.setattr(replay_wrapper, "generate_daily_plan", _fake_generate_daily_plan)


def test_replay_wrapper_help_exits_zero() -> None:
    with pytest.raises(SystemExit) as exc:
        replay_wrapper.main(["--help"])
    assert exc.value.code == 0


def test_replay_wrapper_baseline_missing_fails_without_generation(monkeypatch, tmp_path: Path) -> None:
    called = {"generate": False}
    monkeypatch.setattr(replay_wrapper, "generate_daily_plan", lambda **kwargs: called.__setitem__("generate", True))

    summary, exit_code = replay_wrapper.run_replay_daily_plan_diff(
        account_id="paper_sandbox",
        date="2026-05-20",
        baseline_plan=tmp_path / "missing.json",
        output_dir=tmp_path / "out",
        run_id="run-missing",
    )

    assert exit_code == 1
    assert summary["overall_status"] == STATUS_FAIL
    assert summary["diff_categories"] == [CATEGORY_MISSING_INPUT]
    assert summary["write_executed"] is False
    assert summary["actual_executed"] is False
    assert called["generate"] is False


def test_replay_wrapper_baseline_account_mismatch_fails_before_generation(monkeypatch, tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    _write_json(baseline, _sidecar(account_id="other_account"))
    called = {"generate": False}
    monkeypatch.setattr(replay_wrapper, "generate_daily_plan", lambda **kwargs: called.__setitem__("generate", True))

    summary, exit_code = replay_wrapper.run_replay_daily_plan_diff(
        account_id="paper_sandbox",
        date="2026-05-20",
        baseline_plan=baseline,
        output_dir=tmp_path / "out",
        run_id="run-mismatch",
    )

    assert exit_code == 1
    assert summary["overall_status"] == STATUS_FAIL
    assert summary["diff_categories"] == [CATEGORY_ACCOUNT_DATE_MISMATCH]
    assert called["generate"] is False


def test_replay_wrapper_creates_run_dir_sidecar_and_diff_without_overwriting_baseline(monkeypatch, tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    baseline_payload = _sidecar()
    _write_json(baseline, baseline_payload)
    before = baseline.read_text(encoding="utf-8")
    _patch_replay_generation(monkeypatch, _sidecar())

    summary, exit_code = replay_wrapper.run_replay_daily_plan_diff(
        account_id="paper_sandbox",
        date="2026-05-20",
        baseline_plan=baseline,
        output_dir=tmp_path / "out",
        run_id="run-pass",
    )

    assert exit_code == 0
    assert summary["overall_status"] == STATUS_PASS
    assert Path(summary["regenerated_markdown_path"]).exists()
    assert Path(summary["regenerated_sidecar_path"]).exists()
    assert Path(summary["diff_json_path"]).exists()
    assert Path(summary["diff_markdown_path"]).exists()
    assert "run-pass" in summary["run_dir"]
    assert baseline.read_text(encoding="utf-8") == before
    assert summary["write_executed"] is False
    assert summary["actual_executed"] is False
    assert summary["notion_api_called"] is False
    assert summary["notion_sync_executed"] is False
    assert summary["notion_write_export_sync_executed"] is False
    assert summary["commit_append_executed"] is False


def test_replay_wrapper_quantity_diff_fails(monkeypatch, tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    changed_item = {**_sidecar()["items"][0], "quantity": 11}
    _write_json(baseline, _sidecar())
    _patch_replay_generation(monkeypatch, _sidecar(items=[changed_item]))

    summary, exit_code = replay_wrapper.run_replay_daily_plan_diff(
        account_id="paper_sandbox",
        date="2026-05-20",
        baseline_plan=baseline,
        output_dir=tmp_path / "out",
        run_id="run-quantity",
    )

    assert exit_code == 0
    assert summary["overall_status"] == STATUS_FAIL
    assert CATEGORY_QUANTITY_DIFF in summary["diff_categories"]


def test_replay_wrapper_config_hash_diff_warns_with_cause_candidate(monkeypatch, tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    _write_json(baseline, _sidecar())
    _patch_replay_generation(
        monkeypatch,
        _sidecar(
            fingerprints={
                "generator_version": "paper_daily_plan.v1",
                "config_hash": "sha256:bbb",
                "config_hash_policy": "paper_config_hash.v1",
            }
        ),
    )

    summary, exit_code = replay_wrapper.run_replay_daily_plan_diff(
        account_id="paper_sandbox",
        date="2026-05-20",
        baseline_plan=baseline,
        output_dir=tmp_path / "out",
        run_id="run-config",
    )

    assert exit_code == 0
    assert summary["overall_status"] == STATUS_WARNING
    assert CATEGORY_CONFIG_OR_UNIVERSE_DIFF in summary["diff_categories"]
    assert any("config_hash changed" in candidate for candidate in summary["cause_candidates"])
    assert all(" because " not in candidate.lower() for candidate in summary["cause_candidates"])
