from __future__ import annotations

import argparse
import inspect
import json
from datetime import datetime
from pathlib import Path
import sys
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.paper_preflight_check import (  # noqa: E402
    REPORT_PATH_NAMES,
    render_paper_preflight_report,
    run_paper_preflight_check,
    write_markdown,
    write_paper_preflight_issues_csv,
)
from core.paper_data_freshness import (  # noqa: E402
    run_paper_data_freshness_check,
    write_paper_data_freshness_report,
)
from core.paper_commit_guard import check_same_date_commit_guard  # noqa: E402
from core.paper_status import format_paper_status, paper_status_to_json, run_paper_status  # noqa: E402
from core.paper_weekly_status import generate_paper_weekly_status  # noqa: E402
from core.paper_benchmark_comparison import generate_paper_benchmark_comparison  # noqa: E402
from core.paper_account_paths import build_paper_account_paths  # noqa: E402
from core.paper_account_guard import (  # noqa: E402
    format_writer_account_guard_message,
    guard_paper_writer_account,
)
from core.paper_account_bootstrap import (  # noqa: E402
    PaperAccountBootstrapError,
    initialize_paper_account,
)
from core.paper_prepare_data import (  # noqa: E402
    format_paper_prepare_data_summary,
    run_paper_prepare_data,
)
from core.paths import PAPER_TEST_DIR  # noqa: E402
from scripts.generate_paper_daily_review_summary import generate_paper_daily_review_summary  # noqa: E402
from scripts.generate_paper_drawdown import generate_paper_drawdown_for_account  # noqa: E402
from scripts.generate_paper_manual_review_log_template import generate_paper_manual_review_log_template  # noqa: E402
from scripts.generate_paper_equity_curve import generate_paper_equity_curve_for_account  # noqa: E402
from scripts.generate_paper_realized_ranking_report import generate_paper_realized_ranking_report  # noqa: E402
from scripts.generate_paper_realized_trade_journal import generate_paper_realized_trade_journal  # noqa: E402
from scripts.generate_paper_symbol_realized_performance import generate_paper_symbol_realized_performance  # noqa: E402
from scripts.generate_paper_symbol_review_buckets import generate_paper_symbol_review_buckets  # noqa: E402
from scripts.generate_paper_symbol_review_worksheet import generate_paper_symbol_review_worksheet  # noqa: E402
from scripts.generate_paper_symbol_side_by_side_performance import generate_paper_symbol_side_by_side_performance  # noqa: E402
from scripts.generate_paper_symbol_unrealized_performance import generate_paper_symbol_unrealized_performance  # noqa: E402
from scripts.append_paper_manual_review_log import append_paper_manual_review_log_from_template  # noqa: E402
from scripts.generate_paper_performance_summary import generate_paper_performance_summary  # noqa: E402
from scripts.run_paper_daily_plan import run_paper_daily_plan  # noqa: E402
from scripts.run_paper_eod_update import run_paper_eod_dry_run  # noqa: E402
from scripts.validate_paper_manual_review_log import validate_paper_manual_review_log  # noqa: E402

REPORT_STEPS = [
    ("equity_curve", generate_paper_equity_curve_for_account),
    ("drawdown", generate_paper_drawdown_for_account),
    ("performance_summary", generate_paper_performance_summary),
    ("realized_trade_journal", generate_paper_realized_trade_journal),
    ("symbol_realized_performance", generate_paper_symbol_realized_performance),
    ("realized_ranking_report", generate_paper_realized_ranking_report),
    ("symbol_unrealized_performance", generate_paper_symbol_unrealized_performance),
    ("symbol_side_by_side_performance", generate_paper_symbol_side_by_side_performance),
    ("symbol_review_buckets", generate_paper_symbol_review_buckets),
    ("symbol_review_worksheet", generate_paper_symbol_review_worksheet),
    ("daily_review_summary", generate_paper_daily_review_summary),
]


def _call_with_optional_account_paths(func, *args, account_paths, **kwargs):
    if "account_paths" in inspect.signature(func).parameters:
        return func(*args, account_paths=account_paths, **kwargs)
    return func(*args, **kwargs)


def _normalize_cli_date(date_str: str) -> str:
    clean = str(date_str).replace("-", "").strip()
    if len(clean) != 8 or not clean.isdigit():
        raise ValueError(f"Invalid date format: {date_str}")
    return datetime.strptime(clean, "%Y%m%d").strftime("%Y-%m-%d")


def _print_data_freshness_summary(summary: dict) -> None:
    print("PAPER DATA FRESHNESS")
    print(f"  target_date: {summary['target_date']}")
    print(f"  result: {summary['result']}")
    print(f"  error_count: {summary['error_count']}")
    print(f"  warning_count: {summary['warning_count']}")


