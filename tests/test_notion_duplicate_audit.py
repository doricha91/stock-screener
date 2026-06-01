from __future__ import annotations

import pytest

from core.notion_client import NotionAPIError
from core.notion_duplicate_audit import (
    CLASS_CREATE_CANDIDATE,
    CLASS_DUPLICATE_BLOCKER,
    CLASS_MANUAL_REVIEW_REQUIRED,
    CLASS_UPDATE_CANDIDATE,
    DAILY_OPS_STATUS_AUDIT_TARGET,
    NotionDuplicateAuditError,
    audit_daily_ops_status_duplicate,
    classify_duplicate_audit_matches,
    resolve_daily_ops_status_audit_key,
)
from core.notion_settings import NotionSettings
from scripts.dev import audit_notion_duplicates


def _settings() -> NotionSettings:
    return NotionSettings(
        enabled=True,
        token_env="NOTION_TOKEN",
        data_sources={"daily_ops_status": "ds-daily-ops"},
    )


def _mapping_root() -> dict[str, dict[str, str]]:
    return {"daily_ops_status": {"external_key": "External Key"}}


class _FakeClient:
    def __init__(self, page_ids: list[str]):
        self.page_ids = page_ids
        self.queries: list[tuple[str, str, str]] = []
        self.write_called = False

    def query_by_external_key(self, data_source_id: str, external_key: str, external_key_property: str):
        self.queries.append((data_source_id, external_key, external_key_property))
        return [{"id": page_id} for page_id in self.page_ids]

    def create_page(self, *args, **kwargs):  # pragma: no cover - safety assertion helper
        self.write_called = True
        raise AssertionError("duplicate audit must not call create_page")

    def update_page(self, *args, **kwargs):  # pragma: no cover - safety assertion helper
        self.write_called = True
        raise AssertionError("duplicate audit must not call update_page")

    def upsert_page_by_external_key(self, *args, **kwargs):  # pragma: no cover - safety assertion helper
        self.write_called = True
        raise AssertionError("duplicate audit must not call upsert_page_by_external_key")


class _CliFakeClient(_FakeClient):
    created_tokens: list[str] = []

    def __init__(self, token: str):
        super().__init__(["page-env"])
        self.__class__.created_tokens.append(token)


class _CliQueryErrorClient:
    def __init__(self, token: str):
        self.token = token

    def query_by_external_key(self, data_source_id: str, external_key: str, external_key_property: str):
        raise NotionAPIError(
            f"Notion API request failed: POST /data_sources/{data_source_id}/query -> transport error"
        )


def test_resolve_daily_ops_status_external_key():
    account_id, status_date, external_key, matches = resolve_daily_ops_status_audit_key(
        account_id="paper_sandbox",
        status_date="20260520",
    )
    assert account_id == "paper_sandbox"
    assert status_date == "2026-05-20"
    assert external_key == "daily_ops_status:paper_sandbox:2026-05-20"
    assert matches is True


def test_zero_matches_create_candidate():
    result = audit_daily_ops_status_duplicate(
        client=_FakeClient([]),
        settings=_settings(),
        mapping_root=_mapping_root(),
        account_id="paper_sandbox",
        status_date="2026-05-20",
    )
    assert result.classification == CLASS_CREATE_CANDIDATE
    assert result.recommended_action == "safe_to_create_after_required_preflight"
    assert result.write_executed is False
    assert result.to_dict()["write_executed"] is False
    assert result.to_dict()["data_source_id"].startswith("****")
    assert result.to_dict()["data_source_id"] != result.data_source_id


def test_one_match_update_candidate():
    client = _FakeClient(["page-1"])
    result = audit_daily_ops_status_duplicate(
        client=client,
        settings=_settings(),
        mapping_root=_mapping_root(),
        account_id="paper_sandbox",
        status_date="2026-05-20",
    )
    assert result.classification == CLASS_UPDATE_CANDIDATE
    assert result.recommended_action == "safe_to_update_after_required_preflight"
    assert result.page_ids == ["page-1"]
    assert client.write_called is False


def test_two_or_more_matches_duplicate_blocker():
    result = audit_daily_ops_status_duplicate(
        client=_FakeClient(["page-1", "page-2"]),
        settings=_settings(),
        mapping_root=_mapping_root(),
        account_id="paper_sandbox",
        status_date="2026-05-20",
    )
    assert result.classification == CLASS_DUPLICATE_BLOCKER
    assert result.recommended_action == "stop_actual_duplicate_detected"
    assert result.match_count == 2


