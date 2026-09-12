# MFU-SV2-3 Review Evidence

Status: `PENDING_CHATGPT_REVIEW`

- `import_notion_executions.py` reads `runbook_state.execution_contract.version` before preview creation and passes it explicitly.
- `_stateful_validation_candidates()` activates sequence ordering only for `execution_reconciliation_preview.v3`.
- Existing v3 SELL→BUY / BUY→SELL cash ordering regression is invoked with an explicit v3 contract.
- Stage B SV1 effective candidate gate regression suite passes; identity builders were untouched.
