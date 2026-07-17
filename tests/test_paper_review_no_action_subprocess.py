from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path

from core.paper_account_snapshot import PAPER_ACCOUNT_SNAPSHOT_COLUMNS
from core.paper_execution_intent import build_execution_intent
from core.paper_execution_log import PAPER_EXECUTION_LOG_COLUMNS
from core.paper_manual_review_log_template import PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS
from core.paper_position_snapshot import PAPER_POSITION_SNAPSHOT_COLUMNS


ACCOUNT_ID = "paper_phase4_empty"
DATA_DATE = "2026-06-12"
TRADE_DATE = "2026-06-15"


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _seed_empty_account(account_root: Path) -> None:
    account_root.mkdir(parents=True)
    (account_root / "reports").mkdir()
    (account_root / "reviews").mkdir()
    _write_csv(account_root / "paper_execution_log.csv", PAPER_EXECUTION_LOG_COLUMNS, [])
    account_row = {column: "0" for column in PAPER_ACCOUNT_SNAPSHOT_COLUMNS}
    account_row.update(
        {
            "snapshot_date": TRADE_DATE,
            "initial_cash": "100000",
            "cash": "100000",
            "total_equity_cost_basis": "100000",
            "total_equity_market_value": "100000",
            "market_valuation_status": "success",
            "symbols": "",
            "position_count": "0",
        }
    )
    _write_csv(
        account_root / "paper_account_snapshot.csv",
        PAPER_ACCOUNT_SNAPSHOT_COLUMNS,
        [account_row],
    )
    closed_row = {column: "0" for column in PAPER_POSITION_SNAPSHOT_COLUMNS}
    closed_row.update(
        {
            "snapshot_date": TRADE_DATE,
            "symbol": "CASH",
            "position_status": "CLOSED",
            "valuation_method": "none",
            "valuation_price_date": TRADE_DATE,
            "created_at": f"{TRADE_DATE}T00:00:00Z",
        }
    )
    _write_csv(
        account_root / "paper_position_snapshot.csv",
        PAPER_POSITION_SNAPSHOT_COLUMNS,
        [closed_row],
    )
    items: list[dict[str, object]] = []
    plan = {
        "schema_version": "paper_daily_plan.v1",
        "account_id": ACCOUNT_ID,
        "data_date": DATA_DATE,
        "trade_date": TRADE_DATE,
        "plan_date": TRADE_DATE,
        "run_mode": "official",
        "official_run": True,
        "generated_at": f"{TRADE_DATE}T00:00:00Z",
        "items": items,
        "execution_intent": build_execution_intent(items),
        "fingerprints": {},
    }
    compact = TRADE_DATE.replace("-", "")
    (account_root / f"daily_action_plan_{compact}.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (account_root / f"daily_action_plan_{compact}.md").write_text(
        "# Paper Daily Plan\n\nToday has no executable orders.\n",
        encoding="utf-8",
    )


def _last_json_object(stdout: str) -> dict[str, object]:
    marker = stdout.rfind("\n{")
    text = stdout[marker + 1 :] if marker >= 0 else stdout
    payload = json.loads(text)
    assert isinstance(payload, dict)
    return payload


def test_paper_review_subprocess_supports_empty_no_action_account(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    accounts_root = tmp_path / "paper_accounts"
    account_root = accounts_root / ACCOUNT_ID
    _seed_empty_account(account_root)
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (site_dir / "sitecustomize.py").write_text(
        "import os\n"
        "from pathlib import Path\n"
        "import core.paper_account_paths as account_paths\n"
        "account_paths.PAPER_ACCOUNTS_ROOT = Path(os.environ['PHASE4_PAPER_ACCOUNTS_ROOT'])\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PHASE4_PAPER_ACCOUNTS_ROOT"] = str(accounts_root)
    env["PYTHONPATH"] = os.pathsep.join([str(site_dir), str(repo_root)])

    completed = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "paper.py"),
            "review",
            "--account-id",
            ACCOUNT_ID,
            "--date",
            TRADE_DATE,
            "--json",
        ],
        cwd=repo_root,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = _last_json_object(completed.stdout)
    assert payload["status"] == "PASS"
    assert payload["account_id"] == ACCOUNT_ID
    assert payload["review_date"] == TRADE_DATE
    assert payload["validation_result"] == "PASS"
    daily_review = Path(str(payload["daily_review_report_md"]))
    template_csv = Path(str(payload["manual_review_template_csv"]))
    assert daily_review.is_file()
    assert "- Symbol count: 0" in daily_review.read_text(encoding="utf-8")
    assert template_csv.is_file()
    with template_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS
        assert list(reader) == []
    assert Path(str(payload["validation_report_md"])).is_file()
    assert account_root.is_relative_to(tmp_path)
    assert not (repo_root / "outputs" / "paper_accounts" / ACCOUNT_ID).exists()
