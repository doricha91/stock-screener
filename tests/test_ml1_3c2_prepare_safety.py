from __future__ import annotations

import json
import subprocess
import sys
import stat
from dataclasses import replace
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event, current_thread

import pytest

from core import paper_first_run as prepare
from core import runbook_day_prep, runbook_retirement
from scripts import runbook_state
from tests.test_ml1_3b_prepare_first_run import (
    ACCOUNT_ID, DATA_DATE, TRADE_DATE, first_run, _prepare, _tree_bytes,
    _prepare_artifact_paths,
)


@pytest.mark.parametrize('other_date', [DATA_DATE, '2026-10-03'])
def test_overlapping_context_publish_has_one_identity(first_run, monkeypatch, other_date):
    """Pause A after the existence check; let B finish before A publishes.

    For the different-date race only, supply the same validated bootstrap to
    both callers to isolate publication from the unrelated bootstrap-date gate.
    All identity construction, binding checks, writes and final checks are real.
    """
    original_validate = prepare.validate_prepare_first_request
    def eligible(**kwargs):
        kwargs['data_date'] = DATA_DATE
        return original_validate(**kwargs)
    monkeypatch.setattr(prepare, 'validate_prepare_first_request', eligible)
    paused, release = Event(), Event()
    temp = first_run['day_local'].with_name(first_run['day_local'].name + '.tmp')
    original_write = Path.write_bytes
    context_writes = []
    def interleave(path, data):
        if path == temp and current_thread().name.startswith('first'):
            paused.set()
            assert release.wait(15), 'second invocation did not finish'
        if path == temp:
            context_writes.append(data)
        return original_write(path, data)
    monkeypatch.setattr(Path, 'write_bytes', interleave)
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix='first') as pool:
        first = pool.submit(_prepare, first_run)
        assert paused.wait(15), 'first invocation did not reach publish boundary'
        try:
            second = _prepare(first_run, other_date)
        finally:
            release.set()
        a = first.result(timeout=15)
    winners = [r for r in (a, second) if r['result'] == 'PREPARED']
    assert len(winners) == 1, (a, second)
    assert len(context_writes) == 1, 'an existing context was overwritten'
    winner = winners[0]
    before = _tree_bytes(first_run['workspace'].parent)
    assert _prepare(first_run, winner['data_date'])['result'] == 'REUSE'
    assert _tree_bytes(first_run['workspace'].parent) == before
    evidence = json.loads(prepare.prepare_evidence_path(first_run['account_paths']).read_text())
    context = runbook_day_prep.read_runbook_day_local(first_run['day_local'], account_id=ACCOUNT_ID)
    assert context['DATA_DATE'] == evidence['data_date'] == winner['data_date']
    assert len(list((first_run['workspace'] / runbook_state.STATE_DIRNAME).glob('*.json'))) == 1


@pytest.mark.parametrize('artifact', ['evidence', 'lifecycle', 'context', 'context_parent', 'state', 'state_parent', 'workspace', 'bootstrap', 'account_root'])
def test_existing_artifact_link_is_rejected_before_read(first_run, monkeypatch, artifact):
    assert _prepare(first_run)['result'] == 'PREPARED'
    day, evidence, state = _prepare_artifact_paths(first_run)
    target = {'evidence': evidence, 'lifecycle': evidence.parent, 'context': day,
              'context_parent': day.parent, 'state': state, 'state_parent': state.parent,
              'workspace': first_run['workspace'], 'bootstrap': first_run['account_paths'].account_snapshot_path,
              'account_root': first_run['account_paths'].root}[artifact]
    original = Path.is_symlink
    monkeypatch.setattr(Path, 'is_symlink', lambda p: p == target or original(p))
    original_open = Path.open
    def refuse_read(p, *args, **kwargs):
        assert p != target and target not in p.parents, 'unsafe artifact read before path check'
        return original_open(p, *args, **kwargs)
    before = _tree_bytes(first_run['workspace'].parent)
    with monkeypatch.context() as m:
        m.setattr(Path, 'open', refuse_read)
        result = _prepare(first_run)
    assert result['runner_result'] == 'BLOCKED', result
    assert _tree_bytes(first_run['workspace'].parent) == before


