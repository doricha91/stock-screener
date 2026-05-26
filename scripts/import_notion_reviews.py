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
from core.notion_manual_review_importer import (  # noqa: E402
    ManualReviewImportError,
    build_manual_review_preview,
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
            "Read Manual Reviews rows from Notion, validate them against the existing review log/template, "
            "and generate preview reports. This command does not modify Notion or review source files."
        )
    )
    parser.add_argument("--date", required=True, help="Review date in YYYY-MM-DD format")
    parser.add_argument("--preview", action="store_true", help="Generate preview only")
    parser.add_argument("--commit", action="store_true", help="Reserved for future append workflow")
    parser.add_argument("--json", action="store_true", help="Print machine-readable preview summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.preview and args.commit:
        parser.error("Select either --preview or --commit, not both.")
    if not args.preview and not args.commit:
        parser.error("Select one mode: --preview or --commit.")

    if args.commit:
        message = "not implemented in PAPER14-7D"
        if args.json:
            print(json.dumps({"status": "FAIL", "error": message}, ensure_ascii=False, indent=2))
        else:
            print(f"MANUAL REVIEW IMPORT FAILED\n{message}")
        return 1

    settings = load_notion_settings(allow_missing=True)
    mapping = load_notion_property_mapping()
    client = NotionClient(get_notion_token(settings))
    try:
        preview = build_manual_review_preview(
            client=client,
            settings=settings,
            mapping_root=mapping,
            review_date=args.date,
        )
    except (ManualReviewImportError, NotionAPIError, NotionSettingsError) as exc:
        if args.json:
            print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2))
        else:
            print(f"MANUAL REVIEW IMPORT PREVIEW FAILED\n{exc}")
        return 1

    payload = preview.to_dict()
    print("MANUAL REVIEW IMPORT PREVIEW")
    print(
        f"  date={preview.review_date} candidates={preview.candidate_count} "
        f"append_allowed={preview.append_allowed} json={preview.json_path}"
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
