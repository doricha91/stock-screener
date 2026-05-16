import argparse
import difflib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.daily_plan_generator import generate_daily_plan
from core.paper_state_provider import load_official_paper_state_for_daily_plan
from core.paths import (
    paper_daily_action_plan_path,
    paper_daily_plan_diff_report_path,
    paper_regenerated_daily_action_plan_path,
    paper_replay_diff_config_snapshot_archive_dir,
    paper_replay_diff_config_snapshot_path,
)
from scripts.run_paper_daily_plan import _normalize_date_for_db


STATUS_SAME = "SAME"
STATUS_DIFF = "DIFF"
STATUS_MISSING_BASE = "MISSING_BASE"


def _section_map(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current = "__preamble__"
    sections[current] = []
    for line in text.splitlines():
        if line.startswith("#"):
            current = line.strip()
            sections.setdefault(current, [])
        sections[current].append(line)
    return {key: "\n".join(value) for key, value in sections.items()}


def _changed_sections(base_text: str, regenerated_text: str) -> list[str]:
    base_sections = _section_map(base_text)
    regenerated_sections = _section_map(regenerated_text)
    changed: list[str] = []
    for heading in sorted(set(base_sections) | set(regenerated_sections)):
        if base_sections.get(heading) != regenerated_sections.get(heading):
            changed.append(heading)
    return changed


def _extract_action_lines(text: str) -> list[str]:
    markers = ("BUY", "SELL", "SWITCH_IN", "SWITCH_OUT", "STRATEGY_ENTRY", "REVIEW_EXIT")
    return [line for line in text.splitlines() if any(marker in line for marker in markers)]


def _unified_diff_excerpt(base_text: str, regenerated_text: str, max_lines: int = 80) -> str:
    diff_lines = list(
        difflib.unified_diff(
            base_text.splitlines(),
            regenerated_text.splitlines(),
            fromfile="base",
            tofile="regenerated",
            lineterm="",
        )
    )
    if not diff_lines:
        return "(no diff)"
    excerpt = diff_lines[:max_lines]
    if len(diff_lines) > max_lines:
        excerpt.append("... diff truncated ...")
    return "\n".join(excerpt)


def regenerate_paper_plan_for_diff(
    date_str: str,
    regenerated_plan_path: Path,
    regenerated_config_snapshot_path: Path,
    regenerated_config_snapshot_archive_dir: Path,
) -> str:
    normalized_db_date = _normalize_date_for_db(date_str)
    paper_state = load_official_paper_state_for_daily_plan(normalized_db_date)
    return generate_daily_plan(
        date_str=normalized_db_date,
        current_state=paper_state,
        output_path=regenerated_plan_path,
        market_state_write_log=False,
        config_snapshot_path=regenerated_config_snapshot_path,
        config_snapshot_archive_dir=regenerated_config_snapshot_archive_dir,
        config_snapshot_source="check_paper_plan_regeneration_diff",
    )


def _build_diff_report(
    *,
    date_str: str,
    status: str,
    mode: str,
    base_plan_path: Path,
    regenerated_plan_path: Path,
    diff_report_path: Path,
    regenerated_config_snapshot_path: Path,
    base_text: str | None,
    regenerated_text: str | None,
) -> str:
    changed_sections = []
    action_table_changed = "N/A"
    diff_excerpt = "(base plan missing)"

    if base_text is not None and regenerated_text is not None:
        changed_sections = _changed_sections(base_text, regenerated_text)
        action_table_changed = _extract_action_lines(base_text) != _extract_action_lines(regenerated_text)
        diff_excerpt = _unified_diff_excerpt(base_text, regenerated_text)

    report = [
        f"# Paper Daily Plan Regeneration Diff [{date_str}]",
        "",
        f"- Status: `{status}`",
        f"- Mode: `{mode}`",
        f"- Base Plan: `{base_plan_path}`",
        f"- Regenerated Plan: `{regenerated_plan_path}`",
        f"- Diff Report: `{diff_report_path}`",
        f"- Regenerated Config Snapshot: `{regenerated_config_snapshot_path}`",
        f"- Regenerated Config Snapshot Exists: `{regenerated_config_snapshot_path.exists()}`",
        f"- Action Table Changed: `{action_table_changed}`",
        "",
        "## Changed Sections",
        "",
    ]
    if changed_sections:
        report.extend([f"- {section}" for section in changed_sections])
    else:
        report.append("- None")

    report.extend(
        [
            "",
            "## Diff Excerpt",
            "",
            "```diff",
            diff_excerpt,
            "```",
            "",
            "## Notes",
            "",
            "- Existing base plan file was not overwritten.",
            "- Replay diff artifacts are stored under `outputs/paper_test/replay_diff/`.",
            "- Config/universe snapshots are not forcibly replay-applied in this harness.",
        ]
    )
    return "\n".join(report) + "\n"


def check_paper_plan_regeneration_diff(
    date_str: str,
    *,
    base_plan_path: Path | None = None,
    regenerated_plan_path: Path | None = None,
    diff_report_path: Path | None = None,
    regenerated_config_snapshot_path: Path | None = None,
    regenerated_config_snapshot_archive_dir: Path | None = None,
    mode: str = "full",
) -> dict[str, object]:
    clean_date = date_str.replace("-", "")
    base_plan_path = Path(base_plan_path) if base_plan_path is not None else paper_daily_action_plan_path(clean_date)
    regenerated_plan_path = (
        Path(regenerated_plan_path)
        if regenerated_plan_path is not None
        else paper_regenerated_daily_action_plan_path(clean_date)
    )
    diff_report_path = (
        Path(diff_report_path)
        if diff_report_path is not None
        else paper_daily_plan_diff_report_path(clean_date)
    )
    regenerated_config_snapshot_path = (
        Path(regenerated_config_snapshot_path)
        if regenerated_config_snapshot_path is not None
        else paper_replay_diff_config_snapshot_path(clean_date)
    )
    regenerated_config_snapshot_archive_dir = (
        Path(regenerated_config_snapshot_archive_dir)
        if regenerated_config_snapshot_archive_dir is not None
        else paper_replay_diff_config_snapshot_archive_dir()
    )

    if mode != "full":
        raise ValueError(f"Unsupported mode: {mode}")

    diff_report_path.parent.mkdir(parents=True, exist_ok=True)

    if not base_plan_path.exists():
        report_content = _build_diff_report(
            date_str=clean_date,
            status=STATUS_MISSING_BASE,
            mode=mode,
            base_plan_path=base_plan_path,
            regenerated_plan_path=regenerated_plan_path,
            diff_report_path=diff_report_path,
            regenerated_config_snapshot_path=regenerated_config_snapshot_path,
            base_text=None,
            regenerated_text=None,
        )
        diff_report_path.write_text(report_content, encoding="utf-8")
        return {
            "status": STATUS_MISSING_BASE,
            "base_plan_path": base_plan_path,
            "regenerated_plan_path": regenerated_plan_path,
            "diff_report_path": diff_report_path,
            "regenerated_config_snapshot_path": regenerated_config_snapshot_path,
        }

    base_text = base_plan_path.read_text(encoding="utf-8")
    regenerate_paper_plan_for_diff(
        date_str=clean_date,
        regenerated_plan_path=regenerated_plan_path,
        regenerated_config_snapshot_path=regenerated_config_snapshot_path,
        regenerated_config_snapshot_archive_dir=regenerated_config_snapshot_archive_dir,
    )
    regenerated_text = regenerated_plan_path.read_text(encoding="utf-8")
    status = STATUS_SAME if base_text == regenerated_text else STATUS_DIFF

    report_content = _build_diff_report(
        date_str=clean_date,
        status=status,
        mode=mode,
        base_plan_path=base_plan_path,
        regenerated_plan_path=regenerated_plan_path,
        diff_report_path=diff_report_path,
        regenerated_config_snapshot_path=regenerated_config_snapshot_path,
        base_text=base_text,
        regenerated_text=regenerated_text,
    )
    diff_report_path.write_text(report_content, encoding="utf-8")
    return {
        "status": status,
        "base_plan_path": base_plan_path,
        "regenerated_plan_path": regenerated_plan_path,
        "diff_report_path": diff_report_path,
        "regenerated_config_snapshot_path": regenerated_config_snapshot_path,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare existing paper daily plan against regenerated output")
    parser.add_argument("--date", required=True, help="Target date (YYYYMMDD or YYYY-MM-DD)")
    parser.add_argument("--mode", default="full", choices=["full"], help="Comparison mode")
    args = parser.parse_args()

    result = check_paper_plan_regeneration_diff(args.date, mode=args.mode)
    print(f"Status: {result['status']}")
    print(f"Diff report: {result['diff_report_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
