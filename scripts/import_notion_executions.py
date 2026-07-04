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
from core.execution_reconciliation import (  # noqa: E402
    load_reconciliation_preview,
    validate_reconciliation_preview_for_commit,
)
from core.paper_manual_execution_commit import (  # noqa: E402
    ManualExecutionCommitError,
    commit_manual_execution_preview,
)
from core.notion_mapping import load_notion_property_mapping  # noqa: E402
from core.notion_account_keys import normalize_notion_account_id  # noqa: E402
from core.paper_account_paths import build_paper_account_paths  # noqa: E402
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
    parser.add_argument("--data-date", help="Daily Plan data date in YYYY-MM-DD format; required for --commit gate")
    parser.add_argument("--workspace", help="Runbook workspace path for future/latest artifact resolution")
    parser.add_argument("--account-id", help="Paper account id for preview account filtering")
    parser.add_argument("--preview", action="store_true", help="Generate preview only")
    parser.add_argument("--commit", action="store_true", help="Commit validated preview JSON rows to paper ledger")
    parser.add_argument("--preview-json", help="Preview JSON path required for --commit")
    parser.add_argument("--reconciliation-preview-json", help="Execution Reconciliation Preview JSON required for --commit")
    parser.add_argument("--allow-warnings", action="store_true", help="Allow commit when preview status is true_with_warnings")
    parser.add_argument("--json", action="store_true", help="Print machine-readable preview summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    resolved_account_id = normalize_notion_account_id(args.account_id)
    if args.preview and args.commit:
        parser.error("Select either --preview or --commit, not both.")
    if not args.preview and not args.commit:
        parser.error("Select one mode: --preview or --commit.")

    if args.preview:
        account_paths = (
            None
            if resolved_account_id == "paper_default"
            else build_paper_account_paths(resolved_account_id, create=True)
        )
        settings = load_notion_settings(allow_missing=True)
        mapping = load_notion_property_mapping()
        client = NotionClient(get_notion_token(settings))
        try:
            preview = build_manual_execution_preview(
                client=client,
                settings=settings,
                mapping_root=mapping,
                execution_date=args.date,
                account_id=resolved_account_id,
                account_paths=account_paths,
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
            f"  account_id={preview.account_id} date={preview.execution_date} candidates={preview.candidate_count} "
            f"commit_allowed={preview.commit_allowed} json={preview.json_path}"
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if not args.preview_json:
        parser.error("--preview-json is required for --commit.")
    if not args.data_date:
        return _print_commit_blocked(
            args,
            {
                "ok": False,
                "reason_code": "reconciliation_context_missing",
                "message": "--data-date is required for --commit reconciliation gate.",
            },
        )
    if not args.reconciliation_preview_json:
        return _print_commit_blocked(
            args,
            {
                "ok": False,
                "reason_code": "missing_reconciliation_preview",
                "message": "--reconciliation-preview-json is required for --commit.",
            },
        )
    try:
        reconciliation_preview = load_reconciliation_preview(args.reconciliation_preview_json)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _print_commit_blocked(
            args,
            {
                "ok": False,
                "reason_code": "missing_reconciliation_preview",
                "message": f"Reconciliation preview could not be loaded: {exc}",
            },
        )
    gate_result = validate_reconciliation_preview_for_commit(
        reconciliation_preview,
        account_id=resolved_account_id,
        data_date=args.data_date,
        trade_date=args.date,
    )
    if not gate_result["ok"]:
        return _print_commit_blocked(args, gate_result)
    try:
        account_paths = (
            None
            if resolved_account_id == "paper_default"
            else build_paper_account_paths(resolved_account_id, create=True)
        )
        result = commit_manual_execution_preview(
            execution_date=args.date,
            preview_json_path=Path(args.preview_json),
            allow_warnings=args.allow_warnings,
            account_paths=account_paths,
        )
    except ManualExecutionCommitError as exc:
        if args.json:
            print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2))
        else:
            print(f"MANUAL EXECUTION COMMIT FAILED\n{exc}")
        return 1

    payload = {
        "status": "COMMITTED",
        "account_id": result.account_id,
        "execution_date": result.execution_date,
        "preview_json_path": result.preview_json_path,
        "commit_json_path": result.commit_json_path,
        "commit_markdown_path": result.commit_markdown_path,
        "committed_row_count": result.committed_row_count,
        "committed_trade_ids": result.committed_trade_ids,
        "backups": result.backups,
        "current_state_written": result.current_state_written,
        "account_snapshot_written": result.account_snapshot_written,
        "position_snapshot_written": result.position_snapshot_written,
    }
    print("MANUAL EXECUTION COMMIT")
    print(
        f"  account_id={result.account_id} date={result.execution_date} committed_rows={result.committed_row_count} "
        f"commit_json={result.commit_json_path}"
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _print_commit_blocked(args: argparse.Namespace, gate_result: dict) -> int:
    payload = {
        "status": "BLOCKED",
        "runner_result": "BLOCKED",
        "reason_code": gate_result.get("reason_code"),
        "message": gate_result.get("message"),
        "reconciliation_runner_result": gate_result.get("runner_result"),
        "reconciliation_preview_json": args.reconciliation_preview_json,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("MANUAL EXECUTION COMMIT BLOCKED")
        print(payload["message"])
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