def _validate_explicit_plan_dates(data_date: str, trade_date: str) -> None:
    data_dt = datetime.strptime(data_date, "%Y-%m-%d").date()
    trade_dt = datetime.strptime(trade_date, "%Y-%m-%d").date()
    if trade_dt <= data_dt:
        raise ValueError(f"trade_date {trade_date} must be after data_date {data_date}")
    if trade_dt.weekday() >= 5:
        raise ValueError(f"trade_date {trade_date} must not be a weekend")


def _call_preflight(
    *,
    stage: str,
    date_str: str | None,
    strict: bool,
    write_report: bool,
    account_paths,
):
    if "account_paths" in inspect.signature(run_preflight).parameters:
        return run_preflight(
            stage=stage,
            date_str=date_str,
            strict=strict,
            write_report=write_report,
            account_paths=account_paths,
        )
    return run_preflight(
        stage=stage,
        date_str=date_str,
        strict=strict,
        write_report=write_report,
    )


def _guard_writer_account(
    account_id: str | None,
    command_name: str,
    *,
    allow_non_default: bool = False,
) -> int:
    context = guard_paper_writer_account(
        account_id=account_id,
        command_name=command_name,
        allow_non_default=allow_non_default,
    )
    print(format_writer_account_guard_message(context))
    return 0 if context["write_allowed"] else 1


def _print_preflight_summary(summary: dict) -> None:
    print("PAPER PREFLIGHT CHECK")
    print(f"  stage: {summary['stage']}")
    print(f"  date: {summary['date'] or '-'}")
    print(f"  strict: {summary['strict']}")
    print(f"  result: {summary['result']}")
    print(f"  error_count: {summary['error_count']}")
    print(f"  warning_count: {summary['warning_count']}")
    if summary["issues"]:
        print("  issues:")
        for issue in summary["issues"]:
            print(
                f"    - [{issue['severity']}] {issue['stage']}::{issue['check_name']} "
                f"{issue['message']}"
            )
    else:
        print("  issues: none")


def _maybe_write_preflight_report(summary: dict, write_report: bool) -> None:
    if not write_report:
        return
    reports_dir = PAPER_TEST_DIR / "reports"
    markdown_path = reports_dir / REPORT_PATH_NAMES["markdown"]
    issues_path = reports_dir / REPORT_PATH_NAMES["issues"]
    write_markdown(markdown_path, render_paper_preflight_report(summary))
    write_paper_preflight_issues_csv(summary["issues"], issues_path)
    print(f"  report_path: {markdown_path}")
    print(f"  issues_path: {issues_path}")


def run_preflight(
    stage: str,
    date_str: str | None,
    strict: bool,
    write_report: bool,
    account_paths=None,
) -> dict:
    if account_paths is None:
        summary = run_paper_preflight_check(
            stage=stage,
            date_str=date_str,
            strict=strict,
        )
    else:
        summary = run_paper_preflight_check(
            stage=stage,
            date_str=date_str,
            strict=strict,
            account_paths=account_paths,
        )
    _print_preflight_summary(summary)
    _maybe_write_preflight_report(summary, write_report)
    return summary


def handle_preflight(args: argparse.Namespace) -> int:
    summary = run_preflight(
        stage=args.stage,
        date_str=args.date,
        strict=args.strict,
        write_report=args.write_report,
    )
    return 1 if summary["result"] == "FAIL" else 0


def handle_prepare_data(args: argparse.Namespace) -> int:
    summary = run_paper_prepare_data(
        args.date,
        skip_prices=args.skip_prices,
        skip_indicators=args.skip_indicators,
        include_universe=args.universe,
    )
    print(format_paper_prepare_data_summary(summary))
    return 0


def handle_data_freshness(args: argparse.Namespace) -> int:
    summary = run_paper_data_freshness_check(
        date_str=args.date,
        strict=args.strict,
    )
    print("PAPER DATA FRESHNESS")
    print(f"  target_date: {summary['target_date']}")
    print(f"  market_db_path: {summary['market_db_path']}")
    print(f"  result: {summary['result']}")
    print(f"  error_count: {summary['error_count']}")
    print(f"  warning_count: {summary['warning_count']}")
    for item in summary["checks"]:
        if item["severity"] in {"error", "warning"}:
            print(f"  - [{item['severity']}] {item['check_name']} {item['message']}")
    if args.write_report:
        markdown_path, issues_path = write_paper_data_freshness_report(summary)
        print(f"  report_path: {markdown_path}")
        print(f"  issues_path: {issues_path}")
    return 1 if summary["result"] == "FAIL" else 0


