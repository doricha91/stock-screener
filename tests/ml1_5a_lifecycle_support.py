"""Real CLI/runner integration with an in-memory Notion HTTP service."""
from __future__ import annotations

import copy
import importlib
import io
import json
import os
import sqlite3
from contextlib import redirect_stdout, redirect_stderr
from functools import wraps
from pathlib import Path

from core import paper_account_paths as account_paths
from core import paper_shared_market_prepare as shared
from core import notion_client, notion_settings
from core.notion_mapping import load_notion_property_mapping
from core.notion_schema_validator import build_expected_schema
from core.notion_manual_review_schema import MANUAL_REVIEW_OPTION_CONTRACTS
from core.paper_account_bootstrap import initialize_paper_account
from core.paper_first_run import prepare_first_run
from scripts import runbook_stage_runner as runner, runbook_state, paper
from tests import test_ml1_4b_shared_market_prepare as market_fixture

IDS = ["paper_test_a", "paper_test_b"]
DATA_DATE = "2026-10-01"
TRADE_DATE = "2026-10-02"


def property_value(prop):
    kind = prop.get("type") or next(iter(prop), "")
    value = prop.get(kind)
    if kind in {"rich_text", "title"}:
        return "".join(x.get("plain_text", x.get("text", {}).get("content", "")) for x in value or [])
    if kind == "select":
        return (value or {}).get("name")
    if kind == "date":
        return (value or {}).get("start")
    return value


def matches(page, query):
    if not query:
        return True
    if "and" in query:
        return all(matches(page, child) for child in query["and"])
    if "or" in query:
        return any(matches(page, child) for child in query["or"])
    value = property_value(page["properties"].get(query["property"], {}))
    condition = next(v for k, v in query.items() if k != "property")
    if "equals" in condition:
        return value == condition["equals"]
    if "is_empty" in condition:
        return not value
    raise AssertionError(f"Unsupported synthetic service filter: {query}")


class NotionService:
    @staticmethod
    def response_page(page):
        result = copy.deepcopy(page)
        for prop in result["properties"].values():
            kind = prop.get("type") or next(iter(prop))
            prop["type"] = kind
            if kind in {"rich_text", "title"}:
                for span in prop[kind]:
                    span["plain_text"] = span["text"]["content"]
        return result

    def __init__(self):
        self.pages = {}
        self.calls = []
        self.schemas = {}
        for source, fields in build_expected_schema(load_notion_property_mapping()).items():
            properties = {}
            for field in fields:
                kind = field.notion_type if isinstance(field.notion_type, str) else field.notion_type[0]
                properties[field.source_key] = {"type": kind, kind: {"options": [
                    {"name": v} for v in (*field.select_options, *IDS)
                ]}}
            self.schemas[source] = {"properties": properties}
        mapping = load_notion_property_mapping()["manual_reviews"]
        for field, options in MANUAL_REVIEW_OPTION_CONTRACTS.items():
            prop = self.schemas["manual_reviews"]["properties"][mapping[field]]
            prop[prop["type"]]["options"] = [{"name": value} for value in (*options, *IDS)]

    def request(self, method, path, *, json_payload=None):
        payload = json_payload or {}
        self.calls.append((method, path, copy.deepcopy(payload)))
        parts = path.strip("/").split("/")
        if parts[0] == "data_sources":
            source = parts[1]
            if method == "GET":
                return copy.deepcopy(self.schemas[source])
            assert method == "POST" and parts[2] == "query"
            return {"results": [self.response_page(p) for p in self.pages.values()
                                if p["source"] == source and matches(p, payload.get("filter"))],
                    "has_more": False}
        if path == "/pages" and method == "POST":
            page_id = f"synthetic-page-{len(self.pages)+1}"
            page = {"id": page_id, "source": payload["parent"]["data_source_id"],
                    "created_time": "2026-10-02T00:00:00Z", "properties": copy.deepcopy(payload["properties"])}
            self.pages[page_id] = page
            return self.response_page(page)
        if parts[0] == "pages" and method == "PATCH":
            page = self.pages[parts[1]]
            page["properties"].update(copy.deepcopy(payload.get("properties", {})))
            return self.response_page(page)
        if parts[0] == "blocks":
            return {"results": [], "has_more": False}
        raise AssertionError(f"Unexpected HTTP operation: {method} {path}")

    def complete_execution_input(self, account):
        count = 0
        for page in self.pages.values():
            props = page["properties"]
            if page["source"] != "manual_executions" or property_value(props["Account ID"]) != account:
                continue
            props.update({"Actual Price": {"number": 140.0}, "Status": {"select": {"name": "READY"}},
                          "Execution Sequence": {"number": count + 1}})
            count += 1
        return count

    def complete_review_input(self, account):
        count = 0
        for page in self.pages.values():
            props = page["properties"]
            if page["source"] != "manual_reviews" or property_value(props["Account ID"]) != account:
                continue
            props.update({"Manual Answer": {"rich_text": [{"text": {"content": "Synthetic review completed"}}]},
                          "Review Status": {"select": {"name": "reviewed"}},
                          "Import Status": {"select": {"name": "READY"}},
                          "Follow-up Needed": {"select": {"name": "false"}}})
            count += 1
        return count


