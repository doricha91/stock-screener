from __future__ import annotations

import csv
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from core import operational_gap_recovery, operational_no_trade_gap, runbook_day_rollover
from core.operational_gap_recovery import (
    TerminalProvenNoTradePolicy,
    preview_terminal_proven_no_trade_recovery,
    resolve_operational_gap_authorizations,
    write_generic_authorization,
)
from core.runbook_calendar import load_market_calendar
from core.paper_account_paths import build_paper_account_paths
from scripts import runbook_state
from tests.test_failed_no_trade_closure import _seed_failed_attempt


ACCOUNT_ID = "paper_terminal_gap"
SOURCE_DATA_DATE = "2026-09-09"
SOURCE_TRADE_DATE = "2026-09-10"
RESUME_DATA_DATE = "2026-09-11"
RESUME_TRADE_DATE = "2026-09-14"


def _close_terminal(fixture: dict[str, object]) -> None:
    from core import failed_no_trade_closure

    result = failed_no_trade_closure.close_failed_no_trade(
        workspace=fixture["workspace"],
        account_id=str(fixture["account_id"]),
        data_date=str(fixture["data_date"]),
        trade_date=str(fixture["trade_date"]),
        failed_idempotency_key=str(fixture["failed_key"]),
        operator="terminal-test",
        reason="confirmed failed day with no execution or domain writes",
        confirm_no_actual_trades=True,
        confirm_no_reexecution=True,
        account_root=fixture["account_root"],
    )
    assert result["runner_result"] == "PASS", result


def _fixture(
    tmp_path: Path,
    *,
    account_id: str = ACCOUNT_ID,
    data_date: str = SOURCE_DATA_DATE,
    trade_date: str = SOURCE_TRADE_DATE,
) -> dict[str, object]:
    fixture = _seed_failed_attempt(
        tmp_path,
        account_id=account_id,
        data_date=data_date,
        trade_date=trade_date,
    )
    _close_terminal(fixture)
    return fixture


def _preview(
    fixture: dict[str, object],
    *,
    resume_data_date: str = RESUME_DATA_DATE,
    mode: str = "PAPER",
) -> dict[str, object]:
    return preview_terminal_proven_no_trade_recovery(
        fixture["workspace"],
        account_id=str(fixture["account_id"]),
        source_runbook_day_id=str(fixture["runbook_day_id"]),
        resume_data_date=resume_data_date,
        reason="resume after terminal no-trade gap",
        calendar=load_market_calendar(),
        confirm_paper_test=True,
        confirm_no_real_trades=True,
        confirm_gap_without_backfill=True,
        account_root=fixture["account_root"],
        account_mode_resolver=lambda _account_id: mode,
        operator="terminal-test",
    )


def _authorize(fixture: dict[str, object]) -> dict[str, object]:
    preview = _preview(fixture)
    assert preview["runner_result"] == "PASS", preview
    evidence = preview["evidence"]
    result = write_generic_authorization(
        fixture["workspace"],
        evidence=evidence,
        expected_preview_sha256=str(preview["preview_sha256"]),
        calendar=load_market_calendar(),
        account_root=fixture["account_root"],
        account_mode_resolver=lambda _account_id: "PAPER",
    )
    assert result["runner_result"] == "PASS", result
    return evidence


