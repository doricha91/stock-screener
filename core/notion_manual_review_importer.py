from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from core.notion_client import NotionClient
from core.notion_account_keys import (
    build_legacy_manual_review_canonical_key,
    build_manual_review_canonical_key,
    normalize_notion_account_id,
)
from core.notion_mapping import get_mapping_section, resolve_notion_property_name
from core.notion_settings import NotionSettings, get_notion_data_source_id
from core.paper_account_paths import PaperAccountPaths
from core.paper_manual_review_log_template import PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS
from core.paper_manual_review_log_validator import validate_paper_manual_review_log_rows
from core.paths import paper_reports_dir, paper_reviews_dir


PASS = "PASS"
WARNING = "WARNING"
FAIL = "FAIL"


class ManualReviewImportError(RuntimeError):
    pass


@dataclass(frozen=True)
class ManualReviewIssue:
    severity: str
    code: str
    message: str


@dataclass
class ManualReviewCandidate:
    account_id: str
    page_id: str
    name: str
    review_date: str
    symbol: str
    question_id: str
    question_text: str
    manual_answer: str
    review_status: str
    follow_up_needed: str
    review_tag: str
    reviewer_note: str
    source_template_key: str | None
    notion_external_key: str | None
    validation_status_raw: str | None
    validation_message_raw: str | None
    import_status_raw: str | None
    imported_at_raw: str | None
    synced_at_raw: str | None
    created_at: str
    canonical_key: str = ""
    legacy_canonical_key: str | None = None
    legacy_key_compatible: bool = False
    validation_issues: list[ManualReviewIssue] = field(default_factory=list)

    @property
    def validation_status(self) -> str:
        severities = {issue.severity for issue in self.validation_issues}
        if FAIL in severities:
            return FAIL
        if WARNING in severities:
            return WARNING
        return PASS


@dataclass(frozen=True)
class ManualReviewPreview:
    account_id: str
    review_date: str
    candidate_count: int
    pass_count: int
    warning_count: int
    fail_count: int
    append_allowed: str
    source_data_source_id: str
    json_path: str
    markdown_path: str
    duplicate_candidates: list[str]
    candidates: list[ManualReviewCandidate]

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_date": self.review_date,
            "account_id": self.account_id,
            "candidate_count": self.candidate_count,
            "pass_count": self.pass_count,
            "warning_count": self.warning_count,
            "fail_count": self.fail_count,
            "append_allowed": self.append_allowed,
            "source_data_source_id": self.source_data_source_id,
            "json_path": self.json_path,
            "markdown_path": self.markdown_path,
            "duplicate_candidates": self.duplicate_candidates,
            "candidates": [
                {
                    **asdict(candidate),
                    "validation_status": candidate.validation_status,
                }
                for candidate in self.candidates
            ],
        }


def build_manual_review_preview(
    *,
    client: NotionClient,
    settings: NotionSettings,
    mapping_root: dict[str, dict[str, str]],
    review_date: str,
    account_id: str | None = None,
    env: dict[str, str] | None = None,
    reports_dir: Path | None = None,
    existing_log_path: Path | None = None,
    template_path: Path | None = None,
    account_paths: PaperAccountPaths | None = None,
) -> ManualReviewPreview:
    resolved_account_id = normalize_notion_account_id(account_id)
    if account_paths is not None and account_paths.account_id != resolved_account_id:
        raise ManualReviewImportError(
            f"account_paths account_id mismatch: {account_paths.account_id} != {resolved_account_id}"
        )
    mapping = get_mapping_section(mapping_root, "manual_reviews")
    data_source_id = get_notion_data_source_id(
        settings,
        "manual_reviews",
        env=env,
        env_override="NOTION_MANUAL_REVIEWS_DATA_SOURCE_ID",
    )
    pages = fetch_manual_review_pages(
        client=client,
        data_source_id=data_source_id,
        mapping=mapping,
        review_date=review_date,
        account_id=resolved_account_id,
    )
    candidates = normalize_manual_review_pages(
        pages=pages,
        mapping=mapping,
        account_id=resolved_account_id,
    )
    for candidate in candidates:
        _validate_candidate_shape(candidate)
    _assign_canonical_keys(candidates, account_id=resolved_account_id)
    effective_existing_log_path = _resolve_existing_log_path(
        account_paths=account_paths,
        explicit_path=existing_log_path,
    )
    effective_template_path = _resolve_template_path(
        account_paths=account_paths,
        explicit_path=template_path,
    )
    _apply_existing_review_duplicate_validation(
        candidates,
        existing_log_path=effective_existing_log_path,
    )
    _apply_template_comparison(
        candidates,
        template_path=effective_template_path,
    )
    _apply_validator_rules(candidates)

    append_allowed = _derive_append_allowed(candidates)
    duplicate_candidates = sorted(
        {
            candidate.canonical_key
            for candidate in candidates
            for issue in candidate.validation_issues
            if issue.code in {"duplicate_batch_review_key", "duplicate_existing_review_key"}
        }
    )

    output_dir = _resolve_reports_dir(account_paths=account_paths, explicit_reports_dir=reports_dir)
    compact_date = review_date.replace("-", "")
    json_path = output_dir / f"manual_review_import_preview_{compact_date}.json"
    markdown_path = output_dir / f"manual_review_import_preview_{compact_date}.md"
    preview = ManualReviewPreview(
        account_id=resolved_account_id,
        review_date=review_date,
        candidate_count=len(candidates),
        pass_count=sum(1 for item in candidates if item.validation_status == PASS),
        warning_count=sum(1 for item in candidates if item.validation_status == WARNING),
        fail_count=sum(1 for item in candidates if item.validation_status == FAIL),
        append_allowed=append_allowed,
        source_data_source_id=data_source_id,
        json_path=str(json_path),
        markdown_path=str(markdown_path),
        duplicate_candidates=duplicate_candidates,
        candidates=candidates,
    )
    _write_preview_files(preview, json_path=json_path, markdown_path=markdown_path)
    return preview


