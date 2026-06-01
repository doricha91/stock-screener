from __future__ import annotations

from pathlib import Path
from typing import Any

from core.paper_account_paths import build_paper_account_paths
from core.paper_account_profile import validate_account_id
from core.paths import PAPER_TEST_DIR


def resolve_writer_account_context(account_id: str | None = None) -> dict[str, Any]:
    resolved_account_id = "paper_default" if account_id is None else validate_account_id(account_id)
    account_paths = build_paper_account_paths(resolved_account_id, create=False)
    return {
        "account_id": account_paths.account_id,
        "account_root": str(account_paths.root),
        "legacy_default_used": bool(account_paths.legacy_default_used),
    }


def guard_paper_writer_account(
    account_id: str | None = None,
    *,
    command_name: str,
    allow_non_default: bool = False,
) -> dict[str, Any]:
    context = resolve_writer_account_context(account_id)
    resolved_account_id = context["account_id"]
    write_allowed = resolved_account_id == "paper_default" or allow_non_default
    if write_allowed:
        message = (
            f"Writer account guard: allowing {command_name} for account_id={resolved_account_id} "
            f"(account_root={context['account_root']}, "
            f"legacy_default_used={str(context['legacy_default_used']).lower()})."
        )
    else:
        message = (
            f"Writer account guard blocked {command_name} for non-default account_id={resolved_account_id}. "
            "Writer path is still single-account/legacy. "
            "Only paper_default is allowed until PAPER15-3F."
        )
    return {
        **context,
        "command_name": command_name,
        "write_allowed": write_allowed,
        "message": message,
    }


def format_writer_account_guard_message(context: dict[str, Any]) -> str:
    return str(context["message"])


def assert_path_under_account_root(path: str | Path, account_root: str | Path) -> Path:
    candidate = Path(path).resolve()
    root = Path(account_root).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Path must stay under account root: {candidate} not under {root}") from exc
    return candidate


def assert_non_default_writer_target(
    path: str | Path,
    *,
    account_id: str,
    account_root: str | Path,
) -> Path:
    validate_account_id(account_id)
    if account_id == "paper_default":
        raise ValueError("assert_non_default_writer_target must not be used for paper_default.")
    candidate = assert_path_under_account_root(path, account_root)
    paper_test_root = PAPER_TEST_DIR.resolve()
    try:
        candidate.relative_to(paper_test_root)
    except ValueError:
        return candidate
    raise ValueError(
        f"Non-default writer target must not point to legacy paper_test root: {candidate}"
    )