def _is_blocking_result(result: str, allow_warnings: bool) -> bool:
    if result == "FAIL":
        return True
    if result == "PASS_WITH_WARNINGS" and not allow_warnings:
        return True
    return False


def run_prepare_shortcut(date_str: str, universe: bool, allow_warnings: bool) -> int:
    prepare_summary = run_paper_prepare_data(
        date_str,
        skip_prices=False,
        skip_indicators=False,
        include_universe=universe,
    )
    print(format_paper_prepare_data_summary(prepare_summary))

    freshness_summary = run_paper_data_freshness_check(
        date_str=date_str,
        strict=False,
    )
    print("PAPER DATA FRESHNESS")
    print(f"  target_date: {freshness_summary['target_date']}")
    print(f"  market_db_path: {freshness_summary['market_db_path']}")
    print(f"  result: {freshness_summary['result']}")
    print(f"  error_count: {freshness_summary['error_count']}")
    print(f"  warning_count: {freshness_summary['warning_count']}")
    for item in freshness_summary["checks"]:
        if item["severity"] in {"error", "warning"}:
            print(f"  - [{item['severity']}] {item['check_name']} {item['message']}")

    if _is_blocking_result(freshness_summary["result"], allow_warnings):
        if freshness_summary["result"] == "PASS_WITH_WARNINGS":
            print("Prepare shortcut aborted because data-freshness returned warnings. Use --allow-warnings to continue.")
        else:
            print("Prepare shortcut aborted because data-freshness failed.")
        return 1
    return 0


def run_preview_shortcut(date_str: str, allow_warnings: bool) -> int:
    freshness_summary = run_paper_data_freshness_check(
        date_str=date_str,
        strict=False,
    )
    print("PAPER DATA FRESHNESS")
    print(f"  target_date: {freshness_summary['target_date']}")
    print(f"  market_db_path: {freshness_summary['market_db_path']}")
    print(f"  result: {freshness_summary['result']}")
    print(f"  error_count: {freshness_summary['error_count']}")
    print(f"  warning_count: {freshness_summary['warning_count']}")
    for item in freshness_summary["checks"]:
        if item["severity"] in {"error", "warning"}:
            print(f"  - [{item['severity']}] {item['check_name']} {item['message']}")

    if _is_blocking_result(freshness_summary["result"], allow_warnings):
        if freshness_summary["result"] == "PASS_WITH_WARNINGS":
            print("Preview shortcut aborted because data-freshness returned warnings. Use --allow-warnings to continue.")
        else:
            print("Preview shortcut aborted because data-freshness failed.")
        return 1

    plan_result = handle_plan(argparse.Namespace(date=date_str))
    if plan_result != 0:
        return plan_result
    return handle_eod(argparse.Namespace(date=date_str, dry_run=True, commit=False))


def run_commit_shortcut(date_str: str, replace: bool, account_id: str | None = None) -> int:
    guard = check_same_date_commit_guard(date_str)
    if guard["error"]:
        print(f"Commit guard failed: {guard['error']}")
        return 1
    if not replace and not guard["allowed"]:
        print(f"Commit blocked: snapshot for {guard['normalized_date']} already exists.")
        print("Use --replace only if you intentionally want to replace same-date snapshots.")
        if guard["existing_sources"]:
            print("Existing same-date sources:")
            for item in guard["existing_sources"]:
                print(f"  - {item}")
        return 1
    return handle_eod(
        argparse.Namespace(
            date=date_str,
            dry_run=False,
            commit=True,
            account_id=account_id,
            guard_checked=True,
        )
    )


def run_review_shortcut(
    allow_warnings: bool,
    account_id: str | None = None,
    review_date: str | None = None,
) -> int:
    reports_result = handle_reports(argparse.Namespace(strict=not allow_warnings, account_id=account_id))
    if reports_result != 0:
        return reports_result
    template_result = handle_review_template(argparse.Namespace(account_id=account_id, date=review_date))
    if template_result != 0:
        return template_result
    return handle_review_validate(argparse.Namespace(account_id=account_id))


def handle_prepare(args: argparse.Namespace) -> int:
    return run_prepare_shortcut(
        date_str=args.date,
        universe=args.universe,
        allow_warnings=args.allow_warnings,
    )


def handle_preview(args: argparse.Namespace) -> int:
    return run_preview_shortcut(
        date_str=args.date,
        allow_warnings=args.allow_warnings,
    )


def handle_commit(args: argparse.Namespace) -> int:
    if _guard_writer_account(args.account_id, "paper.py commit", allow_non_default=True) != 0:
        return 1
    return run_commit_shortcut(args.date, replace=args.replace, account_id=args.account_id)