def _resolve_existing_log_path(
    *,
    account_paths: PaperAccountPaths | None,
    explicit_path: Path | None,
) -> Path:
    if account_paths is not None:
        return account_paths.reviews_dir / "paper_manual_review_log.csv"
    return explicit_path or paper_reviews_dir() / "paper_manual_review_log.csv"


def _resolve_template_path(
    *,
    account_paths: PaperAccountPaths | None,
    explicit_path: Path | None,
) -> Path:
    if account_paths is not None:
        return account_paths.reviews_dir / "paper_manual_review_log_template.csv"
    return explicit_path or paper_reviews_dir() / "paper_manual_review_log_template.csv"


def _resolve_reports_dir(
    *,
    account_paths: PaperAccountPaths | None,
    explicit_reports_dir: Path | None,
) -> Path:
    if account_paths is not None:
        return account_paths.reports_dir
    return explicit_reports_dir if explicit_reports_dir is not None else paper_reports_dir()


def fetch_manual_review_pages(
    *,
    client: NotionClient,
    data_source_id: str,
    mapping: dict[str, str],
    review_date: str,
    account_id: str | None = None,
) -> list[dict[str, Any]]:
    resolved_account_id = normalize_notion_account_id(account_id)
    account_id_property = resolve_notion_property_name(mapping, "account_id")
    if resolved_account_id == "paper_default":
        account_filter = {
            "or": [
                {
                    "property": account_id_property,
                    "select": {"equals": resolved_account_id},
                },
                {
                    "property": account_id_property,
                    "select": {"is_empty": True},
                },
            ]
        }
    else:
        account_filter = {
            "property": account_id_property,
            "select": {"equals": resolved_account_id},
        }
    filter_payload = {
        "and": [
            {
                "property": resolve_notion_property_name(mapping, "review_date"),
                "date": {"equals": review_date},
            },
            {
                "property": resolve_notion_property_name(mapping, "import_status"),
                "select": {"equals": "READY"},
            },
            account_filter,
        ]
    }
    sorts = [
        {
            "property": resolve_notion_property_name(mapping, "review_date"),
            "direction": "ascending",
        }
    ]
    return client.query_data_source(
        data_source_id,
        filter_payload=filter_payload,
        sorts=sorts,
    )