class Lifecycle:
    def __init__(self, tmp_path, monkeypatch):
        self.monkeypatch = monkeypatch
        monkeypatch.setattr(market_fixture, "PARTICIPANTS", IDS)
        self.market = market_fixture.environment.__wrapped__(tmp_path, monkeypatch)
        self.workspace = tmp_path / "workspace"
        self.workspace.mkdir()
        self.paths = {}
        self.locals = {}
        fresh_root = tmp_path / "fresh_accounts"
        monkeypatch.setattr(account_paths, "PAPER_ACCOUNTS_ROOT", fresh_root)
        from core import paper_daily_ops_orchestrator
        monkeypatch.setattr(paper_daily_ops_orchestrator, "PAPER_ACCOUNTS_ROOT", fresh_root)
        self.legacy_root = tmp_path / "legacy_default"
        self.legacy_root.mkdir()
        (self.legacy_root / "sentinel.txt").write_text("must remain untouched", encoding="utf-8")
        monkeypatch.setattr(account_paths, "LEGACY_PAPER_DEFAULT_ROOT", self.legacy_root)
        monkeypatch.setattr(paper_daily_ops_orchestrator, "LEGACY_PAPER_DEFAULT_ROOT", self.legacy_root)
        profiles = self.market["profiles"]
        profiles["accounts"][1]["initial_cash"] = 112345
        market_fixture.write_json(self.market["profile_path"], profiles)
        registry = self.market["registry"]
        registry["strategy"][0]["content"]["parameters"] = {"score_threshold": 0.1}
        registry["universe"][1]["content"] = {"kind": "shared_snapshot"}
        universe = json.loads(self.market["universe"].read_text(encoding="utf-8"))
        universe["active_symbols"] = ["META"]
        market_fixture.write_json(self.market["universe"], universe)
        market_fixture.write_json(self.market["registry_path"], registry)
        for index, account in enumerate(IDS):
            paths = account_paths.build_paper_account_paths(account)
            self.paths[account] = paths
            initialize_paper_account(account_id=account, initial_cash=100000 + index * 12345,
                                     currency="USD", date_str=DATA_DATE, confirm_create=True, account_root=paths.root)
            folder = tmp_path / "contexts" / account
            folder.mkdir(parents=True)
            local = folder / "_account.local.cmd"
            local.write_text(f'@echo off\nset "ACCOUNT_ID={account}"\nset "ACCOUNT_MODE=PAPER"\n'
                             f'set "SHARED_PARTICIPANT_ACCOUNT_IDS={",".join(IDS)}"\nexit /b 0\n', encoding="ascii")
            self.locals[account] = (local, folder / "_runbook_day.local.cmd")
        original_refresh = self.market["refresh"]
        def refresh(*args, **kwargs):
            result = original_refresh(*args, **kwargs)
            with sqlite3.connect(self.market["db"]) as conn:
                conn.execute("ALTER TABLE market_index ADD COLUMN adj_close REAL")
                conn.execute("UPDATE market_index SET adj_close=close")
                dates = [r[0] for r in conn.execute("SELECT date FROM daily_price WHERE symbol='AAPL' ORDER BY date")]
                for i, date in enumerate(dates):
                    close = 50 + i * .3
                    conn.execute("UPDATE daily_price SET open=?,high=?,low=?,close=?,adj_close=? WHERE symbol='AAPL' AND date=?",
                                 (close-1, close+2, close-2, close, close, date))
                conn.execute("INSERT INTO daily_price SELECT symbol, ?,open,high,low,close,adj_close,volume FROM daily_price WHERE date=?", (TRADE_DATE, DATA_DATE))
                conn.execute("INSERT INTO market_index SELECT symbol, ?,close,adj_close FROM market_index WHERE date=?", (TRADE_DATE, DATA_DATE))
            return result
        monkeypatch.setattr(shared, "run_paper_prepare_data", refresh)
        monkeypatch.setenv("STOCK_SCREENER_MARKET_DB", str(self.market["db"]))
        self.parent_db = os.environ["STOCK_SCREENER_MARKET_DB"]
        self.notion = NotionService()
        def request(client, method, path, **kwargs):
            return self.notion.request(method, path, **kwargs)
        monkeypatch.setattr(notion_client.NotionClient, "_request_json", request)
        settings_path = tmp_path / "notion_settings.json"
        market_fixture.write_json(settings_path, {"enabled": True, "token_env": "ML1_SYNTHETIC_TOKEN",
                                                "data_sources": {k: k for k in self.notion.schemas}})
        monkeypatch.setattr(notion_settings, "_default_settings_path", lambda: settings_path)
        monkeypatch.setenv("ML1_SYNTHETIC_TOKEN", "synthetic-token")
        import requests
        monkeypatch.setattr(requests.sessions.Session, "request", lambda *a, **k: (_ for _ in ()).throw(AssertionError("real network forbidden")))
        original_plan = paper.run_paper_daily_plan
        @wraps(original_plan)
        def operation_clock(*args, **kwargs):
            return original_plan(*args, observed_at="2026-10-02T08:00:00+09:00", **kwargs)
        monkeypatch.setattr(paper, "run_paper_daily_plan", operation_clock)
        self.commands = []
        monkeypatch.setattr(runner, "run_allowlisted_command", self.execute)

    def execute(self, argv, cwd, timeout_sec, *, env=None):
        module = Path(argv[1].replace("\\", "/")).stem
        arguments = argv[2:]
        self.commands.append({"module": module, "args": list(arguments), "db": (env or os.environ).get("STOCK_SCREENER_MARKET_DB")})
        out, err = io.StringIO(), io.StringIO()
        # Process bridge executes the real Python entrypoint. Only the child DB
        # environment is scoped here, exactly as subprocess.run(env=...) does.
        with self.monkeypatch.context() as child, redirect_stdout(out), redirect_stderr(err):
            if env is not None:
                child.setenv("STOCK_SCREENER_MARKET_DB", env["STOCK_SCREENER_MARKET_DB"])
            mod = importlib.import_module("scripts." + module)
            try:
                code = mod.main(arguments)
            except SystemExit as exc:
                code = exc.code
        result = {"executed": True, "exit_code": code or 0, "stdout": out.getvalue(), "stderr": err.getvalue(), "duration_ms": 1}
        if result["exit_code"]:
            print(module, arguments, result["stdout"][-5000:], result["stderr"])
        return result

    def prepare(self, account):
        local, day = self.locals[account]
        return prepare_first_run(account_id=account, data_date=DATA_DATE, workspace=self.workspace,
                                 account_local_path=local, runbook_day_local_path=day)

    def stage_a(self, account):
        return runner.run_stage_a(self.workspace, account, DATA_DATE, TRADE_DATE,
                                  shared_participant_account_ids=",".join(IDS), confirm_paper_test=True)

    def state(self, account):
        return runbook_state.load_state(runbook_state.get_state_path_for_context(self.workspace, account, DATA_DATE, TRADE_DATE))
