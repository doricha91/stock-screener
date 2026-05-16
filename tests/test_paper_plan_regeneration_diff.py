import shutil
from pathlib import Path
from uuid import uuid4

import pytest

import scripts.check_paper_plan_regeneration_diff as diff_script


@pytest.fixture
def tmp_path() -> Path:
    root = Path("_tmp_test_artifacts")
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"paper_plan_diff_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        if path.exists():
            shutil.rmtree(path)


def test_check_paper_plan_regeneration_diff_reports_same_and_preserves_base(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    base_plan = tmp_path / "daily_action_plan_20260512.md"
    regenerated_plan = tmp_path / "replay_diff" / "regenerated_daily_action_plan_20260512.md"
    diff_report = tmp_path / "replay_diff" / "daily_plan_diff_20260512.md"
    regenerated_config = tmp_path / "replay_diff" / "regenerated_paper_config_snapshot_20260512.json"
    regenerated_archive = tmp_path / "replay_diff" / "archive" / "config_snapshots"
    base_content = "# Plan\n\n## Confirmed Orders\n\n- NONE\n"
    base_plan.write_text(base_content, encoding="utf-8")

    def _fake_regenerate(**kwargs):
        regenerated_plan.parent.mkdir(parents=True, exist_ok=True)
        regenerated_plan.write_text(base_content, encoding="utf-8")
        regenerated_config.write_text("{}", encoding="utf-8")
        return str(regenerated_plan)

    monkeypatch.setattr(diff_script, "regenerate_paper_plan_for_diff", _fake_regenerate)

    result = diff_script.check_paper_plan_regeneration_diff(
        "20260512",
        base_plan_path=base_plan,
        regenerated_plan_path=regenerated_plan,
        diff_report_path=diff_report,
        regenerated_config_snapshot_path=regenerated_config,
        regenerated_config_snapshot_archive_dir=regenerated_archive,
    )

    assert result["status"] == diff_script.STATUS_SAME
    assert base_plan.read_text(encoding="utf-8") == base_content
    assert regenerated_plan.exists()
    assert diff_report.exists()
    assert "Status: `SAME`" in diff_report.read_text(encoding="utf-8")


def test_check_paper_plan_regeneration_diff_reports_diff(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    base_plan = tmp_path / "daily_action_plan_20260512.md"
    regenerated_plan = tmp_path / "replay_diff" / "regenerated_daily_action_plan_20260512.md"
    diff_report = tmp_path / "replay_diff" / "daily_plan_diff_20260512.md"
    regenerated_config = tmp_path / "replay_diff" / "regenerated_paper_config_snapshot_20260512.json"
    regenerated_archive = tmp_path / "replay_diff" / "archive" / "config_snapshots"
    base_plan.write_text("# Plan\n\n## Confirmed Orders\n\n- BUY AAPL\n", encoding="utf-8")

    def _fake_regenerate(**kwargs):
        regenerated_plan.parent.mkdir(parents=True, exist_ok=True)
        regenerated_plan.write_text("# Plan\n\n## Confirmed Orders\n\n- BUY MSFT\n", encoding="utf-8")
        regenerated_config.write_text("{}", encoding="utf-8")
        return str(regenerated_plan)

    monkeypatch.setattr(diff_script, "regenerate_paper_plan_for_diff", _fake_regenerate)

    result = diff_script.check_paper_plan_regeneration_diff(
        "20260512",
        base_plan_path=base_plan,
        regenerated_plan_path=regenerated_plan,
        diff_report_path=diff_report,
        regenerated_config_snapshot_path=regenerated_config,
        regenerated_config_snapshot_archive_dir=regenerated_archive,
    )

    report_text = diff_report.read_text(encoding="utf-8")
    assert result["status"] == diff_script.STATUS_DIFF
    assert "Status: `DIFF`" in report_text
    assert "## Diff Excerpt" in report_text
    assert "Confirmed Orders" in report_text


def test_check_paper_plan_regeneration_diff_reports_missing_base_without_overwriting(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    base_plan = tmp_path / "daily_action_plan_20260512.md"
    regenerated_plan = tmp_path / "replay_diff" / "regenerated_daily_action_plan_20260512.md"
    diff_report = tmp_path / "replay_diff" / "daily_plan_diff_20260512.md"
    regenerated_config = tmp_path / "replay_diff" / "regenerated_paper_config_snapshot_20260512.json"
    regenerated_archive = tmp_path / "replay_diff" / "archive" / "config_snapshots"

    monkeypatch.setattr(
        diff_script,
        "regenerate_paper_plan_for_diff",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("regen should not run when base is missing")),
    )

    result = diff_script.check_paper_plan_regeneration_diff(
        "20260512",
        base_plan_path=base_plan,
        regenerated_plan_path=regenerated_plan,
        diff_report_path=diff_report,
        regenerated_config_snapshot_path=regenerated_config,
        regenerated_config_snapshot_archive_dir=regenerated_archive,
    )

    assert result["status"] == diff_script.STATUS_MISSING_BASE
    assert diff_report.exists()
    assert not regenerated_plan.exists()
    assert "Status: `MISSING_BASE`" in diff_report.read_text(encoding="utf-8")


def test_check_paper_plan_regeneration_diff_uses_replay_diff_paths_by_default(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    base_plan = tmp_path / "paper_test" / "daily_action_plan_20260512.md"
    base_plan.parent.mkdir(parents=True, exist_ok=True)
    base_plan.write_text("# Plan\n", encoding="utf-8")
    replay_dir = tmp_path / "paper_test" / "replay_diff"

    monkeypatch.setattr(diff_script, "paper_daily_action_plan_path", lambda date_str: base_plan)
    monkeypatch.setattr(diff_script, "paper_regenerated_daily_action_plan_path", lambda date_str: replay_dir / "regenerated_daily_action_plan_20260512.md")
    monkeypatch.setattr(diff_script, "paper_daily_plan_diff_report_path", lambda date_str: replay_dir / "daily_plan_diff_20260512.md")
    monkeypatch.setattr(diff_script, "paper_replay_diff_config_snapshot_path", lambda date_str: replay_dir / "regenerated_paper_config_snapshot_20260512.json")
    monkeypatch.setattr(diff_script, "paper_replay_diff_config_snapshot_archive_dir", lambda: replay_dir / "archive" / "config_snapshots")

    def _fake_regenerate(**kwargs):
        plan_path = kwargs["regenerated_plan_path"]
        config_path = kwargs["regenerated_config_snapshot_path"]
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text("# Plan\n", encoding="utf-8")
        config_path.write_text("{}", encoding="utf-8")
        return str(plan_path)

    monkeypatch.setattr(diff_script, "regenerate_paper_plan_for_diff", _fake_regenerate)

    result = diff_script.check_paper_plan_regeneration_diff("20260512")

    assert result["status"] == diff_script.STATUS_SAME
    assert "replay_diff" in str(result["regenerated_plan_path"])
    assert "replay_diff" in str(result["diff_report_path"])
    assert "front_test" not in str(result["regenerated_plan_path"])
