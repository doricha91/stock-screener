from __future__ import annotations

import pytest
import requests

from core.notion_client import (
    NotionAPIError,
    NotionClient,
    NotionDuplicateExternalKeyError,
)


class FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str | None = None):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text if text is not None else ("" if payload is None else "{}")

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses: list[FakeResponse]):
        self.responses = responses
        self.calls: list[dict] = []

    def request(self, method, url, headers=None, timeout=None, json=None):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "timeout": timeout,
                "json": json,
            }
        )
        return self.responses.pop(0)


class RaisingSession:
    def request(self, method, url, headers=None, timeout=None, json=None):
        raise requests.ConnectionError("connection failed")


def test_query_by_external_key_payload_is_correct():
    session = FakeSession([FakeResponse(200, {"results": []})])
    client = NotionClient("secret-token", session=session)
    client.query_by_external_key("ds1", "ext-1", "External Key")
    payload = session.calls[0]["json"]
    assert payload["filter"]["property"] == "External Key"
    assert payload["filter"]["rich_text"]["equals"] == "ext-1"


def test_query_data_source_paginates_until_complete():
    session = FakeSession(
        [
            FakeResponse(200, {"results": [{"id": "row-1"}], "has_more": True, "next_cursor": "cursor-2"}),
            FakeResponse(200, {"results": [{"id": "row-2"}], "has_more": False, "next_cursor": None}),
        ]
    )
    client = NotionClient("secret-token", session=session)
    rows = client.query_data_source(
        "ds1",
        filter_payload={"property": "Status", "select": {"equals": "READY"}},
    )
    assert [row["id"] for row in rows] == ["row-1", "row-2"]
    assert session.calls[0]["json"]["filter"]["property"] == "Status"
    assert session.calls[1]["json"]["start_cursor"] == "cursor-2"


def test_upsert_creates_when_no_existing_row():
    session = FakeSession(
        [
            FakeResponse(200, {"results": []}),
            FakeResponse(200, {"id": "page-created"}),
        ]
    )
    client = NotionClient("secret-token", session=session)
    result = client.upsert_page_by_external_key(
        data_source_id="ds1",
        external_key="ext-1",
        external_key_property="External Key",
        properties={"Name": {"title": []}},
    )
    assert result.action == "created"
    assert result.page_id == "page-created"
    assert session.calls[1]["method"] == "POST"
    assert session.calls[1]["url"].endswith("/pages")


def test_upsert_updates_when_one_existing_row():
    session = FakeSession(
        [
            FakeResponse(200, {"results": [{"id": "page-existing"}]}),
            FakeResponse(200, {"id": "page-existing"}),
        ]
    )
    client = NotionClient("secret-token", session=session)
    result = client.upsert_page_by_external_key(
        data_source_id="ds1",
        external_key="ext-1",
        external_key_property="External Key",
        properties={"Status": {"select": {"name": "UPDATED"}}},
    )
    assert result.action == "updated"
    assert result.page_id == "page-existing"
    assert session.calls[1]["method"] == "PATCH"
    assert session.calls[1]["url"].endswith("/pages/page-existing")


def test_upsert_update_can_refresh_page_children():
    session = FakeSession(
        [
            FakeResponse(200, {"results": [{"id": "page-existing"}]}),
            FakeResponse(200, {"id": "page-existing"}),
            FakeResponse(
                200,
                {
                    "results": [{"id": "block-1"}, {"id": "block-2"}],
                    "has_more": False,
                    "next_cursor": None,
                },
            ),
            FakeResponse(200, payload=None, text=""),
            FakeResponse(200, payload=None, text=""),
            FakeResponse(200, {"results": [{"id": "new-block"}]}),
        ]
    )
    client = NotionClient("secret-token", session=session)
    result = client.upsert_page_by_external_key(
        data_source_id="ds1",
        external_key="ext-1",
        external_key_property="External Key",
        properties={"Status": {"select": {"name": "UPDATED"}}},
        children=[{"object": "block", "type": "paragraph", "paragraph": {"rich_text": []}}],
        refresh_children_on_update=True,
    )
    assert result.action == "updated"
    methods = [call["method"] for call in session.calls]
    assert methods == ["POST", "PATCH", "GET", "DELETE", "DELETE", "PATCH"]
    assert session.calls[-1]["url"].endswith("/blocks/page-existing/children")