def normalize_manual_review_pages(
    *,
    pages: list[dict[str, Any]],
    mapping: dict[str, str],
    account_id: str | None = None,
) -> list[ManualReviewCandidate]:
    resolved_account_id = normalize_notion_account_id(account_id)
    normalized: list[ManualReviewCandidate] = []
    for page in sorted(
        pages,
        key=lambda item: _page_sort_key(
            item,
            review_date_property=resolve_notion_property_name(mapping, "review_date"),
            symbol_property=resolve_notion_property_name(mapping, "symbol"),
            question_id_property=resolve_notion_property_name(mapping, "question_id"),
        ),
    ):
        properties = page.get("properties") or {}
        normalized.append(
            ManualReviewCandidate(
                account_id=resolved_account_id,
                page_id=str(page.get("id") or "").strip(),
                name=_extract_title(properties, mapping.get("name", "Name")),
                review_date=_extract_date(properties, resolve_notion_property_name(mapping, "review_date")),
                symbol=_extract_rich_text(properties, resolve_notion_property_name(mapping, "symbol")).upper().strip(),
                question_id=_extract_rich_text(properties, resolve_notion_property_name(mapping, "question_id")).strip(),
                question_text=_extract_rich_text(properties, resolve_notion_property_name(mapping, "question")).strip(),
                manual_answer=_extract_rich_text(properties, resolve_notion_property_name(mapping, "manual_answer")).strip(),
                review_status=_extract_select(properties, resolve_notion_property_name(mapping, "review_status")).strip().lower(),
                follow_up_needed=_extract_follow_up_needed(properties, resolve_notion_property_name(mapping, "follow_up_needed")),
                review_tag=_extract_tag_value(properties, resolve_notion_property_name(mapping, "review_tag")),
                reviewer_note=_extract_rich_text(properties, resolve_notion_property_name(mapping, "reviewer_note")).strip(),
                source_template_key=_extract_optional_text(properties, mapping.get("source_template_key")),
                notion_external_key=_extract_optional_text(properties, mapping.get("external_key")),
                validation_status_raw=_extract_optional_select(properties, mapping.get("validation_status")),
                validation_message_raw=_extract_optional_text(properties, mapping.get("validation_message")),
                import_status_raw=_extract_optional_select(properties, mapping.get("import_status")),
                imported_at_raw=_extract_optional_text(properties, mapping.get("imported_at")),
                synced_at_raw=_extract_optional_text(properties, mapping.get("synced_at")),
                created_at=str(page.get("created_time") or "").strip(),
            )
        )
    return normalized


def _validate_candidate_shape(candidate: ManualReviewCandidate) -> None:
    if not candidate.review_date:
        candidate.validation_issues.append(ManualReviewIssue(FAIL, "missing_review_date", "Review Date is required."))
    if not candidate.symbol:
        candidate.validation_issues.append(ManualReviewIssue(FAIL, "missing_symbol", "Symbol is required."))
    if not candidate.question_id:
        candidate.validation_issues.append(ManualReviewIssue(FAIL, "missing_question_id", "Question ID is required."))
    if not candidate.question_text:
        candidate.validation_issues.append(ManualReviewIssue(FAIL, "missing_question_text", "Question is required."))
    if not candidate.manual_answer:
        candidate.validation_issues.append(ManualReviewIssue(FAIL, "missing_manual_answer", "Manual Answer is required."))
    if not candidate.review_status:
        candidate.validation_issues.append(ManualReviewIssue(FAIL, "missing_review_status", "Review Status is required."))
    elif candidate.review_status == "pending":
        candidate.validation_issues.append(
            ManualReviewIssue(FAIL, "pending_review_status_not_appendable", "Review Status 'pending' is not appendable.")
        )
    if not candidate.follow_up_needed:
        candidate.validation_issues.append(
            ManualReviewIssue(WARNING, "missing_follow_up_needed", "Follow-up Needed is blank.")
        )
    if not candidate.review_tag:
        candidate.validation_issues.append(
            ManualReviewIssue(WARNING, "missing_review_tag", "Review Tag is blank.")
        )
    if not candidate.source_template_key:
        candidate.validation_issues.append(
            ManualReviewIssue(WARNING, "missing_source_template_key", "Source Template Key is blank.")
        )


def _assign_canonical_keys(
    candidates: list[ManualReviewCandidate],
    *,
    account_id: str | None = None,
) -> None:
    seen_keys: set[str] = set()
    for candidate in sorted(candidates, key=lambda item: (item.review_date, item.symbol, item.question_id, item.page_id)):
        candidate.canonical_key = build_manual_review_canonical_key(
            account_id,
            candidate.review_date,
            candidate.symbol,
            candidate.question_id,
        )
        if candidate.account_id == "paper_default":
            candidate.legacy_canonical_key = build_legacy_manual_review_canonical_key(
                candidate.review_date,
                candidate.symbol,
                candidate.question_id,
            )
            candidate.legacy_key_compatible = True
        if candidate.canonical_key in seen_keys:
            candidate.validation_issues.append(
                ManualReviewIssue(
                    FAIL,
                    "duplicate_batch_review_key",
                    f"Duplicate review key generated in preview batch: {candidate.canonical_key}.",
                )
            )
        seen_keys.add(candidate.canonical_key)


