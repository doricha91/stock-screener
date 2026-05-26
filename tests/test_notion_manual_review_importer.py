from __future__ import annotations

import json
from pathlib import Path

import pytest

import core.notion_manual_review_importer as importer
from core.notion_manual_review_importer import (
    FAIL,
    WARNING,
    build_manual_review_preview,
    normalize_manual_review_pages,
)
from core.notion_settings import NotionSettings
from scripts import import_notion_reviews as review_script


def _settings() -> NotionSettings:
    return NotionSettings(
        enabled=True,
        token_env="NOTION_TOKEN",
        data_sources={"manual_reviews": "ds-manual-reviews"},
    )


def _mapping_root() -> dict[str, dict[str, str]]:
    return {
        "manual_reviews": {
            "name": "Name",
            "external_key": "External Key",
            "review_date": "Review Date",
            "symbol": "Symbol",
            "question_id": "Question ID",
            "question": "Question",
            "manual_answer": "Manual Answer",
            "review_status": "Review Status",
            "follow_up_needed": "Follow-up Needed",
            "review_tag": "Review Tag",
            "reviewer_note": "Reviewer Note",
            "source_template_key": "Source Template Key",
            "validation_status": "Validation Status",
            "validation_message": "Validation Message",
            "import_status": "Import Status",
            "imported_at": "Imported At",
            "synced_at": "Synced At",
        }
    }


def _page(
    *,
    page_id: str,
    review_date: str,
    symbol: str,
    question_id: str,
    question: str,
    manual_answer: str,
    review_status: str = "reviewed",
    follow_up_needed: str | None = "false",
    review_tag: str | None = "entry_rule",
    reviewer_note: str | None = "Looks good",
    import_status: str = "READY",
    source_template_key: str | None = "template:2026-05-25",
) -> dict:
    def rich_text(value: str | None) -> list[dict]:
        return [] if value in {None, ""} else [{"plain_text": value}]

    if follow_up_needed == "checkbox:true":
        follow_up_property = {"type": "checkbox", "checkbox": True}
    elif follow_up_needed == "checkbox:false":
        follow_up_property = {"type": "checkbox", "checkbox": False}
    elif follow_up_needed is None:
        follow_up_property = {"type": "select", "select": None}
    else:
        follow_up_property = {"type": "select", "select": {"name": follow_up_needed}}

    if review_tag == "multi:entry_rule,other":
        review_tag_property = {
            "type": "multi_select",
            "multi_select": [{"name": "entry_rule"}, {"name": "other"}],
        }
    elif review_tag is None:
        review_tag_property = {"type": "select", "select": None}
    else:
        review_tag_property = {"type": "select", "select": {"name": review_tag}}

    return {
        "id": page_id,
        "created_time": f"2026-05-25T0{page_id[-1]}:00:00.000Z",
        "properties": {
            "Name": {"type": "title", "title": [{"plain_text": f"{symbol} {question_id}"}]},
            "External Key": {"type": "rich_text", "rich_text": []},
            "Review Date": {"type": "date", "date": {"start": review_date}},
            "Symbol": {"type": "rich_text", "rich_text": [{"plain_text": symbol}]},
            "Question ID": {"type": "rich_text", "rich_text": [{"plain_text": question_id}]},
            "Question": {"type": "rich_text", "rich_text": [{"plain_text": question}]},
            "Manual Answer": {"type": "rich_text", "rich_text": rich_text(manual_answer)},
            "Review Status": {"type": "select", "select": None if not review_status else {"name": review_status}},
            "Follow-up Needed": follow_up_property,
            "Review Tag": review_tag_property,
            "Reviewer Note": {"type": "rich_text", "rich_text": rich_text(reviewer_note)},
            "Source Template Key": {"type": "rich_text", "rich_text": rich_text(source_template_key)},
            "Validation Status": {"type": "select", "select": None},
            "Validation Message": {"type": "rich_text", "rich_text": []},
            "Import Status": {"type": "select", "select": {"name": import_status}},
            "Imported At": {"type": "rich_text", "rich_text": []},
            "Synced At": {"type": "rich_text", "rich_text": []},
        },
    }


