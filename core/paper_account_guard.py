from __future__ import annotations

from pathlib import Path
from typing import Any

from core.paper_account_paths import PaperAccountPaths, build_paper_account_paths
from core.paper_account_profile import validate_account_id
from core.paths import PAPER_TEST_DIR


def resolve_writer_account_context(account_id: str | None = None) -> dict[str, Any]:
    if account_id is None:
        raise ValueError(
            "account_id is required for a direct write; use an explicit account_id "
            "or the frozen runbook account context."
        )
    resolved_account_id = validate_account_id(account_id)
    account_paths = build_paper_account_paths(
        resolved_account_id,
        allow_legacy_default=False,
        create=False,
    )
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
    legacy_default_used = bool(context["legacy_default_used"])
    write_allowed = not legacy_default_used and (
        resolved_account_id == "paper_default" or allow_non_default
    )
    if write_allowed:
        message = (
            f"Writer account guard: allowing {command_name} for account_id={resolved_account_id} "
            f"(account_root={context['account_root']}, "
            f"legacy_default_used={str(context['legacy_default_used']).lower()})."
        )
    elif legacy_default_used:
        message = (
            f"Writer account guard blocked {command_name} for account_id={resolved_account_id}. "
            "Legacy outputs/paper_test compatibility is read-only and cannot be a write target."
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


def require_initialized_writer_account_paths(
    account_paths: PaperAccountPaths | None,
    *,
    command_name: str,
) -> PaperAccountPaths:
    """Require an explicit, initialized, non-legacy account write context."""
    if account_paths is None:
        raise ValueError(
            f"{command_name} requires explicit account_paths; pass an account_id or "
            "use the frozen runbook account context."
        )
    validate_account_id(account_paths.account_id)
    root = account_paths.root.resolve(strict=False)
    if bool(getattr(account_paths, "legacy_default_used", False)) or root == PAPER_TEST_DIR.resolve(strict=False):
        raise ValueError(
            f"{command_name} cannot write to legacy outputs/paper_test; "
            "initialize and use outputs/paper_accounts/<account_id>."
        )
    if not root.is_dir():
        if account_paths.account_id == "paper_default":
            raise ValueError(
                f"{command_name} requires an initialized canonical paper_default root: {root}. "
                "init-account does not support paper_default; migration or separately approved "
                "initialization is required."
            )
        raise ValueError(
            f"{command_name} requires an initialized account root: {root}. "
            "Run `python scripts/paper.py init-account --account-id "
            f"{account_paths.account_id} --confirm-create` first."
        )
    missing_artifacts = _missing_bootstrap_core_artifacts(account_paths)
    if missing_artifacts:
        missing = ", ".join(missing_artifacts)
        if account_paths.account_id == "paper_default":
            raise ValueError(
                f"{command_name} requires an initialized canonical paper_default root: {root}; "
                f"missing bootstrap core artifacts: {missing}. init-account does not support "
                "paper_default; migration or separately approved initialization is required."
            )
        raise ValueError(
            f"{command_name} requires an initialized account root: {root}; "
            f"missing bootstrap core artifacts: {missing}. Run `python scripts/paper.py "
            f"init-account --account-id {account_paths.account_id} --confirm-create` first."
        )
    return account_paths


def _missing_bootstrap_core_artifacts(account_paths: PaperAccountPaths) -> list[str]:
    missing = [
        path.name
        for path in (
            account_paths.account_snapshot_path,
            account_paths.position_snapshot_path,
            account_paths.execution_log_path,
        )
        if not path.is_file()
    ]
    current_states = [
        path
        for path in account_paths.root.glob("paper_current_state_*.json")
        if path.is_file()
        and len(path.stem.removeprefix("paper_current_state_")) == 8
        and path.stem.removeprefix("paper_current_state_").isdigit()
    ]
    if not current_states:
        missing.append("paper_current_state_<date>.json")
    return missing


def assert_account_writer_target(
    path: str | Path,
    *,
    account_paths: PaperAccountPaths | None,
    command_name: str,
) -> Path:
    context = require_initialized_writer_account_paths(
        account_paths,
        command_name=command_name,
    )
    candidate = assert_path_under_account_root(path, context.root)
    try:
        candidate.relative_to(PAPER_TEST_DIR.resolve(strict=False))
    except ValueError:
        return candidate
    raise ValueError(f"{command_name} cannot write to legacy outputs/paper_test: {candidate}")


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
