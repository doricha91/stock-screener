## Purpose

PAPER15-3E-4A applies account-aware preview filtering and canonical key namespacing to the Notion Manual Execution / Manual Review importer layer.

## Scope / Non-scope

In scope:
- `--account-id` on preview/import CLI entrypoints
- Account ID filter in READY-row preview queries
- account-aware preview canonical keys
- preview JSON / Markdown account metadata
- non-default commit / append blocking in CLI

Out of scope:
- account-aware commit / append implementation
- status sync changes
- Notion row migration
- writer path changes

## Account Filter Policy

Manual Execution / Manual Review preview queries follow this rule:

- `paper_default`
  - allow `Account ID == paper_default`
  - allow blank `Account ID`
- non-default account
  - require `Account ID == {account_id}`

This preserves legacy `paper_default` compatibility while preventing READY rows from other accounts from leaking into preview batches.

## Canonical Key Namespace

Preview candidates now use account-aware canonical keys:

- `manual_execution:{account_id}:{execution_date}:{symbol}:{side}:{sequence}`
- `manual_review:{account_id}:{review_date}:{symbol}:{question_id}`

For `paper_default`, preview payloads also expose the legacy account-less key for compatibility tracking.

## Commit / Append Guard

Non-default commit / append remains blocked in this MFU because:

- writer path is still legacy single-account
- status sync is still account-less
- allowing non-default commit would risk ledger contamination

`paper_default` legacy commit compatibility remains unchanged.

## Next Step

Recommended follow-up:

- account-aware commit / append path wiring
- account-aware status sync namespace
