from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
import sys

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.notion_client import NotionAPIError, NotionClient  # noqa: E402
from core.notion_account_keys import normalize_notion_account_id  # noqa: E402
from core.notion_manual_execution_status_sync import (  # noqa: E402
    ManualExecutionStatusSyncError,
    sync_manual_execution_status,
)
from core.notion_mapping import load_notion_property_mapping  # noqa: E402
from core.notion_settings import (  # noqa: E402
    NotionSettingsError,
    get_notion_data_source_id,
    get_notion_token,
    load_notion_settings,
)
from core.paper_account_paths import build_paper_account_paths  # noqa: E402

load_dotenv()


def _resolve_report_account_id(payload: dict) -> str:
    explicit = payload.get("account_id")
    if explicit is not None:
        return normalize_notion_account_id(explicit)
    rows = payload.get("committed_rows")
    if isinstance(rows, list):
        row_ids = {
            normalize_notion_account_id(row.get("account_id"))
            for row in rows
            if isinstance(row, dict) and row.get("account_id") is not None
        }
        if len(row_ids) == 1:
            return next(iter(row_ids))
    return normalize_notion_account_id(None)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Sync committed Manual Execution results back to Notion status fields using "
            "the PAPER14-5D commit sidecar report."
        )
    )
    parser.add_argument("--date", required=True, help="Execution date in YYYY-MM-DD format")
    parser.add_argument("--commit-report", required=True, help="Path to manual execution commit report JSON")
    parser.add_argument("--account-id", help="Paper account id for status sync namespace")
    parser.add_argument("--dry-run", action="store_true", help="Build sync payload without updating Notion pages")
    parser.add_argument("--json", action="store_true", help="Print machine-readable result JSON")
    return parser


def write_status_sync_report(payload: dict, account_id: str, execution_date: str) -> tuple[Path, Path]:
    account_paths = build_paper_account_paths(account_id, create=True)
    compact_date = str(execution_date).replace("-", "")
    json_path = account_paths.reports_dir / f"manual_execution_status_sync_{compact_date}.json"
    markdown_path = account_paths.reports_dir / f"manual_execution_status_sync_{compact_date}.md"
    account_paths.reports_dir.mkdir(parents=True, exist_ok=True)
    payload["sync_json_path"] = str(json_path)
    payload["sync_markdown_path"] = str(markdown_path)
    payload["written_at"] = datetime.now().isoformat(timespec="seconds")
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_format_status_sync_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def _format_status_sync_markdown(payload: dict) -> str:
    lines = [
        f"# Manual Execution Status Sync [{payload.get('execution_date', '-')}]",
        "",
        f"- account_id: {payload.get('account_id', '-')}",
        f"- overall_status: {payload.get('overall_status', '-')}",
        f"- candidate_count: {payload.get('candidate_count', 0)}",
        f"- updated_count: {payload.get('updated_count', 0)}",
        f"- skipped_count: {payload.get('skipped_count', 0)}",
        f"- failed_count: {payload.get('failed_count', 0)}",
        f"- dry_run: {payload.get('dry_run', False)}",
        f"- commit_report_path: {payload.get('commit_report_path', '-')}",
        "",
        "## Rows",
    ]
    for row in payload.get("rows", []):
        if not isinstance(row, dict):
            continue
        lines.append(
            "- "
            f"{row.get('canonical_key') or row.get('legacy_canonical_key') or row.get('page_id') or '-'} "
            f"status={row.get('status', '-')} trade_id={row.get('committed_trade_id') or '-'}"
        )
    return "\n".join(lines).strip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    resolved_account_id = normalize_notion_account_id(args.account_id)

    mapping = load_notion_property_mapping()
    settings = load_notion_settings(allow_missing=True)

    data_source_check = "not_checked"
    try:
        get_notion_data_source_id(
            settings,
            "manual_executions",
            env_override="NOTION_MANUAL_EXECUTIONS_DATA_SOURCE_ID",
        )
        data_source_check = "configured"
    except NotionSettingsError:
        data_source_check = "missing"

    client: NotionClient | None = None
    if not args.dry_run:
        client = NotionClient(get_notion_token(settings))

    try:
        commit_report_payload = json.loads(Path(args.commit_report).read_text(encoding="utf-8"))
        report_account_id = _resolve_report_account_id(commit_report_payload)
        if report_account_id != resolved_account_id:
            raise ManualExecutionStatusSyncError(
                f"CLI account_id '{resolved_account_id}' does not match commit report account_id '{report_account_id}'."
            )
        result = sync_manual_execution_status(
            client=client,
            mapping_root=mapping,
            execution_date=args.date,
            commit_report_path=Path(args.commit_report),
            dry_run=args.dry_run,
            account_id=resolved_account_id,
            data_source_check=data_source_check,
        )
    except (ManualExecutionStatusSyncError, NotionSettingsError, NotionAPIError) as exc:
        if args.json:
            print(json.dumps({"overall_status": "FAILED", "error": str(exc)}, ensure_ascii=False, indent=2))
        else:
            print(f"MANUAL EXECUTION STATUS SYNC FAILED\n{exc}")
        return 1

    payload = result.to_dict()
    try:
        write_status_sync_report(payload, resolved_account_id, args.date)
    except OSError as exc:
        if args.json:
            print(json.dumps({"overall_status": "FAILED", "error": str(exc)}, ensure_ascii=False, indent=2))
        else:
            print(f"MANUAL EXECUTION STATUS SYNC REPORT WRITE FAILED\n{exc}")
        return 1
    mode = "DRY RUN" if args.dry_run else "APPLY"
    print("MANUAL EXECUTION STATUS SYNC")
    print(
        f"  mode={mode} account_id={result.account_id} date={result.execution_date} candidates={result.candidate_count} "
        f"overall_status={result.overall_status}"
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if result.overall_status == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
