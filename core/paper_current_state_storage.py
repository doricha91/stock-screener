from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paper_current_state_serializer import paper_account_state_to_current_state_dict
from core.paper_safety import assert_paper_path
from core.paths import PAPER_TEST_DIR


REQUIRED_CURRENT_STATE_FIELDS = [
    "current_symbols",
    "current_cash_ratio",
    "current_hedge_ratio",
    "absolute_cash",
    "shares",
    "avg_price",
    "highest_prices",
]


def build_paper_current_state_backup_path(
    output_path: Path,
    archive_dir: Path,
    now: datetime | None = None,
) -> Path:
    timestamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
    return archive_dir / f"{output_path.stem}_{timestamp}_backup{output_path.suffix}"


def _validate_saved_current_state_payload(data: dict[str, Any]) -> None:
    missing = [field for field in REQUIRED_CURRENT_STATE_FIELDS if field not in data]
    if missing:
        raise ValueError(f"missing required current_state fields: {missing}")
    if "positions" in data:
        raise ValueError("positions top-level field must not be present")


def save_paper_current_state(
    state,
    date_str: str,
    output_path: Path,
    archive_dir: Path,
    now: datetime | None = None,
) -> dict[str, Any]:
    assert_paper_path(output_path, PAPER_TEST_DIR)
    assert_paper_path(archive_dir, PAPER_TEST_DIR)

    payload = paper_account_state_to_current_state_dict(state, date_str)
    _validate_saved_current_state_payload(payload)

    backup_path: Path | None = None
    if output_path.exists():
        archive_dir.mkdir(parents=True, exist_ok=True)
        backup_path = build_paper_current_state_backup_path(output_path, archive_dir, now=now)
        assert_paper_path(backup_path, PAPER_TEST_DIR)
        shutil.copy2(output_path, backup_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=4, ensure_ascii=False)

    with output_path.open("r", encoding="utf-8") as handle:
        saved_data = json.load(handle)
    _validate_saved_current_state_payload(saved_data)

    return {
        "path": output_path,
        "backup_path": backup_path,
        "payload": saved_data,
    }
