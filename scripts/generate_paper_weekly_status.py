from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.paper_weekly_status import generate_paper_weekly_status  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate paper weekly status markdown/json summary")
    parser.add_argument("--days", type=int, default=5, help="Use the latest N snapshot_date rows")
    parser.add_argument("--start", help="Inclusive snapshot_date start (YYYYMMDD or YYYY-MM-DD)")
    parser.add_argument("--end", help="Inclusive snapshot_date end (YYYYMMDD or YYYY-MM-DD)")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = generate_paper_weekly_status(
        days=args.days,
        start=args.start,
        end=args.end,
    )
    summary = result["summary"]
    print("Paper weekly status summary generated")
    print(f"  markdown_path: {result['markdown_path']}")
    print(f"  json_path: {result['json_path']}")
    print(f"  schema_version: {summary['schema_version']}")
    print(f"  period_start: {summary['period']['actual_start']}")
    print(f"  period_end: {summary['period']['actual_end']}")
    print(f"  snapshot_count: {summary['period']['snapshot_count']}")
    print(f"  coverage_status: {summary['period']['coverage_status']}")
    print(f"  overall_status: {summary['overall_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
