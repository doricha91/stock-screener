from __future__ import annotations

from collections import Counter
from typing import Any, Callable

from core.notion_account_keys import build_manual_review_canonical_key
from core.paper_daily_review_scope import validate_scope_manifest


CreateRow = Callable[[dict[str, Any]], str]
ArchivePage = Callable[[str], None]
FetchRows = Callable[[], list[dict[str, Any]]]


class ManualReviewReconciliationError(RuntimeError):
    pass


def assess_manual_review_reconciliation(
    existing_rows: list[dict[str, Any]],
    scope_manifest: dict[str, Any],
) -> dict[str, Any]:
    scope = validate_scope_manifest(scope_manifest)
    context = scope["frozen_context"]
    desired_keys = list(scope["canonical_keys"])
    desired_set = set(desired_keys)
    normalized = [_normalize_existing(row) for row in existing_rows]
    wrong_context = [
        row for row in normalized
        if row["account_id"] != context["account_id"] or row["review_date"] != context["trade_date"]
    ]
    active = [row for row in normalized if row not in wrong_context]
    invalid_identity = [row for row in active if not row["external_key_matches_fields"]]
    counts = Counter(row["canonical_key"] for row in active if row["canonical_key"])
    duplicate_keys = sorted(key for key, count in counts.items() if count > 1)
    existing_keys = set(counts)
    overlap_keys = [key for key in desired_keys if key in existing_keys]
    missing_keys = [key for key in desired_keys if key not in existing_keys]
    stale_rows = [row for row in active if row["canonical_key"] not in desired_set]
    stale_keys = [row["canonical_key"] for row in stale_rows]
    return {
        "schema_version": "manual_review_scope_reconciliation.v1",
        "runner_result": "BLOCKED" if duplicate_keys or wrong_context or invalid_identity else "PASS",
        "frozen_context": context,
        "scope_sha256": scope["scope_sha256"],
        "desired_count": len(desired_keys),
        "active_existing_count": len(active),
        "overlap_count": len(overlap_keys),
        "missing_count": len(missing_keys),
        "stale_count": len(stale_rows),
        "duplicate_count": len(duplicate_keys),
        "wrong_context_count": len(wrong_context),
        "invalid_identity_count": len(invalid_identity),
        "desired_keys": desired_keys,
        "overlap_keys": overlap_keys,
        "missing_keys": missing_keys,
        "stale_keys": stale_keys,
        "duplicate_keys": duplicate_keys,
        "wrong_context_rows": wrong_context,
        "invalid_identity_rows": invalid_identity,
        "stale_rows": stale_rows,
        "archive_allowed": not duplicate_keys and not wrong_context and not invalid_identity,
        "hard_delete_allowed": False,
    }


def apply_manual_review_reconciliation(
    *,
    existing_rows: list[dict[str, Any]],
    scope_manifest: dict[str, Any],
    confirmed_scope_sha256: str,
    create_row: CreateRow,
    archive_page: ArchivePage,
    fetch_rows: FetchRows,
) -> dict[str, Any]:
    scope = validate_scope_manifest(scope_manifest)
    if confirmed_scope_sha256 != scope["scope_sha256"]:
        raise ManualReviewReconciliationError("Operator-confirmed scope SHA-256 mismatch")
    assessment = assess_manual_review_reconciliation(existing_rows, scope)
    if not assessment["archive_allowed"]:
        raise ManualReviewReconciliationError("Duplicate or wrong-context rows block reconciliation")
    row_by_key = {row["canonical_key"]: row for row in scope["rows"]}
    created: list[dict[str, str]] = []
    for key in assessment["missing_keys"]:
        try:
            page_id = create_row(row_by_key[key])
        except Exception as exc:
            return {
                **assessment,
                "runner_result": "FAILED",
                "created": created,
                "archived": [],
                "failed": [{"canonical_key": key, "phase": "create", "error": str(exc)}],
                "archive_started": False,
            }
        created.append({"canonical_key": key, "page_id": str(page_id)})

    post_create = assess_manual_review_reconciliation(fetch_rows(), scope)
    if (
        post_create["missing_count"]
        or post_create["duplicate_count"]
        or post_create["wrong_context_count"]
        or post_create["invalid_identity_count"]
    ):
        return {
            **post_create,
            "runner_result": "FAILED",
            "created": created,
            "archived": [],
            "failed": [{"phase": "verify_canonical", "error": "Canonical rows are not complete and unique"}],
            "archive_started": False,
        }

    archived: list[dict[str, str]] = []
    failed: list[dict[str, str]] = []
    for stale in post_create["stale_rows"]:
        page_id = str(stale.get("page_id") or "")
        if not page_id:
            failed.append({"canonical_key": stale["canonical_key"], "phase": "archive", "error": "page_id missing"})
            continue
        try:
            archive_page(page_id)
        except Exception as exc:
            failed.append({"canonical_key": stale["canonical_key"], "phase": "archive", "error": str(exc)})
        else:
            archived.append({"canonical_key": stale["canonical_key"], "page_id": page_id})
    return {
        **post_create,
        "runner_result": "FAILED" if failed else "PASS",
        "created": created,
        "archived": archived,
        "failed": failed,
        "archive_started": bool(post_create["stale_rows"]),
        "archived_count": len(archived),
        "archive_failed_count": len(failed),
        "hard_deleted_count": 0,
    }


def _normalize_existing(row: dict[str, Any]) -> dict[str, Any]:
    account_id = str(row.get("account_id") or "").strip()
    review_date = str(row.get("review_date") or "").strip()
    symbol = str(row.get("symbol") or "").strip().upper()
    question_id = str(row.get("question_id") or "").strip()
    computed = (
        build_manual_review_canonical_key(account_id, review_date, symbol, question_id)
        if all((account_id, review_date, symbol, question_id))
        else ""
    )
    external_key = str(row.get("external_key") or row.get("notion_external_key") or "").strip()
    return {
        **row,
        "page_id": str(row.get("page_id") or row.get("id") or "").strip(),
        "account_id": account_id,
        "review_date": review_date,
        "symbol": symbol,
        "question_id": question_id,
        "external_key": external_key,
        "canonical_key": external_key or computed,
        "computed_canonical_key": computed,
        "external_key_matches_fields": bool(external_key and external_key == computed),
    }