def test_expected_page_id_mismatch_requires_manual_review():
    result = audit_daily_ops_status_duplicate(
        client=_FakeClient(["page-actual"]),
        settings=_settings(),
        mapping_root=_mapping_root(),
        account_id="paper_sandbox",
        status_date="2026-05-20",
        expected_page_id="page-expected",
    )
    assert result.classification == CLASS_MANUAL_REVIEW_REQUIRED
    assert result.recommended_action == "stop_actual_manual_review_required"


def test_external_key_account_date_mismatch_requires_manual_review():
    result = audit_daily_ops_status_duplicate(
        client=_FakeClient([]),
        settings=_settings(),
        mapping_root=_mapping_root(),
        account_id="paper_sandbox",
        status_date="2026-05-20",
        external_key="daily_ops_status:paper_default:2026-05-20",
    )
    assert result.classification == CLASS_MANUAL_REVIEW_REQUIRED
    assert result.recommended_action == "stop_actual_manual_review_required"
    assert result.external_key == "daily_ops_status:paper_default:2026-05-20"


def test_classify_result_always_reports_no_write():
    result = classify_duplicate_audit_matches(
        target=DAILY_OPS_STATUS_AUDIT_TARGET,
        account_id="paper_sandbox",
        status_date="2026-05-20",
        external_key="daily_ops_status:paper_sandbox:2026-05-20",
        page_ids=[],
    )
    assert result.write_executed is False
    assert result.to_dict()["write_executed"] is False


def test_unsupported_cli_target_fails():
    with pytest.raises(SystemExit) as excinfo:
        audit_notion_duplicates.main(["--target", "weekly_reports", "--account-id", "paper_sandbox", "--date", "2026-05-20"])
    assert excinfo.value.code == 2


def test_external_key_requires_date_for_consistency_check():
    with pytest.raises(SystemExit) as excinfo:
        audit_notion_duplicates.main(
            [
                "--target",
                DAILY_OPS_STATUS_AUDIT_TARGET,
                "--account-id",
                "paper_sandbox",
                "--external-key",
                "daily_ops_status:paper_sandbox:2026-05-20",
            ]
        )
    assert excinfo.value.code == 2


def test_invalid_date_fails():
    with pytest.raises(NotionDuplicateAuditError):
        resolve_daily_ops_status_audit_key(account_id="paper_sandbox", status_date="2026/05/20")


def test_cli_uses_env_settings_without_settings_file(monkeypatch, capsys):
    _CliFakeClient.created_tokens.clear()
    monkeypatch.setenv("NOTION_TOKEN", "secret-token-value")
    monkeypatch.setenv("NOTION_DAILY_OPS_STATUS_DATA_SOURCE_ID", "secret-ds-value")
    monkeypatch.setattr(audit_notion_duplicates, "NotionClient", _CliFakeClient)

    exit_code = audit_notion_duplicates.main(
        [
            "--target",
            DAILY_OPS_STATUS_AUDIT_TARGET,
            "--account-id",
            "paper_sandbox",
            "--date",
            "2026-05-20",
            "--json",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "secret-token-value" not in output
    assert "secret-ds-value" not in output
    assert '"data_source_id": "****alue"' in output
    assert '"write_executed": false' in output
    assert _CliFakeClient.created_tokens == ["secret-token-value"]


def test_cli_missing_env_settings_returns_settings_error(monkeypatch, capsys):
    monkeypatch.delenv("NOTION_TOKEN", raising=False)
    monkeypatch.delenv("NOTION_DAILY_OPS_STATUS_DATA_SOURCE_ID", raising=False)

    exit_code = audit_notion_duplicates.main(
        [
            "--target",
            DAILY_OPS_STATUS_AUDIT_TARGET,
            "--account-id",
            "paper_sandbox",
            "--date",
            "2026-05-20",
            "--json",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert '"classification": "settings_error"' in output
    assert '"write_executed": false' in output


def test_cli_query_error_does_not_expose_secret_values(monkeypatch, capsys):
    monkeypatch.setenv("NOTION_TOKEN", "secret-token-value")
    monkeypatch.setenv("NOTION_DAILY_OPS_STATUS_DATA_SOURCE_ID", "secret-ds-value")
    monkeypatch.setattr(audit_notion_duplicates, "NotionClient", _CliQueryErrorClient)

    exit_code = audit_notion_duplicates.main(
        [
            "--target",
            DAILY_OPS_STATUS_AUDIT_TARGET,
            "--account-id",
            "paper_sandbox",
            "--date",
            "2026-05-20",
            "--json",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert '"classification": "query_error"' in output
    assert "secret-token-value" not in output
    assert "secret-ds-value" not in output
    assert "/data_sources/****/query" in output
    assert '"write_executed": false' in output