@pytest.mark.parametrize('artifact', ['evidence_temp', 'lifecycle_extra', 'context_temp', 'state_temp', 'state_extra'])
def test_prepared_with_unexpected_residue_is_not_reused(first_run, artifact):
    assert _prepare(first_run)['result'] == 'PREPARED'
    day, evidence, state = _prepare_artifact_paths(first_run)
    target = {'evidence_temp': evidence.with_suffix('.json.tmp'),
              'lifecycle_extra': evidence.parent / 'unknown.json',
              'context_temp': day.with_suffix('.cmd.tmp'),
              'state_temp': state.with_suffix('.json.tmp'),
              'state_extra': state.parent / 'unknown.txt'}[artifact]
    target.write_text('{}')
    before = _tree_bytes(first_run['workspace'].parent)
    assert _prepare(first_run)['runner_result'] == 'BLOCKED'
    assert _tree_bytes(first_run['workspace'].parent) == before


@pytest.mark.parametrize('mutation', ['schema', 'digest'])
def test_prepare_evidence_semantic_corruption_blocks_reuse(first_run, mutation):
    assert _prepare(first_run)['result'] == 'PREPARED'
    evidence = prepare.prepare_evidence_path(first_run['account_paths'])
    data = json.loads(evidence.read_text())
    data['schema_version' if mutation == 'schema' else 'prepare_identity_digest'] = 'invalid'
    evidence.write_text(json.dumps(data))
    before = _tree_bytes(first_run['workspace'].parent)
    assert _prepare(first_run)['runner_result'] == 'BLOCKED'
    assert _tree_bytes(first_run['workspace'].parent) == before


def test_retired_pristine_prepare_is_not_reactivated(first_run):
    result = _prepare(first_run)
    state_path = Path(result['state_path'])
    state = runbook_state.load_state(state_path)
    assert runbook_retirement.assess_zero_progress(first_run['workspace'], state_path, state)['eligible']
    retired = runbook_retirement.retire_runbook(
        first_run['workspace'], account_id=ACCOUNT_ID, data_date=DATA_DATE, trade_date=TRADE_DATE,
        runbook_day_id=state.runbook_day_id, reason='C2 zero progress fixture',
        confirm_paper_test=True, confirm_retire_zero_progress=True)
    assert retired['runner_result'] == 'PASS', retired
    before = _tree_bytes(first_run['workspace'].parent)
    assert _prepare(first_run)['result'] not in {'PREPARED', 'REUSE'}
    assert _tree_bytes(first_run['workspace'].parent) == before


def test_competing_binding_identity_cannot_publish(first_run, monkeypatch):
    paused, release = Event(), Event()
    original = prepare.write_runbook_day_local_exact
    def hold(*args, **kwargs):
        paused.set()
        assert release.wait(15)
        return original(*args, **kwargs)
    monkeypatch.setattr(prepare, 'write_runbook_day_local_exact', hold)
    registry = first_run['registry_file']
    original_bytes = registry.read_bytes()
    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(_prepare, first_run)
        assert paused.wait(15)
        try:
            changed = json.loads(original_bytes)
            changed['strategy'][0]['content']['parameters']['entry_period'] = 20
            registry.write_text(json.dumps(changed))
            competitor = _prepare(first_run)
            assert competitor['runner_result'] == 'BLOCKED', competitor
        finally:
            registry.write_bytes(original_bytes)
            release.set()
        assert first.result(timeout=15)['result'] == 'PREPARED'
    assert _prepare(first_run)['result'] == 'REUSE'


def test_exclusive_lock_cross_process_and_crash_release(first_run):
    root = first_run['account_paths'].root
    script = '''
import os, sys
from pathlib import Path
from types import SimpleNamespace
from core.paper_first_run import _prepare_write_lock
with _prepare_write_lock(SimpleNamespace(root=Path(sys.argv[1]))):
    os._exit(23)
'''
    with prepare._prepare_write_lock(first_run['account_paths']):
        result = subprocess.run([sys.executable, '-c', script, str(root)], capture_output=True, timeout=15)
        assert result.returncode != 23
        assert b'Error' in result.stderr
    result = subprocess.run([sys.executable, '-c', script, str(root)], capture_output=True, timeout=15)
    assert result.returncode == 23, result.stderr
    assert not (root / prepare.PREPARE_LOCK_FILENAME).exists()
    assert _prepare(first_run)['result'] == 'PREPARED'


