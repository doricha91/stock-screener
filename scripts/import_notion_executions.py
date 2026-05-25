from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.notion_client import NotionAPIError, NotionClient  # noqa: E402
from core.notion_manual_execution_importer import (  # noqa: E402
    ManualExecutionImportError,
    build_manual_execution_preview,
)
from core.notion_mapping import load_notion_property_mapping  # noqa: E402
from core.notion_settings import (  # noqa: E402
    NotionSettingsError,
    get_notion_token,
    load_notion_settings,
)

load_dotenv()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read Manual Executions rows from Notion, validate them against current paper state, "
            "and generate preview reports. This command does not modify Notion or paper ledgers."
        )
    )
    parser.add_argument("--date", required=True, help="Execution date in YYYY-MM-DD format")
    parser.add_argument("--preview", action="store_true", help="Generate preview only")
    parser.add_argument("--commit", action="store_true", help="Not implemented in PAPER14-5C")
    parser.add_argument("--json", action="store_true", help="Print machine-readable preview summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.commit:
        parser.error("not implemented in PAPER14-5C: --commit")
    if not args.preview:
        parser.error("Select --preview. --commit is intentionally unavailable in PAPER14-5C.")

    settings = load_notion_settings(allow_missing=True)
    mapping = load_notion_property_mapping()
    client = NotionClient(get_notion_token(settings))
    try:
        preview = build_manual_execution_preview(
            client=client,
            settings=settings,
            mapping_root=mapping,
            execution_date=args.date,
        )
    except (ManualExecutionImportError, NotionAPIError, NotionSettingsError) as exc:
        if args.json:
            print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2))
        else:
            print(f"MANUAL EXECUTION IMPORT PREVIEW FAILED\n{exc}")
        return 1

    payload = preview.to_dict()
    print("MANUAL EXECUTION IMPORT PREVIEW")
    print(
        f"  date={preview.execution_date} candidates={preview.candidate_count} "
        f"commit_allowed={preview.commit_allowed} json={preview.json_path}"
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