def handle_review(args: argparse.Namespace) -> int:
    try:
        review_date = _normalize_cli_date(args.date) if args.date else None
    except ValueError as exc:
        print(f"Paper review aborted: {exc}")
        return 1
    return run_review_shortcut(
        allow_warnings=args.allow_warnings,
        account_id=args.account_id,
        review_date=review_date,
    )


def handle_status(args: argparse.Namespace) -> int:
    account_paths = build_paper_account_paths(args.account_id, create=False)
    status = _call_with_optional_account_paths(
        run_paper_status,
        args.date,
        account_paths=account_paths,
    )
    if args.json:
        print(paper_status_to_json(status))
    else:
        print(format_paper_status(status, verbose=args.verbose))
    return 0


def handle_init_account(args: argparse.Namespace) -> int:
    if args.dry_run and args.confirm_create:
        raise PaperAccountBootstrapError("--dry-run and --confirm-create cannot be used together.")
    effective_confirm_create = bool(args.confirm_create)
    summary = initialize_paper_account(
        account_id=args.account_id,
        initial_cash=args.initial_cash,
        currency=args.currency,
        date_str=args.date,
        confirm_create=effective_confirm_create,
        allow_existing=args.allow_existing,
    )
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print("PAPER INIT ACCOUNT")
        print(f"  account_id: {summary['account_id']}")
        print(f"  account_root: {summary['account_root']}")
        print(f"  snapshot_date: {summary['snapshot_date']}")
        print(f"  initial_cash: {summary['initial_cash']}")
        print(f"  currency: {summary['currency']}")
        print(f"  dry_run: {str(bool(summary['dry_run'])).lower()}")
        print(f"  created: {str(bool(summary['created'])).lower()}")
        print(f"  blocked_reason: {summary['blocked_reason'] or '-'}")
    return 0


