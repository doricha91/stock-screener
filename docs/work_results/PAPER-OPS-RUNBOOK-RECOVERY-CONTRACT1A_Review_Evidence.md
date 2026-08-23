# PAPER-OPS-RUNBOOK-RECOVERY-CONTRACT1A Review Evidence

## Identity and instruction

- Repository: `D:\python\StockScreener`
- Branch/baseline: `gemini_cli_update` / `7945ea854faf025db8fd0710e24f5209a32e9f9b`
- Requested instruction path: `D:\python\StockScreener\docs_chatGPT_work\Paper ops runbook recovery contract1A.md.md`
- Actual unique instruction path read: `D:\python\StockScreener\docs_chatGPT_work\Paper ops runbook recovery contract1A.md`
- Title: `Codex 작업지시문 — PAPER-OPS-RUNBOOK-RECOVERY-CONTRACT1A`
- Numbered top-level items: 24
- Instruction length: 807 lines, read in full.
- Root `AGENTS.md`: read in full as UTF-8 and applied.
- Git mutation commands: none.
- Actual operational writes: none.

The duplicate `.md.md` path did not exist. The single-extension file was the only matching candidate, so it was treated as the intended instruction without changing or renaming it.

## Preflight

~~~~text
Exit code: 0
Wall time: 4.5 seconds
Output:
gemini_cli_update
7945ea854faf025db8fd0710e24f5209a32e9f9b
~~~~

Task-scoped extraction from the initial `git status --short`:

~~~~text
?? core/runbook_recovery.py
?? tests/test_runbook_recovery.py
~~~~

The full pre-existing cumulative dirty/untracked worktree reported in chat was preserved. It included unrelated tracked changes, many prior untracked files and protected `outputs/backtest_log.db`. No unexpected stop condition was found. Both task source/test paths were already untracked CONTRACT1 files at task start.

## Current behavior and minimal change

The confirmed gap was:

~~~~text
recovery target STANDARD_COMPLETED
-> preview_rollover() returns normal exact next pair
-> init_state_file_for_context()
-> assert_initialization_allowed()
-> recovery_authorization_already_consumed
-> BLOCK
~~~~

The call graph has no recursion: `preview_rollover()` does not call initialization. CONTRACT1A therefore reuses it as the normal rollover SSOT. Only `core/runbook_recovery.py` and `tests/test_runbook_recovery.py` were edited. No schema, CLI, storage, normal date calculation, prep, state entrypoint or lifecycle status was added.

## Outcome matrix

| Requirement | Result |
|---|---|
| Recovery target ACTIVE | next initialization BLOCKED with `active_runbook_day_exists` |
| Target STANDARD_COMPLETED | normal non-RECOVERY preview PASS |
| Exact normal next initialization | `CREATED` |
| Arbitrary next pairs | BLOCKED with existing `recovery_target_mismatch` |
| Recovery pair reuse | existing state returned; no recreate/overwrite |
| New normal target ACTIVE | following initialization BLOCKED |
| Calendar consistency | caller calendar propagated through classification and preview |
| Invalid consumed sidecar | source returns active/fail-closed |
| No-sidecar normal workflow | preview and exact initialization preserved |
| Sidecar | immutable bytes across full lifecycle |
| Actual source | SHA unchanged |
| Actual operational writes | none |

## Targeted test stdout

Command:

~~~~powershell
python -m pytest -q -p no:cacheprovider tests\test_runbook_recovery.py --basetemp .tmp\recovery_contract1a_targeted_evidence
~~~~

Actual stdout:

~~~~text
Exit code: 0
Wall time: 38.5 seconds
Output:
...........................                                              [100%]
27 passed in 35.60s
~~~~

## Full lifecycle test stdout

Command:

~~~~powershell
python -m pytest -q -p no:cacheprovider tests\test_runbook_recovery.py::test_consumed_recovery_full_lifecycle_returns_to_exact_normal_initialization --basetemp .tmp\recovery_contract1a_lifecycle
~~~~

Actual stdout:

~~~~text
Exit code: 0
Wall time: 6.8 seconds
Output:
.                                                                        [100%]
1 passed in 5.17s
~~~~

## Core recovery/rollover/prep/state/retirement regression

Command:

~~~~powershell
python -m pytest -q -p no:cacheprovider tests\test_runbook_recovery.py tests\test_runbook_day_rollover.py tests\test_runbook_day_prep.py tests\test_runbook_state.py tests\test_runbook_retirement.py --basetemp .tmp\recovery_contract1a_core
~~~~

Actual stdout:

~~~~text
Exit code: 0
Wall time: 54.5 seconds
Output:
........................................................................ [ 37%]
........................................................................ [ 74%]
.................................................                        [100%]
193 passed in 53.02s
~~~~

## Stage A AS-OF regression

Command:

~~~~powershell
python -m pytest -q -p no:cacheprovider tests\test_stage_a_asof_contract.py tests\test_paper_daily_plan_universe_asof.py tests\test_paper_daily_plan_screener_cutoff.py tests\test_paper_data_freshness.py --basetemp .tmp\recovery_contract1a_stage_a
~~~~

Actual stdout:

~~~~text
Exit code: 0
Wall time: 17.7 seconds
Output:
.............................                                            [100%]
============================== warnings summary ===============================
C:\Users\inocha\anaconda3\envs\HANTU311_64\Lib\site-packages\pandas_ta\__init__.py:7
  C:\Users\inocha\anaconda3\envs\HANTU311_64\Lib\site-packages\pandas_ta\__init__.py:7: DeprecationWarning: pkg_resources is deprecated as an API. See https://setuptools.pypa.io/en/latest/pkg_resources.html
    from pkg_resources import get_distribution, DistributionNotFound

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
29 passed, 1 warning in 15.31s
~~~~

## MFU-EO2 / Stage B regression

Command:

~~~~powershell
python -m pytest -q -p no:cacheprovider tests\test_execution_outcome_derivation.py tests\test_execution_outcome_flow.py tests\test_mfu_eo2_zerocount_standard_downstream.py tests\test_runbook_execution_reconciliation_preview.py tests\test_runbook_stage_b_verifier.py tests\test_runbook_stage_b_recovery.py tests\test_runbook_stage_runner_stage_b.py --basetemp .tmp\recovery_contract1a_stage_b
~~~~

Actual stdout:

~~~~text
Exit code: 0
Wall time: 22.6 seconds
Output:
........................................................................ [ 49%]
........................................................................ [ 98%]
..                                                                       [100%]
146 passed in 21.01s
~~~~

## Completion / Stage F regression

Command:

~~~~powershell
python -m pytest -q -p no:cacheprovider tests\test_runbook_completion_evidence.py tests\test_runbook_stage_runner_stage_f.py --basetemp .tmp\recovery_contract1a_completion
~~~~

Actual stdout:

~~~~text
Exit code: 0
Wall time: 23.3 seconds
Output:
........................................................................ [ 61%]
.............................................                            [100%]
117 passed in 20.67s
~~~~

## Stage runner integration regression

Command:

~~~~powershell
python -m pytest -q -p no:cacheprovider tests\test_runbook_stage_runner.py --basetemp .tmp\recovery_contract1a_stage_runner
~~~~

Actual stdout:

~~~~text
Exit code: 0
Wall time: 10.7 seconds
Output:
..............................                                           [100%]
30 passed in 8.14s
~~~~

## Compile and diff validation

Commands:

~~~~powershell
python -m py_compile core\runbook_recovery.py tests\test_runbook_recovery.py core\runbook_day_rollover.py scripts\runbook_state.py
git diff --check
git branch --show-current
git rev-parse HEAD
git status --short --untracked-files=all -- core\runbook_recovery.py tests\test_runbook_recovery.py docs\work_results\PAPER-OPS-RUNBOOK-RECOVERY-CONTRACT1A_Result.md docs\work_results\PAPER-OPS-RUNBOOK-RECOVERY-CONTRACT1A_Review_Evidence.md
~~~~

Actual stdout:

~~~~text
Exit code: 0
Wall time: 1.3 seconds
Output:
py_compile_exit=0
git_diff_check_exit=0
gemini_cli_update
7945ea854faf025db8fd0710e24f5209a32e9f9b
?? core/runbook_recovery.py
?? tests/test_runbook_recovery.py
warning: in the working copy of 'core/daily_plan_generator.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'core/execution_reconciliation.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'core/notion_manual_execution_importer.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'core/paper_account_paths.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'core/paper_config_snapshot.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'core/paper_daily_ops_orchestrator.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'core/paper_daily_review_scope.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'core/paper_data_freshness.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'core/paper_manual_execution_commit.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'core/paper_manual_review_append_commit.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'core/paper_prepare_data.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'core/runbook_day_rollover.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'core/universe_manager.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/operations/paper_daily_cycle_commands.md', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'idea, PRD, TRD/paper 운영 기능 개발 로드맵 v1.3.md', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'scripts/import_notion_executions.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'scripts/paper.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'scripts/run_paper_daily_plan.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'scripts/runbook_command_registry.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'scripts/runbook_completion_evidence.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'scripts/runbook_execution_reconciliation_preview.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'scripts/runbook_gate_checker.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'scripts/runbook_stage_b_verifier.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'scripts/runbook_stage_runner.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'scripts/runbook_state.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'scripts/sync_notion_review_status.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'tests/runbook_standard_evidence_fixtures.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'tests/test_paper_daily_plan_generation.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'tests/test_paper_daily_review_scope.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'tests/test_paper_data_freshness.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'tests/test_paper_manual_execution_commit.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'tests/test_paper_prepare_data.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'tests/test_runbook_execution_reconciliation_preview.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'tests/test_runbook_gate_checker.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'tests/test_runbook_stage_b_verifier.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'tests/test_runbook_stage_runner.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'tests/test_runbook_stage_runner_stage_b.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'tests/test_runbook_state.py', LF will be replaced by CRLF the next time Git touches it
~~~~

## Actual operational read-only status

Command:

~~~~powershell
python scripts\runbook_recovery.py status --workspace D:\n8n\workspace\stock_screener_ops --account-id paper_pilot_202606 --runbook-day-id paper_pilot_202606_2026-08-13_2026-08-14
~~~~

Actual stdout:

~~~~text
Exit code: 0
Wall time: 2.4 seconds
Output:
{
  "runner_result": "PASS",
  "mode": "RECOVERY_STATUS",
  "account_id": "paper_pilot_202606",
  "source_runbook_day_id": "paper_pilot_202606_2026-08-13_2026-08-14",
  "source_state_sha256": "22799cb39561210183333fe0b0ae49299aa184709abc96a4dd983b25218b8bcb",
  "current_classification": "ACTIVE_INCOMPLETE",
  "sidecar_exists": false,
  "sidecar_valid": false,
  "disposition": null,
  "restart": null,
  "consumed": false,
  "blockers": [],
  "next_required_action": "Run a recovery preview."
}
~~~~

## Actual source, ledger, sidecar and target read-only evidence

Actual stdout:

~~~~text
Exit code: 0
Wall time: 0.8 seconds
Output:
source_sha256=22799cb39561210183333fe0b0ae49299aa184709abc96a4dd983b25218b8bcb
ledger_sha256=2b6309ce21e3475b69e874cbf92413451ed703f5016f953688304320b3324f00
recovery_sidecar_exists=False
target_state_exists=False
~~~~

No `authorize`, `00_prepare_next_runbook_day.cmd`, `01_stage_a_plan_prep.cmd`, Stage A–F, Notion, EOD, broker, ledger or DB write command was run.

## Dependent tracked-file current diffs

CONTRACT1A did not edit these tracked files, but they contain the CONTRACT1 integration and pre-existing user changes on which the fix depends. Complete current diffs are retained for review. In particular, `scripts/runbook_state.py` contains unrelated MFU-EO2 changes predating recovery work.

### core/runbook_day_rollover.py

Command: `git diff --no-ext-diff -- core\runbook_day_rollover.py`

~~~~~diff
Exit code: 0
Wall time: 3.1 seconds
Output:
diff --git a/core/runbook_day_rollover.py b/core/runbook_day_rollover.py
index cfc76f8..303c977 100644
--- a/core/runbook_day_rollover.py
+++ b/core/runbook_day_rollover.py
@@ -9,7 +9,7 @@ from typing import Any

 from core.paper_account_paths import build_paper_account_paths
 from core.runbook_calendar import CalendarCoverageError, MarketCalendar
-from core import runbook_retirement
+from core import runbook_recovery, runbook_retirement
 from scripts import runbook_stage_e_evidence
 from scripts import runbook_stage_f_evidence
 from scripts import runbook_state
@@ -104,7 +104,11 @@ def _is_legacy_completed(workspace: Path, record: StateRecord) -> bool:
     )


