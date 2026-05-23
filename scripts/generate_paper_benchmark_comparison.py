from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.paper_benchmark_comparison import generate_paper_benchmark_comparison  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate paper benchmark comparison markdown/json report")
    parser.add_argument("--json", action="store_true", help="Print JSON summary to stdout after writing files")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = generate_paper_benchmark_comparison()
    summary = result["summary"]
    print("Paper benchmark comparison generated")
    print(f"  markdown_path: {result['markdown_path']}")
    print(f"  json_path: {result['json_path']}")
    print(f"  schema_version: {summary['schema_version']}")
    print(f"  latest_snapshot_date: {summary['latest_snapshot_date']}")
    print(f"  availability_status: {summary['availability_status']}")
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