def handle_weekly_status(args: argparse.Namespace) -> int:
    account_paths = build_paper_account_paths(args.account_id, create=False)
    if not account_paths.root.exists():
        summary = {
            "account_id": account_paths.account_id,
            "account_root": str(account_paths.root),
            "legacy_default_used": account_paths.legacy_default_used,
            "status": "NO_DATA",
            "message": f"Account root does not exist: {account_paths.root}",
        }
        print("PAPER WEEKLY STATUS")
        print(f"  account_id: {summary['account_id']}")
        print(f"  account_root: {summary['account_root']}")
        print(f"  status: {summary['status']}")
        print(f"  message: {summary['message']}")
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 1
    result = _call_with_optional_account_paths(
        generate_paper_weekly_status,
        days=args.days,
        start=args.start,
        end=args.end,
        account_paths=account_paths,
    )
    summary = result["summary"]
    print("PAPER WEEKLY STATUS")
    print(f"  account_id: {summary.get('account_id')}")
    print(f"  account_root: {summary.get('account_root')}")
    print(f"  legacy_default_used: {str(bool(summary.get('legacy_default_used'))).lower()}")
    print(f"  markdown_path: {result['markdown_path']}")
    print(f"  json_path: {result['json_path']}")
    print(f"  schema_version: {summary['schema_version']}")
    print(f"  period_start: {summary['period']['actual_start']}")
    print(f"  period_end: {summary['period']['actual_end']}")
    print(f"  snapshot_count: {summary['period']['snapshot_count']}")
    print(f"  coverage_status: {summary['period']['coverage_status']}")
    print(f"  overall_status: {summary['overall_status']}")
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def handle_benchmark(args: argparse.Namespace) -> int:
    account_paths = build_paper_account_paths(args.account_id, create=False)
    if not account_paths.root.exists():
        summary = {
            "account_id": account_paths.account_id,
            "account_root": str(account_paths.root),
            "legacy_default_used": account_paths.legacy_default_used,
            "availability_status": "NO_DATA",
            "message": f"Account root does not exist: {account_paths.root}",
        }
        print("PAPER BENCHMARK COMPARISON")
        print(f"  account_id: {summary['account_id']}")
        print(f"  account_root: {summary['account_root']}")
        print(f"  availability_status: {summary['availability_status']}")
        print(f"  message: {summary['message']}")
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 1
    result = _call_with_optional_account_paths(
        generate_paper_benchmark_comparison,
        account_paths=account_paths,
    )
    summary = result["summary"]
    print("PAPER BENCHMARK COMPARISON")
    print(f"  account_id: {summary.get('account_id')}")
    print(f"  account_root: {summary.get('account_root')}")
    print(f"  legacy_default_used: {str(bool(summary.get('legacy_default_used'))).lower()}")
    print(f"  markdown_path: {result['markdown_path']}")
    print(f"  json_path: {result['json_path']}")
    print(f"  schema_version: {summary['schema_version']}")
    print(f"  run_mode: {summary['run_mode']}")
    print(f"  official_run: {summary['official_run']}")
    print(f"  latest_snapshot_date: {summary['latest_snapshot_date']}")
    print(f"  availability_status: {summary['availability_status']}")
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def handle_plan(args: argparse.Namespace) -> int:
    if _guard_writer_account(args.account_id, "paper.py plan", allow_non_default=True) != 0:
        return 1
    explicit_mode = bool(args.data_date or args.trade_date)
    if explicit_mode and (not args.data_date or not args.trade_date):
        print("Paper plan aborted: --data-date and --trade-date must be provided together.")
        return 1
    if explicit_mode and args.date:
        print("Paper plan aborted: use either legacy --date or explicit --data-date/--trade-date, not both.")
        return 1
    if not explicit_mode and not args.date:
        print("Paper plan aborted: provide --date or both --data-date and --trade-date.")
        return 1

    try:
        preflight_date = _normalize_cli_date(args.trade_date if explicit_mode else args.date)
        data_date = _normalize_cli_date(args.data_date) if explicit_mode else None
        if explicit_mode:
            _validate_explicit_plan_dates(data_date, preflight_date)
    except ValueError as exc:
        print(f"Paper plan aborted: {exc}")
        return 1

    if explicit_mode:
        data_freshness = run_paper_data_freshness_check(date_str=data_date, strict=True)
        _print_data_freshness_summary(data_freshness)
        if data_freshness["result"] != "PASS":
            print("Paper plan aborted because data_date freshness failed.")
            return 1
    else:
        print(
            "WARNING: legacy --date mode does not separate data_date and trade_date. "
            "Use --data-date and --trade-date for official EOD operation."
        )

    account_paths = None
    if args.account_id and args.account_id != "paper_default":
        account_paths = build_paper_account_paths(args.account_id, create=True)
    summary = _call_preflight(
        stage="plan",
        date_str=preflight_date,
        strict=False,
        write_report=False,
        account_paths=account_paths,
    )
    if summary["result"] == "FAIL":
        print("Paper plan aborted because preflight failed.")
        return 1
    if summary["result"] == "PASS_WITH_WARNINGS":
        print("Paper plan continues with preflight warnings.")

    try:
        if explicit_mode:
            report_path = _call_with_optional_account_paths(
                run_paper_daily_plan,
                None,
                account_paths=account_paths,
                data_date=data_date,
                trade_date=preflight_date,
            )
        else:
            report_path = _call_with_optional_account_paths(
                run_paper_daily_plan,
                args.date,
                account_paths=account_paths,
            )
    except ValueError as exc:
        print(f"Paper plan aborted: {exc}")
        return 1
    if not report_path:
        print("Failed to generate official paper daily plan.")
        return 1
    print("Official paper daily plan is ready at:")
    print(report_path)
    return 0


def handle_eod(args: argparse.Namespace) -> int:
    if not getattr(args, "guard_checked", False):
        if _guard_writer_account(args.account_id, "paper.py eod", allow_non_default=True) != 0:
            return 1
    summary = run_preflight(
        stage="eod",
        date_str=args.date,
        strict=False,
        write_report=False,
    )
    if summary["result"] == "FAIL":
        print("Paper EOD aborted because preflight failed.")
        return 1
    if summary["result"] == "PASS_WITH_WARNINGS":
        print("Paper EOD continues with preflight warnings.")

    commit = bool(args.commit)
    account_paths = None
    if args.account_id and args.account_id != "paper_default":
        account_paths = build_paper_account_paths(args.account_id, create=commit)
    return run_paper_eod_dry_run(
        args.date,
        allow_empty_journal=True,
        commit=commit,
        plan_path=None,
        account_paths=account_paths,
    )


def run_report_chain(account_paths=None) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for step_name, runner in REPORT_STEPS:
        try:
            result = _call_with_optional_account_paths(
                runner,
                account_paths=account_paths,
            )
            exit_code = result if isinstance(result, int) else 0
            if exit_code != 0:
                results.append(
                    {
                        "step_name": step_name,
                        "status": "failed",
                        "exit_code": exit_code,
                        "message": f"{step_name} returned exit code {exit_code}",
                    }
                )
                break
            results.append(
                {
                    "step_name": step_name,
                    "status": "success",
                    "exit_code": 0,
                    "message": "ok",
                }
            )
        except Exception as exc:
            results.append(
                {
                    "step_name": step_name,
                    "status": "failed",
                    "exit_code": 1,
                    "message": str(exc),
                }
            )
            break
    return results


