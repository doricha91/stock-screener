# MFU-SV2-2 Review Evidence

Status: `PENDING_CHATGPT_REVIEW`

| Requirement | Evidence |
| --- | --- |
| Preview stateful order uses v3 sequence | `_stateful_validation_candidates()` selects trade-bearing candidates and sorts sequence-bearing input. |
| SELL then BUY is accepted; BUY then SELL blocks intermediate cash | `test_preview_uses_v3_execution_sequence_for_stateful_cash_validation`. |
| v3 is an outcome preview at Stage B gate | `_validate_execution_preview_payload()` accepts both `EXECUTION_CONTRACT_V2` and `EXECUTION_CONTRACT_V3`. |
| SV1 gate and writer ordering remain | Stage B and outcome/writer targeted suites; no change to identity builders. |
| v1/v2 preview semantics remain | No-sequence preview stream keeps existing candidate order. |
