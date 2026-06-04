# PAPER20-3 Controlled Baseline Capture and Replay Smoke

## Purpose

PAPER20-3 attempted to perform a controlled baseline capture for `paper_sandbox / 2026-05-26` and then run the PAPER19 replay wrapper operational smoke.

The intended controlled smoke definition is:

```text
This is not historical actual-operation verification.
This is controlled operational smoke based on current code, current database, and current configuration.
```

Korean definition:

```text
이번 smoke는 과거 2026-05-26 당시 실제 운영 결과의 재현성 검증이 아니다.
현재 코드/현재 DB/현재 config 기준으로 baseline capture와 replay wrapper가 정상 연결되는지 확인하는 controlled smoke다.
```

Actual PAPER20-3 outcome:

```text
controlled baseline capture was not executed
replay wrapper smoke was not executed
blocker was documented
```

## Historical Verification Boundary

This MFU does not claim historical actual-operation verification.

Even if the controlled capture had run, it would have represented current code/current DB/current config behavior for `2026-05-26`, not the real state of the system as it existed on that historical date.

The operational meaning is limited to connection readiness:

- can a Daily Plan baseline sidecar be captured safely?
- can the replay wrapper consume that baseline sidecar?
- can a regenerated sidecar and replay diff report be produced safely?

It does not validate trading correctness for 2026-05-26.

## Controlled Baseline Capture

Preflight command results:

```cmd
python scripts\run_paper_daily_plan.py --help
```

Observed CLI support:

```text
usage: run_paper_daily_plan.py [-h] --date DATE

options:
  --date DATE
```

The CLI does not support:

- `--account-id`
- `--output-dir`
- explicit output path
- controlled baseline capture directory

Blocker:

```text
controlled output-dir or controlled output path is not available through the Daily Plan CLI
```

Decision:

```text
Do not run Daily Plan generation.
```

Reason:

- running `scripts/run_paper_daily_plan.py --date 2026-05-26` would use official/default output paths
- official artifact overwrite risk cannot be ruled out
- the task explicitly requires stopping if controlled output cannot be guaranteed

## Baseline Sidecar Eligibility

Baseline sidecar was not created.

Expected controlled baseline sidecar path was:

```text
outputs/tmp_paper20_baseline_capture/daily_action_plan_20260526.json
```

Eligibility result:

```text
eligible_baseline_sidecar = false
```

Fields not available because capture was blocked:

- `schema_version = paper_daily_plan.v1`
- `account_id = paper_sandbox`
- `plan_date = 2026-05-26`
- `items[]`
- `fingerprints`
- `generator_version`
- `config_snapshot_path`
- `config_hash`
- `config_hash_policy`
- `state_snapshot_path`

## Replay Wrapper Smoke

Replay wrapper CLI help passed:

```cmd
python scripts\dev\replay_daily_plan_diff.py --help
```

Pure diff CLI help passed:

```cmd
python scripts\dev\diff_daily_plan.py --help
```

Replay wrapper smoke was not executed.

Reason:

```text
No eligible controlled baseline sidecar exists.
```

The intended smoke command remains a draft only:

```cmd
python scripts\dev\replay_daily_plan_diff.py --account-id paper_sandbox --date 2026-05-26 --baseline-plan outputs\tmp_paper20_baseline_capture\daily_action_plan_20260526.json --output-dir outputs\tmp_paper20_replay_smoke --json
```

## Output Directory Policy

Required controlled directories:

```text
outputs/tmp_paper20_baseline_capture/
outputs/tmp_paper20_replay_smoke/
```

PAPER20-3 did not create these directories or artifacts.

Future controlled smoke must keep this policy:

- baseline capture artifacts only under `outputs/tmp_paper20_baseline_capture/`
- replay smoke artifacts only under `outputs/tmp_paper20_replay_smoke/`
- no generated artifacts staged or committed by default
- no official artifact overwrite
- no baseline artifact overwrite

## PASS / WARNING / FAIL Result