@pytest.mark.parametrize('artifact', ['evidence', 'lifecycle', 'context', 'state', 'state_parent', 'bootstrap', 'account_root', 'context_parent', 'workspace'])
def test_actual_outside_symlink_does_not_read_or_write_target(first_run, monkeypatch, artifact):
    assert _prepare(first_run)['result'] == 'PREPARED'
    day, evidence, state = _prepare_artifact_paths(first_run)
    path = {'evidence': evidence, 'lifecycle': evidence.parent, 'context': day,
            'state': state, 'state_parent': state.parent,
            'bootstrap': first_run['account_paths'].account_snapshot_path,
            'account_root': first_run['account_paths'].root,
            'context_parent': day.parent, 'workspace': first_run['workspace']}[artifact]
    outside = first_run['workspace'].parent / 'outside'
    outside.mkdir()
    target = outside / path.name
    is_dir = path.is_dir()
    probe = outside / 'probe'
    try:
        probe.symlink_to(target, target_is_directory=is_dir)
    except OSError as exc:
        pytest.skip(f'actual symlink unavailable: {exc}; modeled no-read matrix runs separately')
    probe.unlink()
    path.rename(target)
    path.symlink_to(target, target_is_directory=is_dir)
    before = _tree_bytes(outside)
    original = Path.open
    def no_follow(p, *args, **kwargs):
        assert p != path and path not in p.parents
        assert p != target and target not in p.parents
        return original(p, *args, **kwargs)
    with monkeypatch.context() as m:
        m.setattr(Path, 'open', no_follow)
        assert _prepare(first_run)['runner_result'] == 'BLOCKED'
    assert _tree_bytes(outside) == before


@pytest.mark.parametrize('kind', ['recovery', 'failed', 'terminal', 'legacy'])
def test_progressed_without_prepare_evidence_preserves_resume(first_run, kind):
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    state = runbook_state.start_stage(state, 'A')
    if kind == 'recovery':
        authorization = dict.fromkeys(('logical_operation_id', 'failed_idempotency_key',
            'assessment_path', 'assessment_sha256', 'state_before_sha256', 'operator',
            'reason', 'issued_at'), 'fixture')
        authorization.update(authorization_id='attempt', stage_id='B', status='AUTHORIZED')
        state = replace(state, recovery_authorizations={'attempt': authorization})
    elif kind == 'failed':
        state = replace(state, current_status='FAILED', last_error={'reason': 'fixture'})
    elif kind == 'terminal':
        state = replace(state, current_stage='F', current_status='PASS', last_completed_stage='F', last_completed_step=21)
    elif kind == 'legacy':
        state = replace(state, schema_version=runbook_state.SCHEMA_VERSION,
                        frozen_context=runbook_state.FrozenRunbookContext(ACCOUNT_ID, DATA_DATE, TRADE_DATE))
    assert not runbook_state.validate_state(state)
    path = _prepare_artifact_paths(first_run)[2]
    runbook_state.save_state(state, path)
    before = _tree_bytes(first_run['workspace'].parent)
    result = _prepare(first_run)
    assert result['result'] == 'RESUME_EXISTING_RUN', result
    assert _tree_bytes(first_run['workspace'].parent) == before
    assert not prepare.prepare_evidence_path(first_run['account_paths']).exists()


@pytest.mark.parametrize('directory', ['runbook_recoveries', 'failed_no_trade_closures', 'operational_no_trade_gaps', 'runbook_retirements'])
def test_lifecycle_history_without_state_never_becomes_fresh(first_run, directory):
    path = first_run['workspace'] / directory / 'history.json'
    path.parent.mkdir()
    path.write_text(json.dumps({'account_id': ACCOUNT_ID}))
    before = _tree_bytes(first_run['workspace'].parent)
    assert _prepare(first_run)['runner_result'] == 'BLOCKED'
    assert _tree_bytes(first_run['workspace'].parent) == before