def handle_reports(args: argparse.Namespace) -> int:
    summary = run_preflight(
        stage="reports",
        date_str=None,
        strict=args.strict,
        write_report=False,
    )
    if summary["result"] == "FAIL":
        print("Paper reports aborted because preflight failed.")
        return 1

    account_paths = None
    if args.account_id and args.account_id != "paper_default":
        account_paths = build_paper_account_paths(args.account_id, create=True)
    results = run_report_chain(account_paths=account_paths)
    print("PAPER REPORTS")
    for item in results:
        print(
            f"  {item['step_name']}: {item['status']} "
            f"(exit_code={item['exit_code']}) {item['message']}"
        )
        if item["status"] != "success":
            print("Paper reports aborted because a report step failed.")
            return 1
    print("Paper reports completed successfully.")
    return 0


def handle_review_template(args: argparse.Namespace) -> int:
    try:
        review_date = _normalize_cli_date(args.date) if getattr(args, "date", None) else None
    except ValueError as exc:
        print(f"Paper review-template aborted: {exc}")
        return 1
    summary = run_preflight(
        stage="review-template",
        date_str=review_date,
        strict=False,
        write_report=False,
    )
    if summary["result"] == "FAIL":
        print("Paper review-template aborted because preflight failed.")
        return 1
    account_paths = None
    if args.account_id and args.account_id != "paper_default":
        account_paths = build_paper_account_paths(args.account_id, create=True)
    result = generate_paper_manual_review_log_template(account_paths=account_paths, review_date=review_date)
    print("PAPER REVIEW TEMPLATE")
    print(f"  csv_output_path: {result['csv_output_path']}")
    print(f"  markdown_output_path: {result['markdown_output_path']}")
    print(f"  review_date: {result['summary'].get('review_date') or review_date or '-'}")
    print(f"  review_template_row_count: {result['summary']['review_template_row_count']}")
    return 0


def handle_review_validate(args: argparse.Namespace) -> int:
    account_paths = None
    if args.account_id and args.account_id != "paper_default":
        account_paths = build_paper_account_paths(args.account_id, create=True)
    result = validate_paper_manual_review_log(account_paths=account_paths)
    summary = result["summary"]
    print("PAPER REVIEW VALIDATE")
    print(f"  input_path: {result['input_path']}")
    print(f"  report_output_path: {result['report_output_path']}")
    print(f"  issues_output_path: {result['issues_output_path']}")
    print(f"  validation_result: {summary['validation_result']}")
    print(f"  error_count: {summary['error_count']}")
    print(f"  warning_count: {summary['warning_count']}")
    return 1 if summary["error_count"] > 0 else 0


