import json
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

import core.universe_manager as universe_manager


@pytest.fixture
def tmp_path() -> Path:
    root = Path("_tmp_test_artifacts")
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"universe_asof_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        if path.exists():
            shutil.rmtree(path)


def _write_snapshot(target_dir: Path, date_str: str, payload: dict) -> Path:
    path = target_dir / f"universe_snapshot_{date_str.replace('-', '')}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def test_load_universe_snapshot_as_of_quarter_uses_latest_snapshot_within_same_quarter(tmp_path: Path):
    target_dir = tmp_path / "universe"
    _write_snapshot(target_dir, "2026-04-01", {"removed": ["OLD"]})
    chosen = _write_snapshot(target_dir, "2026-05-10", {"removed": ["MID"]})
    _write_snapshot(target_dir, "2026-05-20", {"removed": ["FUTURE"]})

    result = universe_manager.load_universe_snapshot_as_of_quarter("2026-05-12", snapshots_dir=target_dir)

    assert result["snapshot"]["removed"] == ["MID"]
    assert result["metadata"]["snapshot_path"] == str(chosen)
    assert result["metadata"]["snapshot_date"] == "2026-05-10"
    assert result["metadata"]["snapshot_quarter"] == "2026Q2"
    assert result["metadata"]["fallback_used"] is False
    assert result["metadata"]["warning"] is None


def test_load_universe_snapshot_as_of_quarter_blocks_future_snapshot(tmp_path: Path):
    target_dir = tmp_path / "universe"
    chosen = _write_snapshot(target_dir, "2026-04-01", {"removed": ["APR"]})
    _write_snapshot(target_dir, "2026-05-20", {"removed": ["FUTURE"]})

    result = universe_manager.load_universe_snapshot_as_of_quarter("2026-05-12", snapshots_dir=target_dir)

    assert result["snapshot"]["removed"] == ["APR"]
    assert result["metadata"]["snapshot_path"] == str(chosen)
    assert result["metadata"]["snapshot_date"] == "2026-04-01"


def test_load_universe_snapshot_as_of_quarter_falls_back_to_prior_quarter_with_warning(tmp_path: Path):
    target_dir = tmp_path / "universe"
    chosen = _write_snapshot(target_dir, "2026-03-31", {"removed": ["Q1"]})
    _write_snapshot(target_dir, "2026-05-20", {"removed": ["FUTURE"]})

    result = universe_manager.load_universe_snapshot_as_of_quarter("2026-05-12", snapshots_dir=target_dir)

    assert result["snapshot"]["removed"] == ["Q1"]
    assert result["metadata"]["snapshot_path"] == str(chosen)
    assert result["metadata"]["snapshot_date"] == "2026-03-31"
    assert result["metadata"]["snapshot_quarter"] == "2026Q1"
    assert result["metadata"]["fallback_used"] is True
    assert "using latest prior snapshot" in result["metadata"]["warning"]


def test_load_latest_universe_snapshot_behavior_is_unchanged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    target_dir = tmp_path / "universe"
    _write_snapshot(target_dir, "2026-04-01", {"removed": ["OLD"]})
    _write_snapshot(target_dir, "2026-05-20", {"removed": ["LATEST"]})

    monkeypatch.setattr(universe_manager, "OUTPUTS", tmp_path)

    latest = universe_manager.load_latest_universe_snapshot()

    assert latest["removed"] == ["LATEST"]
