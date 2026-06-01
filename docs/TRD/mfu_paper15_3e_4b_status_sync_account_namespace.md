## Purpose

PAPER15-3E-4B aligns Manual Execution / Manual Review status sync with the account-aware preview namespace introduced in PAPER15-3E-4A.

## Scope / Non-scope

In scope:
- `--account-id` on status sync CLI
- `Account ID` property in status back-write payload
- account-aware `External Key` handling
- legacy `paper_default` canonical key compatibility
- dry-run summary/account metadata updates

Out of scope:
- commit / append implementation changes
- writer path changes
- Notion row migration
- bulk legacy rewrite

## Status Sync Policy

- CLI `--account-id` defaults to `paper_default`
- commit report `account_id` is compared to CLI `account_id`
- missing report `account_id` is interpreted as `paper_default`
- mismatch fails before sync proceeds

## Canonical Key Handling

Execution:
- `manual_execution:{account_id}:{execution_date}:{symbol}:{side}:{sequence}`

Review:
- `manual_review:{account_id}:{review_date}:{symbol}:{question_id}`

Legacy behavior:
- `paper_default` legacy canonical keys are upgraded to account-aware keys for `External Key` write
- non-default legacy-only canonical keys are rejected

## Property Payload

Status sync now writes:

- `External Key`
- `Account ID`
- `Validation Status`
- `Validation Message`
- `Import Status`
- `Imported At`
- `Synced At`

User-entered fields remain untouched.

## Next Step

Recommended follow-up:

- account-aware commit / append sidecar report production
- account-aware writer path implementation
