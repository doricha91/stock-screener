from __future__ import annotations

from pathlib import Path

from core.paper_account_paths import PaperAccountPaths
from scripts import paper


def _account_paths(account_id: str, root: Path) -> PaperAccountPaths:
    return PaperAccountPaths(
        account_id=account_id,
        root=root,
        legacy_default_used=False,
        execution_log_path=root / "paper_execution_log.csv",
        account_snapshot_path=root / "paper_account_snapshot.csv",
        position_snapshot_path=root / "paper_position_snapshot.csv",
        reports_dir=root / "reports",
        reviews_dir=root / "reviews",
        config_snapshots_dir=root / "config_snapshots",
        config_snapshot_archive_dir=root / "archive" / "config_snapshots",
        replay_diff_dir=root / "replay_diff",
        replay_diff_config_snapshot_archive_dir=root / "replay_diff" / "archive" / "config_snapshots",
    )


def test_reports_passes_non_default_account_paths(monkeypatch):
    root = Path("outputs/paper_accounts/paper_growth")
    account_paths = _account_paths("paper_growth", root)
    captured: dict[str, object] = {}

    monkeypatch.setattr(paper, "run_preflight", lambda **kwargs: {"result": "PASS"})
    def fake_build_paper_account_paths(account_id=None, *, create=False):
        captured["built"] = (account_id, create)
        return account_paths

    monkeypatch.setattr(paper, "build_paper_account_paths", fake_build_paper_account_paths)

    def fake_run_report_chain(account_paths=None):
        captured["account_id"] = account_paths.account_id
        return [{"step_name": "ok", "status": "success", "exit_code": 0, "message": "ok"}]

    monkeypatch.setattr(paper, "run_report_chain", fake_run_report_chain)
    exit_code = paper.main(["reports", "--account-id", "paper_growth"])
    assert exit_code == 0
    assert captured["built"] == ("paper_growth", True)
    assert captured["account_id"] == "paper_growth"


def test_review_template_and_validate_use_non_default_account_paths(monkeypatch):
    root = Path("outputs/paper_accounts/paper_growth")
    account_paths = _account_paths("paper_growth", root)
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        paper,
        "build_paper_account_paths",
        lambda account_id=None, *, create=False: account_paths,
    )
    monkeypatch.setattr(paper, "run_preflight", lambda **kwargs: {"result": "PASS"})
    def fake_generate_paper_manual_review_log_template(account_paths=None):
        captured["template_account_id"] = account_paths.account_id
        return {
            "csv_output_path": root / "reviews" / "paper_manual_review_log_template.csv",
            "markdown_output_path": root / "reviews" / "paper_manual_review_log_template.md",
            "summary": {"review_template_row_count": 1},
        }

    def fake_validate_paper_manual_review_log(account_paths=None):
        captured["validate_account_id"] = account_paths.account_id
        return {
            "input_path": root / "reviews" / "paper_manual_review_log_template.csv",
            "report_output_path": root / "reviews" / "paper_manual_review_log_validation_report.md",
            "issues_output_path": root / "reviews" / "paper_manual_review_log_validation_issues.csv",
            "summary": {"validation_result": "PASS", "error_count": 0, "warning_count": 0},
        }

    monkeypatch.setattr(paper, "generate_paper_manual_review_log_template", fake_generate_paper_manual_review_log_template)
    monkeypatch.setattr(paper, "validate_paper_manual_review_log", fake_validate_paper_manual_review_log)

    assert paper.main(["review-template", "--account-id", "paper_growth"]) == 0
    assert paper.main(["review-validate", "--account-id", "paper_growth"]) == 0
    assert captured["template_account_id"] == "paper_growth"
    assert captured["validate_account_id"] == "paper_growth"


def test_review_shortcut_passes_account_id(monkeypatch):
    captured: list[tuple[str, str | None]] = []

    monkeypatch.setattr(
        paper,
        "handle_reports",
        lambda args: captured.append(("reports", args.account_id)) or 0,
    )
    monkeypatch.setattr(
        paper,
        "handle_review_template",
        lambda args: captured.append(("review-template", args.account_id)) or 0,
    )
    monkeypatch.setattr(
        paper,
        "handle_review_validate",
        lambda args: captured.append(("review-validate", args.account_id)) or 0,
    )

    assert paper.main(["review", "--account-id", "paper_growth"]) == 0
    assert captured == [
        ("reports", "paper_growth"),
        ("review-template", "paper_growth"),
        ("review-validate", "paper_growth"),
    ]