def handle_review_append(args: argparse.Namespace) -> int:
    if _guard_writer_account(args.account_id, "paper.py review-append", allow_non_default=True) != 0:
        return 1
    summary = run_preflight(
        stage="review-append",
        date_str=None,
        strict=False,
        write_report=False,
    )
    if summary["result"] == "FAIL":
        print("Paper review-append aborted because preflight failed.")
        return 1
    account_paths = None
    if args.account_id and args.account_id != "paper_default":
        account_paths = build_paper_account_paths(args.account_id, create=True)
    result = _call_with_optional_account_paths(
        append_paper_manual_review_log_from_template,
        account_paths=account_paths,
    )
    append_summary = result["summary"]
    print("PAPER REVIEW APPEND")
    print(f"  target_log_path: {result['target_log_path']}")
    print(f"  append_report_path: {result['append_report_path']}")
    print(f"  append_issues_path: {result['append_issues_path']}")
    print(f"  validation_result: {append_summary['validation_result']}")
    print(f"  rows_appended: {append_summary['rows_appended']}")
    print(f"  rows_skipped_pending: {append_summary['rows_skipped_pending']}")
    print(f"  rows_skipped_duplicate: {append_summary['rows_skipped_duplicate']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Paper workflow CLI. Supports explicit prepare-data, data-freshness, status, operator shortcuts, preflight, plan, eod, reports, and review wrappers only. "
            "This command does not include integrated market-data orchestration shortcuts, EOD commit automation, or integrated review orchestration."
        )
    )
    subparsers = parser.add_subparsers(dest="command")

    prepare_data_parser = subparsers.add_parser(
        "prepare-data",
        help="Refresh minimal paper market-data inputs explicitly. This command may update market_data.db.",
    )
    prepare_data_parser.add_argument("--date", required=True, help="Target date (YYYYMMDD or YYYY-MM-DD)")
    prepare_data_parser.add_argument("--universe", action="store_true", help="Refresh universe snapshot for the requested date")
    prepare_data_parser.add_argument("--skip-prices", action="store_true", help="Skip market index / tickers / daily price refresh")
    prepare_data_parser.add_argument("--skip-indicators", action="store_true", help="Skip daily_indicators refresh")
    prepare_data_parser.set_defaults(handler=handle_prepare_data)

    prepare_parser = subparsers.add_parser(
        "prepare",
        help="Operator shortcut: prepare-data then data-freshness",
    )
    prepare_parser.add_argument("--date", required=True, help="Target date (YYYYMMDD or YYYY-MM-DD)")
    prepare_parser.add_argument("--universe", action="store_true", help="Refresh universe snapshot during prepare-data")
    prepare_parser.add_argument("--allow-warnings", action="store_true", help="Allow PASS_WITH_WARNINGS to continue")
    prepare_parser.set_defaults(handler=handle_prepare)

    data_freshness_parser = subparsers.add_parser(
        "data-freshness",
        help="Run read-only market data freshness/readiness checks for paper planning",
    )
    data_freshness_parser.add_argument("--date", required=True, help="Target date (YYYYMMDD or YYYY-MM-DD)")
    data_freshness_parser.add_argument("--strict", action="store_true", help="Escalate stale-data warnings to failures where applicable")
    data_freshness_parser.add_argument("--write-report", action="store_true", help="Write freshness report under outputs/paper_test/reports")
    data_freshness_parser.set_defaults(handler=handle_data_freshness)

    status_parser = subparsers.add_parser(
        "status",
        help="Run read-only paper workflow status summary",
    )
    status_parser.add_argument("--date", help="Target date (YYYYMMDD or YYYY-MM-DD)")
    status_parser.add_argument("--account-id", help="Paper account id. Defaults to paper_default.")
    status_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output")
    status_parser.add_argument("--verbose", action="store_true", help="Print extra status details")
    status_parser.set_defaults(handler=handle_status)

    init_account_parser = subparsers.add_parser(
        "init-account",
        help="Bootstrap a new non-default paper account root with initial CSV/JSON seeds",
    )
    init_account_parser.add_argument("--account-id", required=True, help="Non-default paper account id")
    init_account_parser.add_argument("--initial-cash", required=True, type=float, help="Initial cash amount (> 0)")
    init_account_parser.add_argument("--currency", required=True, help="Account currency (for example USD)")
    init_account_parser.add_argument("--date", required=True, help="Bootstrap date (YYYYMMDD or YYYY-MM-DD)")
    init_account_parser.add_argument("--dry-run", action="store_true", help="Show bootstrap plan without writing files")
    init_account_parser.add_argument("--confirm-create", action="store_true", help="Actually create the bootstrap root and seed files")
    init_account_parser.add_argument("--allow-existing", action="store_true", help="Allow read-only inspection of an existing target without overwrite")
    init_account_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON summary")
    init_account_parser.set_defaults(handler=handle_init_account)

    weekly_status_parser = subparsers.add_parser(
        "weekly-status",
        help="Generate snapshot-based weekly paper status markdown/json summary",
    )
    weekly_status_parser.add_argument("--days", type=int, default=5, help="Use the latest N snapshot_date rows")
    weekly_status_parser.add_argument("--start", help="Inclusive snapshot_date start (YYYYMMDD or YYYY-MM-DD)")
    weekly_status_parser.add_argument("--end", help="Inclusive snapshot_date end (YYYYMMDD or YYYY-MM-DD)")
    weekly_status_parser.add_argument("--account-id", help="Paper account id. Defaults to paper_default.")
    weekly_status_parser.add_argument("--json", action="store_true", help="Print JSON summary to stdout after writing files")
    weekly_status_parser.set_defaults(handler=handle_weekly_status)

    benchmark_parser = subparsers.add_parser(
        "benchmark",
        help="Generate exploratory paper benchmark comparison markdown/json report",
    )
    benchmark_parser.add_argument("--account-id", help="Paper account id. Defaults to paper_default.")
    benchmark_parser.add_argument("--json", action="store_true", help="Print JSON summary to stdout after writing files")
    benchmark_parser.set_defaults(handler=handle_benchmark)

    preview_parser = subparsers.add_parser(
        "preview",
        help="Operator shortcut: data-freshness, plan, then EOD dry-run",
    )
    preview_parser.add_argument("--date", required=True, help="Target date (YYYYMMDD or YYYY-MM-DD)")
    preview_parser.add_argument("--allow-warnings", action="store_true", help="Allow PASS_WITH_WARNINGS to continue")
    preview_parser.set_defaults(handler=handle_preview)

    commit_parser = subparsers.add_parser(
        "commit",
        help="Operator shortcut: explicit EOD commit only",
    )
    commit_parser.add_argument("--date", required=True, help="Target date (YYYYMMDD or YYYY-MM-DD)")
    commit_parser.add_argument("--replace", action="store_true", help="Allow same-date snapshot replacement intentionally")
    commit_parser.add_argument("--account-id", help="Paper account id. Defaults to paper_default.")
    commit_parser.set_defaults(handler=handle_commit)

    preflight_parser = subparsers.add_parser(
        "preflight",
        help="Run paper-specific preflight checks",
    )
    preflight_parser.add_argument("--date", help="Target date (YYYYMMDD or YYYY-MM-DD)")
    preflight_parser.add_argument(
        "--stage",
        required=True,
        choices=["plan", "eod", "reports", "review-template", "review-append", "all"],
        help="Paper workflow stage to validate",
    )
    preflight_parser.add_argument("--strict", action="store_true", help="Escalate warnings to errors")
    preflight_parser.add_argument("--write-report", action="store_true", help="Write preflight report under outputs/paper_test/reports")
    preflight_parser.set_defaults(handler=handle_preflight)

    plan_parser = subparsers.add_parser(
        "plan",
        help="Run paper daily plan after automatic paper preflight",
    )
    plan_parser.add_argument("--date", help="Legacy target date (YYYYMMDD or YYYY-MM-DD)")
    plan_parser.add_argument("--data-date", help="Completed market data date (YYYYMMDD or YYYY-MM-DD)")
    plan_parser.add_argument("--trade-date", help="Paper trade/plan date (YYYYMMDD or YYYY-MM-DD)")
    plan_parser.add_argument("--account-id", help="Paper account id. Defaults to paper_default.")
    plan_parser.set_defaults(handler=handle_plan)

    eod_parser = subparsers.add_parser(
        "eod",
        help=(
            "Run paper EOD wrapper after automatic paper preflight. "
            "--dry-run is read-only preview; --commit may modify paper ledger files."
        ),
    )
    eod_parser.add_argument("--date", required=True, help="Target date (YYYYMMDD or YYYY-MM-DD)")
    eod_parser.add_argument("--account-id", help="Paper account id. Defaults to paper_default.")
    eod_mode_group = eod_parser.add_mutually_exclusive_group(required=True)
    eod_mode_group.add_argument("--dry-run", action="store_true", help="Run read-only EOD preview wrapper")
    eod_mode_group.add_argument("--commit", action="store_true", help="Run EOD commit wrapper that may modify paper ledger files")
    eod_parser.set_defaults(handler=handle_eod)

    reports_parser = subparsers.add_parser(
        "reports",
        help="Run paper report generator chain after automatic paper preflight",
    )
    reports_parser.add_argument("--strict", action="store_true", help="Treat preflight warnings as failures")
    reports_parser.add_argument("--account-id", help="Paper account id. Defaults to paper_default.")
    reports_parser.set_defaults(handler=handle_reports)

    review_parser = subparsers.add_parser(
        "review",
        help="Operator shortcut: reports, review-template, review-validate",
    )
    review_parser.add_argument("--allow-warnings", action="store_true", help="Allow PASS_WITH_WARNINGS during reports preflight")
    review_parser.add_argument("--account-id", help="Paper account id. Defaults to paper_default.")
    review_parser.add_argument("--date", help="Review date / trade date (YYYYMMDD or YYYY-MM-DD)")
    review_parser.set_defaults(handler=handle_review)

    review_template_parser = subparsers.add_parser(
        "review-template",
        help="Run manual review log template generator after automatic paper preflight",
    )
    review_template_parser.add_argument("--account-id", help="Paper account id. Defaults to paper_default.")
    review_template_parser.add_argument("--date", help="Review date / trade date (YYYYMMDD or YYYY-MM-DD)")
    review_template_parser.set_defaults(handler=handle_review_template)

    review_validate_parser = subparsers.add_parser(
        "review-validate",
        help="Run manual review log validator",
    )
    review_validate_parser.add_argument("--account-id", help="Paper account id. Defaults to paper_default.")
    review_validate_parser.set_defaults(handler=handle_review_validate)

    review_append_parser = subparsers.add_parser(
        "review-append",
        help="Run manual review log append workflow after automatic paper preflight",
    )
    review_append_parser.add_argument("--account-id", help="Paper account id. Defaults to paper_default.")
    review_append_parser.set_defaults(handler=handle_review_append)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    if not hasattr(args, "handler"):
        parser.print_help()
        return 0
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
