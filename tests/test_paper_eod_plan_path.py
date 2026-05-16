import shutil
from pathlib import Path
from uuid import uuid4

import pytest

import scripts.run_paper_eod_update as run_paper_eod_update
from core.paths import paper_daily_action_plan_path


@pytest.fixture
def tmp_path() -> Path:
    root = Path("_tmp_test_artifacts")
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"paper_eod_plan_path_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        if path.exists():
            shutil.rmtree(path)


def test_build_paper_eod_paths_defaults_to_paper_daily_plan():
    paths = run_paper_eod_update.build_paper_eod_paths("20260512")
    assert paths["input_report"] == paper_daily_action_plan_path("20260512")


def test_build_paper_eod_paths_normalizes_dashed_date():
    paths = run_paper_eod_update.build_paper_eod_paths("2026-05-12")
    assert paths["input_report"] == paper_daily_action_plan_path("20260512")


def test_build_paper_eod_paths_uses_plan_path_override(tmp_path: Path):
    override_path = tmp_path / "custom_paper_plan.md"
    paths = run_paper_eod_update.build_paper_eod_paths("20260512", plan_path=override_path)
    assert paths["input_report"] == override_path


def test_run_paper_eod_dry_run_does_not_fallback_to_front_plan(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    missing_paper_plan = tmp_path / "paper_test" / "daily_action_plan_20260512.md"
    missing_paper_plan.parent.mkdir(parents=True, exist_ok=True)
    front_plan = tmp_path / "front_test" / "daily_action_plan_20260512.md"
    front_plan.parent.mkdir(parents=True, exist_ok=True)
    front_plan.write_text("front plan should not be used", encoding="utf-8")

    monkeypatch.setattr(
        run_paper_eod_update,
        "paper_daily_action_plan_path",
        lambda date_str: missing_paper_plan,
    )

    exit_code = run_paper_eod_update.run_paper_eod_dry_run(
        "20260512",
        allow_empty_journal=True,
        commit=False,
    )

    captured = capsys.readouterr().out
    assert exit_code == 1
    assert str(missing_paper_plan) in captured
    assert "ERROR: input report not found" in captured
    assert str(front_plan) not in captured
