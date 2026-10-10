"""Focused failures discovered by the real two-account lifecycle."""
import csv
import json

import pytest

from core.paper_account_fresh import _history_blockers
from core.paper_account_snapshot import load_account_replay_seed, PAPER_ACCOUNT_SNAPSHOT_COLUMNS
from core.paper_performance_summary import load_latest_position_snapshot_rows, build_paper_performance_summary
from core.paper_position_snapshot import PAPER_POSITION_SNAPSHOT_COLUMNS
from core.runbook_day_prep import read_account_local
from scripts import runbook_state
from scripts.runbook_completion_evidence import _csv_source, CompletionEvidenceError
from tests.paper_account_test_support import create_initialized_account_paths


@pytest.mark.parametrize("mutation", ["valid", "no_state", "bad_state", "own", "loose", "json", "unknown", "wrong_identity"])
def test_other_account_sidecar_attribution_remains_fail_closed(tmp_path, mutation):
    owner = "paper_test_b" if mutation == "own" else "paper_test_a"
    state = runbook_state.create_initial_state(owner, "2026-10-01", "2026-10-02")
    state_path = runbook_state.get_state_path_for_runbook_day_id(tmp_path, state.runbook_day_id)
    if mutation != "no_state":
        runbook_state.save_state(state, state_path)
    if mutation == "bad_state":
        state_path.write_text("{", encoding="utf-8")
    if mutation == "wrong_identity":
        raw = json.loads(state_path.read_text())
        raw["frozen_context"]["account_id"] = "different_account"
        state_path.write_text(json.dumps(raw))
    folder = tmp_path / "artifacts"
    if mutation != "loose":
        folder /= state.runbook_day_id
    folder.mkdir(parents=True)
    suffix = ".json" if mutation == "json" else ".tmp" if mutation == "unknown" else ".md"
    (folder / ("report" + suffix)).write_text("unattributed content", encoding="utf-8")
    blockers = _history_blockers(tmp_path, "paper_test_b")
    assert bool(blockers) == (mutation != "valid"), blockers


@pytest.mark.parametrize("line", [
    'set "UNRECOGNIZED=x"',
    'set "ACCOUNT_ID=duplicate"',
    'echo unsafe',
    'rem arbitrary comment',
])
def test_optional_participants_does_not_allow_other_assignments(tmp_path, line):
    path = tmp_path / "account.cmd"
    path.write_text('@echo off\nset "ACCOUNT_ID=paper_test_a"\nset "ACCOUNT_MODE=PAPER"\n' + line + '\nexit /b 0\n')
    with pytest.raises(ValueError):
        read_account_local(path)


@pytest.mark.parametrize("header", [PAPER_POSITION_SNAPSHOT_COLUMNS, [], ["wrong"]])
def test_empty_positions_require_canonical_header(tmp_path, header):
    path = tmp_path / "positions.csv"
    with path.open("w", newline="") as handle:
        csv.writer(handle).writerow(header)
    if header == PAPER_POSITION_SNAPSHOT_COLUMNS:
        assert load_latest_position_snapshot_rows(path, allowed_root=tmp_path) == ("", [])
    else:
        with pytest.raises(ValueError, match="empty"):
            load_latest_position_snapshot_rows(path, allowed_root=tmp_path)


def test_empty_positions_cannot_hide_open_holdings():
    with pytest.raises(ValueError, match="account has open positions"):
        build_paper_performance_summary([{}], [{}], [{"position_count": "1"}], "", [])


@pytest.mark.parametrize("mutation", ["none", "foreign_account", "mixed_seed", "nan", "zero"])
def test_account_replay_seed_preserves_identity_and_capital(tmp_path, mutation):
    paths = create_initialized_account_paths(tmp_path / "account", account_id="paper_test_b")
    with paths.account_snapshot_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows[0]["initial_cash"] = "112345"
    if mutation == "foreign_account":
        rows[0]["account_id"] = "paper_test_a"
    elif mutation == "mixed_seed":
        rows.append({**rows[0], "initial_cash": "100000"})
    elif mutation == "nan":
        rows[0]["initial_cash"] = "nan"
    elif mutation == "zero":
        rows[0]["initial_cash"] = "0"
    with paths.account_snapshot_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAPER_ACCOUNT_SNAPSHOT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    if mutation == "none":
        assert load_account_replay_seed(paths) == (112345, "USD")
    else:
        with pytest.raises(ValueError):
            load_account_replay_seed(paths)


def test_absent_review_source_requires_verified_no_action_and_is_pinned(tmp_path):
    path = tmp_path / "review.csv"
    args = dict(logical_ref="account:reviews/paper_manual_review_log.csv", scope_date="2026-10-02",
                date_field="review_date", loader=lambda p: [], expected_account_id="paper_test_b")
    with pytest.raises(CompletionEvidenceError, match="source_file_missing"):
        _csv_source(path, **args)
    absent = _csv_source(path, allow_absent=True, **args)
    assert absent["record_count"] == 0
    path.write_text("review_date\n", encoding="utf-8")
    assert _csv_source(path, allow_absent=True, **args) != absent