def _apply_existing_review_duplicate_validation(
    candidates: list[ManualReviewCandidate],
    *,
    existing_log_path: Path,
) -> None:
    if not existing_log_path.exists():
        return
    existing_keys = _load_existing_review_keys(existing_log_path)
    for candidate in candidates:
        review_key = (candidate.review_date, candidate.symbol, candidate.question_id)
        if review_key in existing_keys:
            candidate.validation_issues.append(
                ManualReviewIssue(
                    FAIL,
                    "duplicate_existing_review_key",
                    "Review key already exists in paper_manual_review_log.csv.",
                )
            )


def _apply_template_comparison(
    candidates: list[ManualReviewCandidate],
    *,
    template_path: Path,
) -> None:
    if not template_path.exists():
        return
    template_rows = _read_csv_rows(template_path)
    template_by_key = {
        (
            str(row.get("review_date") or "").strip(),
            str(row.get("symbol") or "").strip().upper(),
            str(row.get("question_id") or "").strip(),
        ): row
        for row in template_rows
    }
    for candidate in candidates:
        key = (candidate.review_date, candidate.symbol, candidate.question_id)
        template_row = template_by_key.get(key)
        if template_row is None:
            candidate.validation_issues.append(
                ManualReviewIssue(
                    WARNING,
                    "missing_template_question",
                    "Question ID is not present in the current manual review template.",
                )
            )
            continue
        template_question = str(template_row.get("question_text") or "").strip()
        if template_question != candidate.question_text:
            candidate.validation_issues.append(
                ManualReviewIssue(
                    WARNING,
                    "question_text_mismatch",
                    "Question text does not match the current manual review template.",
                )
            )


def _apply_validator_rules(candidates: list[ManualReviewCandidate]) -> None:
    rows = [_candidate_to_validator_row(candidate) for candidate in candidates]
    issues, _summary = validate_paper_manual_review_log_rows(rows)
    for issue in issues:
        row_number = int(issue.get("row_number") or 0)
        candidate_index = row_number - 2
        if candidate_index < 0 or candidate_index >= len(candidates):
            continue
        severity = FAIL if issue.get("severity") == "error" else WARNING
        candidates[candidate_index].validation_issues.append(
            ManualReviewIssue(
                severity=severity,
                code=str(issue.get("issue_code") or "validator_issue"),
                message=str(issue.get("message") or "").strip(),
            )
        )


def _candidate_to_validator_row(candidate: ManualReviewCandidate) -> dict[str, str]:
    row = {column: "" for column in PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS}
    row.update(
        {
            "review_date": candidate.review_date,
            "symbol": candidate.symbol,
            "question_id": candidate.question_id,
            "question_text": candidate.question_text,
            "is_actionable": "false",
            "manual_answer": candidate.manual_answer,
            "review_status": candidate.review_status,
            "follow_up_needed": candidate.follow_up_needed or "false",
            "review_tag": candidate.review_tag,
            "reviewer_note": candidate.reviewer_note,
            "source_worksheet_path": candidate.source_template_key or "",
            "created_at": candidate.created_at or "",
        }
    )
    return row


def _load_existing_review_keys(path: Path) -> set[tuple[str, str, str]]:
    keys: set[tuple[str, str, str]] = set()
    for row in _read_csv_rows(path):
        keys.add(
            (
                str(row.get("review_date") or "").strip(),
                str(row.get("symbol") or "").strip().upper(),
                str(row.get("question_id") or "").strip(),
            )
        )
    return keys


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows: list[dict[str, str]] = []
        for row in csv.DictReader(handle):
            normalized: dict[str, str] = {}
            for key, value in row.items():
                normalized[(key or "").replace("\ufeff", "").strip()] = value or ""
            rows.append(normalized)
        return rows


def _derive_append_allowed(candidates: list[ManualReviewCandidate]) -> str:
    statuses = {candidate.validation_status for candidate in candidates}
    if FAIL in statuses:
        return "false"
    if WARNING in statuses:
        return "true_with_warnings"
    return "true"


