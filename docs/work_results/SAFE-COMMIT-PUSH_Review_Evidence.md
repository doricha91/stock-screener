# Summary

이 문서는 혼합 worktree에서 commit 대상을 실제 content로 선별한 근거다. pre-commit 기준 branch와 remote가 일치하고, staged 집합에는 source/test/docs만 있으며 generated DB, runtime evidence, secret 또는 unrelated dirty 파일이 없다.

# Baseline

- Branch: `gemini_cli_update`
- Pre-commit HEAD: `e17978f332a8853588f287cf5aa2a5ef9bd57c74`
- Upstream: `origin/gemini_cli_update`
- Remote: `https://github.com/doricha91/stock-screener.git`
- Fetch 후 divergence: local-only 0, remote-only 0
- Initial `git status --short`: 134개 항목
- Initial tracked diff: 15개 파일, 그중 protected DB 1개

# Classification evidence

## A. COMMIT

각 source 변경은 함께 staged한 focused test 및 완료 결과 문서와 대응한다.

| Workstream | Source/docs | Regression evidence |
| --- | --- | --- |
| Recovery restart/lifecycle | `core/runbook_recovery.py`, `core/runbook_day_rollover.py`, recovery contract | `test_runbook_recovery.py`, `test_runbook_day_rollover.py` |
| OPS-UX-1 | Gate1 checker와 detailed wrapper | Gate checker 및 wrapper tests |
| OPS-UX-2/2.1 | primary flow, daily wrapper 5개, Quick Start | primary flow 및 wrapper tests |
| OPS-UX-2.2 | Notion exporter semantic count | exporter 및 CLI tests |

## B. GENERATED / OPERATIONAL — EXCLUDE

- tracked `outputs/backtest_log.db`는 binary generated DB이므로 unstaged 유지했다.
- untracked 루트 `backtest_log.db`는 0-byte generated DB로 제외했다.
- `^` 파일의 내용을 읽어 `stage_b_recovery_assessment.v1` runtime evidence임을 확인하고 제외했다.
- `.tmp/`, `_tmp_*/`, PNG와 테스트/운영 산출물은 모두 제외했다.

## C. RECOVERY / EVIDENCE — PRESERVE, EXCLUDE

운영 Recovery authorization, state/evidence, command result와 artifact는 삭제·수정·stage하지 않았다. 이번 commit의 Recovery 파일은 runtime sidecar가 아니라 validator/lifecycle source code, tests, contract 및 개발 review 문서다.

## D. UNRELATED DIRTY — PRESERVE, EXCLUDE

기존 roadmap SHA 변경, n8n/EOD 문서 hunk, 다른 MFU 결과/설계 문서와 `docs_chatGPT_work`, `docs_n8n`은 현재 네 workstream과 분리해 unstaged/untracked로 보존했다.

# Partial staging evidence

`docs/operations/paper_daily_cycle_commands.md`에는 네 개의 tracked hunk가 있었다.

- 제외: n8n/Telegram 운영 원칙
- 포함: 5-wrapper Quick Start 및 stop/retry 경계
- 포함: 상세 흐름을 Advanced/Manual Recovery로 구분하는 heading
- 제외: EOD accounting-close 기준

따라서 working tree의 unrelated 문서 변경은 보존하면서 commit에는 OPS-UX 문서 변경만 포함된다.

# Staged safety review

- DB/binary: 없음
- generated runtime artifact: 없음
- Recovery sidecar/state: 없음
- secret/token/credential: 없음
- source의 accidental absolute local path: 없음
- temporary debug print: 없음; CLI의 의도된 JSON/operator summary 출력만 존재
- force/rebase/merge/reset/checkout/restore/clean/stash: 사용하지 않음
- protected DB touched: NO

# Validation evidence

Compile command:

`python -m py_compile core/notion_exporters.py scripts/runbook_primary_flow.py scripts/runbook_stage_runner.py scripts/export_paper_to_notion.py core/runbook_day_rollover.py core/runbook_recovery.py scripts/runbook_gate_checker.py`

Result: PASS

Focused regression command:

`python -m pytest tests/test_notion_exporters.py tests/test_export_paper_to_notion_cli.py tests/test_export_paper_to_notion_daily_ops_status_cli.py tests/test_runbook_primary_flow.py tests/test_runbook_gate_checker.py tests/test_runbook_recovery.py tests/test_runbook_stage_wrappers.py tests/test_runbook_day_rollover.py -q`

Result: `274 passed in 55.97s`

Additional checks:

- `git diff --check`: PASS
- `git diff --cached --check`: PASS
- cached secret keyword scan: no actual secret values found
- remote divergence after `git fetch origin`: `0 0`

# Acceptance checklist before commit

- AC-1 branch `gemini_cli_update`: PASS
- AC-2 source/test/docs only: PASS
- AC-3 generated operational artifacts excluded: PASS
- AC-4 Recovery runtime evidence preserved/excluded: PASS
- AC-5 protected DB excluded: PASS
- AC-6 unrelated dirty preserved: PASS
- AC-7 relevant tests: PASS
- AC-8 cached diff check: PASS
- AC-9 remote divergence absent: PASS
- AC-13 force push prohibited: preserved
- AC-14 destructive Git commands prohibited: preserved

Commit SHA와 push 이후 local/remote equality는 Git이 commit을 생성한 뒤 최종 handoff에서 기록한다.