def _append_domain_row(path: Path, values: dict[str, str]) -> None:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        fieldnames = list(csv.DictReader(handle).fieldnames or [])
    with path.open("a", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writerow({name: values.get(name, "") for name in fieldnames})


def test_terminal_policy_accepts_only_valid_bound_closed_source(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    preview = _preview(fixture)

    assert preview["runner_result"] == "PASS"
    evidence = preview["evidence"]
    assert evidence["source_policy"] == {
        "type": "TERMINAL_PROVEN_NO_TRADE",
        "version": 1,
    }
    policy = TerminalProvenNoTradePolicy(
        Path(fixture["workspace"]),
        load_market_calendar(),
        account_mode_resolver=lambda _account_id: "PAPER",
    )
    assert policy.assess_eligibility(evidence["source"]).eligible is True

    wrong_lifecycle = dict(evidence["source"], lifecycle="COMPLETED")
    wrong = policy.assess_eligibility(wrong_lifecycle)
    assert wrong.eligible is False
    assert "source_lifecycle_not_accepted" in wrong.blockers

    mismatch = dict(evidence["source"], identity="wrong-source")
    mismatched = policy.assess_eligibility(mismatch)
    assert mismatched.eligible is False
    assert "source_identity_mismatch" in mismatched.blockers

    unsupported = _preview(fixture, mode="LIVE")
    assert unsupported["runner_result"] == "BLOCKED"
    assert "paper_or_test_account_required" in unsupported["blockers"]


@pytest.mark.parametrize("problem", ["missing", "tampered"])
def test_terminal_policy_rejects_missing_or_invalid_closure(
    tmp_path: Path, problem: str
) -> None:
    fixture = _fixture(tmp_path)
    closure_path = (
        Path(fixture["workspace"])
        / "failed_no_trade_closures"
        / f"{fixture['runbook_day_id']}.json"
    )
    if problem == "missing":
        closure_path.unlink()
    else:
        payload = json.loads(closure_path.read_text(encoding="utf-8"))
        payload["reason"] = "tampered"
        closure_path.write_text(json.dumps(payload), encoding="utf-8")

    result = _preview(fixture)
    assert result["runner_result"] == "BLOCKED"
    assert any("closure" in item for item in result["blockers"])


def test_terminal_gap_excludes_source_day_and_derives_canonical_resume(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    preview = _preview(fixture)
    assert preview["runner_result"] == "PASS"
    evidence = preview["evidence"]

    assert SOURCE_TRADE_DATE not in evidence["gap"]["trading_dates"]
    assert evidence["gap"] == {
        "start_date": "2026-09-11",
        "end_date": "2026-09-11",
        "trading_dates": ["2026-09-11"],
    }
    assert evidence["resume"] == {
        "data_date": RESUME_DATA_DATE,
        "trade_date": RESUME_TRADE_DATE,
        "runbook_day_id": runbook_state.get_runbook_day_id(
            ACCOUNT_ID, RESUME_DATA_DATE, RESUME_TRADE_DATE
        ),
    }


def test_terminal_gap_start_skips_weekend_and_market_holiday(tmp_path: Path) -> None:
    fixture = _fixture(
        tmp_path,
        account_id="paper_terminal_holiday",
        data_date="2026-09-03",
        trade_date="2026-09-04",
    )
    preview = _preview(fixture, resume_data_date="2026-09-08")
    assert preview["runner_result"] == "PASS", preview
    evidence = preview["evidence"]
    assert evidence["gap"]["start_date"] == "2026-09-08"
    assert evidence["gap"]["trading_dates"] == ["2026-09-08"]
    assert evidence["resume"]["trade_date"] == "2026-09-09"


def test_terminal_authorization_uses_generic_resolver_and_lifecycle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture(tmp_path)
    evidence = _authorize(fixture)
    calendar = load_market_calendar()
    workspace = Path(fixture["workspace"])
    paths = build_paper_account_paths(
        ACCOUNT_ID, account_root=Path(fixture["account_root"]), create=False
    )
    monkeypatch.setattr(
        operational_gap_recovery,
        "build_paper_account_paths",
        lambda _account_id, create=False: paths,
    )
    monkeypatch.setattr(
        runbook_day_rollover,
        "build_paper_account_paths",
        lambda _account_id, create=False: paths,
    )
    monkeypatch.setattr(
        operational_no_trade_gap,
        "resolve_paper_account_profile",
        lambda _account_id: SimpleNamespace(account_type="PAPER"),
    )

    unconsumed = resolve_operational_gap_authorizations(
        workspace,
        account_id=ACCOUNT_ID,
        calendar=calendar,
        account_root=fixture["account_root"],
        account_mode_resolver=lambda _account_id: "PAPER",
    )
    assert unconsumed["state"] == "UNCONSUMED"
    rollover = runbook_day_rollover.preview_rollover(
        workspace, ACCOUNT_ID, calendar, confirm_paper_test=True
    )
    assert rollover["runner_result"] == "PASS", rollover
    assert {
        "data_date": rollover["next_data_date"],
        "trade_date": rollover["next_trade_date"],
        "runbook_day_id": rollover["next_runbook_day_id"],
    } == evidence["resume"]

    uninitialized_eod = operational_gap_recovery.guard_operational_gap_boundary(
        workspace,
        account_id=ACCOUNT_ID,
        data_date=RESUME_DATA_DATE,
        trade_date=RESUME_TRADE_DATE,
        calendar=calendar,
        account_root=fixture["account_root"],
        account_mode_resolver=lambda _account_id: "PAPER",
        boundary="EOD_SNAPSHOT_WRITE",
    )
    assert uninitialized_eod["decision"] == operational_gap_recovery.GUARD_BLOCKED
    assert uninitialized_eod["reason"] == "operational_gap_target_not_initialized"

    assert runbook_state.init_state_file_for_context(
        workspace,
        ACCOUNT_ID,
        RESUME_DATA_DATE,
        RESUME_TRADE_DATE,
    )[0] == "CREATED"
    consumed = resolve_operational_gap_authorizations(
        workspace,
        account_id=ACCOUNT_ID,
        calendar=calendar,
        account_root=fixture["account_root"],
        account_mode_resolver=lambda _account_id: "PAPER",
    )
    assert consumed["state"] == "CONSUMED"
    for boundary in ("LIFECYCLE_ENTRY", "EXECUTION_COMMIT", "EOD_SNAPSHOT_WRITE"):
        guard = operational_gap_recovery.guard_operational_gap_boundary(
            workspace,
            account_id=ACCOUNT_ID,
            data_date=RESUME_DATA_DATE,
            trade_date=RESUME_TRADE_DATE,
            calendar=calendar,
            account_root=fixture["account_root"],
            account_mode_resolver=lambda _account_id: "PAPER",
            boundary=boundary,
        )
        assert guard["decision"] == operational_gap_recovery.GUARD_ALLOW


@pytest.mark.parametrize(
    "contradiction",
    ["execution", "account", "position", "current_state", "closure", "source_state"],
)
def test_terminal_late_contradiction_blocks_common_boundary(
    tmp_path: Path, contradiction: str
) -> None:
    fixture = _fixture(tmp_path)
    evidence = _authorize(fixture)
    gap_date = str(evidence["gap"]["trading_dates"][0])
    if contradiction == "execution":
        _append_domain_row(
            Path(fixture["execution_path"]),
            {"date": gap_date, "trade_id": "late-gap-trade"},
        )
    elif contradiction == "account":
        _append_domain_row(Path(fixture["account_path"]), {"snapshot_date": gap_date})
    elif contradiction == "position":
        _append_domain_row(Path(fixture["position_path"]), {"snapshot_date": gap_date})
    elif contradiction == "current_state":
        Path(fixture["account_root"], "paper_current_state_20260911.json").write_text(
            "{}", encoding="utf-8"
        )
    elif contradiction == "closure":
        path = Path(fixture["workspace"], evidence["source"]["closure_ref"])
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["reason"] = "late tamper"
        path.write_text(json.dumps(payload), encoding="utf-8")
    else:
        path = Path(fixture["state_path"])
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["updated_at"] = "2099-01-01T00:00:00+00:00"
        path.write_text(json.dumps(payload), encoding="utf-8")

    guard = operational_gap_recovery.guard_operational_gap_boundary(
        fixture["workspace"],
        account_id=ACCOUNT_ID,
        data_date=RESUME_DATA_DATE,
        trade_date=RESUME_TRADE_DATE,
        calendar=load_market_calendar(),
        account_root=fixture["account_root"],
        account_mode_resolver=lambda _account_id: "PAPER",
        boundary="EOD_SNAPSHOT_WRITE",
    )
    assert guard["decision"] == operational_gap_recovery.GUARD_BLOCKED


def test_terminal_production_activation_remains_disabled(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    result = operational_gap_recovery.authorize_terminal_proven_no_trade_recovery(
        fixture["workspace"],
        account_id=ACCOUNT_ID,
        source_runbook_day_id=str(fixture["runbook_day_id"]),
        resume_data_date=RESUME_DATA_DATE,
        reason="production must stay disabled",
        calendar=load_market_calendar(),
        confirm_paper_test=True,
        confirm_no_real_trades=True,
        confirm_gap_without_backfill=True,
        account_root=fixture["account_root"],
        account_mode_resolver=lambda _account_id: "PAPER",
        operator="terminal-test",
    )
    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "ntg_production_activation_disabled"
