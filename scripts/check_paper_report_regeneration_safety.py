from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Any, Callable

from core.paths import FRONT_TEST_DIR, PAPER_TEST_DIR
from scripts.audit_paper_performance_inputs import run_audit
from scripts.generate_paper_drawdown import generate_paper_drawdown
from scripts.generate_paper_equity_curve import generate_paper_equity_curve
from scripts.generate_paper_performance_summary import main as generate_paper_performance_summary_main


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hash(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def normalized_report_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if path.name == "paper_performance_input_audit.md":
        lines = [line for line in text.splitlines() if not line.startswith("- Generated at:")]
        return "\n".join(lines) + "\n"
    return text


def comparable_report_hash(path: Path) -> str:
    return _sha256_bytes(normalized_report_text(path).encode("utf-8"))


def snapshot_file_hashes(paths: list[Path]) -> dict[str, str]:
    return {str(path): file_hash(path) for path in paths}


def snapshot_tree_hashes(root: Path) -> dict[str, str]:
    results: dict[str, str] = {}
    if not root.exists():
        return results
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        results[str(path.relative_to(root))] = file_hash(path)
    return results


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def extract_summary_metrics(
    account_snapshot_path: Path,
    position_snapshot_path: Path,
    equity_curve_path: Path,
    drawdown_path: Path,
) -> dict[str, str]:
    account_rows = load_csv_rows(account_snapshot_path)
    position_rows = load_csv_rows(position_snapshot_path)
    equity_rows = load_csv_rows(equity_curve_path)
    drawdown_rows = load_csv_rows(drawdown_path)

    latest_account = sorted(account_rows, key=lambda row: row["snapshot_date"])[-1]
    latest_equity = sorted(equity_rows, key=lambda row: row["snapshot_date"])[-1]
    drawdown_rows_sorted = sorted(drawdown_rows, key=lambda row: row["snapshot_date"])
    latest_drawdown = drawdown_rows_sorted[-1]
    primary_mdd_row = min(drawdown_rows_sorted, key=lambda row: float(row["primary_drawdown_pct"]))
    latest_date = latest_equity["snapshot_date"]
    open_position_count = sum(1 for row in position_rows if row.get("snapshot_date", "") == latest_date)

    return {
        "latest_snapshot_date": latest_date,
        "latest_primary_equity": latest_equity["primary_equity"],
        "latest_secondary_equity": latest_equity["secondary_equity"],
        "latest_primary_drawdown_pct": latest_drawdown["primary_drawdown_pct"],
        "primary_mdd_pct": primary_mdd_row["primary_drawdown_pct"],
        "primary_mdd_date": primary_mdd_row["snapshot_date"],
        "realized_pnl": latest_account["realized_pnl"],
        "unrealized_pnl": latest_account["unrealized_pnl"],
        "total_pnl": latest_account["total_pnl"],
        "open_position_count": str(open_position_count),
    }


def run_report_generation_sequence() -> list[str]:
    run_audit()
    generate_paper_equity_curve()
    generate_paper_drawdown()
    generate_paper_performance_summary_main()
    return [
        "python scripts/audit_paper_performance_inputs.py",
        "python scripts/generate_paper_equity_curve.py",
        "python scripts/generate_paper_drawdown.py",
        "python scripts/generate_paper_performance_summary.py",
    ]


def safe_extract_summary_metrics(
    account_snapshot_path: Path,
    position_snapshot_path: Path,
    equity_curve_path: Path,
    drawdown_path: Path,
) -> tuple[dict[str, str], str | None]:
    try:
        return (
            extract_summary_metrics(
                account_snapshot_path,
                position_snapshot_path,
                equity_curve_path,
                drawdown_path,
            ),
            None,
        )
    except FileNotFoundError as exc:
        return {}, str(exc)


def render_safety_report(result: dict[str, Any]) -> str:
    lines = [
        "# Paper Report Regeneration Safety",
        "",
        f"- Source files unchanged: {result['source_hashes_unchanged']}",
        f"- Front-test unchanged: {result['front_test_unchanged']}",
        f"- Report metrics consistent across regenerations: {result['summary_metrics_consistent']}",
        f"- Report content comparable across regenerations: {result['report_hashes_consistent']}",
        "",
        "## Sequence",
    ]
    lines.extend(f"- {command}" for command in result["sequence"])
    lines.extend(
        [
            "",
            "## Source Hash Check",
            f"- paper_execution_log.csv unchanged: {result['source_file_results']['paper_execution_log.csv']}",
            f"- paper_account_snapshot.csv unchanged: {result['source_file_results']['paper_account_snapshot.csv']}",
            f"- paper_position_snapshot.csv unchanged: {result['source_file_results']['paper_position_snapshot.csv']}",
            "",
            "## Official Report Paths",
        ]
    )
    for path_str in result["official_report_paths"]:
        lines.append(f"- {path_str}")
    lines.extend(
        [
            "",
            "## Summary Metrics",
        ]
    )
    for key, value in result["summary_metrics_after_second"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## Warnings",
        ]
    )
    if result["warnings"]:
        lines.extend(f"- {warning}" for warning in result["warnings"])
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Issues",
        ]
    )
    if result["issues"]:
        lines.extend(f"- {issue}" for issue in result["issues"])
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def check_paper_report_regeneration_safety(
    paper_root: Path = PAPER_TEST_DIR,
    front_root: Path = FRONT_TEST_DIR,
    runner: Callable[[], list[str]] = run_report_generation_sequence,
) -> dict[str, Any]:
    reports_dir = paper_root / "reports"
    source_paths = [
        paper_root / "paper_execution_log.csv",
        paper_root / "paper_account_snapshot.csv",
        paper_root / "paper_position_snapshot.csv",
    ]
    official_report_paths = [
        reports_dir / "paper_performance_input_audit.md",
        reports_dir / "paper_equity_curve.csv",
        reports_dir / "paper_equity_curve_summary.md",
        reports_dir / "paper_drawdown.csv",
        reports_dir / "paper_drawdown_summary.md",
        reports_dir / "paper_performance_summary.md",
    ]
    safety_report_path = reports_dir / "paper_report_regeneration_safety.md"
    deprecated_root_summary = paper_root / "paper_performance_summary.md"

    source_hashes_before = snapshot_file_hashes(source_paths)
    front_hashes_before = snapshot_tree_hashes(front_root)
    report_hashes_before = {
        str(path): comparable_report_hash(path)
        for path in official_report_paths
        if path.exists()
    }

    sequence = runner()

    missing_after_first = [str(path) for path in official_report_paths if not path.exists()]
    report_hashes_after_first = {str(path): comparable_report_hash(path) for path in official_report_paths if path.exists()}
    summary_metrics_after_first, metrics_error_after_first = safe_extract_summary_metrics(
        paper_root / "paper_account_snapshot.csv",
        paper_root / "paper_position_snapshot.csv",
        reports_dir / "paper_equity_curve.csv",
        reports_dir / "paper_drawdown.csv",
    )

    runner()

    source_hashes_after = snapshot_file_hashes(source_paths)
    front_hashes_after = snapshot_tree_hashes(front_root)
    report_hashes_after_second = {str(path): comparable_report_hash(path) for path in official_report_paths if path.exists()}
    summary_metrics_after_second, metrics_error_after_second = safe_extract_summary_metrics(
        paper_root / "paper_account_snapshot.csv",
        paper_root / "paper_position_snapshot.csv",
        reports_dir / "paper_equity_curve.csv",
        reports_dir / "paper_drawdown.csv",
    )

    warnings: list[str] = []
    issues: list[str] = []

    if deprecated_root_summary.exists():
        warnings.append(f"Deprecated root report exists: {deprecated_root_summary}")
    if missing_after_first:
        issues.append("Missing official report files after regeneration: " + ", ".join(missing_after_first))
    if metrics_error_after_first:
        issues.append("Could not extract summary metrics after first regeneration: " + metrics_error_after_first)
    if metrics_error_after_second:
        issues.append("Could not extract summary metrics after second regeneration: " + metrics_error_after_second)

    source_file_results = {
        Path(path_str).name: source_hashes_before[path_str] == source_hashes_after[path_str]
        for path_str in source_hashes_before
    }
    if not all(source_file_results.values()):
        issues.append("One or more source CSV files changed during regeneration.")

    front_test_unchanged = front_hashes_before == front_hashes_after
    if not front_test_unchanged:
        issues.append("outputs/front_test changed during regeneration.")

    summary_metrics_consistent = bool(summary_metrics_after_first) and summary_metrics_after_first == summary_metrics_after_second
    if not summary_metrics_consistent:
        issues.append("Summary metrics differ between regeneration runs.")

    report_hashes_consistent = report_hashes_after_first == report_hashes_after_second
    if not report_hashes_consistent:
        issues.append("Comparable report content differs between regeneration runs.")

    result = {
        "sequence": sequence,
        "official_report_paths": [str(path) for path in official_report_paths],
        "source_hashes_before": source_hashes_before,
        "source_hashes_after": source_hashes_after,
        "source_hashes_unchanged": source_hashes_before == source_hashes_after,
        "source_file_results": source_file_results,
        "front_test_unchanged": front_test_unchanged,
        "report_hashes_before": report_hashes_before,
        "report_hashes_after_first": report_hashes_after_first,
        "report_hashes_after_second": report_hashes_after_second,
        "report_hashes_consistent": report_hashes_consistent,
        "summary_metrics_after_first": summary_metrics_after_first,
        "summary_metrics_after_second": summary_metrics_after_second,
        "summary_metrics_consistent": summary_metrics_consistent,
        "warnings": warnings,
        "issues": issues,
        "deprecated_root_summary_exists": deprecated_root_summary.exists(),
        "safety_report_path": safety_report_path,
    }

    safety_report_path.parent.mkdir(parents=True, exist_ok=True)
    safety_report_path.write_text(render_safety_report(result), encoding="utf-8")
    return result


def main() -> int:
    result = check_paper_report_regeneration_safety()
    print("Paper report regeneration safety check completed")
    print(f"  safety_report_path: {result['safety_report_path']}")
    print(f"  source_hashes_unchanged: {result['source_hashes_unchanged']}")
    print(f"  front_test_unchanged: {result['front_test_unchanged']}")
    print(f"  summary_metrics_consistent: {result['summary_metrics_consistent']}")
    print(f"  report_hashes_consistent: {result['report_hashes_consistent']}")
    print(f"  warnings: {len(result['warnings'])}")
    print(f"  issues: {len(result['issues'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
