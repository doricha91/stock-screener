import argparse
import csv
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.execution_logger import parse_journal_from_markdown, map_journal_to_trades
from core.paper_account_state import PaperAccountState, build_paper_state_from_trades
from core.paper_current_state_storage import save_paper_current_state
from core.paper_execution_log import append_paper_execution_log
from core.paper_safety import assert_paper_path
from core.paper_trade_preview import build_paper_trade_previews
from core.paths import (
    FRONT_TEST_DIR,
    PAPER_TEST_DIR,
    paper_account_snapshot_path,
    paper_current_state_snapshot_path,
    paper_execution_log_path,
)


def _normalize_date(date_str: str) -> str:
    clean_date = date_str.replace("-", "").strip()
    if len(clean_date) != 8 or not clean_date.isdigit():
        raise ValueError(f"Invalid date format: {date_str}")
    return clean_date


def build_paper_eod_paths(date_str: str) -> dict[str, Path]:
    clean_date = _normalize_date(date_str)
    input_report = FRONT_TEST_DIR / f"daily_action_plan_{clean_date}.md"
    outputs = {
        "input_report": input_report,
        "paper_state": paper_current_state_snapshot_path(clean_date),
        "paper_execution_log": paper_execution_log_path(),
        "paper_account_snapshot": paper_account_snapshot_path(),
    }
    for key in ("paper_state", "paper_execution_log", "paper_account_snapshot"):
        assert_paper_path(outputs[key], PAPER_TEST_DIR)
    return outputs


def parse_journal_preview_from_markdown(report_path: Path) -> list[dict[str, Any]]:
    if not report_path.exists():
        raise FileNotFoundError(f"Markdown report not found: {report_path}")

    lines = report_path.read_text(encoding="utf-8").splitlines()
    in_journal = False
    rows: list[dict[str, Any]] = []

    for line in lines:
        if line.startswith("## 5."):
            in_journal = True
            continue

        if not in_journal:
            continue

        if line.startswith("## ") and not line.startswith("## 5."):
            break

        if "|" not in line:
            continue

        if "Date" in line or "---" in line:
            continue

        parts = [p.strip() for p in line.split("|")[1:-1]]
        if len(parts) != 10:
            continue

        row = {
            "date": parts[0].replace("**", "").strip(),
            "regime": parts[1].replace("**", "").strip(),
            "symbol": parts[2].replace("**", "").strip(),
            "type": parts[3].replace("**", "").strip().upper(),
            "rec_shares": parts[4].replace("**", "").strip(),
            "rec_price": parts[5].replace("**", "").strip(),
            "act_shares": parts[6].replace("**", "").strip(),
            "act_price": parts[7].replace("**", "").strip(),
            "reason": parts[8].replace("**", "").strip(),
            "notes": parts[9].replace("**", "").strip(),
        }

        reason_upper = row["reason"].upper()
        type_upper = row["type"].upper()
        if type_upper not in {"BUY", "SELL"}:
            continue
        if reason_upper.startswith("REVIEW") or reason_upper.startswith("WARNING"):
            continue

        row["status"] = (
            "READY_FOR_PAPER_TRADE"
            if row["act_shares"] and row["act_price"] and row["reason"]
            else "PENDING_ACTUAL_FILL"
        )
        rows.append(row)

    return rows


def _preview_summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "total_rows": len(rows),
        "ready_for_paper_trade": sum(1 for row in rows if row["status"] == "READY_FOR_PAPER_TRADE"),
        "pending_actual_fill": sum(1 for row in rows if row["status"] == "PENDING_ACTUAL_FILL"),
        "skipped_review_or_warning": 0,
    }


def load_paper_execution_rows(log_path: Path) -> list[dict[str, Any]]:
    assert_paper_path(log_path, PAPER_TEST_DIR)
    if not log_path.exists():
        return []

    with log_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build_paper_account_preview_from_log(
    log_path: Path,
    initial_cash: float = 100000.0,
    currency: str = "USD",
) -> PaperAccountState:
    trade_rows = load_paper_execution_rows(log_path)
    return build_paper_state_from_trades(
        trade_rows,
        initial_cash=initial_cash,
        currency=currency,
    )