class FakeClient:
    def __init__(self, pages: list[dict]):
        self.pages = pages
        self.calls: list[dict] = []

    def query_data_source(self, data_source_id: str, *, filter_payload=None, sorts=None, page_size=100):
        self.calls.append(
            {
                "data_source_id": data_source_id,
                "filter_payload": filter_payload,
                "sorts": sorts,
                "page_size": page_size,
            }
        )
        return self.pages


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_review_files(tmp_path: Path) -> None:
    _write(
        tmp_path / "paper_manual_review_log.csv",
        "review_date,symbol,review_bucket,review_priority,sample_size_flag,symbol_status,question_id,question_text,question_category,is_actionable,manual_answer,review_status,follow_up_needed,review_tag,reviewer_note,source_worksheet_path,created_at\n",
    )
    _write(
        tmp_path / "paper_manual_review_log_template.csv",
        "review_date,symbol,review_bucket,review_priority,sample_size_flag,symbol_status,question_id,question_text,question_category,is_actionable,manual_answer,review_status,follow_up_needed,review_tag,reviewer_note,source_worksheet_path,created_at\n"
        "2026-05-25,AAPL,review_loss,high,low_sample,realized_only,review_loss_1,진입 신호가 원래 전략 조건과 일치했는가?,review_loss,false,,pending,false,,,template-key,2026-05-25T12:00:00\n",
    )


def test_normalize_manual_review_pages_handles_checkbox_and_multi_select():
    pages = [
        _page(
            page_id="page-1",
            review_date="2026-05-25",
            symbol=" aapl ",
            question_id="review_loss_1",
            question="질문",
            manual_answer="답변",
            follow_up_needed="checkbox:true",
            review_tag="multi:entry_rule,other",
        )
    ]
    candidates = normalize_manual_review_pages(pages=pages, mapping=_mapping_root()["manual_reviews"])
    candidate = candidates[0]
    assert candidate.symbol == "AAPL"
    assert candidate.review_status == "reviewed"
    assert candidate.follow_up_needed == "true"
    assert candidate.review_tag == "entry_rule,other"


def test_preview_generates_reports_and_queries_ready_rows(monkeypatch, tmp_path):
    _seed_review_files(tmp_path)
    monkeypatch.setattr(importer, "paper_reviews_dir", lambda: tmp_path)
    monkeypatch.setattr(importer, "paper_reports_dir", lambda: tmp_path / "reports")
    client = FakeClient(
        [
            _page(
                page_id="page-1",
                review_date="2026-05-25",
                symbol="AAPL",
                question_id="review_loss_1",
                question="진입 신호가 원래 전략 조건과 일치했는가?",
                manual_answer="예, 조건과 일치했다.",
                follow_up_needed="false",
                review_tag="entry_rule",
                reviewer_note="정상",
            )
        ]
    )
    preview = build_manual_review_preview(
        client=client,
        settings=_settings(),
        mapping_root=_mapping_root(),
        review_date="2026-05-25",
    )
    assert preview.candidate_count == 1
    assert preview.pass_count == 1
    assert preview.append_allowed == "true"
    payload = json.loads(Path(preview.json_path).read_text(encoding="utf-8"))
    assert payload["review_date"] == "2026-05-25"
    assert payload["candidate_count"] == 1
    markdown = Path(preview.markdown_path).read_text(encoding="utf-8")
    assert "Manual Review Import Preview" in markdown
    assert "AAPL review_loss_1" in markdown
    filters = client.calls[0]["filter_payload"]["and"]
    assert filters[0]["date"]["equals"] == "2026-05-25"
    assert filters[1]["select"]["equals"] == "READY"


def test_missing_manual_answer_is_fail(monkeypatch, tmp_path):
    _seed_review_files(tmp_path)
    monkeypatch.setattr(importer, "paper_reviews_dir", lambda: tmp_path)
    monkeypatch.setattr(importer, "paper_reports_dir", lambda: tmp_path / "reports")
    client = FakeClient(
        [
            _page(
                page_id="page-1",
                review_date="2026-05-25",
                symbol="AAPL",
                question_id="review_loss_1",
                question="진입 신호가 원래 전략 조건과 일치했는가?",
                manual_answer="",
            )
        ]
    )
    preview = build_manual_review_preview(
        client=client,
        settings=_settings(),
        mapping_root=_mapping_root(),
        review_date="2026-05-25",
    )
    assert preview.fail_count == 1
    assert preview.append_allowed == "false"
    assert preview.candidates[0].validation_status == FAIL


