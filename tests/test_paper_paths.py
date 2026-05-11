from core.paths import (
    current_state_snapshot_path,
    paper_account_snapshot_path,
    paper_current_state_snapshot_path,
    paper_execution_log_path,
)
from scripts.run_paper_eod_update import build_paper_eod_paths, run_paper_eod_dry_run


def test_paper_path_differs_from_front_test_path():
    assert current_state_snapshot_path("2026-05-07") != paper_current_state_snapshot_path("2026-05-07")


def test_paper_state_is_under_paper_test_dir():
    assert "paper_test" in str(paper_current_state_snapshot_path("2026-05-07"))


def test_live_front_test_state_path_is_unchanged():
    path = str(current_state_snapshot_path("2026-05-07"))
    assert "front_test" in path
    assert "paper_test" not in path


def test_paper_execution_log_path():
    path = paper_execution_log_path()
    assert path.name == "paper_execution_log.csv"
    assert "paper_test" in str(path)


def test_paper_account_snapshot_path():
    path = paper_account_snapshot_path()
    assert path.name == "paper_account_snapshot.csv"
    assert "paper_test" in str(path)


def test_paper_eod_build_paths_are_separated():
    paths = build_paper_eod_paths("20260507")
    assert "front_test" in str(paths["input_report"])
    assert "paper_test" in str(paths["paper_state"])
    assert "paper_test" in str(paths["paper_execution_log"])
    assert "paper_test" in str(paths["paper_account_snapshot"])


def test_paper_eod_dry_run_smoke(capsys):
    exit_code = run_paper_eod_dry_run("20260507")
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "PAPER EOD UPDATE - SAFE DRY RUN" in output
    assert "path separation OK" in output
    assert "no live/front-test files will be written" in output
