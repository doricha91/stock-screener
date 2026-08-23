from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.paper_account_profile import resolve_paper_account_profile, validate_account_id
from core.paths import OUTPUTS, PAPER_TEST_DIR


LEGACY_PAPER_DEFAULT_ROOT = PAPER_TEST_DIR
PAPER_ACCOUNTS_ROOT = OUTPUTS / "paper_accounts"


def _clean_date(date_str: str) -> str:
    return str(date_str).replace("-", "")


def latest_current_state_snapshot_path(
    account_paths: "PaperAccountPaths",
    as_of_date: str,
) -> Path | None:
    clean_limit = _clean_date(as_of_date)
    candidates: list[tuple[str, Path]] = []
    for path in account_paths.root.glob("paper_current_state_*.json"):
        date_part = path.stem.replace("paper_current_state_", "")
        if len(date_part) == 8 and date_part.isdigit() and date_part <= clean_limit:
            candidates.append((date_part, path))
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item[0])[-1][1]


@dataclass(frozen=True)
class PaperAccountPaths:
    account_id: str
    root: Path
    legacy_default_used: bool
    execution_log_path: Path
    account_snapshot_path: Path
    position_snapshot_path: Path
    reports_dir: Path
    reviews_dir: Path
    config_snapshots_dir: Path
    config_snapshot_archive_dir: Path
    replay_diff_dir: Path
    replay_diff_config_snapshot_archive_dir: Path

    def current_state_snapshot_path(self, date_str: str) -> Path:
        clean_date = _clean_date(date_str)
        return self.root / f"paper_current_state_{clean_date}.json"

    def daily_action_plan_path(self, date_str: str) -> Path:
        clean_date = _clean_date(date_str)
        return self.root / f"daily_action_plan_{clean_date}.md"

    def config_snapshot_path(self, date_str: str) -> Path:
        clean_date = _clean_date(date_str)
        return self.config_snapshots_dir / f"paper_config_snapshot_{clean_date}.json"

    def regenerated_daily_action_plan_path(self, date_str: str) -> Path:
        clean_date = _clean_date(date_str)
        return self.replay_diff_dir / f"regenerated_daily_action_plan_{clean_date}.md"

    def daily_plan_diff_report_path(self, date_str: str) -> Path:
        clean_date = _clean_date(date_str)
        return self.replay_diff_dir / f"daily_plan_diff_{clean_date}.md"

    def replay_diff_config_snapshot_path(self, date_str: str) -> Path:
        clean_date = _clean_date(date_str)
        return self.replay_diff_dir / f"regenerated_paper_config_snapshot_{clean_date}.json"


def resolve_paper_account_root(
    account_id: str | None = None,
    *,
    account_root: Path | None = None,
    allow_legacy_default: bool = True,
    create: bool = False,
) -> Path:
    resolved_account_id = _resolve_account_id(account_id)

    if account_root is not None:
        root = Path(account_root)
    else:
        new_root = PAPER_ACCOUNTS_ROOT / resolved_account_id
        if resolved_account_id != "paper_default":
            root = new_root
        elif new_root.exists():
            root = new_root
        elif allow_legacy_default:
            root = LEGACY_PAPER_DEFAULT_ROOT
        else:
            root = new_root

    if create:
        root.mkdir(parents=True, exist_ok=True)

    return root


def build_paper_account_paths(
    account_id: str | None = None,
    *,
    account_root: Path | None = None,
    allow_legacy_default: bool = True,
    create: bool = False,
) -> PaperAccountPaths:
    resolved_account_id = _resolve_account_id(account_id)
    root = resolve_paper_account_root(
        resolved_account_id,
        account_root=account_root,
        allow_legacy_default=allow_legacy_default,
        create=create,
    )
    legacy_default_used = (
        resolved_account_id == "paper_default" and root == LEGACY_PAPER_DEFAULT_ROOT
    )

    reports_dir = root / "reports"
    reviews_dir = root / "reviews"
    config_snapshots_dir = root / "config_snapshots"
    config_snapshot_archive_dir = root / "archive" / "config_snapshots"
    replay_diff_dir = root / "replay_diff"
    replay_diff_config_snapshot_archive_dir = replay_diff_dir / "archive" / "config_snapshots"

    if create:
        for path in (
            reports_dir,
            reviews_dir,
            config_snapshots_dir,
            config_snapshot_archive_dir,
            replay_diff_dir,
            replay_diff_config_snapshot_archive_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

    return PaperAccountPaths(
        account_id=resolved_account_id,
        root=root,
        legacy_default_used=legacy_default_used,
        execution_log_path=root / "paper_execution_log.csv",
        account_snapshot_path=root / "paper_account_snapshot.csv",
        position_snapshot_path=root / "paper_position_snapshot.csv",
        reports_dir=reports_dir,
        reviews_dir=reviews_dir,
        config_snapshots_dir=config_snapshots_dir,
        config_snapshot_archive_dir=config_snapshot_archive_dir,
        replay_diff_dir=replay_diff_dir,
        replay_diff_config_snapshot_archive_dir=replay_diff_config_snapshot_archive_dir,
    )


def _resolve_account_id(account_id: str | None) -> str:
    if account_id is None:
        return resolve_paper_account_profile(None).account_id
    return validate_account_id(account_id)