@pytest.mark.parametrize('mutation', ['malformed', 'schema', 'unattributable'])
def test_bad_state_blocks_prepare_without_rewrite(first_run, mutation):
    result = _prepare(first_run)
    path = Path(result['state_path'])
    if mutation == 'malformed':
        path.write_text('{')
    elif mutation == 'schema':
        data = json.loads(path.read_text())
        data['schema_version'] = 'unknown'
        path.write_text(json.dumps(data))
    else:
        (path.parent / 'unknown.json').write_text('{}')
    before = _tree_bytes(first_run['workspace'].parent)
    assert _prepare(first_run)['runner_result'] == 'BLOCKED'
    assert _tree_bytes(first_run['workspace'].parent) == before


def test_junction_attribute_is_rejected_without_following(tmp_path, monkeypatch):
    alias = tmp_path / 'junction'
    alias.mkdir()
    original = Path.lstat
    def junction_stat(path, *args, **kwargs):
        if path == alias:
            return SimpleNamespace(st_mode=stat.S_IFDIR,
                                   st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT)
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'lstat', junction_stat)
    with pytest.raises(ValueError, match='prepare_path_unsafe'):
        prepare._assert_regular_path(alias / 'artifact.json')


@pytest.mark.parametrize('kind', ['evidence', 'context_temp', 'state_temp'])
def test_dangling_link_is_not_missing_artifact(first_run, monkeypatch, kind):
    day, evidence, state = _prepare_artifact_paths(first_run)
    path = {'evidence': evidence, 'context_temp': day.with_suffix('.cmd.tmp'),
            'state_temp': state.with_suffix('.json.tmp')}[kind]
    # Ensure traversal sees the dangling entry, but exists() remains false.
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    original_link, original_exists = Path.is_symlink, Path.exists
    monkeypatch.setattr(Path, 'is_symlink', lambda p: p == path or original_link(p))
    monkeypatch.setattr(Path, 'exists', lambda p: False if p == path else original_exists(p))
    before = _tree_bytes(first_run['workspace'].parent)
    assert _prepare(first_run)['runner_result'] == 'BLOCKED'
    assert _tree_bytes(first_run['workspace'].parent) == before


def test_stale_lock_blocks_prepared_and_stage_a(first_run):
    assert _prepare(first_run)['result'] == 'PREPARED'
    lock = first_run['account_paths'].root / prepare.PREPARE_LOCK_FILENAME
    lock.touch()
    before = _tree_bytes(first_run['workspace'].parent)
    assert _prepare(first_run)['runner_result'] == 'BLOCKED'
    assert prepare.stage_a_prepare_guard(first_run['workspace'], ACCOUNT_ID, DATA_DATE, TRADE_DATE) == 'prepare_lock_present'
    assert _tree_bytes(first_run['workspace'].parent) == before


def test_real_failed_closure_remains_terminal(tmp_path, monkeypatch):
    from tests import test_failed_no_trade_closure as fixtures
    from core import paper_account_paths
    from core.runbook_calendar import load_market_calendar
    fixture = fixtures._seed_failed_attempt(tmp_path)
    assert fixtures._close(fixture)['runner_result'] == 'PASS'
    monkeypatch.setattr(paper_account_paths, 'PAPER_ACCOUNTS_ROOT', tmp_path / 'outputs' / 'paper_accounts')
    account_local = tmp_path / '_account.local.cmd'
    account_local.write_text(f'@echo off\nset "ACCOUNT_ID={fixtures.ACCOUNT_ID}"\nset "ACCOUNT_MODE=PAPER"\nexit /b 0\n')
    before = _tree_bytes(tmp_path)
    result = prepare.prepare_first_run(account_id=fixtures.ACCOUNT_ID, data_date=fixtures.DATA_DATE,
        workspace=fixture['workspace'], account_local_path=account_local,
        runbook_day_local_path=tmp_path / '_runbook_day.local.cmd', calendar=load_market_calendar())
    assert result['result'] == 'RECOVERY_REQUIRED', result
    assert _tree_bytes(tmp_path) == before