def _write_preview_files(
    preview: ManualReviewPreview,
    *,
    json_path: Path,
    markdown_path: Path,
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(preview.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_render_preview_markdown(preview), encoding="utf-8")


def _render_preview_markdown(preview: ManualReviewPreview) -> str:
    lines = [
        f"# Manual Review Import Preview [{preview.review_date}]",
        "",
        "## Summary",
        f"- Account ID: {preview.account_id}",
        f"- Candidate Rows: {preview.candidate_count}",
        f"- PASS: {preview.pass_count}",
        f"- WARNING: {preview.warning_count}",
        f"- FAIL: {preview.fail_count}",
        f"- Append Allowed: {preview.append_allowed}",
        f"- Source Data Source ID: {preview.source_data_source_id}",
        "",
        "## Duplicate Candidates",
    ]
    if preview.duplicate_candidates:
        lines.extend(f"- {item}" for item in preview.duplicate_candidates)
    else:
        lines.append("- None")
    lines.extend(["", "## Candidates"])
    if not preview.candidates:
        lines.append("- No READY review rows found for the selected Review Date.")
        return "\n".join(lines) + "\n"

    for candidate in preview.candidates:
        lines.extend(
            [
                f"### {candidate.symbol} {candidate.question_id}",
                f"- Account ID: {candidate.account_id}",
                f"- Canonical Key: {candidate.canonical_key}",
                f"- Legacy Canonical Key: {candidate.legacy_canonical_key or '-'}",
                f"- Validation Status: {candidate.validation_status}",
                f"- Review Status: {candidate.review_status or '-'}",
                f"- Question: {candidate.question_text}",
            ]
        )
        if candidate.validation_issues:
            lines.append("- Messages:")
            for issue in candidate.validation_issues:
                lines.append(f"  - [{issue.severity}] {issue.message}")
        else:
            lines.append("- Messages: none")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _page_sort_key(
    page: dict[str, Any],
    *,
    review_date_property: str,
    symbol_property: str,
    question_id_property: str,
) -> tuple[str, str, str, str]:
    properties = page.get("properties") or {}
    return (
        _extract_date(properties, review_date_property),
        _extract_rich_text(properties, symbol_property).upper().strip(),
        _extract_rich_text(properties, question_id_property).strip(),
        str(page.get("created_time") or page.get("id") or ""),
    )


def _extract_title(properties: dict[str, Any], property_name: str) -> str:
    payload = properties.get(property_name) or {}
    return _join_rich_text(payload.get("title") or [])


def _extract_rich_text(properties: dict[str, Any], property_name: str) -> str:
    payload = properties.get(property_name) or {}
    return _join_rich_text(payload.get("rich_text") or [])


def _extract_select(properties: dict[str, Any], property_name: str) -> str:
    payload = properties.get(property_name) or {}
    select_payload = payload.get("select") or {}
    return str(select_payload.get("name") or "").strip()


def _extract_optional_select(properties: dict[str, Any], property_name: str | None) -> str | None:
    if not property_name:
        return None
    value = _extract_select(properties, property_name)
    return value or None


def _extract_date(properties: dict[str, Any], property_name: str) -> str:
    payload = properties.get(property_name) or {}
    date_payload = payload.get("date") or {}
    return str(date_payload.get("start") or "").strip()


def _extract_follow_up_needed(properties: dict[str, Any], property_name: str) -> str:
    payload = properties.get(property_name) or {}
    property_type = str(payload.get("type") or "").strip()
    if property_type == "checkbox":
        return "true" if bool(payload.get("checkbox")) else "false"
    if property_type == "select":
        return str((payload.get("select") or {}).get("name") or "").strip().lower()
    return ""


def _extract_tag_value(properties: dict[str, Any], property_name: str) -> str:
    payload = properties.get(property_name) or {}
    property_type = str(payload.get("type") or "").strip()
    if property_type == "select":
        return str((payload.get("select") or {}).get("name") or "").strip()
    if property_type == "multi_select":
        names = [str(item.get("name") or "").strip() for item in payload.get("multi_select") or []]
        return ",".join(name for name in names if name)
    if property_type == "rich_text":
        return _join_rich_text(payload.get("rich_text") or [])
    return ""


def _extract_optional_text(properties: dict[str, Any], property_name: str | None) -> str | None:
    if not property_name:
        return None
    payload = properties.get(property_name) or {}
    property_type = str(payload.get("type") or "").strip()
    if property_type == "rich_text":
        value = _join_rich_text(payload.get("rich_text") or [])
    elif property_type == "title":
        value = _join_rich_text(payload.get("title") or [])
    elif property_type == "select":
        value = str((payload.get("select") or {}).get("name") or "").strip()
    else:
        value = ""
    return value or None


def _join_rich_text(items: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for item in items:
        plain = str(item.get("plain_text") or "").strip()
        if plain:
            parts.append(plain)
            continue
        text_payload = item.get("text") or {}
        content = str(text_payload.get("content") or "").strip()
        if content:
            parts.append(content)
    return "".join(parts).strip()