def run_paper_eod_dry_run(date_str: str, allow_empty_journal: bool = False, commit: bool = False) -> int:
    paths = build_paper_eod_paths(date_str)
    report_exists = paths["input_report"].exists()
    parser_mode = "not_run"
    journal_rows: list[dict[str, Any]] = []
    mapped_trades: list[dict[str, Any]] = []
    paper_trade_previews = []
    preview_warnings: list[str] = []
    rows_to_append: list[dict[str, Any]] = []
    append_warnings: list[str] = []
    parser_error: str | None = None
    account_preview_error: str | None = None
    paper_state_save_error: str | None = None
    paper_log_exists = paths["paper_execution_log"].exists()
    paper_account_state: PaperAccountState | None = None
    paper_state_save_result: dict[str, Any] | None = None

    if report_exists:
        try:
            strict_rows = parse_journal_from_markdown(paths["input_report"])
            parser_mode = "strict"
            journal_rows = [
                {
                    "date": row["Date"],
                    "regime": row["Regime"],
                    "symbol": row["Symbol"],
                    "type": row["Type"].upper(),
                    "rec_shares": row["Rec_Shares"],
                    "rec_price": row["Rec_Price"],
                    "act_shares": row["Act_Shares"],
                    "act_price": row["Act_Price"],
                    "reason": row["Reason"],
                    "notes": row["Notes"],
                    "status": "READY_FOR_PAPER_TRADE",
                }
                for row in strict_rows
                if row["Type"].upper() in {"BUY", "SELL"}
                and not row["Reason"].upper().startswith("REVIEW")
                and not row["Reason"].upper().startswith("WARNING")
            ]
            mapped_trades = map_journal_to_trades(strict_rows)
        except Exception as exc:
            parser_error = str(exc)
            if allow_empty_journal:
                parser_mode = "fallback_preview"
                journal_rows = parse_journal_preview_from_markdown(paths["input_report"])
            else:
                parser_mode = "strict_failed"

    if report_exists and parser_mode in {"strict", "fallback_preview"}:
        paper_trade_previews, preview_warnings = build_paper_trade_previews(journal_rows)
        rows_to_append, append_warnings = append_paper_execution_log(
            paper_trade_previews,
            paths["paper_execution_log"],
            commit=commit,
        )

    paper_log_exists = paths["paper_execution_log"].exists()
    try:
        paper_account_state = build_paper_account_preview_from_log(paths["paper_execution_log"])
    except ValueError as exc:
        account_preview_error = str(exc)

    if commit and account_preview_error is None and paper_account_state is not None:
        try:
            paper_state_save_result = save_paper_current_state(
                paper_account_state,
                date_str,
                paths["paper_state"],
                PAPER_TEST_DIR / "archive",
            )
        except Exception as exc:
            paper_state_save_error = str(exc)

    mode_label = "COMMIT MODE" if commit else "SAFE DRY RUN"
    print(f"PAPER EOD UPDATE - {mode_label}")
    print("Input report:")
    print(f"  {paths['input_report']}")
    print()
    print("Paper outputs:")
    print(f"  {paths['paper_state']}")
    print(f"  {paths['paper_execution_log']}")
    print(f"  {paths['paper_account_snapshot']}")
    print()
    if report_exists and parser_mode in {"strict", "fallback_preview"}:
        summary = _preview_summary(journal_rows)
        print("Journal preview:")
        print(f"  total_rows: {summary['total_rows']}")
        print(f"  ready_for_paper_trade: {summary['ready_for_paper_trade']}")
        print(f"  pending_actual_fill: {summary['pending_actual_fill']}")
        print(f"  skipped_review_or_warning: {summary['skipped_review_or_warning']}")
        print()
        print("Trade candidates:")
        print("| Symbol | Type | Rec_Shares | Rec_Price | Act_Shares | Act_Price | Status |")
        if not journal_rows:
            print("| - | - | - | - | - | - | no_candidates |")
        else:
            for row in journal_rows:
                print(
                    f"| {row['symbol']} | {row['type']} | {row['rec_shares']} | {row['rec_price']} | "
                    f"{row['act_shares']} | {row['act_price']} | {row['status']} |"
                )
        if mapped_trades:
            print()
            print("Mapped trade preview:")
            for trade in mapped_trades:
                print(
                    f"  {trade['type']} {trade['symbol']} shares={trade['shares']} price={trade['price']}"
                )
        print()
        print("Paper execution preview:")
        print(f"  total_journal_rows: {len(journal_rows)}")
        print(f"  ready_previews: {len(paper_trade_previews)}")
        print(f"  skipped_or_pending: {len(preview_warnings)}")
        print()
        print("| Date | Symbol | Side | Shares | Price | Gross | Source | Reason |")
        if not paper_trade_previews:
            print("| - | - | - | - | - | - | - | no_ready_previews |")
        else:
            for preview in paper_trade_previews:
                print(
                    f"| {preview.date} | {preview.symbol} | {preview.side} | {preview.shares} | "
                    f"{preview.price:.2f} | {preview.gross_amount:.2f} | {preview.source} | {preview.reason} |"
                )
        if preview_warnings:
            print()
            print("Preview warnings:")
            for warning in preview_warnings:
                print(f"  - {warning}")
        print()
        duplicate_count = sum(
            1 for warning in append_warnings if warning.startswith("Skipping duplicate paper trade:")
        )
        print("Paper execution log:")
        print(f"  mode: {'COMMIT' if commit else 'DRY-RUN'}")
        print(f"  log_path: {paths['paper_execution_log']}")
        print(f"  ready_previews: {len(paper_trade_previews)}")
        if commit:
            print(f"  rows_appended: {len(rows_to_append)}")
        else:
            print(f"  rows_to_append: {len(rows_to_append)}")
        print(f"  duplicates_skipped: {duplicate_count}")
        print(f"  write_performed: {commit and bool(rows_to_append)}")
        other_append_warnings = [
            warning for warning in append_warnings
            if not warning.startswith("Skipping duplicate paper trade:")
        ]
        if other_append_warnings:
            print()
            print("Paper execution log warnings:")
            for warning in other_append_warnings:
                print(f"  - {warning}")
        print()
    print("Paper account preview:")
    if account_preview_error is not None:
        print("  failed")
        print(f"  {account_preview_error}")
        print()
    elif not paper_log_exists:
        print("  paper_execution_log.csv not found")
        print("  no trades applied")
        print(f"  initial_cash: {100000.0:.2f} USD")
        print(f"  cash: {paper_account_state.cash:.2f} {paper_account_state.currency}")
        print(f"  positions: {len(paper_account_state.positions)}")
        print(f"  applied_trades: {len(paper_account_state.applied_trade_ids)}")
        print()
        print("Positions:")
        print("  none")
        print()
    else:
        print(f"  initial_cash: {100000.0:.2f} USD")
        print(f"  cash: {paper_account_state.cash:.2f} {paper_account_state.currency}")
        print(f"  positions: {len(paper_account_state.positions)}")
        print(f"  applied_trades: {len(paper_account_state.applied_trade_ids)}")
        if not paper_account_state.applied_trade_ids:
            print("  no trades applied")
        print()
        print("Positions:")
        if not paper_account_state.positions:
            print("  none")
        else:
            print("| Symbol | Shares | Avg Price | Highest Price |")
            for symbol in sorted(paper_account_state.positions):
                position = paper_account_state.positions[symbol]
                print(
                    f"| {position.symbol} | {position.shares} | "
                    f"{position.avg_price:.2f} | {position.highest_price:.2f} |"
                )
        print()
    print("Paper current state:")
    print(f"  path: {paths['paper_state']}")
    print(f"  write_performed: {commit and paper_state_save_result is not None}")
    if not commit:
        print("  dry-run mode: no paper_current_state file written")
    elif paper_state_save_error is not None:
        print("  failed")
        print(f"  {paper_state_save_error}")
    elif paper_state_save_result is not None:
        backup_path = paper_state_save_result.get("backup_path")
        print("  saved")
        if backup_path is not None:
            print(f"  backup_path: {backup_path}")
        print(
            "  saved_fields: "
            + ", ".join(sorted(paper_state_save_result["payload"].keys()))
        )
    print()
    print("Status:")
    if report_exists:
        print("  input report found")
    else:
        print("  WARNING: input report not found")
    if parser_mode == "strict":
        print("  read-only parser OK (strict parser)")
    elif parser_mode == "fallback_preview":
        print("  read-only parser OK (fallback preview parser)")
    elif parser_mode == "strict_failed":
        print(f"  ERROR: strict parser failed: {parser_error}")
        print("  rerun with --allow-empty-journal to preview pending paper trades")
        return 1
    print("  path separation OK")
    print("  paper execution preview OK")
    if account_preview_error is not None:
        print("  ERROR: paper account preview failed")
        print("  invalid paper execution log must be fixed before account state can be previewed")
        return 1
    if paper_state_save_error is not None:
        print("  ERROR: paper current state save failed")
        return 1
    if commit and rows_to_append:
        print("  paper execution log append committed")
    if commit and paper_state_save_result is not None:
        print("  paper_current_state write committed")
    if not (commit and (rows_to_append or paper_state_save_result is not None)):
        print("  no paper files were written")
    print("  no live/front-test files will be written")
    print("  paper account preview OK")
    if commit and paper_state_save_result is not None:
        print("  paper_current_state saved")
    else:
        print("  paper_current_state not written")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Paper EOD update dry-run")
    parser.add_argument("--date", required=True, help="Target date (YYYYMMDD or YYYY-MM-DD)")
    parser.add_argument(
        "--allow-empty-journal",
        action="store_true",
        help="Allow fallback preview parsing when actual fill fields are empty.",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Append READY_FOR_PAPER_TRADE previews to outputs/paper_test/paper_execution_log.csv.",
    )
    args = parser.parse_args()
    return run_paper_eod_dry_run(
        args.date,
        allow_empty_journal=args.allow_empty_journal,
        commit=args.commit,
    )


if __name__ == "__main__":
    raise SystemExit(main())