No replay result exists because no smoke was executed.

Interpretation for future controlled smoke:

`PASS`:

- compared Daily Plan fields match
- controlled replay smoke chain works
- actual/export/sync approval is not implied

`PASS_WITH_METADATA_DIFF`:

- differences are limited to metadata such as `generated_at`, `run_id`, or paths
- generally not an operational blocker by itself

`WARNING`:

- price, warning, reason, note, fingerprint, or `config_hash` differs
- cause candidate exists, but root cause is not confirmed
- follow-up review required

`FAIL`:

- baseline missing or malformed
- account/date mismatch
- symbol/action/quantity differs
- replay wrapper execution failure

Current PAPER20-3 status:

```text
BLOCKED_BEFORE_CAPTURE
```

## Safety Marker Verification

No wrapper summary exists because the wrapper was not executed.

Safety verification from executed steps:

- Daily Plan baseline capture was not executed
- replay wrapper smoke was not executed
- Notion API was not called
- Notion write/export/sync was not executed
- actual export was not executed
- Manual Execution commit was not executed
- Manual Review append was not executed
- source-of-truth ledger commit/append was not executed
- account/position/current_state ledger was not modified
- generated artifacts were not created or staged

## Operating Loop Readiness Checklist

Daily Plan:

- controlled Daily Plan generation: blocked
- Markdown generation: not executed
- JSON sidecar generation: not executed
- config snapshot generation: not executed
- current_state reference: not exercised in PAPER20-3

Replay:

- replay wrapper CLI availability: confirmed through `--help`
- regenerated sidecar generation: not executed
- diff report generation: not executed
- safety marker verification: not available because wrapper did not run

Notion:

- Notion export/sync not executed
- Manual Execution/Review sync not executed
- future Notion UI or export checks remain out of scope

Ledger:

- commit/append not executed
- account/position/current_state ledger not modified

Market Data:

- 2026-05-20 이후 market data update를 하지 않았다는 한계가 유지된다.
- Therefore, any future 2026-05-26 plan generated without freshness updates must be treated as operational smoke, not trading correctness validation.

## Market Data Limitation

The controlled smoke target date is `2026-05-26`, but market data freshness has not been advanced as part of this MFU.

Therefore:

- a future generated `2026-05-26` Daily Plan is not proof of correct historical trading decisions
- stale or incomplete market data may affect the generated plan
- this remains a wrapper/connectivity smoke, not a trading validity test

## Generated Artifact Policy

No generated artifacts were created in PAPER20-3.

If future controlled capture or replay smoke creates artifacts under:

```text
outputs/tmp_paper20_baseline_capture/
outputs/tmp_paper20_replay_smoke/
```

they must not be staged or committed unless explicitly approved.

## Non-scope

This MFU did not perform:

- historical actual-operation verification
- Markdown-to-JSON reverse generation
- Notion API calls
- Notion write/export/sync
- actual export
- Manual Execution commit
- Manual Review append
- source-of-truth ledger commit/append
- account/position/current_state ledger modification
- generated artifact commit
- stable `plan_item_id`
- `universe_hash`
- `market_data_asof`
- `indicator_snapshot_hash`
- `state_snapshot_hash`

## PAPER20-4 Recommendation

Recommended next MFU:

```text
PAPER20-4 Controlled Daily Plan Capture Interface
```

Goal:

- add or approve a controlled capture path for Daily Plan generation
- support `paper_sandbox`, explicit date, and explicit output directory/path
- preserve official artifacts
- keep Notion/export/sync/ledger mutation out of scope
- then rerun PAPER20 controlled baseline capture and replay smoke

Candidate implementation directions:

- add explicit `--account-id` and `--output-dir` or `--output-path` support to `scripts/run_paper_daily_plan.py`
- or add a dedicated dev-only controlled capture CLI that calls `generate_daily_plan()` with explicit paths
- require generated artifacts to stay under `outputs/tmp_paper20_baseline_capture/`
