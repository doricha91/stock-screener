from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.notion_client import NotionClient  # noqa: E402
from core.notion_client import NotionAPIError  # noqa: E402
from core.notion_mapping import load_notion_property_mapping  # noqa: E402
from core.notion_schema_validator import (  # noqa: E402
    FAIL,
    format_validation_results,
    validate_selected_data_sources,
    validation_results_to_json,
)
from core.notion_settings import NotionSettingsError, get_notion_token, load_notion_settings  # noqa: E402

load_dotenv()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only validation for Notion data source schemas used by paper exporters. "
            "This command does not create, update, or delete Notion pages."
        )
    )
    parser.add_argument("--weekly", action="store_true", help="Validate weekly_reports")
    parser.add_argument("--benchmark", action="store_true", help="Validate benchmark_reports")
    parser.add_argument("--account-snapshot", action="store_true", help="Validate account_snapshots")
    parser.add_argument("--all", action="store_true", help="Validate all supported data sources")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON summary")
    return parser


def _resolve_targets(args: argparse.Namespace) -> list[str]:
    targets: list[str] = []
    if args.weekly or args.all:
        targets.append("weekly_reports")
    if args.benchmark or args.all:
        targets.append("benchmark_reports")
    if args.account_snapshot or args.all:
        targets.append("account_snapshots")
    if not targets:
        raise SystemExit("Select at least one target: --weekly, --benchmark, --account-snapshot, or --all")
    return targets


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    targets = _resolve_targets(args)

    settings = load_notion_settings(allow_missing=True)
    mapping = load_notion_property_mapping()
    client = NotionClient(get_notion_token(settings))
    try:
        results = validate_selected_data_sources(
            client=client,
            settings=settings,
            mapping_root=mapping,
            targets=targets,
        )
    except (NotionAPIError, NotionSettingsError) as exc:
        if args.json:
            print(json.dumps({"overall_status": FAIL, "error": str(exc), "results": []}, ensure_ascii=False, indent=2))
        else:
            print(f"NOTION SCHEMA VALIDATION FAILED\n{exc}")
        return 1

    if args.json:
        print(json.dumps(validation_results_to_json(results), ensure_ascii=False, indent=2))
    else:
        print(format_validation_results(results))

    return 1 if any(result.status == FAIL for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
