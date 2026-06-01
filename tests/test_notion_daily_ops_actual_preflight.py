from __future__ import annotations

from core.notion_client import NotionAPIError
from core.notion_daily_ops_actual_preflight import run_daily_ops_status_actual_preflight
from core.notion_duplicate_audit import classify_duplicate_audit_matches
from core.notion_schema_validator import DataSourceValidationResult, FAIL, PASS, ValidationIssue
from core.notion_settings import NotionSettings


def _settings() -> NotionSettings:
    return NotionSettings(enabled=True, token_env="NOTION_TOKEN", data_sources={})


def _mapping_root() -> dict[str, dict[str, str]]:
    return {"daily_ops_status": {"external_key": "External Key", "name": "Name"}}


def _env() -> dict[str, str]:
    return {
        "NOTION_TOKEN": "token",
        "NOTION_DAILY_OPS_STATUS_DATA_SOURCE_ID": "ds-daily-ops",
    }


class _FakeClient:
    def __init__(self):
        self.write_called = False

    def create_page(self, *args, **kwargs):  # pragma: no cover - safety assertion helper
        self.write_called = True
        raise AssertionError("preflight must not call create_page")

    def update_page(self, *args, **kwargs):  # pragma: no cover - safety assertion helper
        self.write_called = True
        raise AssertionError("preflight must not call update_page")

    def upsert_page_by_external_key(self, *args, **kwargs):  # pragma: no cover - safety assertion helper
        self.write_called = True
        raise AssertionError("preflight must not call upsert_page_by_external_key")


def _schema(status: str = PASS):
    def validator(**kwargs):
        issues = []
        if status == FAIL:
            issues = [ValidationIssue(severity=FAIL, property_name="External Key", code="missing", message="missing")]
        return [
            DataSourceValidationResult(
                target="daily_ops_status",
                data_source_id="ds-daily-ops",
                status=status,
                issues=issues,
                checked_property_count=1,
            )
        ]

    return validator


def _duplicate(classification: str, page_ids: list[str] | None = None):
    def auditor(**kwargs):
        return classify_duplicate_audit_matches(
            target="daily_ops_status",
            account_id=kwargs["account_id"],
            status_date=kwargs["status_date"],
            external_key=kwargs["external_key"] or "daily_ops_status:paper_sandbox:2026-05-20",
            page_ids=page_ids or [],
        )

    if classification == "duplicate_blocker":
        return _duplicate("unused", ["page-1", "page-2"])
    if classification == "update_candidate":
        return _duplicate("unused", ["page-1"])
    return auditor


def _schema_error(**kwargs):
    data_source_id = kwargs["env"]["NOTION_DAILY_OPS_STATUS_DATA_SOURCE_ID"]
    raise NotionAPIError(f"GET /data_sources/{data_source_id} failed")


def _duplicate_error(**kwargs):
    data_source_id = kwargs["env"]["NOTION_DAILY_OPS_STATUS_DATA_SOURCE_ID"] if "env" in kwargs else "secret-ds"
    raise NotionAPIError(f"POST /data_sources/{data_source_id}/query failed")


def _run(**overrides):
    kwargs = {
        "client": _FakeClient(),
        "settings": _settings(),
        "mapping_root": _mapping_root(),
        "account_id": "paper_sandbox",
        "status_date": "2026-05-20",
        "env": _env(),
        "schema_validator": _schema(PASS),
        "duplicate_auditor": _duplicate("create_candidate"),
    }
    kwargs.update(overrides)
    return run_daily_ops_status_actual_preflight(**kwargs)


def test_missing_env_fails():
    result = _run(env={})
    payload = result.to_dict()
    assert payload["overall_status"] == FAIL
    assert payload["write_executed"] is False
    assert any(check["name"] == "settings_env_check" and check["status"] == FAIL for check in payload["checks"])


def test_non_sandbox_account_fails():
    result = _run(account_id="paper_growth")
    assert result.overall_status == FAIL


def test_external_key_mismatch_fails():
    result = _run(external_key="daily_ops_status:paper_default:2026-05-20")
    assert result.overall_status == FAIL


def test_duplicate_create_candidate_is_warning_without_expected_page_id():
    result = _run(duplicate_auditor=_duplicate("create_candidate"))
    assert result.overall_status == "WARNING"
    assert result.duplicate_audit["classification"] == "create_candidate"


def test_duplicate_update_candidate_is_warning_without_expected_page_id():
    result = _run(duplicate_auditor=_duplicate("update_candidate"))
    assert result.overall_status == "WARNING"
    assert result.duplicate_audit["classification"] == "update_candidate"


def test_duplicate_blocker_fails():
    result = _run(duplicate_auditor=_duplicate("duplicate_blocker"))
    assert result.overall_status == FAIL
    assert result.duplicate_audit["classification"] == "duplicate_blocker"


def test_schema_validation_fail_fails():
    result = _run(schema_validator=_schema(FAIL))
    assert result.overall_status == FAIL
    assert result.schema_validation_result == FAIL


def test_write_executed_is_always_false_and_fake_write_not_called():
    client = _FakeClient()
    result = _run(client=client)
    assert result.write_executed is False
    assert result.to_dict()["write_executed"] is False
    assert client.write_called is False


def test_error_messages_do_not_expose_data_source_id():
    result = _run(
        env={
            "NOTION_TOKEN": "secret-token-value",
            "NOTION_DAILY_OPS_STATUS_DATA_SOURCE_ID": "secret-ds-value",
        },
        schema_validator=_schema_error,
        duplicate_auditor=_duplicate_error,
    )
    payload = result.to_dict()
    rendered = str(payload)
    assert result.overall_status == FAIL
    assert "secret-token-value" not in rendered
    assert "secret-ds-value" not in rendered
    assert "/data_sources/****" in rendered