@pytest.mark.parametrize('kind', ['legacy_recovery', 'operational_gap'])
def test_authorized_recovery_cannot_be_replaced_by_fresh_prepare(tmp_path, monkeypatch, kind):
    from tests import test_runbook_recovery as fixtures
    from core import paper_account_paths, runbook_recovery, runbook_day_rollover, operational_gap_recovery
    from core.runbook_calendar import load_market_calendar
    monkeypatch.setattr(paper_account_paths, 'PAPER_ACCOUNTS_ROOT', tmp_path / 'outputs' / 'paper_accounts')
    for module in (runbook_recovery, runbook_day_rollover, operational_gap_recovery):
        monkeypatch.setattr(module, 'build_paper_account_paths', paper_account_paths.build_paper_account_paths)
    monkeypatch.setattr(runbook_recovery, 'resolve_authoritative_account_mode', lambda _: 'PAPER')
    workspace, source, _ = fixtures._seed_incident(tmp_path)
    args = fixtures._arguments(workspace)
    if kind == 'legacy_recovery':
        result = runbook_recovery.authorize_recovery(**args)
    else:
        root = tmp_path / 'outputs' / 'paper_accounts' / fixtures.ACCOUNT_ID
        preview = operational_gap_recovery.preview_progressed_active_recovery(
            **args, account_root=root, account_mode_resolver=lambda _: 'PAPER')
        assert preview['runner_result'] == 'PASS', preview
        result = operational_gap_recovery.write_generic_authorization(
            workspace=workspace, calendar=load_market_calendar(), account_root=root,
            account_mode_resolver=lambda _: 'PAPER', evidence=preview['evidence'],
            expected_preview_sha256=preview['preview_sha256'])
    assert result['runner_result'] == 'PASS', result
    account_local = tmp_path / '_account.local.cmd'
    account_local.write_text(f'@echo off\nset "ACCOUNT_ID={fixtures.ACCOUNT_ID}"\nset "ACCOUNT_MODE=PAPER"\nexit /b 0\n')
    before = _tree_bytes(tmp_path)
    retry = prepare.prepare_first_run(account_id=fixtures.ACCOUNT_ID,
        data_date=fixtures.SOURCE_DATA_DATE, workspace=workspace,
        account_local_path=account_local, runbook_day_local_path=tmp_path / '_runbook_day.local.cmd',
        calendar=load_market_calendar())
    assert retry['runner_result'] == 'BLOCKED', retry
    assert _tree_bytes(tmp_path) == before


@pytest.mark.parametrize('boundary,expected', [('before_context', 'PREPARED'), ('before_state', 'RECOVERY_REQUIRED'), ('after_state', 'REUSE')])
def test_process_exit_releases_lock_and_preserves_c1_contract(first_run, boundary, expected):
    script = '''
import os, sys
from pathlib import Path
from core import paper_first_run as p, paper_account_paths as paths, paper_account_profile as profiles, paper_account_binding as binding
from core.runbook_calendar import load_market_calendar
profiles._default_settings_path = lambda: Path(sys.argv[1])
binding.paper_binding_registry_path = lambda: Path(sys.argv[2])
paths.PAPER_ACCOUNTS_ROOT = Path(sys.argv[3])
def terminate(*args, **kwargs):
    os._exit(23)
if sys.argv[7] == 'before_context':
    p.write_runbook_day_local_exact = terminate
elif sys.argv[7] == 'before_state':
    p.runbook_state.save_state = terminate
else:
    p._validate_existing_prepared = terminate
print(p.prepare_first_run(account_id='paper_fresh', data_date='2026-10-02',
    workspace=sys.argv[4], account_local_path=sys.argv[5], runbook_day_local_path=sys.argv[6],
    calendar=load_market_calendar()))
'''
    result = subprocess.run([sys.executable, '-c', script, str(first_run['account_file']),
        str(first_run['registry_file']), str(first_run['account_paths'].root.parent),
        str(first_run['workspace']), str(first_run['account_local']), str(first_run['day_local']), boundary],
        capture_output=True, timeout=20)
    assert result.returncode == 23, (result.stdout, result.stderr)
    assert _prepare(first_run)['result'] == expected


def test_non_directory_history_root_blocks_reuse(first_run):
    assert _prepare(first_run)['result'] == 'PREPARED'
    (first_run['workspace'] / 'runbook_recoveries').write_text('{}')
    before = _tree_bytes(first_run['workspace'].parent)
    assert _prepare(first_run)['runner_result'] == 'BLOCKED'
    assert _tree_bytes(first_run['workspace'].parent) == before