def test_upsert_update_without_refresh_keeps_existing_behavior():
    session = FakeSession(
        [
            FakeResponse(200, {"results": [{"id": "page-existing"}]}),
            FakeResponse(200, {"id": "page-existing"}),
        ]
    )
    client = NotionClient("secret-token", session=session)
    result = client.upsert_page_by_external_key(
        data_source_id="ds1",
        external_key="ext-1",
        external_key_property="External Key",
        properties={"Status": {"select": {"name": "UPDATED"}}},
        children=[{"object": "block", "type": "paragraph", "paragraph": {"rich_text": []}}],
    )
    assert result.action == "updated"
    assert [call["method"] for call in session.calls] == ["POST", "PATCH"]


def test_replace_page_children_failure_bubbles_up():
    session = FakeSession(
        [
            FakeResponse(200, {"results": [{"id": "page-existing"}]}),
            FakeResponse(200, {"id": "page-existing"}),
            FakeResponse(
                200,
                {
                    "results": [{"id": "block-1"}],
                    "has_more": False,
                    "next_cursor": None,
                },
            ),
            FakeResponse(500, text='{"message":"server_error"}'),
        ]
    )
    client = NotionClient("secret-token", session=session)
    with pytest.raises(NotionAPIError):
        client.upsert_page_by_external_key(
            data_source_id="ds1",
            external_key="ext-1",
            external_key_property="External Key",
            properties={"Status": {"select": {"name": "UPDATED"}}},
            children=[{"object": "block", "type": "paragraph", "paragraph": {"rich_text": []}}],
            refresh_children_on_update=True,
        )


def test_upsert_errors_on_duplicate_external_key():
    session = FakeSession([FakeResponse(200, {"results": [{"id": "1"}, {"id": "2"}]})])
    client = NotionClient("secret-token", session=session)
    with pytest.raises(NotionDuplicateExternalKeyError):
        client.upsert_page_by_external_key(
            data_source_id="ds1",
            external_key="ext-1",
            external_key_property="External Key",
            properties={"Name": {"title": []}},
        )


def test_http_error_raises_clear_exception_without_token_leak():
    session = FakeSession([FakeResponse(401, text='{"message":"unauthorized"}')])
    client = NotionClient("secret-token", session=session)
    with pytest.raises(NotionAPIError) as exc_info:
        client.get_bot_user()
    message = str(exc_info.value)
    assert "HTTP 401" in message
    assert "secret-token" not in message
    assert exc_info.value.response_body == '{"message":"unauthorized"}'


def test_retrieve_data_source_404_mentions_data_source_id_not_database_id():
    session = FakeSession([FakeResponse(404, text='{"message":"object_not_found"}')])
    client = NotionClient("secret-token", session=session)
    with pytest.raises(NotionAPIError) as exc_info:
        client.retrieve_data_source("ds_missing")
    message = str(exc_info.value)
    assert "data source not found" in message
    assert "database id" in message
    assert "secret-token" not in message


def test_retrieve_data_source_403_mentions_access_denied():
    session = FakeSession([FakeResponse(403, text='{"message":"restricted_resource"}')])
    client = NotionClient("secret-token", session=session)
    with pytest.raises(NotionAPIError) as exc_info:
        client.get_data_source_schema("ds_forbidden")
    message = str(exc_info.value)
    assert "access denied" in message
    assert "secret-token" not in message


def test_transport_error_is_wrapped_without_token_leak():
    client = NotionClient("secret-token", session=RaisingSession())
    with pytest.raises(NotionAPIError) as exc_info:
        client.get_bot_user()
    message = str(exc_info.value)
    assert "transport error" in message
    assert "secret-token" not in message