-def classify_state(workspace: Path, record: StateRecord) -> dict[str, Any]:
+def classify_state(
+    workspace: Path,
+    record: StateRecord,
+    calendar: MarketCalendar | None = None,
+) -> dict[str, Any]:
     if _is_standard_completed(workspace, record.state):
         classification = "STANDARD_COMPLETED"
         blockers: list[str] = []
@@ -119,8 +123,20 @@ def classify_state(workspace: Path, record: StateRecord) -> dict[str, Any]:
             classification = "RETIRED"
             blockers = []
         else:
-            classification = "ACTIVE_INCOMPLETE"
-            blockers = retirement["blockers"] if retirement["exists"] else []
+            recovery = runbook_recovery.validate_recovery_evidence(
+                workspace,
+                record.path,
+                record.state,
+                calendar or runbook_recovery.default_calendar(),
+            )
+            if recovery["valid"]:
+                classification = "RECOVERY_EXCLUDED"
+                blockers = []
+            else:
+                classification = "ACTIVE_INCOMPLETE"
+                blockers = recovery["blockers"] if recovery["exists"] else (
+                    retirement["blockers"] if retirement["exists"] else []
+                )
     return {
         "runbook_day_id": record.state.runbook_day_id,
         "data_date": record.state.frozen_context.data_date,
@@ -212,7 +228,7 @@ def preview_rollover(
     if not records:
         return _blocked("completed_runbook_day_not_found")

-    classified = [(record, classify_state(workspace_path, record)) for record in records]
+    classified = [(record, classify_state(workspace_path, record, calendar)) for record in records]
     active = [record for record, item in classified if item["classification"] == "ACTIVE_INCOMPLETE"]
     if len(active) > 1:
         return _blocked(
@@ -225,6 +241,42 @@ def preview_rollover(
             [f"active_runbook_day:{active[0].state.runbook_day_id}"],
         )

+    recoveries = [
+        record for record, item in classified if item["classification"] == "RECOVERY_EXCLUDED"
+    ]
+    if len(recoveries) > 1:
+        return _blocked(
+            "multiple_recovery_authorizations",
+            [f"recovery_source:{record.state.runbook_day_id}" for record in recoveries],
+        )
+    if recoveries:
+        source = recoveries[0]
+        recovery = runbook_recovery.validate_recovery_evidence(
+            workspace_path, source.path, source.state, calendar
+        )
+        if not recovery["valid"]:
+            return _blocked("recovery_authorization_invalid", recovery["blockers"])
+        if not recovery["consumed"]:
+            restart = recovery["payload"]["restart"]
+            already_exists = _already_exists(workspace_path, restart["runbook_day_id"])
+            if already_exists:
+                return _blocked("recovery_target_already_exists")
+            return {
+                "runner_result": "PASS",
+                "mode": "PREVIEW",
+                "rollover_mode": "RECOVERY",
+                "account_id": account_id,
+                "previous_runbook_day_id": recovery["payload"]["latest_completed"]["runbook_day_id"],
+                "recovery_source_runbook_day_id": source.state.runbook_day_id,
+                "next_data_date": restart["data_date"],
+                "next_trade_date": restart["trade_date"],
+                "next_runbook_day_id": restart["runbook_day_id"],
+                "runbook_classifications": [item for _, item in classified],
+                "already_exists": False,
+                "safe_to_prepare": True,
+                "next_required_action": NEXT_ACTION,
+            }
+
     completed = [
         record
         for record, item in classified
warning: in the working copy of 'core/runbook_day_rollover.py', LF will be replaced by CRLF the next time Git touches it
~~~~~

### scripts/runbook_state.py

Command: `git diff --no-ext-diff -- scripts\runbook_state.py`

~~~~~diff
Exit code: 0
Wall time: 3.2 seconds
Output:
diff --git a/scripts/runbook_state.py b/scripts/runbook_state.py
index bcde7c1..4a8d2bb 100644
--- a/scripts/runbook_state.py
+++ b/scripts/runbook_state.py
@@ -19,6 +19,9 @@ STATE_DIRNAME = "runbook_states"
 # It does not replace the existing n8n runner context.json contract.
 # It shares account_id/data_date/trade_date concepts but owns controller state.
 SCHEMA_VERSION = "runbook_state.v1"
+EXECUTION_CONTRACT_V1 = "execution_reconciliation_preview.v1"
+EXECUTION_CONTRACT_V2 = "execution_reconciliation_preview.v2"
+SUPPORTED_EXECUTION_CONTRACTS = {EXECUTION_CONTRACT_V1, EXECUTION_CONTRACT_V2}
 STAGE_IDS = ("A", "GATE1", "B", "C", "GATE2", "D", "E", "F")
 ALLOWED_STATUSES = {"READY", "PENDING", "RUNNING", "WAIT", "PASS", "BLOCKED", "FAILED", "DONE"}
 ALLOWED_IDEMPOTENCY_STATUSES = {
@@ -54,6 +57,7 @@ class RunbookState:
     last_completed_step: int | None
     last_completed_stage: str | None
     stage_status: dict[str, str]
+    execution_contract: dict[str, Any] = field(default_factory=dict)
     artifacts: dict[str, Any] = field(default_factory=dict)
     idempotency_records: dict[str, Any] = field(default_factory=dict)
     recovery_authorizations: dict[str, Any] = field(default_factory=dict)
@@ -130,6 +134,11 @@ def create_initial_state(
         last_completed_step=None,
         last_completed_stage=None,
         stage_status={stage_id: "PENDING" for stage_id in STAGE_IDS},
+        execution_contract={
+            "version": EXECUTION_CONTRACT_V2,
+            "input_finalized": False,
+            "finalized_at": None,
+        },
         artifacts={},
         idempotency_records={},
         recovery_authorizations={},
@@ -160,6 +169,11 @@ def _state_from_dict(data: dict[str, Any]) -> RunbookState:
         last_completed_step=data.get("last_completed_step"),
         last_completed_stage=data.get("last_completed_stage"),
         stage_status=stage_status,
+        execution_contract=(
+            dict(data.get("execution_contract", {}))
+            if isinstance(data.get("execution_contract"), dict)
+            else {}
+        ),
         artifacts=dict(data.get("artifacts", {})) if isinstance(data.get("artifacts"), dict) else {},
         idempotency_records=(
             dict(data.get("idempotency_records", {}))
@@ -211,6 +225,84 @@ def context_matches_state(
     )


+def get_execution_contract(state: RunbookState) -> dict[str, Any]:
+    """Return the effective execution contract without migrating legacy state."""
+    if not state.execution_contract:
+        return {
+            "version": EXECUTION_CONTRACT_V1,
+            "input_finalized": False,
+            "finalized_at": None,
+        }
+    return dict(state.execution_contract)
+
+
+def activate_execution_outcome_v2(state: RunbookState) -> RunbookState:
+    contract = get_execution_contract(state)
+    version = contract.get("version")
+    if version == EXECUTION_CONTRACT_V2:
+        return state
+    if version != EXECUTION_CONTRACT_V1 or contract.get("input_finalized"):
+        raise ValueError("execution_contract_cannot_be_upgraded")
+    if (
+        state.stage_status.get("B") != "PENDING"
+        or (state.last_completed_step is not None and state.last_completed_step >= 7)
+        or "execution_reconciliation_preview_json" in state.artifacts
+        or "execution_commit_report_json" in state.artifacts
+    ):
+        raise ValueError("completed_or_started_v1_execution_contract_is_immutable")
+    timestamp = _next_updated_at(state)
+    next_contract = {
+        "version": EXECUTION_CONTRACT_V2,
+        "input_finalized": False,
+        "finalized_at": None,
+    }
+    return replace(
+        state,
+        updated_at=timestamp,
+        execution_contract=next_contract,
+        history=_append_history(
+            state,
+            {
+                "event_type": "execution_outcome_v2_activated",
+                "stage_id": state.current_stage,
+                "step_id": state.last_completed_step,
+                "status": state.current_status,
+                "reason": None,
+                "created_at": timestamp,
+            },
+        ),
+    )
+
+
+def finalize_execution_input(state: RunbookState) -> RunbookState:
+    """Finalize v2 input once; a repeated Finalize is an exact no-op."""
+    contract = get_execution_contract(state)
+    if contract.get("version") != EXECUTION_CONTRACT_V2:
+        raise ValueError("execution_finalize_requires_v2_contract")
+    if contract.get("input_finalized") is True:
+        return state
+    timestamp = _next_updated_at(state)
+    next_contract = dict(contract)
+    next_contract["input_finalized"] = True
+    next_contract["finalized_at"] = timestamp
+    return replace(
+        state,
+        updated_at=timestamp,
+        execution_contract=next_contract,
+        history=_append_history(
+            state,
+            {
+                "event_type": "execution_input_finalized",
+                "stage_id": state.current_stage,
+                "step_id": state.last_completed_step,
+                "status": state.current_status,
+                "reason": None,
+                "created_at": timestamp,
+            },
+        ),
+    )
+
+
 def validate_state(state: RunbookState) -> list[str]:
     errors: list[str] = []
     if state.schema_version != SCHEMA_VERSION:
@@ -250,6 +342,17 @@ def validate_state(state: RunbookState) -> list[str]:
         errors.append("last_completed_stage must be null or one of A/GATE1/B/C/GATE2/D/E/F")
     if not isinstance(state.artifacts, dict):
         errors.append("artifacts must be an object")
+    execution_contract = state.execution_contract
+    if not isinstance(execution_contract, dict):
+        errors.append("execution_contract must be an object")
+    elif execution_contract:
+        version = execution_contract.get("version")
+        if version not in SUPPORTED_EXECUTION_CONTRACTS:
+            errors.append(f"execution_contract.version is unsupported: {version}")
+        if not isinstance(execution_contract.get("input_finalized"), bool):
+            errors.append("execution_contract.input_finalized must be a boolean")
+        if execution_contract.get("input_finalized") and not execution_contract.get("finalized_at"):
+            errors.append("execution_contract.finalized_at is required after Finalize")
     if not isinstance(state.idempotency_records, dict):
         errors.append("idempotency_records must be an object")
     else:
@@ -1062,6 +1165,16 @@ def init_state_file_for_context(
     path = get_state_path_for_context(workspace, account_id, data_date, trade_date)
     requested_state = create_initial_state(account_id, data_date, trade_date, timezone)
     if not path.exists():
+        from core.runbook_calendar import load_market_calendar
+        from core.runbook_recovery import assert_initialization_allowed
+
+        assert_initialization_allowed(
+            workspace,
+            account_id,
+            data_date,
+            trade_date,
+            load_market_calendar(),
+        )
         save_state(requested_state, path)
         return "CREATED", path, requested_state

@@ -1113,6 +1226,16 @@ def main(argv: Sequence[str] | None = None) -> int:
     validate_parser = subparsers.add_parser("validate", help="Validate current runbook_state.json")
     validate_parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)

+    for command_name, help_text in (
+        ("activate-execution-v2", "Activate the v2 execution outcome contract for this runbook"),
+        ("finalize-execution-input", "Finalize v2 execution input once for this runbook"),
+    ):
+        command_parser = subparsers.add_parser(command_name, help=help_text)
+        command_parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
+        command_parser.add_argument("--account-id", required=True)
+        command_parser.add_argument("--data-date", required=True)
+        command_parser.add_argument("--trade-date", required=True)
+
     key_parser = subparsers.add_parser("idempotency-key", help="Build an idempotency key")
     key_parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
     key_parser.add_argument("--command-key", required=True)
@@ -1161,6 +1284,36 @@ def main(argv: Sequence[str] | None = None) -> int:
             return 1
         _print_json({"runner_result": "PASS", "runbook_day_id": state.runbook_day_id})
         return 0
+    if args.command in {"activate-execution-v2", "finalize-execution-input"}:
+        path = get_state_path_for_context(
+            args.workspace,
+            args.account_id,
+            args.data_date,
+            args.trade_date,
+        )
+        try:
+            state = load_state(path)
+            if not context_matches_state(state, args.account_id, args.data_date, args.trade_date):
+                raise ValueError("context_mismatch_existing_runbook_state")
+            next_state = (
+                activate_execution_outcome_v2(state)
+                if args.command == "activate-execution-v2"
+                else finalize_execution_input(state)
+            )
+            if next_state is not state:
+                save_state(next_state, path)
+        except (OSError, ValueError, json.JSONDecodeError) as exc:
+            _print_json({"runner_result": "BLOCKED", "reason": str(exc)})
+            return 1
+        _print_json(
+            {
+                "runner_result": "PASS",
+                "runbook_day_id": next_state.runbook_day_id,
+                "execution_contract": get_execution_contract(next_state),
+                "no_op": next_state is state,
+            }
+        )
+        return 0
     if args.command == "idempotency-key":
         state = load_state(get_state_path(args.workspace))
         try:
warning: in the working copy of 'scripts/runbook_state.py', LF will be replaced by CRLF the next time Git touches it
~~~~~

## Full current untracked production content

### core/runbook_recovery.py

~~~~~python
Exit code: 0
Wall time: 5 seconds
Output:
from __future__ import annotations

import csv
import hashlib
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from core.paper_account_paths import build_paper_account_paths
from core.runbook_calendar import (
    CALENDAR_SCHEMA_VERSION,
    DEFAULT_CALENDAR_PATH,
    CalendarCoverageError,
    MarketCalendar,
    load_market_calendar,
)
from core import runbook_retirement
from scripts import runbook_state


SCHEMA_VERSION = "runbook_recovery.v1"
RECOVERY_DIRNAME = "runbook_recoveries"
DISPOSITION = "RECOVERY_EXCLUDED"
TARGET_EVIDENCE_DIRS = (
    "artifacts",
    "command_runs",
    "stage_runs",
    "gate_runs",
    "reconciliation_runs",
    "verification_runs",
    "completion_manifests",
    "no_action_runs",
)


def default_calendar() -> MarketCalendar:
    return load_market_calendar()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def recovery_path(workspace: Path, source_runbook_day_id: str) -> Path:
    return Path(workspace) / RECOVERY_DIRNAME / f"{source_runbook_day_id}.json"


def _blocked(reason: str, blockers: list[str] | None = None, *, mode: str) -> dict[str, Any]:
    return {
        "runner_result": "BLOCKED",
        "mode": mode,
        "reason": reason,
        "blockers": blockers or [reason],
        "eligible": False,
        "next_required_action": "Resolve every blocker before continuing recovery.",
    }


def _is_paper_test(account_id: str) -> bool:
    lowered = account_id.lower()
    return "paper" in lowered or "test" in lowered


def _target_exists(workspace: Path, runbook_day_id: str) -> bool:
    if runbook_state.get_state_path_for_runbook_day_id(workspace, runbook_day_id).exists():
        return True
    return any((workspace / dirname / runbook_day_id).exists() for dirname in TARGET_EVIDENCE_DIRS)


def _target_state_status(
    workspace: Path,
    account_id: str,
    data_date: str,
    trade_date: str,
    runbook_day_id: str,
) -> tuple[str, list[str]]:
    state_path = runbook_state.get_state_path_for_runbook_day_id(workspace, runbook_day_id)
    evidence_exists = any(
        (workspace / dirname / runbook_day_id).exists() for dirname in TARGET_EVIDENCE_DIRS
    )
    if not state_path.exists():
        return ("CONFLICT", ["target_artifact_exists_without_state"]) if evidence_exists else ("ABSENT", [])
    try:
        state = runbook_state.load_state(state_path)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        return "CONFLICT", [f"target_state_invalid:{type(exc).__name__}"]
    if not runbook_state.context_matches_state(state, account_id, data_date, trade_date):
        return "CONFLICT", ["target_state_context_mismatch"]
    return "PRESENT", []


def _calendar_gap(calendar: MarketCalendar, start: date, end: date) -> list[str]:
    if end < start:
        raise ValueError("restart_data_date_precedes_source_trade_date")
    values: list[str] = []
    current = start
    while current <= end:
        if calendar.is_trading_day(current):
            values.append(current.isoformat())
        current += timedelta(days=1)
    return values


def _execution_gap(
    account_id: str,
    gap_dates: list[str],
) -> tuple[Path, str, list[dict[str, str]], list[str]]:
    blockers: list[str] = []
    try:
        paths = build_paper_account_paths(account_id, create=False)
        ledger_path = paths.execution_log_path.resolve(strict=False)
    except (OSError, ValueError) as exc:
        return Path("."), "", [], [f"execution_ledger_path_invalid:{type(exc).__name__}"]
    if not ledger_path.is_file():
        return ledger_path, "", [], ["execution_ledger_missing"]
    try:
        with ledger_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or "date" not in reader.fieldnames:
                return ledger_path, sha256_file(ledger_path), [], ["execution_ledger_date_column_missing"]
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as exc:
        return ledger_path, "", [], [f"execution_ledger_invalid:{type(exc).__name__}"]
    gap_set = set(gap_dates)
    conflicts: list[dict[str, str]] = []
    for index, row in enumerate(rows, start=2):
        value = str(row.get("date") or "").strip()
        try:
            normalized = date.fromisoformat(value).isoformat()
        except ValueError:
            blockers.append(f"execution_ledger_invalid_date:row_{index}")
            continue
        if normalized in gap_set:
            conflicts.append(dict(row))
    if conflicts:
        blockers.append(f"execution_gap_not_empty:{len(conflicts)}")
    return ledger_path, sha256_file(ledger_path), conflicts, blockers


def _raw_classification(workspace: Path, record: Any) -> str:
    from core import runbook_day_rollover

    if runbook_day_rollover._is_standard_completed(workspace, record.state):
        return "STANDARD_COMPLETED"
    if runbook_day_rollover._is_legacy_completed(workspace, record):
        return "LEGACY_COMPLETED"
    retirement = runbook_retirement.validate_retirement_evidence(
        workspace, record.path, record.state
    )
    return "RETIRED" if retirement["valid"] else "ACTIVE_INCOMPLETE"


def _load_recovery_context(
    workspace: Path,
    account_id: str,
    source_runbook_day_id: str,
) -> tuple[Any | None, list[Any], list[Any], list[str]]:
    from core import runbook_day_rollover

    records, blockers = runbook_day_rollover._load_account_states(workspace, account_id)
    if blockers:
        return None, [], [], blockers
    source = next(
        (record for record in records if record.state.runbook_day_id == source_runbook_day_id),
        None,
    )
    raw = [(record, _raw_classification(workspace, record)) for record in records]
    active = [record for record, classification in raw if classification == "ACTIVE_INCOMPLETE"]
    completed = [
        record
        for record, classification in raw
        if classification in {"STANDARD_COMPLETED", "LEGACY_COMPLETED"}
    ]
    return source, active, completed, []


def _latest_completed(completed: list[Any]) -> tuple[Any | None, list[str]]:
    if not completed:
        return None, ["completed_runbook_day_not_found"]
    latest_date = max(record.state.frozen_context.trade_date for record in completed)
    latest = [record for record in completed if record.state.frozen_context.trade_date == latest_date]
    if len(latest) != 1:
        return None, [
            "latest_completed_runbook_day_ambiguous",
            *(f"candidate:{record.state.runbook_day_id}" for record in latest),
        ]
    return latest[0], []


def preview_recovery(
    workspace: str | Path,
    *,
    account_id: str,
    source_runbook_day_id: str,
    restart_data_date: str,
    restart_trade_date: str,
    reason: str,
    calendar: MarketCalendar,
    confirm_paper_test: bool,
    confirm_contaminated_incomplete: bool,
    confirm_no_real_trades: bool,
    confirm_gap_without_backfill: bool,
) -> dict[str, Any]:
    mode = "RECOVERY_PREVIEW"
    workspace_path = Path(workspace).resolve(strict=False)
    account_id = str(account_id or "").strip()
    source_runbook_day_id = str(source_runbook_day_id or "").strip()
    reason = str(reason or "").strip()
    blockers: list[str] = []
    if not workspace_path.is_dir():
        blockers.append("invalid_workspace")
    if not confirm_paper_test:
        blockers.append("paper_test_confirmation_required")
    if not _is_paper_test(account_id):
        blockers.append("paper_account_required")
    if not confirm_contaminated_incomplete:
        blockers.append("contaminated_incomplete_confirmation_required")
    if not confirm_no_real_trades:
        blockers.append("no_real_trades_confirmation_required")
    if not confirm_gap_without_backfill:
        blockers.append("gap_without_backfill_confirmation_required")
    if not reason:
        blockers.append("recovery_reason_required")
    try:
        restart_data = date.fromisoformat(str(restart_data_date))
        restart_trade = date.fromisoformat(str(restart_trade_date))
    except ValueError:
        return _blocked("recovery_context_invalid", [*blockers, "restart_date_invalid"], mode=mode)
    if blockers:
        return _blocked("recovery_confirmation_or_input_invalid", blockers, mode=mode)
    if recovery_path(workspace_path, source_runbook_day_id).exists():
        return _blocked("recovery_authorization_already_exists", mode=mode)

    source, active, completed, state_blockers = _load_recovery_context(
        workspace_path, account_id, source_runbook_day_id
    )
    blockers.extend(state_blockers)
    if source is None:
        blockers.append("source_runbook_not_found")
    if len(active) != 1:
        blockers.append("active_runbook_day_count_must_equal_one")
    elif source is not None and active[0].state.runbook_day_id != source_runbook_day_id:
        blockers.append("source_is_not_the_only_active_runbook")
    latest, latest_blockers = _latest_completed(completed)
    blockers.extend(latest_blockers)
    if source is not None:
        if source.state.frozen_context.account_id != account_id:
            blockers.append("source_account_mismatch")
        if _raw_classification(workspace_path, source) != "ACTIVE_INCOMPLETE":
            blockers.append("source_not_active_incomplete")
        zero_progress = runbook_retirement.assess_zero_progress(
            workspace_path, source.path, source.state
        )
        if zero_progress["eligible"]:
            blockers.append("source_is_zero_progress_retirement_candidate")
    try:
        if not calendar.is_trading_day(restart_data):
            blockers.append("restart_data_date_not_trading_day")
        if not calendar.is_trading_day(restart_trade):
            blockers.append("restart_trade_date_not_trading_day")
        if calendar.next_trading_day(restart_data) != restart_trade:
            blockers.append("restart_trade_date_not_next_trading_day")
    except CalendarCoverageError as exc:
        blockers.append(str(exc))
    if source is not None and restart_data <= date.fromisoformat(source.state.frozen_context.trade_date):
        blockers.append("restart_data_date_not_after_source_trade_date")
    if latest is not None and restart_data <= date.fromisoformat(latest.state.frozen_context.trade_date):
        blockers.append("restart_data_date_not_after_latest_completed_trade_date")
    try:
        gap_dates = (
            _calendar_gap(
                calendar,
                date.fromisoformat(source.state.frozen_context.trade_date),
                restart_data,
            )
            if source is not None
            else []
        )
    except (ValueError, CalendarCoverageError) as exc:
        blockers.append(str(exc))
        gap_dates = []
    ledger_path, ledger_sha256, conflicts, ledger_blockers = _execution_gap(account_id, gap_dates)
    blockers.extend(ledger_blockers)
    target_id = runbook_state.get_runbook_day_id(
        account_id, restart_data.isoformat(), restart_trade.isoformat()
    )
    if _target_exists(workspace_path, target_id):
        blockers.append("recovery_target_already_exists")
    if blockers:
        return _blocked("recovery_not_eligible", blockers, mode=mode)

    assert source is not None and latest is not None
    return {
        "runner_result": "PASS",
        "mode": mode,
        "eligible": True,
        "account_id": account_id,
        "source_runbook_day_id": source_runbook_day_id,
        "source_frozen_context": source.state.to_dict()["frozen_context"],
        "source_state_ref": source.path.relative_to(workspace_path).as_posix(),
        "source_state_sha256": sha256_file(source.path),
        "latest_completed": {
            "runbook_day_id": latest.state.runbook_day_id,
            "frozen_context": latest.state.to_dict()["frozen_context"],
            "state_ref": latest.path.relative_to(workspace_path).as_posix(),
            "state_sha256": sha256_file(latest.path),
        },
        "no_trade_interval": {
            "start_date": gap_dates[0],
            "end_date": gap_dates[-1],
            "trading_dates": gap_dates,
            "execution_count": len(conflicts),
            "ledger_ref": str(ledger_path),
            "ledger_sha256_at_authorization": ledger_sha256,
        },
        "restart": {
            "data_date": restart_data.isoformat(),
            "trade_date": restart_trade.isoformat(),
            "runbook_day_id": target_id,
        },
        "calendar": {
            "schema_version": CALENDAR_SCHEMA_VERSION,
            "market": calendar.market,
            "timezone": calendar.timezone,
            "coverage_start": calendar.coverage_start.isoformat(),
            "coverage_end": calendar.coverage_end.isoformat(),
            "calendar_ref": str(Path(DEFAULT_CALENDAR_PATH).resolve(strict=False)),
            "calendar_sha256": sha256_file(Path(DEFAULT_CALENDAR_PATH)),
        },
        "reason": reason,
        "required_confirmations": {
            "paper_test": True,
            "contaminated_incomplete": True,
            "no_real_trades": True,
            "gap_without_backfill": True,
        },
        "blockers": [],
        "next_required_action": "Review the preview, then run authorize with the exact same inputs.",
    }


def _evidence_from_preview(preview: dict[str, Any], timezone: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "account_id": preview["account_id"],
        "source_runbook_day_id": preview["source_runbook_day_id"],
        "source_frozen_context": preview["source_frozen_context"],
        "source_state_ref": preview["source_state_ref"],
        "source_state_sha256": preview["source_state_sha256"],
        "disposition": DISPOSITION,
        "reason": preview["reason"],
        "latest_completed": preview["latest_completed"],
        "no_trade_interval": preview["no_trade_interval"],
        "restart": preview["restart"],
        "calendar": preview["calendar"],
        "operator_confirmations": preview["required_confirmations"],
        "authorized_at": datetime.now(ZoneInfo(timezone)).isoformat(),
    }


def authorize_recovery(workspace: str | Path, **kwargs: Any) -> dict[str, Any]:
    workspace_path = Path(workspace).resolve(strict=False)
    preview = preview_recovery(workspace_path, **kwargs)
    if preview["runner_result"] != "PASS":
        return {**preview, "mode": "RECOVERY_AUTHORIZE", "authorized": False}
    state_path = workspace_path / preview["source_state_ref"]
    if sha256_file(state_path) != preview["source_state_sha256"]:
        return _blocked(
            "source_state_changed_before_authorization",
            mode="RECOVERY_AUTHORIZE",
        )
    state = runbook_state.load_state(state_path)
    evidence = _evidence_from_preview(preview, state.timezone)
    path = recovery_path(workspace_path, preview["source_runbook_day_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError:
        return _blocked("recovery_authorization_already_exists", mode="RECOVERY_AUTHORIZE")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(evidence, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            path.unlink()
        except OSError:
            pass
        raise
    return {
        "runner_result": "PASS",
        "mode": "RECOVERY_AUTHORIZE",
        "eligible": True,
        "authorized": True,
        "source_runbook_day_id": preview["source_runbook_day_id"],
        "disposition": DISPOSITION,
        "restart": preview["restart"],
        "evidence_path": str(path),
        "evidence_sha256": sha256_file(path),
        "blockers": [],
        "next_required_action": "Run recovery status, then the read-only rollover preview.",
    }


def _load_json_object(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, [f"recovery_evidence_invalid_json:{type(exc).__name__}"]
    if not isinstance(value, dict):
        return None, ["recovery_evidence_must_be_object"]
    return value, []


def validate_recovery_evidence(
    workspace: str | Path,
    source_state_path: Path,
    source_state: runbook_state.RunbookState,
    calendar: MarketCalendar,
) -> dict[str, Any]:
    from core import runbook_day_rollover

    workspace_path = Path(workspace).resolve(strict=False)
    path = recovery_path(workspace_path, source_state.runbook_day_id)
    if not path.is_file():
        return {"valid": False, "exists": False, "path": path, "blockers": ["recovery_evidence_missing"]}
    payload, blockers = _load_json_object(path)
    if payload is None:
        return {"valid": False, "exists": True, "path": path, "blockers": blockers}
    expected_context = source_state.to_dict()["frozen_context"]
    expected_ref = source_state_path.relative_to(workspace_path).as_posix()
    expected_values = {
        "schema_version": SCHEMA_VERSION,
        "account_id": source_state.frozen_context.account_id,
        "source_runbook_day_id": source_state.runbook_day_id,
        "source_frozen_context": expected_context,
        "source_state_ref": expected_ref,
        "disposition": DISPOSITION,
    }
    for field, expected in expected_values.items():
        if payload.get(field) != expected:
            blockers.append(f"recovery_{field}_mismatch")
    if payload.get("source_state_sha256") != sha256_file(source_state_path):
        blockers.append("recovery_source_state_sha256_mismatch")
    if not isinstance(payload.get("reason"), str) or not payload["reason"].strip():
        blockers.append("recovery_reason_missing")
    confirmations = payload.get("operator_confirmations")
    required = {"paper_test", "contaminated_incomplete", "no_real_trades", "gap_without_backfill"}
    if not isinstance(confirmations, dict) or any(confirmations.get(key) is not True for key in required):
        blockers.append("recovery_confirmations_invalid")
    try:
        authorized_at = datetime.fromisoformat(str(payload.get("authorized_at") or ""))
        if authorized_at.tzinfo is None:
            raise ValueError
    except ValueError:
        blockers.append("recovery_authorized_at_invalid")
    calendar_payload = payload.get("calendar")
    if not isinstance(calendar_payload, dict):
        blockers.append("recovery_calendar_invalid")
    else:
        expected_calendar = {
            "schema_version": CALENDAR_SCHEMA_VERSION,
            "market": calendar.market,
            "timezone": calendar.timezone,
            "coverage_start": calendar.coverage_start.isoformat(),
            "coverage_end": calendar.coverage_end.isoformat(),
        }
        for field, expected in expected_calendar.items():
            if calendar_payload.get(field) != expected:
                blockers.append(f"recovery_calendar_{field}_mismatch")
        if calendar_payload.get("calendar_sha256") != sha256_file(Path(DEFAULT_CALENDAR_PATH)):
            blockers.append("recovery_calendar_sha256_mismatch")
    latest = payload.get("latest_completed")
    if not isinstance(latest, dict):
        blockers.append("recovery_latest_completed_invalid")
    else:
        latest_ref = latest.get("state_ref")
        if not isinstance(latest_ref, str):
            blockers.append("recovery_latest_completed_state_ref_invalid")
        else:
            latest_path = workspace_path / latest_ref
            try:
                latest_state = runbook_state.load_state(latest_path)
                raw = json.loads(latest_path.read_text(encoding="utf-8"))
                record = runbook_day_rollover.StateRecord(
                    latest_path, latest_state, dict(raw.get("stage_status") or {})
                )
                completed_valid = (
                    runbook_day_rollover._is_standard_completed(workspace_path, latest_state)
                    or runbook_day_rollover._is_legacy_completed(workspace_path, record)
                )
                if not completed_valid:
                    blockers.append("recovery_latest_completed_no_longer_valid")
                if latest.get("runbook_day_id") != latest_state.runbook_day_id:
                    blockers.append("recovery_latest_completed_id_mismatch")
                if latest.get("frozen_context") != latest_state.to_dict()["frozen_context"]:
                    blockers.append("recovery_latest_completed_context_mismatch")
                if latest.get("state_sha256") != sha256_file(latest_path):
                    blockers.append("recovery_latest_completed_sha256_mismatch")
            except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
                blockers.append("recovery_latest_completed_state_invalid")
    restart = payload.get("restart")
    if not isinstance(restart, dict):
        blockers.append("recovery_restart_invalid")
        restart = {}
    try:
        restart_data = date.fromisoformat(str(restart.get("data_date") or ""))
        restart_trade = date.fromisoformat(str(restart.get("trade_date") or ""))
        expected_target_id = runbook_state.get_runbook_day_id(
            source_state.frozen_context.account_id,
            restart_data.isoformat(),
            restart_trade.isoformat(),
        )
        if restart.get("runbook_day_id") != expected_target_id:
            blockers.append("recovery_restart_runbook_day_id_mismatch")
        if not calendar.is_trading_day(restart_data):
            blockers.append("recovery_restart_data_date_not_trading_day")
        if not calendar.is_trading_day(restart_trade):
            blockers.append("recovery_restart_trade_date_not_trading_day")
        if calendar.next_trading_day(restart_data) != restart_trade:
            blockers.append("recovery_restart_pair_invalid")
    except (ValueError, CalendarCoverageError):
        blockers.append("recovery_restart_dates_invalid")
        restart_data = restart_trade = None
        expected_target_id = str(restart.get("runbook_day_id") or "")
    interval = payload.get("no_trade_interval")
    if not isinstance(interval, dict) or not isinstance(interval.get("trading_dates"), list):
        blockers.append("recovery_no_trade_interval_invalid")
        gap_dates: list[str] = []
    else:
        gap_dates = [str(item) for item in interval["trading_dates"]]
        try:
            expected_gap = _calendar_gap(
                calendar,
                date.fromisoformat(source_state.frozen_context.trade_date),
                restart_data,
            ) if restart_data is not None else []
        except (ValueError, CalendarCoverageError):
            expected_gap = []
        if gap_dates != expected_gap:
            blockers.append("recovery_gap_dates_mismatch")
        if gap_dates and (
            interval.get("start_date") != gap_dates[0]
            or interval.get("end_date") != gap_dates[-1]
        ):
            blockers.append("recovery_gap_bounds_mismatch")
        if interval.get("execution_count") != 0:
            blockers.append("recovery_execution_count_invalid")
    _, _, conflicts, ledger_blockers = _execution_gap(
        source_state.frozen_context.account_id, gap_dates
    )
    blockers.extend(f"recovery_{item}" for item in ledger_blockers)
    if conflicts:
        blockers.append("recovery_execution_contradiction")
    target_status, target_blockers = _target_state_status(
        workspace_path,
        source_state.frozen_context.account_id,
        restart_data.isoformat() if restart_data else "",
        restart_trade.isoformat() if restart_trade else "",
        expected_target_id,
    )
    blockers.extend(f"recovery_{item}" for item in target_blockers)
    return {
        "valid": not blockers,
        "exists": True,
        "path": path,
        "payload": payload,
        "blockers": blockers,
        "consumed": target_status == "PRESENT",
        "target_status": target_status,
    }


def recovery_status(
    workspace: str | Path,
    *,
    account_id: str,
    source_runbook_day_id: str,
    calendar: MarketCalendar,
) -> dict[str, Any]:
    workspace_path = Path(workspace).resolve(strict=False)
    source, _, _, blockers = _load_recovery_context(
        workspace_path, account_id, source_runbook_day_id
    )
    if source is None:
        return _blocked("source_runbook_not_found", blockers or None, mode="RECOVERY_STATUS")
    validation = validate_recovery_evidence(
        workspace_path, source.path, source.state, calendar
    )
    classification = DISPOSITION if validation["valid"] else _raw_classification(workspace_path, source)
    payload = validation.get("payload") or {}
    return {
        "runner_result": "PASS" if not validation["exists"] or validation["valid"] else "BLOCKED",
        "mode": "RECOVERY_STATUS",
        "account_id": account_id,
        "source_runbook_day_id": source_runbook_day_id,
        "source_state_sha256": sha256_file(source.path),
        "current_classification": classification,
        "sidecar_exists": validation["exists"],
        "sidecar_valid": validation["valid"],
        "disposition": payload.get("disposition"),
        "restart": payload.get("restart"),
        "consumed": bool(validation.get("consumed")),
        "blockers": validation["blockers"] if validation["exists"] else [],
        "next_required_action": (
            "Run a recovery preview."
            if not validation["exists"]
            else "Use the exact authorized restart pair." if not validation.get("consumed")
            else "Continue the existing target lifecycle; do not reuse the authorization."
        ),
    }


def assert_initialization_allowed(
    workspace: str | Path,
    account_id: str,
    data_date: str,
    trade_date: str,
    calendar: MarketCalendar,
) -> None:
    from core import runbook_day_rollover

    workspace_path = Path(workspace).resolve(strict=False)
    records, blockers = runbook_day_rollover._load_account_states(workspace_path, account_id)
    if blockers == ["runbook_states_directory_not_found"]:
        return
    if blockers:
        raise ValueError("initialization_invalid_runbook_state")
    if not records:
        return
    classified = [
        (record, runbook_day_rollover.classify_state(workspace_path, record, calendar))
        for record in records
    ]
    active = [record for record, item in classified if item["classification"] == "ACTIVE_INCOMPLETE"]
    progressed_active = [
        record
        for record in active
        if not runbook_retirement.assess_zero_progress(workspace_path, record.path, record.state)["eligible"]
    ]
    recovery_items = [
        (record, item)
        for record, item in classified
        if item["classification"] == DISPOSITION
    ]
    requested_id = runbook_state.get_runbook_day_id(account_id, data_date, trade_date)
    if progressed_active:
        raise ValueError("active_runbook_day_exists")
    if not recovery_items:
        return
    if len(recovery_items) != 1:
        raise ValueError("multiple_recovery_authorizations")
    source = recovery_items[0][0]
    validation = validate_recovery_evidence(
        workspace_path, source.path, source.state, calendar
    )
    if not validation["valid"]:
        raise ValueError("recovery_authorization_invalid")
    if validation["consumed"]:
        if active:
            raise ValueError("active_runbook_day_exists")
        rollover = runbook_day_rollover.preview_rollover(
            workspace_path,
            account_id,
            calendar,
            confirm_paper_test=True,
        )
        if (
            rollover.get("runner_result") != "PASS"
            or rollover.get("rollover_mode") == "RECOVERY"
        ):
            raise ValueError("recovery_authorization_already_consumed")
        requested_context = {
            "account_id": account_id,
            "data_date": data_date,
            "trade_date": trade_date,
            "runbook_day_id": requested_id,
        }
        normal_next_context = {
            "account_id": rollover.get("account_id"),
            "data_date": rollover.get("next_data_date"),
            "trade_date": rollover.get("next_trade_date"),
            "runbook_day_id": rollover.get("next_runbook_day_id"),
        }
        if requested_context != normal_next_context:
            raise ValueError("recovery_target_mismatch")
        return
    if validation["payload"]["restart"]["runbook_day_id"] != requested_id:
        raise ValueError("recovery_target_mismatch")
~~~~~

## Full current untracked test content

### tests/test_runbook_recovery.py

~~~~~python
Exit code: 0
Wall time: 2.9 seconds
Output:
from __future__ import annotations

import csv
import json
from dataclasses import replace
from pathlib import Path

import pytest

from core import runbook_day_rollover, runbook_recovery
from core.paper_execution_log import PAPER_EXECUTION_LOG_COLUMNS
from core.runbook_calendar import load_market_calendar
from core.runbook_day_prep import prepare_runbook_day_local, read_runbook_day_local
from scripts import runbook_recovery as recovery_cli
from scripts import runbook_state
from tests.test_runbook_day_rollover import _complete_state


ACCOUNT_ID = "paper_pilot_202606"
SOURCE_DATA_DATE = "2026-08-13"
SOURCE_TRADE_DATE = "2026-08-14"
SOURCE_ID = f"{ACCOUNT_ID}_{SOURCE_DATA_DATE}_{SOURCE_TRADE_DATE}"
RESTART_DATA_DATE = "2026-08-21"
RESTART_TRADE_DATE = "2026-08-24"
TARGET_ID = f"{ACCOUNT_ID}_{RESTART_DATA_DATE}_{RESTART_TRADE_DATE}"
REASON = "Stage A look-ahead contaminated; no real trades; gap accepted"
CONFIRMATIONS = {
    "confirm_paper_test": True,
    "confirm_contaminated_incomplete": True,
    "confirm_no_real_trades": True,
    "confirm_gap_without_backfill": True,
}


@pytest.fixture(autouse=True)
def _patch_account_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_paths(account_id: str, create: bool = False) -> object:
        account_root = tmp_path / "outputs" / "paper_accounts" / account_id
        if create:
            account_root.mkdir(parents=True, exist_ok=True)
        return type(
            "Paths",
            (),
            {
                "root": account_root,
                "execution_log_path": account_root / "paper_execution_log.csv",
            },
        )()

    monkeypatch.setattr(runbook_day_rollover, "build_paper_account_paths", fake_paths)
    monkeypatch.setattr(runbook_recovery, "build_paper_account_paths", fake_paths)


def _seed_incident(tmp_path: Path) -> tuple[Path, Path, Path]:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _complete_state(workspace, "2026-08-12", "2026-08-13")
    state = runbook_state.create_initial_state(ACCOUNT_ID, SOURCE_DATA_DATE, SOURCE_TRADE_DATE)
    statuses = dict(state.stage_status)
    statuses["A"] = "PASS"
    artifact = workspace / "artifacts" / SOURCE_ID / "stage_a" / "daily_action_plan_20260814.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text('{"contaminated": true}\n', encoding="utf-8")
    state = replace(
        state,
        current_stage="A",
        current_status="PASS",
        last_completed_step=5,
        last_completed_stage="A",
        stage_status=statuses,
        artifacts={"daily_plan_json": artifact.relative_to(workspace).as_posix()},
        history=[{"event_type": "stage_completed", "stage_id": "A", "status": "PASS"}],
    )
    state_path = runbook_state.get_state_path_for_context(
        workspace, ACCOUNT_ID, SOURCE_DATA_DATE, SOURCE_TRADE_DATE
    )
    runbook_state.save_state(state, state_path)
    return workspace, state_path, artifact


def _arguments(workspace: Path, **overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "workspace": workspace,
        "account_id": ACCOUNT_ID,
        "source_runbook_day_id": SOURCE_ID,
        "restart_data_date": RESTART_DATA_DATE,
        "restart_trade_date": RESTART_TRADE_DATE,
        "reason": REASON,
        "calendar": load_market_calendar(),
        **CONFIRMATIONS,
    }
    values.update(overrides)
    return values


def _hash_tree(workspace: Path, state_path: Path, artifact: Path) -> dict[str, str]:
    ledger = workspace.parent / "outputs" / "paper_accounts" / ACCOUNT_ID / "paper_execution_log.csv"
    return {
        "state": runbook_recovery.sha256_file(state_path),
        "artifact": runbook_recovery.sha256_file(artifact),
        "ledger": runbook_recovery.sha256_file(ledger),
    }


def _mark_recovery_target_standard_completed(
    workspace: Path,
    target_path: Path,
    target: runbook_state.RunbookState,
    monkeypatch: pytest.MonkeyPatch,
) -> runbook_state.RunbookState:
    completed = replace(
        target,
        current_stage="F",
        current_status="PASS",
        last_completed_step=21,
        last_completed_stage="F",
        stage_status={stage: "PASS" for stage in runbook_state.STAGE_IDS},
    )
    runbook_state.save_state(completed, target_path)
    original = runbook_day_rollover._is_standard_completed

    def classify_standard(workspace_arg: Path, state: runbook_state.RunbookState) -> bool:
        return state.runbook_day_id == TARGET_ID or original(workspace_arg, state)

    monkeypatch.setattr(runbook_day_rollover, "_is_standard_completed", classify_standard)
    return completed


def test_current_incident_blocks_rollover_and_eligible_preview_is_read_only(tmp_path: Path) -> None:
    workspace, state_path, artifact = _seed_incident(tmp_path)
    before = _hash_tree(workspace, state_path, artifact)

    rollover = runbook_day_rollover.preview_rollover(
        workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True
    )
    preview = runbook_recovery.preview_recovery(**_arguments(workspace))

    assert rollover["reason"] == "active_runbook_day_exists"
    source = runbook_state.load_state(state_path)
    retirement = runbook_recovery.runbook_retirement.assess_zero_progress(
        workspace, state_path, source
    )
    assert retirement["eligible"] is False
    assert preview["runner_result"] == "PASS" and preview["eligible"] is True
    assert preview["restart"] == {
        "data_date": RESTART_DATA_DATE,
        "trade_date": RESTART_TRADE_DATE,
        "runbook_day_id": TARGET_ID,
    }
    assert preview["no_trade_interval"]["trading_dates"] == [
        "2026-08-14", "2026-08-17", "2026-08-18",
        "2026-08-19", "2026-08-20", "2026-08-21",
    ]
    assert preview["no_trade_interval"]["execution_count"] == 0
    assert not runbook_recovery.recovery_path(workspace, SOURCE_ID).exists()
    assert _hash_tree(workspace, state_path, artifact) == before


def test_authorize_creates_immutable_sidecar_and_exact_recovery_rollover(tmp_path: Path) -> None:
    workspace, state_path, artifact = _seed_incident(tmp_path)
    before = _hash_tree(workspace, state_path, artifact)

    result = runbook_recovery.authorize_recovery(**_arguments(workspace))
    evidence_path = runbook_recovery.recovery_path(workspace, SOURCE_ID)
    evidence_before = evidence_path.read_bytes()
    source = runbook_state.load_state(state_path)
    validation = runbook_recovery.validate_recovery_evidence(
        workspace, state_path, source, load_market_calendar()
    )
    classification = runbook_day_rollover.classify_account_runbooks(workspace, ACCOUNT_ID)
    rollover = runbook_day_rollover.preview_rollover(
        workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True
    )

    assert result["runner_result"] == "PASS" and result["authorized"] is True
    assert evidence_path.read_bytes() == evidence_before
    assert validation["valid"] is True and validation["consumed"] is False
    assert classification["classifications"][-1]["classification"] == "RECOVERY_EXCLUDED"
    assert rollover["rollover_mode"] == "RECOVERY"
    assert rollover["next_data_date"] == RESTART_DATA_DATE
    assert rollover["next_trade_date"] == RESTART_TRADE_DATE
    assert rollover["previous_runbook_day_id"] == f"{ACCOUNT_ID}_2026-08-12_2026-08-13"
    assert _hash_tree(workspace, state_path, artifact) == before


@pytest.mark.parametrize("missing", list(CONFIRMATIONS))
def test_missing_confirmation_blocks_without_sidecar(tmp_path: Path, missing: str) -> None:
    workspace, _, _ = _seed_incident(tmp_path)
    result = runbook_recovery.authorize_recovery(
        **_arguments(workspace, **{missing: False})
    )
    assert result["runner_result"] == "BLOCKED"
    assert not runbook_recovery.recovery_path(workspace, SOURCE_ID).exists()


def test_duplicate_authorization_is_blocked_without_overwrite(tmp_path: Path) -> None:
    workspace, _, _ = _seed_incident(tmp_path)
    assert runbook_recovery.authorize_recovery(**_arguments(workspace))["runner_result"] == "PASS"
    path = runbook_recovery.recovery_path(workspace, SOURCE_ID)
    before = path.read_bytes()

    duplicate = runbook_recovery.authorize_recovery(**_arguments(workspace))
    status = runbook_recovery.recovery_status(
        workspace,
        account_id=ACCOUNT_ID,
        source_runbook_day_id=SOURCE_ID,
        calendar=load_market_calendar(),
    )

    assert duplicate["runner_result"] == "BLOCKED"
    assert duplicate["reason"] == "recovery_authorization_already_exists"
    assert path.read_bytes() == before
    assert status["runner_result"] == "PASS" and status["sidecar_valid"] is True


def test_source_hash_mutation_invalidates_exclusion_and_blocks_rollover(tmp_path: Path) -> None:
    workspace, state_path, _ = _seed_incident(tmp_path)
    assert runbook_recovery.authorize_recovery(**_arguments(workspace))["runner_result"] == "PASS"
    state_path.write_bytes(state_path.read_bytes() + b" ")

    classified = runbook_day_rollover.classify_account_runbooks(workspace, ACCOUNT_ID)
    rollover = runbook_day_rollover.preview_rollover(
        workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True
    )

    source_item = next(item for item in classified["classifications"] if item["runbook_day_id"] == SOURCE_ID)
    assert source_item["classification"] == "ACTIVE_INCOMPLETE"
    assert "recovery_source_state_sha256_mismatch" in source_item["blockers"]
    assert rollover["reason"] == "active_runbook_day_exists"


def test_execution_contradiction_before_and_after_authorization_fails_closed(tmp_path: Path) -> None:
    workspace, state_path, _ = _seed_incident(tmp_path)
    ledger = workspace.parent / "outputs" / "paper_accounts" / ACCOUNT_ID / "paper_execution_log.csv"
    with ledger.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAPER_EXECUTION_LOG_COLUMNS)
        writer.writerow({"date": "2026-08-20", "symbol": "AAPL", "status": "COMMITTED"})
    preview = runbook_recovery.preview_recovery(**_arguments(workspace))
    assert preview["runner_result"] == "BLOCKED"
    assert any(item.startswith("execution_gap_not_empty") for item in preview["blockers"])

    rows = list(csv.DictReader(ledger.open("r", encoding="utf-8")))
    with ledger.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAPER_EXECUTION_LOG_COLUMNS)
        writer.writeheader()
        writer.writerows(row for row in rows if row["date"] != "2026-08-20")
    assert runbook_recovery.authorize_recovery(**_arguments(workspace))["runner_result"] == "PASS"
    with ledger.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAPER_EXECUTION_LOG_COLUMNS)
        writer.writerow({"date": "2026-08-20", "symbol": "AAPL", "status": "COMMITTED"})
    source = runbook_state.load_state(state_path)
    validation = runbook_recovery.validate_recovery_evidence(
        workspace, state_path, source, load_market_calendar()
    )
    assert validation["valid"] is False
    assert "recovery_execution_contradiction" in validation["blockers"]


def test_multiple_active_and_missing_completed_block(tmp_path: Path) -> None:
    workspace, _, _ = _seed_incident(tmp_path)
    extra = runbook_state.create_initial_state(ACCOUNT_ID, "2026-08-18", "2026-08-19")
    runbook_state.save_state(
        extra,
        runbook_state.get_state_path_for_context(workspace, ACCOUNT_ID, "2026-08-18", "2026-08-19"),
    )
    multiple = runbook_recovery.preview_recovery(**_arguments(workspace))
    assert multiple["runner_result"] == "BLOCKED"
    assert "active_runbook_day_count_must_equal_one" in multiple["blockers"]

    empty_workspace = tmp_path / "empty_workspace"
    empty_workspace.mkdir()
    source = runbook_state.create_initial_state(ACCOUNT_ID, SOURCE_DATA_DATE, SOURCE_TRADE_DATE)
    source = replace(source, current_status="PASS", last_completed_step=5, last_completed_stage="A")
    runbook_state.save_state(
        source,
        runbook_state.get_state_path_for_context(
            empty_workspace, ACCOUNT_ID, SOURCE_DATA_DATE, SOURCE_TRADE_DATE
        ),
    )
    missing = runbook_recovery.preview_recovery(**_arguments(empty_workspace))
    assert missing["runner_result"] == "BLOCKED"
    assert "completed_runbook_day_not_found" in missing["blockers"]


def test_context_account_mismatch_and_ambiguous_latest_completed_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, _, _ = _seed_incident(tmp_path)
    wrong_account = runbook_recovery.preview_recovery(
        **_arguments(workspace, account_id="paper_other")
    )
    wrong_id = runbook_recovery.preview_recovery(
        **_arguments(workspace, source_runbook_day_id=f"{ACCOUNT_ID}_2026-08-12_2026-08-14")
    )
    assert wrong_account["runner_result"] == "BLOCKED"
    assert "source_runbook_not_found" in wrong_account["blockers"]
    assert wrong_id["runner_result"] == "BLOCKED"
    assert "source_runbook_not_found" in wrong_id["blockers"]

    duplicate = runbook_state.create_initial_state(ACCOUNT_ID, "2026-08-11", "2026-08-13")
    duplicate_path = runbook_state.get_state_path_for_context(
        workspace, ACCOUNT_ID, "2026-08-11", "2026-08-13"
    )
    runbook_state.save_state(duplicate, duplicate_path)
    original = runbook_recovery._raw_classification

    def classify(workspace_arg: Path, record: object) -> str:
        if record.state.runbook_day_id == duplicate.runbook_day_id:
            return "STANDARD_COMPLETED"
        return original(workspace_arg, record)

    monkeypatch.setattr(runbook_recovery, "_raw_classification", classify)
    ambiguous = runbook_recovery.preview_recovery(**_arguments(workspace))
    assert ambiguous["runner_result"] == "BLOCKED"
    assert "latest_completed_runbook_day_ambiguous" in ambiguous["blockers"]


@pytest.mark.parametrize(
    ("data_date", "trade_date", "blocker"),
    [
        ("2026-08-22", "2026-08-24", "restart_data_date_not_trading_day"),
        ("2026-08-21", "2026-08-25", "restart_trade_date_not_next_trading_day"),
        ("2028-01-03", "2028-01-04", "calendar_coverage_exceeded"),
    ],
)
def test_calendar_validation_blocks_invalid_pairs(
    tmp_path: Path, data_date: str, trade_date: str, blocker: str
) -> None:
    workspace, _, _ = _seed_incident(tmp_path)
    result = runbook_recovery.preview_recovery(
        **_arguments(
            workspace,
            restart_data_date=data_date,
            restart_trade_date=trade_date,
        )
    )
    assert result["runner_result"] == "BLOCKED"
    assert any(blocker in item for item in result["blockers"])


def test_target_conflict_blocks_authorization(tmp_path: Path) -> None:
    workspace, _, _ = _seed_incident(tmp_path)
    conflict = workspace / "artifacts" / TARGET_ID / "unexpected.json"
    conflict.parent.mkdir(parents=True)
    conflict.write_text("{}", encoding="utf-8")
    result = runbook_recovery.authorize_recovery(**_arguments(workspace))
    assert result["runner_result"] == "BLOCKED"
    assert "recovery_target_already_exists" in result["blockers"]


def test_sidecar_pair_cannot_be_overridden_and_calendar_evidence_is_fail_closed(tmp_path: Path) -> None:
    workspace, state_path, _ = _seed_incident(tmp_path)
    assert runbook_recovery.authorize_recovery(**_arguments(workspace))["runner_result"] == "PASS"
    different = runbook_recovery.preview_recovery(
        **_arguments(
            workspace,
            restart_data_date="2026-08-20",
            restart_trade_date="2026-08-21",
        )
    )
    assert different["runner_result"] == "BLOCKED"
    assert different["reason"] == "recovery_authorization_already_exists"

    path = runbook_recovery.recovery_path(workspace, SOURCE_ID)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["calendar"]["calendar_sha256"] = "0" * 64
    path.write_text(json.dumps(payload), encoding="utf-8")
    source = runbook_state.load_state(state_path)
    validation = runbook_recovery.validate_recovery_evidence(
        workspace, state_path, source, load_market_calendar()
    )
    assert validation["valid"] is False
    assert "recovery_calendar_sha256_mismatch" in validation["blockers"]
    rollover = runbook_day_rollover.preview_rollover(
        workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True
    )
    assert rollover["reason"] == "active_runbook_day_exists"


@pytest.mark.parametrize("mutation", ["malformed", "account", "context", "disposition"])
def test_malformed_or_mismatched_sidecar_restores_active_blocker(
    tmp_path: Path, mutation: str
) -> None:
    workspace, state_path, _ = _seed_incident(tmp_path)
    assert runbook_recovery.authorize_recovery(**_arguments(workspace))["runner_result"] == "PASS"
    path = runbook_recovery.recovery_path(workspace, SOURCE_ID)
    if mutation == "malformed":
        path.write_text("{invalid", encoding="utf-8")
    else:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if mutation == "account":
            payload["account_id"] = "paper_other"
        elif mutation == "context":
            payload["source_frozen_context"]["trade_date"] = "2026-08-15"
        else:
            payload["disposition"] = "STANDARD_COMPLETED"
        path.write_text(json.dumps(payload), encoding="utf-8")
    source = runbook_state.load_state(state_path)
    validation = runbook_recovery.validate_recovery_evidence(
        workspace, state_path, source, load_market_calendar()
    )
    assert validation["valid"] is False
    classified = runbook_day_rollover.classify_account_runbooks(workspace, ACCOUNT_ID)
    source_item = next(item for item in classified["classifications"] if item["runbook_day_id"] == SOURCE_ID)
    assert source_item["classification"] == "ACTIVE_INCOMPLETE"
    rollover = runbook_day_rollover.preview_rollover(
        workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True
    )
    assert rollover["reason"] == "active_runbook_day_exists"


def test_initialization_requires_exact_authorized_target_and_reapplies_active_guard(tmp_path: Path) -> None:
    workspace, _, _ = _seed_incident(tmp_path)
    with pytest.raises(ValueError, match="active_runbook_day_exists"):
        runbook_state.init_state_file_for_context(
            workspace, ACCOUNT_ID, RESTART_DATA_DATE, RESTART_TRADE_DATE
        )
    assert runbook_recovery.authorize_recovery(**_arguments(workspace))["runner_result"] == "PASS"
    with pytest.raises(ValueError, match="recovery_target_mismatch"):
        runbook_state.init_state_file_for_context(
            workspace, ACCOUNT_ID, "2026-08-20", "2026-08-21"
        )

    created, target_path, target = runbook_state.init_state_file_for_context(
        workspace, ACCOUNT_ID, RESTART_DATA_DATE, RESTART_TRADE_DATE
    )
    assert created == "CREATED" and target.runbook_day_id == TARGET_ID
    rollover = runbook_day_rollover.preview_rollover(
        workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True
    )
    assert rollover["reason"] == "active_runbook_day_exists"
    assert f"active_runbook_day:{TARGET_ID}" in rollover["blockers"]
    with pytest.raises(ValueError, match="active_runbook_day_exists"):
        runbook_state.init_state_file_for_context(
            workspace, ACCOUNT_ID, "2026-08-24", "2026-08-25"
        )
    assert target_path.exists()


def test_prep_consumes_only_the_authorized_exact_pair(tmp_path: Path) -> None:
    workspace, _, _ = _seed_incident(tmp_path)
    assert runbook_recovery.authorize_recovery(**_arguments(workspace))["runner_result"] == "PASS"
    wrapper_dir = tmp_path / "wrappers"
    wrapper_dir.mkdir()
    account_local = wrapper_dir / "_account.local.cmd"
    account_local.write_text(
        f'@echo off\nset "ACCOUNT_ID={ACCOUNT_ID}"\nset "ACCOUNT_MODE=PAPER"\nexit /b 0\n',
        encoding="ascii",
    )
    day_local = wrapper_dir / "_runbook_day.local.cmd"
    result = prepare_runbook_day_local(
        workspace,
        ACCOUNT_ID,
        account_local,
        day_local,
        load_market_calendar(),
        write_env_local=True,
        confirm_paper_test=True,
    )
    assert result["runner_result"] == "PASS"
    assert read_runbook_day_local(day_local, account_id=ACCOUNT_ID) == {
        "DATA_DATE": RESTART_DATA_DATE,
        "TRADE_DATE": RESTART_TRADE_DATE,
        "RUNBOOK_DAY_ID": TARGET_ID,
    }


def test_target_standard_completion_returns_to_normal_sequential_rollover(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, _, _ = _seed_incident(tmp_path)
    assert runbook_recovery.authorize_recovery(**_arguments(workspace))["runner_result"] == "PASS"
    _, target_path, target = runbook_state.init_state_file_for_context(
        workspace, ACCOUNT_ID, RESTART_DATA_DATE, RESTART_TRADE_DATE
    )
    _mark_recovery_target_standard_completed(workspace, target_path, target, monkeypatch)
    result = runbook_day_rollover.preview_rollover(
        workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True
    )
    assert result["runner_result"] == "PASS"
    assert result.get("rollover_mode") != "RECOVERY"
    assert result["previous_runbook_day_id"] == TARGET_ID
    assert result["next_data_date"] == "2026-08-24"
    assert result["next_trade_date"] == "2026-08-25"


def test_consumed_recovery_full_lifecycle_returns_to_exact_normal_initialization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, _, _ = _seed_incident(tmp_path)
    assert runbook_recovery.authorize_recovery(**_arguments(workspace))["runner_result"] == "PASS"
    sidecar_path = runbook_recovery.recovery_path(workspace, SOURCE_ID)
    sidecar_before = sidecar_path.read_bytes()

    created, target_path, target = runbook_state.init_state_file_for_context(
        workspace, ACCOUNT_ID, RESTART_DATA_DATE, RESTART_TRADE_DATE
    )
    assert created == "CREATED" and target.runbook_day_id == TARGET_ID
    with pytest.raises(ValueError, match="active_runbook_day_exists"):
        runbook_state.init_state_file_for_context(
            workspace, ACCOUNT_ID, "2026-08-24", "2026-08-25"
        )

    _mark_recovery_target_standard_completed(workspace, target_path, target, monkeypatch)
    rollover = runbook_day_rollover.preview_rollover(
        workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True
    )
    assert rollover["runner_result"] == "PASS"
    assert rollover.get("rollover_mode") != "RECOVERY"
    assert rollover["next_runbook_day_id"] == f"{ACCOUNT_ID}_2026-08-24_2026-08-25"

    for data_date, trade_date in (
        ("2026-08-24", "2026-08-26"),
        ("2026-08-25", "2026-08-26"),
        ("2026-08-30", "2026-08-31"),
    ):
        with pytest.raises(ValueError, match="recovery_target_mismatch"):
            runbook_state.init_state_file_for_context(
                workspace, ACCOUNT_ID, data_date, trade_date
            )

    existing, existing_path, existing_target = runbook_state.init_state_file_for_context(
        workspace, ACCOUNT_ID, RESTART_DATA_DATE, RESTART_TRADE_DATE
    )
    assert existing == "EXISTING"
    assert existing_path == target_path
    assert existing_target.runbook_day_id == TARGET_ID

    def fail_if_default_calendar_is_reloaded() -> object:
        raise AssertionError("caller calendar was not propagated")

    monkeypatch.setattr(runbook_recovery, "default_calendar", fail_if_default_calendar_is_reloaded)
    normal_created, normal_path, normal_state = runbook_state.init_state_file_for_context(
        workspace, ACCOUNT_ID, "2026-08-24", "2026-08-25"
    )
    assert normal_created == "CREATED"
    assert normal_state.runbook_day_id == f"{ACCOUNT_ID}_2026-08-24_2026-08-25"
    assert normal_path.exists()
    assert sidecar_path.read_bytes() == sidecar_before

    with pytest.raises(ValueError, match="active_runbook_day_exists"):
        runbook_state.init_state_file_for_context(
            workspace, ACCOUNT_ID, "2026-08-25", "2026-08-26"
        )


def test_invalid_consumed_sidecar_keeps_normal_initialization_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, _, _ = _seed_incident(tmp_path)
    assert runbook_recovery.authorize_recovery(**_arguments(workspace))["runner_result"] == "PASS"
    _, target_path, target = runbook_state.init_state_file_for_context(
        workspace, ACCOUNT_ID, RESTART_DATA_DATE, RESTART_TRADE_DATE
    )
    _mark_recovery_target_standard_completed(workspace, target_path, target, monkeypatch)
    sidecar_path = runbook_recovery.recovery_path(workspace, SOURCE_ID)
    payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
    payload["calendar"]["calendar_sha256"] = "0" * 64
    sidecar_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="active_runbook_day_exists"):
        runbook_state.init_state_file_for_context(
            workspace, ACCOUNT_ID, "2026-08-24", "2026-08-25"
        )


def test_no_sidecar_normal_preview_and_exact_initialization_are_preserved(tmp_path: Path) -> None:
    workspace = tmp_path / "normal_workspace"
    workspace.mkdir()
    _complete_state(workspace, "2026-08-12", "2026-08-13")

    rollover = runbook_day_rollover.preview_rollover(
        workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True
    )
    assert rollover["runner_result"] == "PASS"
    assert rollover.get("rollover_mode") != "RECOVERY"
    assert rollover["next_data_date"] == "2026-08-13"
    assert rollover["next_trade_date"] == "2026-08-14"

    created, _, state = runbook_state.init_state_file_for_context(
        workspace, ACCOUNT_ID, "2026-08-13", "2026-08-14"
    )
    assert created == "CREATED"
    assert state.runbook_day_id == f"{ACCOUNT_ID}_2026-08-13_2026-08-14"


def test_cli_preview_and_status_are_readable(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    workspace, _, _ = _seed_incident(tmp_path)
    common = [
        "--workspace", str(workspace), "--account-id", ACCOUNT_ID,
        "--runbook-day-id", SOURCE_ID,
    ]
    preview_code = recovery_cli.main([
        "preview", *common,
        "--restart-data-date", RESTART_DATA_DATE,
        "--restart-trade-date", RESTART_TRADE_DATE,
        "--reason", REASON,
        "--confirm-paper-test", "--confirm-contaminated-incomplete",
        "--confirm-no-real-trades", "--confirm-gap-without-backfill",
    ])
    preview = json.loads(capsys.readouterr().out)
    status_code = recovery_cli.main(["status", *common])
    status = json.loads(capsys.readouterr().out)
    assert preview_code == 0 and preview["eligible"] is True
    assert status_code == 0 and status["current_classification"] == "ACTIVE_INCOMPLETE"
    assert status["sidecar_exists"] is False

    authorize_code = recovery_cli.main([
        "authorize", *common,
        "--restart-data-date", RESTART_DATA_DATE,
        "--restart-trade-date", RESTART_TRADE_DATE,
        "--reason", REASON,
        "--confirm-paper-test", "--confirm-contaminated-incomplete",
        "--confirm-no-real-trades", "--confirm-gap-without-backfill",
    ])
    authorized = json.loads(capsys.readouterr().out)
    assert authorize_code == 0 and authorized["authorized"] is True
~~~~~

## Full Result content

### PAPER-OPS-RUNBOOK-RECOVERY-CONTRACT1A_Result.md

~~~~~markdown
Exit code: 0
Wall time: 2.5 seconds
Output:
# Summary

PAPER-OPS-RUNBOOK-RECOVERY-CONTRACT1A의 lifecycle gap을 최소 수정했다. Recovery target가 `STANDARD_COMPLETED`된 뒤 consumed sidecar는 historical incident evidence로 남고, initialization guard는 기존 normal `preview_rollover()`가 반환한 exact next context만 허용한다. 실제 운영 workspace에는 read-only 조회만 수행했다.

# Gap fixed

기존에는 target 완료 후 rollover preview가 정상 순차 pair를 반환해도 `assert_initialization_allowed()`가 `recovery_authorization_already_consumed`로 실제 state 생성을 막았다. 이제 consumed recovery를 무조건 허용하지 않고 normal rollover SSOT와 requested context를 정확히 비교해 정상 lifecycle만 재개한다.

# Files changed

Production:

- `core/runbook_recovery.py`

Tests:

- `tests/test_runbook_recovery.py`

Task documents:

- `docs/work_results/PAPER-OPS-RUNBOOK-RECOVERY-CONTRACT1A_Result.md`
- `docs/work_results/PAPER-OPS-RUNBOOK-RECOVERY-CONTRACT1A_Review_Evidence.md`

`core/runbook_day_rollover.py`, `scripts/runbook_state.py`, sidecar schema/CLI/storage와 operations documentation은 CONTRACT1A에서 추가 변경하지 않았다.

# Consumed recovery semantics

Consumed는 recovery target state가 exact context로 이미 존재한다는 뜻이다. Target가 active이면 기존 active guard가 먼저 BLOCK한다. Target가 standard completed이고 다른 active가 없으면 guard는 `preview_rollover()`를 동일 calendar와 account로 호출한다. Preview가 PASS, non-RECOVERY이고 exact requested context와 일치할 때만 생성이 허용된다. Sidecar는 삭제·수정·재활성화되지 않는다.

# Target-active behavior

Recovery target `paper_pilot_202606_2026-08-21_2026-08-24`가 `ACTIVE_INCOMPLETE`인 동안 다음 runbook initialization은 `active_runbook_day_exists`로 BLOCK된다. 기존 CONTRACT1 behavior를 유지했다.

# Target-completed behavior

Target가 `STANDARD_COMPLETED`가 되면 recovery routing은 종료된다. Normal preview는 target를 latest completed baseline으로 사용해 `DATA_DATE=2026-08-24`, `TRADE_DATE=2026-08-25`와 exact runbook ID를 반환한다. `rollover_mode=RECOVERY`는 재사용되지 않는다.

# Normal initialization recovery

Normal preview가 반환한 exact pair `2026-08-24`→`2026-08-25`를 `init_state_file_for_context()`에 전달하면 `CREATED`가 반환된다. 생성 직후 새 state는 ordinary `ACTIVE_INCOMPLETE`이므로 그 다음 추가 initialization은 다시 active guard로 BLOCK된다.

# Arbitrary initialization guard

Consumed sidecar가 존재해도 다음 임의 context는 `recovery_target_mismatch`로 BLOCK된다.

- `2026-08-24`→`2026-08-26`
- `2026-08-25`→`2026-08-26`
- `2026-08-30`→`2026-08-31`

기존 recovery pair를 다시 요청하면 기존 target가 `EXISTING`으로 반환될 뿐 재생성·overwrite되지 않는다.

# Calendar consistency

Initialization guard의 모든 `classify_state()` 호출에 caller가 제공한 `calendar`를 전달한다. Consumed branch의 normal preview에도 같은 객체를 전달한다. 별도 날짜 계산이나 calendar abstraction은 추가하지 않았다. 테스트는 guard 내부에서 default calendar 재로딩이 발생하면 실패하도록 구성했다.

# Recovery sidecar immutability

`runbook_recovery.v1` schema, create-only authorization, `RECOVERY_EXCLUDED` 의미와 storage는 변경하지 않았다. Full lifecycle 전후 sidecar bytes가 동일함을 테스트했다. Sidecar는 completion, retirement, baseline 또는 source state 대체물이 아니다.

# Source incident protection

실제 source `paper_pilot_202606_2026-08-13_2026-08-14`는 수정하지 않았다. 최종 SHA-256은 `22799cb39561210183333fe0b0ae49299aa184709abc96a4dd983b25218b8bcb`로 CONTRACT1과 동일하다. Actual sidecar와 target state는 모두 존재하지 않는다.

# Tests

실제로 실행한 테스트:

- Recovery targeted: 27 passed.
- 핵심 full lifecycle 단일 테스트: 1 passed.
- Recovery/rollover/prep/state/retirement: 193 passed.
- Stage A AS-OF: 29 passed, 기존 dependency deprecation warning 1건.
- MFU-EO2/Stage B: 146 passed.
- Completion/Stage F: 117 passed.
- Stage runner integration: 30 passed.

# Regression results

CONTRACT1 immutable sidecar, duplicate/malformed/hash/calendar/ledger/target conflict fail-closed, exact recovery target, prep consumption과 active guard 회귀가 모두 PASS했다. Normal rollover, legacy/retirement/completion, Stage A AS-OF, MFU-EO2, Stage B 및 Stage F semantics에는 production 변경이 없고 관련 suite가 모두 PASS했다. `py_compile`과 `git diff --check`도 PASS했다.

# Actual operational state protection

실제 `D:\n8n\workspace\stock_screener_ops`에서는 recovery `status`와 SHA/existence 조회만 실행했다. `authorize`, prepare wrapper, Stage A~F, Notion, EOD, broker, ledger/DB write는 실행하지 않았다.

- source SHA-256: `22799cb39561210183333fe0b0ae49299aa184709abc96a4dd983b25218b8bcb`
- ledger SHA-256: `2b6309ce21e3475b69e874cbf92413451ed703f5016f953688304320b3324f00`
- actual recovery sidecar: 없음
- actual recovery target state: 없음

# Risks / limitations

- Target standard completion은 실제 completion evidence가 모두 유효해야 한다. Recovery가 이를 우회하지 않는다.
- Target-completed routing test는 CONTRACT1과 동일하게 target standard classification을 격리해 검증하며, 실제 completion evidence semantics는 별도 117개 completion/Stage F 회귀로 검증했다.
- No-sidecar 기존 workflow는 그대로 유지되어 CONTRACT1A의 exact consumed-recovery guard 대상이 아니다.
- 기존 worktree의 다수 dirty/untracked 변경과 보호 DB 변경은 범위 밖이며 보존했다.

# Decisions Needed

구현에 필요한 추가 결정은 없다. 실제 recovery authorize와 운영 재시작은 여전히 별도 operator 승인 대상이다.

# Suggested next step

Result와 Review Evidence를 검토한다. 실제 운영 recovery를 승인할 경우 CONTRACT1 Result의 exact operator procedure를 따르되 실행 직전 status/preview, source/ledger hash, data readiness를 다시 확인한다.

# Review Evidence path

`docs/work_results/PAPER-OPS-RUNBOOK-RECOVERY-CONTRACT1A_Review_Evidence.md`
~~~~~

## Files attributable to CONTRACT1A

- `core/runbook_recovery.py` — consumed recovery exact-normal guard and calendar propagation.
- `tests/test_runbook_recovery.py` — characterization, exact/arbitrary/full lifecycle, invalid consumed sidecar and no-sidecar regressions.
- `docs/work_results/PAPER-OPS-RUNBOOK-RECOVERY-CONTRACT1A_Result.md`
- `docs/work_results/PAPER-OPS-RUNBOOK-RECOVERY-CONTRACT1A_Review_Evidence.md`

No existing user file was deleted, renamed, reset, restored, staged, committed, pushed, stashed, merged or rebased.


## Final bundle validation

Commands covered required Result headings, trailing whitespace in task production/test/Result files, `py_compile`, `git diff --check`, branch/HEAD, actual source hash, actual sidecar/target absence and scoped end status.

~~~~text
Exit code: 0
Wall time: 6.4 seconds
Output:
required_heading_count=18
missing_headings=
core\runbook_recovery.py trailing_whitespace_matches=0
tests\test_runbook_recovery.py trailing_whitespace_matches=0
docs\work_results\PAPER-OPS-RUNBOOK-RECOVERY-CONTRACT1A_Result.md trailing_whitespace_matches=0
evidence_trailing_whitespace_matches=9
py_compile_exit=0
git_diff_check_exit=0
branch=gemini_cli_update
HEAD=7945ea854faf025db8fd0710e24f5209a32e9f9b
source_sha256=22799cb39561210183333fe0b0ae49299aa184709abc96a4dd983b25218b8bcb
recovery_sidecar_exists=False
target_state_exists=False
--- scoped end status ---
?? core/runbook_recovery.py
?? docs/work_results/PAPER-OPS-RUNBOOK-RECOVERY-CONTRACT1A_Result.md
?? docs/work_results/PAPER-OPS-RUNBOOK-RECOVERY-CONTRACT1A_Review_Evidence.md
?? tests/test_runbook_recovery.py
warning: in the working copy of 'core/daily_plan_generator.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'core/execution_reconciliation.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'core/notion_manual_execution_importer.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'core/paper_account_paths.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'core/paper_config_snapshot.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'core/paper_daily_ops_orchestrator.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'core/paper_daily_review_scope.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'core/paper_data_freshness.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'core/paper_manual_execution_commit.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'core/paper_manual_review_append_commit.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'core/paper_prepare_data.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'core/runbook_day_rollover.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'core/universe_manager.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/operations/paper_daily_cycle_commands.md', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'idea, PRD, TRD/paper 운영 기능 개발 로드맵 v1.3.md', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'scripts/import_notion_executions.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'scripts/paper.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'scripts/run_paper_daily_plan.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'scripts/runbook_command_registry.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'scripts/runbook_completion_evidence.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'scripts/runbook_execution_reconciliation_preview.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'scripts/runbook_gate_checker.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'scripts/runbook_stage_b_verifier.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'scripts/runbook_stage_runner.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'scripts/runbook_state.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'scripts/sync_notion_review_status.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'tests/runbook_standard_evidence_fixtures.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'tests/test_paper_daily_plan_generation.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'tests/test_paper_daily_review_scope.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'tests/test_paper_data_freshness.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'tests/test_paper_manual_execution_commit.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'tests/test_paper_prepare_data.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'tests/test_runbook_execution_reconciliation_preview.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'tests/test_runbook_gate_checker.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'tests/test_runbook_stage_b_verifier.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'tests/test_runbook_stage_runner.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'tests/test_runbook_stage_runner_stage_b.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'tests/test_runbook_state.py', LF will be replaced by CRLF the next time Git touches it
~~~~

The nine evidence whitespace matches are the mandatory one-space blank context markers in the two embedded verbatim unified diffs. They are retained so those diffs remain syntactically faithful. Production, test and Result files have zero trailing-whitespace matches.

## End git status --short

Command: `git status --short`

~~~~text
Exit code: 0
Wall time: 1.3 seconds
Output:
 M core/daily_plan_generator.py
 M core/execution_reconciliation.py
 M core/notion_manual_execution_importer.py
 M core/paper_account_paths.py
 M core/paper_config_snapshot.py
 M core/paper_daily_ops_orchestrator.py
 M core/paper_daily_review_scope.py
 M core/paper_data_freshness.py
 M core/paper_manual_execution_commit.py
 M core/paper_manual_review_append_commit.py
 M core/paper_prepare_data.py
 M core/runbook_day_rollover.py
 M core/universe_manager.py
 M docs/operations/paper_daily_cycle_commands.md
 M "idea, PRD, TRD/paper \354\232\264\354\230\201 \352\270\260\353\212\245 \352\260\234\353\260\234 \353\241\234\353\223\234\353\247\265 v1.3.md"
 M outputs/backtest_log.db
 M scripts/import_notion_executions.py
 M scripts/paper.py
 M scripts/run_paper_daily_plan.py
 M scripts/runbook_command_registry.py
 M scripts/runbook_completion_evidence.py
 M scripts/runbook_execution_reconciliation_preview.py
 M scripts/runbook_gate_checker.py
 M scripts/runbook_stage_b_verifier.py
 M scripts/runbook_stage_runner.py
 M scripts/runbook_state.py
 M scripts/sync_notion_review_status.py
 M tests/runbook_standard_evidence_fixtures.py
 M tests/test_paper_daily_plan_generation.py
 M tests/test_paper_daily_review_scope.py
 M tests/test_paper_data_freshness.py
 M tests/test_paper_manual_execution_commit.py
 M tests/test_paper_prepare_data.py
 M tests/test_runbook_execution_reconciliation_preview.py
 M tests/test_runbook_gate_checker.py
 M tests/test_runbook_stage_b_verifier.py
 M tests/test_runbook_stage_runner.py
 M tests/test_runbook_stage_runner_stage_b.py
 M tests/test_runbook_state.py
?? .tmp/
?? ^
?? _tmp_blocker5_debug_alias/
?? _tmp_pytest/
?? _tmp_pytest_blocker5_gate/
?? _tmp_pytest_blocker5_gate2/
?? _tmp_pytest_blocker5_gate2_retry/
?? _tmp_pytest_blocker5_gates/
?? _tmp_pytest_blocker5_notion/
?? _tmp_pytest_blocker5_notion_abs/
?? _tmp_pytest_blocker5_review_prep/
?? _tmp_pytest_blocker5_review_prep_final/
?? _tmp_pytest_blocker5_review_prep_retry/
?? _tmp_pytest_blocker5_scope/
?? _tmp_pytest_blocker5_stage_d/
?? _tmp_pytest_daily_ops_status_fix/
?? _tmp_pytest_gate/
?? _tmp_pytest_import_exec/
?? _tmp_pytest_recon/
?? _tmp_pytest_recon_preview/
?? _tmp_pytest_review_prep/
?? _tmp_pytest_stage_b/
?? _tmp_pytest_stage_b_verify/
?? _tmp_pytest_stage_d_after_e_fix/
?? _tmp_pytest_stage_e_fix/
?? _tmp_pytest_stage_runner/
?? _tmp_pytest_state/
?? _tmp_pytest_state_after_e_fix/
?? _tmp_pytest_sync_status/
?? _tmp_r4_char_postcommit/
?? _tmp_test_artifacts/
?? analysis_results/market_regime_timeline.png
?? backtest_log.db
?? core/execution_outcome_flow.py
?? core/runbook_recovery.py
?? core/stage_a_asof_contract.py
?? "docs/00. \355\210\254\354\236\220 \354\213\234\354\212\244\355\205\234 \352\270\260\353\212\245 \353\262\244\354\271\230\353\247\210\355\201\254 \353\260\217 \352\260\234\353\260\234 \354\232\260\354\204\240\354\210\234\354\234\204 \355\217\211\352\260\200 \352\270\260\354\244\200\354\204\234.md"
?? docs/operations/runbook_recovery_contract.md
?? docs/work_results/
?? docs_chatGPT_work/
?? docs_n8n/
?? "idea, PRD, TRD/mfu-doo1_daily ops orchestrator stage inventory, gate policy \354\204\244\352\263\204.md"
?? "idea, PRD, TRD/mfu-oper1_account aware daily plan post fix smoke.md"
?? "idea, PRD, TRD/mfu-oper1_account aware daily plan state loading.md"
?? "idea, PRD, TRD/mfu-oper1~5_closeout.md"
?? "idea, PRD, TRD/mfu-oper2_account aware daily plan notion export.md"
?? "idea, PRD, TRD/mfu-oper3_account aware manual execution preview.md"
?? "idea, PRD, TRD/mfu-oper4_account aware manual review template notion export.md"
?? "idea, PRD, TRD/mfu-oper5_fix review progress status from manual review log.md"
?? "idea, PRD, TRD/mfu-oper6-1_market date semantics audit, KST operatin window design.md"
?? "idea, PRD, TRD/mfu-oper6-2_explicit data date, trade date daily plan.md"
?? "idea, PRD, TRD/mfu-oper6-2a_align universe freshness with quarterly policy.md"
?? "idea, PRD, TRD/mfu-oper6~8_closeout.md"
?? "idea, PRD, TRD/mfu-oper7_daily plan to manual execution template export.md"
?? "idea, PRD, TRD/mfu-oper8a_review date, trade date awareness.md"
?? "idea, PRD, TRD/mfu-oper8b_manual review question simplification.md"
?? "idea, PRD, TRD/mfu-oper8c-1_manual review optional note and tag mapping.md"
?? "idea, PRD, TRD/mfu-oper9-10_notion env loading alignment.md"
?? "idea, PRD, TRD/mfu-oper9-11_operational path consistency audit after env alignment.md"
?? "idea, PRD, TRD/mfu-oper9-12_notion manual execution review schema validation.md"
?? "idea, PRD, TRD/mfu-oper9-13_manual execution state reconciliation hardening.md"
?? "idea, PRD, TRD/mfu-oper9-14_manual review wait state reconciliation hardening.md"
?? "idea, PRD, TRD/mfu-oper9-15_manual review post commit status sunc reconcliation fix.md"
?? "idea, PRD, TRD/mfu-oper9-16_date scoped review artifact guard.md"
?? "idea, PRD, TRD/mfu-oper9-18_no action day daily review completion guard.md"
?? "idea, PRD, TRD/mfu-oper9-19a_eod preflight account scope alignment.md"
?? "idea, PRD, TRD/mfu-oper9-19b_no action day eod roll forward and final closure.md"
?? "idea, PRD, TRD/mfu-oper9-1_daily ops orchestrator inventory design.md"
?? "idea, PRD, TRD/mfu-oper9-20a_orchestrator decision criterria audit.md"
?? "idea, PRD, TRD/mfu-oper9-20b_orchestrator decision criteria delta analysis.md"
?? "idea, PRD, TRD/mfu-oper9-20c_execution candidate schema alignment.md"
?? "idea, PRD, TRD/mfu-oper9-20d-a_eod duplicate append, idempotency investiagion.md"
?? "idea, PRD, TRD/mfu-oper9-20d-b_eod accounting close role hardening.md"
?? "idea, PRD, TRD/mfu-oper9-2_daily ops orchestrator local mvp.md"
?? "idea, PRD, TRD/mfu-oper9-3_daily ops orchestrator contract hardening.md"
?? "idea, PRD, TRD/mfu-oper9-4 daily ops orchestrator evidence contract.md"
?? "idea, PRD, TRD/mfu-oper9-4a_evidence filename date format alignment.md"
?? "idea, PRD, TRD/mfu-oper9-5_notion live read status verification.md"
?? "idea, PRD, TRD/mfu-oper9-6_local notion reconciliation matrix.md"
?? "idea, PRD, TRD/mfu-oper9-7_operator summary json contract.md"
?? "idea, PRD, TRD/mfu-oper9-8 orchestrator step advancement fix.md"
?? "idea, PRD, TRD/mfu-oper9-9_orchestrator stage advancement matrix audit.md"
?? "idea, PRD, TRD/mfu-oper9-post15_closeout.md"
?? "idea, PRD, TRD/mfu-oper9_closeout.md"
?? "idea, PRD, TRD/mfu-oper9_final closeout after smoke hardening.md"
?? "idea, PRD, TRD/mfu-roadmap-v1.3 \354\236\221\354\227\205 \354\247\200\354\213\234\353\254\270.md"
?? "idea, PRD, TRD/mfu-ui1_notion view spec from actual mapping.md"
?? "idea, PRD, TRD/paper \354\232\264\354\230\201 \352\270\260\353\212\245 \352\260\234\353\260\234 \353\241\234\353\223\234\353\247\265 v1.4.md"
?? scripts/runbook_recovery.py
?? tests/test_execution_outcome_derivation.py
?? tests/test_execution_outcome_flow.py
?? tests/test_mfu_eo2_zerocount_standard_downstream.py
?? tests/test_runbook_recovery.py
?? tests/test_stage_a_asof_contract.py
warning: could not open directory 'tmpvt37771o/': Permission denied
warning: could not open directory '_tmp_pytest_gate2_after_append/': Permission denied
warning: could not open directory '_tmp_pytest_gate2_after_d_preview/': Permission denied
warning: could not open directory '_tmp_pytest_gate2_final/': Permission denied
warning: could not open directory '_tmp_pytest_gate2_new/': Permission denied
warning: could not open directory '_tmp_pytest_gate2_new2/': Permission denied
warning: could not open directory '_tmp_pytest_gate_checker_final/': Permission denied
warning: could not open directory '_tmp_pytest_gate_checker_new/': Permission denied
warning: could not open directory '_tmp_pytest_gate_checker_new2/': Permission denied
warning: could not open directory '_tmp_pytest_paper_cli_scope_stage_e/': Permission denied
warning: could not open directory '_tmp_pytest_result_after_e/': Permission denied
warning: could not open directory '_tmp_pytest_review_prep_norm/': Permission denied
warning: could not open directory '_tmp_pytest_review_status_sync_after_append/': Permission denied
warning: could not open directory '_tmp_pytest_stage_b_after_e/': Permission denied
warning: could not open directory '_tmp_pytest_stage_b_gate2/': Permission denied
warning: could not open directory '_tmp_pytest_stage_b_gate2_final/': Permission denied
warning: could not open directory '_tmp_pytest_stage_b_new/': Permission denied
warning: could not open directory '_tmp_pytest_stage_b_norm/': Permission denied
warning: could not open directory '_tmp_pytest_stage_b_verify_norm/': Permission denied
warning: could not open directory '_tmp_pytest_stage_c_after_d_preview/': Permission denied
warning: could not open directory '_tmp_pytest_stage_c_gate2/': Permission denied
warning: could not open directory '_tmp_pytest_stage_c_gate2_final/': Permission denied
warning: could not open directory '_tmp_pytest_stage_c_new/': Permission denied
warning: could not open directory '_tmp_pytest_stage_d_append/': Permission denied
warning: could not open directory '_tmp_pytest_stage_d_append_after_e/': Permission denied
warning: could not open directory '_tmp_pytest_stage_d_preview/': Permission denied
warning: could not open directory '_tmp_pytest_stage_d_preview_after_append/': Permission denied
warning: could not open directory '_tmp_pytest_stage_d_preview_final/': Permission denied
warning: could not open directory '_tmp_pytest_stage_e/': Permission denied
warning: could not open directory '_tmp_pytest_stage_runner_after_e/': Permission denied
warning: could not open directory '_tmp_pytest_state_after_append/': Permission denied
warning: could not open directory '_tmp_pytest_state_after_d_preview/': Permission denied
warning: could not open directory '_tmp_pytest_state_after_e/': Permission denied
warning: could not open directory '_tmp_pytest_state_gate2/': Permission denied
warning: could not open directory '_tmp_pytest_state_gate2_final/': Permission denied
warning: could not open directory '_tmp_pytest_state_new/': Permission denied
warning: could not open directory '_tmp_pytest_state_norm/': Permission denied
~~~~

The end status preserves the cumulative pre-existing worktree. CONTRACT1A added no git index, commit, branch or remote mutation.
