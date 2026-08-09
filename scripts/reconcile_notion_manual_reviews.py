from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.notion_client import NotionClient  # noqa: E402
from core.notion_exporters import build_manual_review_template_properties  # noqa: E402
from core.notion_manual_review_reconciliation import (  # noqa: E402
    ManualReviewReconciliationError,
    apply_manual_review_reconciliation,
    assess_manual_review_reconciliation,
)
from core.notion_mapping import (  # noqa: E402
    get_mapping_section,
    load_notion_property_mapping,
    resolve_notion_property_name,
)
from core.notion_manual_review_schema import (  # noqa: E402
    assess_manual_review_schema,
    validate_manual_review_create_payload,
)
from core.notion_settings import (  # noqa: E402
    get_notion_data_source_id,
    get_notion_token,
    load_notion_settings,
)
from core.paper_daily_review_scope import load_scope_manifest  # noqa: E402
from scripts import runbook_state  # noqa: E402
from scripts import runbook_stage_runner  # noqa: E402
from scripts.runbook_gate_checker import normalize_notion_manual_review_page  # noqa: E402


def reconcile(
    *,
    workspace: Path,
    account_id: str,
    data_date: str,
    trade_date: str,
    apply: bool = False,
    confirm_scope_sha256: str | None = None,
    confirm_archive_stale: bool = False,
    client: NotionClient | None = None,
) -> dict[str, Any]:
    workspace = Path(workspace).resolve(strict=False)
    state_path = runbook_state.get_state_path_for_context(workspace, account_id, data_date, trade_date)
    state = runbook_state.load_state(state_path)
    if state.stage_status.get("B") != "PASS" or state.stage_status.get("C") != "PASS":
        raise ManualReviewReconciliationError("Stage B and Stage C must be PASS")
    if state.stage_status.get("GATE2") != "PENDING" or any(
        state.stage_status.get(stage) != "PENDING" for stage in ("D", "E", "F")
    ):
        raise ManualReviewReconciliationError("Reconciliation is allowed only before Gate2 and Stage D/E/F")
    if apply and any(
        state.artifacts.get(name)
        for name in ("review_preview_json", "review_append_report_json", "review_status_sync_report_json")
    ):
        raise ManualReviewReconciliationError("Review preview/append/sync evidence blocks reconciliation apply")
    scope_ref = state.artifacts.get("manual_review_scope_json")
    if not scope_ref:
        if apply:
            raise ManualReviewReconciliationError("manual_review_scope_json must be pinned before apply")
        scope_path: Path | None = None
        scope = runbook_stage_runner._build_stage_c_scope(workspace, state)
    else:
        scope_path = Path(scope_ref)
        if not scope_path.is_absolute():
            scope_path = workspace / scope_path
        scope = load_scope_manifest(
            scope_path,
            account_id=account_id,
            data_date=data_date,
            trade_date=trade_date,
        )

    _load_dotenv_if_available()
    settings = load_notion_settings(allow_missing=True)
    mapping_root = load_notion_property_mapping()
    mapping = get_mapping_section(mapping_root, "manual_reviews")
    data_source_id = get_notion_data_source_id(
        settings,
        "manual_reviews",
        env_override="NOTION_MANUAL_REVIEWS_DATA_SOURCE_ID",
    )
    notion = client or NotionClient(get_notion_token(settings))
    live_schema: dict[str, Any] | None = None
    if apply:
        live_schema = notion.get_data_source_schema(data_source_id)
        schema_assessment = assess_manual_review_schema(live_schema, mapping)
        if schema_assessment["runner_result"] != "PASS":
            raise ManualReviewReconciliationError(
                "Manual Reviews schema must pass compatibility assess before reconciliation apply"
            )

    def fetch_rows() -> list[dict[str, Any]]:
        filter_payload = {
            "and": [
                {
                    "property": resolve_notion_property_name(mapping, "account_id"),
                    "select": {"equals": account_id},
                },
                {
                    "property": resolve_notion_property_name(mapping, "review_date"),
                    "date": {"equals": trade_date},
                },
            ]
        }
        pages = notion.query_data_source(data_source_id, filter_payload=filter_payload, page_size=100)
        return [normalize_notion_manual_review_page(page, mapping) for page in pages]

    existing = fetch_rows()
    if not apply:
        return {
            **assess_manual_review_reconciliation(existing, scope),
            "mode": "ASSESS",
            "would_write": False,
            "scope_manifest_path": str(scope_path) if scope_path else None,
            "scope_source": "PINNED" if scope_path else "EPHEMERAL_READ_ONLY",
        }
    if not confirm_archive_stale:
        raise ManualReviewReconciliationError("--confirm-archive-stale is required for apply")

    def create_row(scope_row: dict[str, Any]) -> str:
        template_row = {
            "symbol": scope_row["symbol"],
            "question_id": scope_row["question_id"],
            "question_text": scope_row["question_text"],
            "review_tag": scope_row["review_tag"],
            "source_worksheet_path": str(scope_path),
        }
        properties = build_manual_review_template_properties(
            template_row,
            mapping,
            account_id=account_id,
            review_date=trade_date,
            external_key=scope_row["canonical_key"],
        )
        assert live_schema is not None
        payload_errors = validate_manual_review_create_payload(properties, live_schema)
        if payload_errors:
            raise ManualReviewReconciliationError(
                "Manual Review create payload is incompatible with live schema: "
                + ", ".join(payload_errors)
            )
        created = notion.create_page(data_source_id, properties)
        page_id = str(created.get("id") or "")
        if not page_id:
            raise ManualReviewReconciliationError("Notion create did not return a page id")
        return page_id

    result = apply_manual_review_reconciliation(
        existing_rows=existing,
        scope_manifest=scope,
        confirmed_scope_sha256=str(confirm_scope_sha256 or ""),
        create_row=create_row,
        archive_page=notion.archive_page,
        fetch_rows=fetch_rows,
    )
    return {
        **result,
        "mode": "APPLY",
        "would_write": True,
        "scope_manifest_path": str(scope_path),
        "scope_source": "PINNED",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Assess or explicitly apply canonical Manual Review reconciliation")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--data-date", required=True)
    parser.add_argument("--trade-date", required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--assess", action="store_true", help="Read-only comparison; no Notion writes")
    mode.add_argument("--apply", action="store_true", help="Create missing rows, then archive stale rows")
    parser.add_argument("--confirm-scope-sha256")
    parser.add_argument("--confirm-archive-stale", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        result = reconcile(
            workspace=args.workspace,
            account_id=args.account_id,
            data_date=args.data_date,
            trade_date=args.trade_date,
            apply=args.apply,
            confirm_scope_sha256=args.confirm_scope_sha256,
            confirm_archive_stale=args.confirm_archive_stale,
        )
    except Exception as exc:
        print(json.dumps({"runner_result": "BLOCKED", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("runner_result") == "PASS" else 1


def _load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ROOT / ".env")


if __name__ == "__main__":
    raise SystemExit(main())