def test_missing_optional_fields_produce_warning(monkeypatch, tmp_path):
    _seed_review_files(tmp_path)
    monkeypatch.setattr(importer, "paper_reviews_dir", lambda: tmp_path)
    monkeypatch.setattr(importer, "paper_reports_dir", lambda: tmp_path / "reports")
    client = FakeClient(
        [
            _page(
                page_id="page-1",
                review_date="2026-05-25",
                symbol="AAPL",
                question_id="review_loss_1",
                question="진입 신호가 원래 전략 조건과 일치했는가?",
                manual_answer="예, 조건과 일치했다.",
                follow_up_needed=None,
                review_tag=None,
                reviewer_note=None,
                source_template_key=None,
            )
        ]
    )
    preview = build_manual_review_preview(
        client=client,
        settings=_settings(),
        mapping_root=_mapping_root(),
        review_date="2026-05-25",
    )
    assert preview.warning_count == 1
    assert preview.append_allowed == "true_with_warnings"
    assert preview.candidates[0].validation_status == WARNING


def test_batch_duplicate_is_fail(monkeypatch, tmp_path):
    _seed_review_files(tmp_path)
    monkeypatch.setattr(importer, "paper_reviews_dir", lambda: tmp_path)
    monkeypatch.setattr(importer, "paper_reports_dir", lambda: tmp_path / "reports")
    pages = [
        _page(
            page_id="page-1",
            review_date="2026-05-25",
            symbol="AAPL",
            question_id="review_loss_1",
            question="진입 신호가 원래 전략 조건과 일치했는가?",
            manual_answer="첫 답변",
        ),
        _page(
            page_id="page-2",
            review_date="2026-05-25",
            symbol="AAPL",
            question_id="review_loss_1",
            question="진입 신호가 원래 전략 조건과 일치했는가?",
            manual_answer="둘째 답변",
        ),
    ]
    preview = build_manual_review_preview(
        client=FakeClient(pages),
        settings=_settings(),
        mapping_root=_mapping_root(),
        review_date="2026-05-25",
    )
    assert preview.fail_count == 2
    assert preview.duplicate_candidates


def test_existing_review_log_duplicate_is_fail(monkeypatch, tmp_path):
    _seed_review_files(tmp_path)
    _write(
        tmp_path / "paper_manual_review_log.csv",
        "review_date,symbol,review_bucket,review_priority,sample_size_flag,symbol_status,question_id,question_text,question_category,is_actionable,manual_answer,review_status,follow_up_needed,review_tag,reviewer_note,source_worksheet_path,created_at\n"
        "2026-05-25,AAPL,review_loss,high,low_sample,realized_only,review_loss_1,진입 신호가 원래 전략 조건과 일치했는가?,review_loss,false,기존 답변,reviewed,false,entry_rule,,template-key,2026-05-25T12:00:00\n",
    )
    monkeypatch.setattr(importer, "paper_reviews_dir", lambda: tmp_path)
    monkeypatch.setattr(importer, "paper_reports_dir", lambda: tmp_path / "reports")
    preview = build_manual_review_preview(
        client=FakeClient(
            [
                _page(
                    page_id="page-1",
                    review_date="2026-05-25",
                    symbol="AAPL",
                    question_id="review_loss_1",
                    question="진입 신호가 원래 전략 조건과 일치했는가?",
                    manual_answer="새 답변",
                )
            ]
        ),
        settings=_settings(),
        mapping_root=_mapping_root(),
        review_date="2026-05-25",
    )
    assert preview.fail_count == 1
    assert any(issue.code == "duplicate_existing_review_key" for issue in preview.candidates[0].validation_issues)


def test_commit_mode_returns_not_implemented(capsys):
    exit_code = review_script.main(["--date", "2026-05-25", "--commit", "--json", "--preview-json", "missing.json"])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Preview JSON not found" in captured.out
