from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import requests
from requests import RequestException

NOTION_VERSION = "2026-03-11"
NOTION_BASE_URL = "https://api.notion.com/v1"


class NotionAPIError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, response_body: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


def _redact_secret_text(value: Any) -> str:
    normalized = " ".join(str(value or "").split())
    normalized = re.sub(r"(?i)bearer\s+[^\s,;]+", "Bearer [REDACTED]", normalized)
    return re.sub(
        r"(?i)(authorization|token|secret)(\s*[:=]\s*)[^\s,;]+",
        r"\1\2[REDACTED]",
        normalized,
    )


def _safe_notion_error_details(body: str, *, limit: int = 400) -> str:
    """Return bounded operator-facing response details without echoing credentials."""
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, TypeError):
        normalized = _redact_secret_text(body)
        return f"body={normalized[:limit]}" if normalized else ""
    if not isinstance(payload, dict):
        return ""
    details: list[str] = []
    for key in ("code", "message", "request_id"):
        value = payload.get(key)
        if value is not None:
            details.append(f"{key}={_redact_secret_text(value)[:limit]}")
    return " ".join(details)


class NotionDuplicateExternalKeyError(RuntimeError):
    pass


@dataclass
class NotionUpsertResult:
    action: str
    page_id: str
    payload: dict[str, Any]


