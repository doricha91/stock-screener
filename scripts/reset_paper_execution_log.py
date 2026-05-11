import argparse
import csv
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.paper_execution_log import PAPER_EXECUTION_LOG_COLUMNS
from core.paper_safety import assert_paper_path
from core.paths import PAPER_TEST_DIR, paper_execution_log_path


def build_paper_archive_dir() -> Path:
    return PAPER_TEST_DIR / "archive"


def build_backup_target(log_path: Path, archive_dir: Path, now: datetime | None = None) -> Path:
    timestamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
    return archive_dir / f"{log_path.stem}_{timestamp}_backup{log_path.suffix}"


def write_header_only_paper_execution_log(log_path: Path) -> None:
    with log_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAPER_EXECUTION_LOG_COLUMNS)
        writer.writeheader()


def reset_paper_execution_log(
    log_path: Path | None = None,
    archive_dir: Path | None = None,
    commit: bool = False,
    now: datetime | None = None,
) -> dict[str, object]:
    target_log_path = log_path or paper_execution_log_path()
    target_archive_dir = archive_dir or build_paper_archive_dir()

    assert_paper_path(target_log_path, PAPER_TEST_DIR)
    assert_paper_path(target_archive_dir, PAPER_TEST_DIR)

    backup_target = build_backup_target(target_log_path, target_archive_dir, now=now)
    assert_paper_path(backup_target, PAPER_TEST_DIR)

    log_exists = target_log_path.exists()
    backup_created = False

    if commit:
        target_archive_dir.mkdir(parents=True, exist_ok=True)
        if log_exists:
            shutil.copy2(target_log_path, backup_target)
            backup_created = True
        write_header_only_paper_execution_log(target_log_path)

    return {
        "log_path": target_log_path,
        "archive_dir": target_archive_dir,
        "backup_target": backup_target,
        "log_exists": log_exists,
        "backup_created": backup_created,
        "write_performed": commit,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset paper execution log with backup")
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Backup the current paper_execution_log.csv and recreate it as header-only.",
    )
    args = parser.parse_args()

    result = reset_paper_execution_log(commit=args.commit)

    print(f"{'COMMIT' if args.commit else 'DRY-RUN'}: paper_execution_log reset preview")
    print(f"current log: {result['log_path']}")
    print(f"backup target: {result['backup_target']}")
    print("new log: header-only paper_execution_log.csv")
    print(f"write_performed: {result['write_performed']}")

    if args.commit:
        if result["backup_created"]:
            print("backup_created: True")
        else:
            print("backup_created: False (current log not found)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