class NotionClient:
    def __init__(
        self,
        token: str,
        *,
        notion_version: str = NOTION_VERSION,
        base_url: str = NOTION_BASE_URL,
        timeout: int = 30,
        session: requests.Session | None = None,
    ) -> None:
        self._token = token
        self.notion_version = notion_version
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Notion-Version": self.notion_version,
            "Content-Type": "application/json",
        }

    def _request_json(self, method: str, path: str, *, json_payload: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            response = self.session.request(
                method,
                f"{self.base_url}{path}",
                headers=self._headers(),
                timeout=self.timeout,
                json=json_payload,
            )
        except RequestException as exc:
            raise NotionAPIError(
                f"Notion API request failed: {method} {path} -> transport error ({exc.__class__.__name__})"
            ) from exc
        if response.status_code >= 400:
            body = response.text
            details = _safe_notion_error_details(body)
            suffix = f" {details}" if details else ""
            raise NotionAPIError(
                f"Notion API request failed: {method} {path} -> HTTP {response.status_code}{suffix}",
                status_code=response.status_code,
                response_body=body,
            )
        if not response.text:
            return {}
        return response.json()

    def get_bot_user(self) -> dict[str, Any]:
        return self._request_json("GET", "/users/me")

    def retrieve_data_source(self, data_source_id: str) -> dict[str, Any]:
        try:
            return self._request_json("GET", f"/data_sources/{data_source_id}")
        except NotionAPIError as exc:
            raise self._translate_data_source_error(data_source_id, exc) from exc

    def get_data_source_schema(self, data_source_id: str) -> dict[str, Any]:
        return self.retrieve_data_source(data_source_id)

    def update_data_source_properties(
        self,
        data_source_id: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        return self._request_json(
            "PATCH",
            f"/data_sources/{data_source_id}",
            json_payload={"properties": properties},
        )

    def _translate_data_source_error(
        self,
        data_source_id: str,
        exc: NotionAPIError,
    ) -> NotionAPIError:
        status_code = exc.status_code
        body = exc.response_body or ""
        if status_code is None:
            message = (
                f"Notion data source schema read failed for '{data_source_id}': "
                "transport error while reaching the Notion API."
            )
        elif status_code == 403:
            message = (
                f"Notion data source schema read failed for '{data_source_id}': "
                "access denied (HTTP 403). Check integration access and token scope."
            )
        elif status_code == 404:
            message = (
                f"Notion data source schema read failed for '{data_source_id}': "
                "data source not found (HTTP 404). Check that you are using a data source id, not a database id."
            )
        elif status_code == 400:
            message = (
                f"Notion data source schema read failed for '{data_source_id}': "
                "validation error (HTTP 400). Check the data source id format."
            )
        else:
            message = (
                f"Notion data source schema read failed for '{data_source_id}': "
                f"HTTP {status_code if status_code is not None else 'unknown'}."
            )
        return NotionAPIError(message, status_code=status_code, response_body=body)

    def query_by_external_key(
        self,
        data_source_id: str,
        external_key: str,
        external_key_property: str,
    ) -> list[dict[str, Any]]:
        payload = {
            "filter": {
                "property": external_key_property,
                "rich_text": {
                    "equals": external_key,
                },
            },
            "page_size": 10,
        }
        result = self._request_json(
            "POST",
            f"/data_sources/{data_source_id}/query",
            json_payload=payload,
        )
        return result.get("results", [])

    def query_data_source(
        self,
        data_source_id: str,
        *,
        filter_payload: dict[str, Any] | None = None,
        sorts: list[dict[str, Any]] | None = None,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        next_cursor: str | None = None
        while True:
            payload: dict[str, Any] = {"page_size": page_size}
            if filter_payload:
                payload["filter"] = filter_payload
            if sorts:
                payload["sorts"] = sorts
            if next_cursor:
                payload["start_cursor"] = next_cursor
            response = self._request_json(
                "POST",
                f"/data_sources/{data_source_id}/query",
                json_payload=payload,
            )
            results.extend(response.get("results", []))
            if not response.get("has_more"):
                return results
            next_cursor = response.get("next_cursor")
            if not next_cursor:
                return results

    def create_page(
        self,
        data_source_id: str,
        properties: dict[str, Any],
        *,
        children: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "parent": {
                "type": "data_source_id",
                "data_source_id": data_source_id,
            },
            "properties": properties,
        }
        if children:
            payload["children"] = children
        return self._request_json("POST", "/pages", json_payload=payload)

    def update_page(self, page_id: str, properties: dict[str, Any]) -> dict[str, Any]:
        return self._request_json(
            "PATCH",
            f"/pages/{page_id}",
            json_payload={"properties": properties},
        )

    def archive_page(self, page_id: str) -> dict[str, Any]:
        return self._request_json(
            "PATCH",
            f"/pages/{page_id}",
            json_payload={"archived": True},
        )

    def list_block_children(self, block_id: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            path = f"/blocks/{block_id}/children?page_size=100"
            if cursor:
                path = f"{path}&start_cursor={cursor}"
            payload = self._request_json("GET", path)
            results.extend(payload.get("results", []))
            if not payload.get("has_more"):
                return results
            cursor = payload.get("next_cursor")
            if not cursor:
                return results

    def delete_block(self, block_id: str) -> dict[str, Any]:
        return self._request_json("DELETE", f"/blocks/{block_id}")

    def append_block_children(self, block_id: str, children: list[dict[str, Any]]) -> dict[str, Any]:
        if not children:
            return {}
        return self._request_json(
            "PATCH",
            f"/blocks/{block_id}/children",
            json_payload={"children": children},
        )

    def replace_page_children(self, page_id: str, children: list[dict[str, Any]]) -> None:
        existing_children = self.list_block_children(page_id)
        for child in existing_children:
            child_id = str(child.get("id") or "").strip()
            if not child_id:
                continue
            self.delete_block(child_id)
        if children:
            self.append_block_children(page_id, children)

    def upsert_page_by_external_key(
        self,
        *,
        data_source_id: str,
        external_key: str,
        external_key_property: str,
        properties: dict[str, Any],
        children: list[dict[str, Any]] | None = None,
        refresh_children_on_update: bool = False,
    ) -> NotionUpsertResult:
        existing = self.query_by_external_key(
            data_source_id,
            external_key,
            external_key_property,
        )
        if len(existing) >= 2:
            raise NotionDuplicateExternalKeyError(
                f"Multiple Notion pages found for external key '{external_key}'."
            )
        if len(existing) == 1:
            page_id = existing[0]["id"]
            payload = self.update_page(page_id, properties)
            if refresh_children_on_update:
                self.replace_page_children(page_id, children or [])
            return NotionUpsertResult(action="updated", page_id=page_id, payload=payload)
        payload = self.create_page(
            data_source_id,
            properties,
            children=children,
        )
        return NotionUpsertResult(action="created", page_id=payload["id"], payload=payload)


def notion_title(value: str) -> dict[str, Any]:
    return {
        "title": [
            {
                "text": {
                    "content": value,
                }
            }
        ]
    }


def notion_rich_text(value: str) -> dict[str, Any]:
    return {
        "rich_text": [
            {
                "text": {
                    "content": value,
                }
            }
        ]
    }


def notion_select(value: str) -> dict[str, Any]:
    return {"select": {"name": value}}


def notion_multi_select(values: list[str] | tuple[str, ...]) -> dict[str, Any]:
    return {
        "multi_select": [
            {"name": str(value).strip()}
            for value in values
            if str(value).strip()
        ]
    }


def notion_date(value: str) -> dict[str, Any]:
    return {"date": {"start": value}}


def notion_number(value: float | int) -> dict[str, Any]:
    return {"number": value}
