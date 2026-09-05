# Summary

분류 결과는 Case A다. 실제 2026-09-01 canonical JSON에는 실행 후보와 경고가 없지만, Markdown의 “없음” 안내 행에 Note/Reason 텍스트가 있어 raw table row counter가 각각 1을 반환했다. 수정 후 canonical/semantic count는 0/10/0이며 날짜 지정 dry-run도 정확한 2026-09-01 key를 선택한다.

# Baseline

- Branch: `gemini_cli_update`
- HEAD: `e17978f332a8853588f287cf5aa2a5ef9bd57c74`
- Task: `D:\python\StockScreener\docs_chatGPT_work\Ops-Ux2.2_daily plan no action notion count fix.md`
- Runbook: `paper_pilot_202606_2026-08-31_2026-09-01`
- Root `AGENTS.md`: 작업 전 전체 확인 및 적용
- 예상하지 못한 blocking change: 없음
- 기존 dirty/untracked 파일과 protected DB: 보존

# Actual artifact evidence

운영 workspace를 읽기 전용으로 탐색해 다음 원본을 확인했다.

- `D:\n8n\workspace\stock_screener_ops\artifacts\paper_pilot_202606_2026-08-31_2026-09-01\stage_a\daily_action_plan_20260901.json`
- `D:\n8n\workspace\stock_screener_ops\artifacts\paper_pilot_202606_2026-08-31_2026-09-01\stage_a\daily_action_plan_20260901.md`
- exporter account source:
  - `D:\python\StockScreener\outputs\paper_accounts\paper_pilot_202606\daily_action_plan_20260901.json`
  - `D:\python\StockScreener\outputs\paper_accounts\paper_pilot_202606\daily_action_plan_20260901.md`
  - `D:\python\StockScreener\outputs\paper_accounts\paper_pilot_202606\config_snapshots\paper_config_snapshot_20260901.json`

Canonical JSON 값:

| Field | Value |
| --- | --- |
| `action_mode` | `NO_ACTION` |
| `execution_required` | `false` |
| `candidate_execution_count` | `0` |
| `no_action_reason` | `no_executable_orders` |
| `items` | `[]` |

Markdown 원문 의미:

- Confirmed Trades: `| - | - | - | - | 오늘 실행할 확정 매매 없음 |`
- Warnings: `| - | - | - | 경고 없음 |`
- Review Items: 실제 `REVIEW_EXIT` 10행
- 별도 structured warning collection: 없음

# Root cause and derivation

기존 call chain:

`export_daily_plan_to_notion` → `summarize_daily_plan_artifacts` → `_count_markdown_table_rows` → `build_daily_plan_properties` → Notion number property

`_count_markdown_table_rows`는 모든 cell이 빈 marker일 때만 행을 제외한다. 두 placeholder 행에는 마지막 설명 cell이 있으므로 Confirmed/Warning 모두 1로 계산됐다. 실제 2026-09-01 원문을 기존 helper에 적용해 다음을 재현했다.

| Property | 기존 값 | 원인 |
| --- | ---: | --- |
| Confirmed Trade Count | 1 | “확정 매매 없음” 표시 행 포함 |
| Warning Count | 1 | “경고 없음” 표시 행 포함 |
| Review Item Count | 10 | 실제 review 행 10개; 정상 |

Notion export result의 `source_path`는 config snapshot이지만 summary 생성 시 같은 날짜의 Markdown을 함께 읽는다. 기존 구현은 인접 canonical Daily Plan JSON을 count SSOT로 사용하지 않았다.

# SSOT decision

- Confirmed Trade Count:
  1. 인접 Daily Plan JSON에 최신 `execution_intent`가 있으면 기존 validator로 전체 contract와 날짜를 검증한다.
  2. 검증된 `candidate_execution_count`를 사용한다.
  3. 최신 contract가 없는 legacy artifact는 confirmed 의미 필드 기반 Markdown fallback을 사용한다.
- Warning Count:
  - 현재 actual artifact에 structured warning list/count가 없으므로 Symbol/Severity/Reason 의미 필드 기반 fallback을 사용한다.
- Review Item Count:
  - 별도 기존 계약을 그대로 유지한다.

명시된 최신 execution intent가 잘못된 경우에는 Markdown으로 조용히 우회하지 않고 fail-closed 한다. execution intent field 자체가 없는 legacy JSON만 호환 fallback 대상이다.

# Secondary validation blocker

필수 실제 fixture dry-run에서 `scripts/export_paper_to_notion.py`는 `--date`를 정상 전달했지만 `export_selected_paper_reports_to_notion`이 `daily_plan_date`를 weekly 함수에 잘못 넘기고 daily 함수에는 누락하고 있었다. 이 때문에 최초 dry-run이 최신 2026-09-02를 선택했다. 동일 exporter orchestration에서 인자 위치만 최소 수정했고, weekly+daily 동시 선택 회귀 테스트로 날짜가 daily target에만 전달됨을 고정했다.

# Acceptance evidence

수정 후 실제 2026-09-01 summary:

| Field | Value |
| --- | ---: |
| Confirmed Trade Count | 0 |
| Review Item Count | 10 |
| Warning Count | 0 |
| Confirmed placeholder body items | 0 |
| Warning placeholder body items | 0 |

공식 dry-run 결과:

- action: `dry_run`
- external key: `daily_plan:paper_pilot_202606:2026-09-01`
- source: `outputs\paper_accounts\paper_pilot_202606\config_snapshots\paper_config_snapshot_20260901.json`
- failed count: 0
- Notion write: 0건

# Historical impact audit

`outputs/paper_test`와 `outputs/paper_accounts/*`의 config snapshot이 존재하는 Daily Plan 22건을 읽기 전용 비교했다.

- 처리 성공: 22
- 오류: 0
- 기존 raw count와 달라지는 unique artifact: 10
- Confirmed 차이: 5
- Warning 차이: 6
- 두 count가 함께 달라지는 중복: 1

영향 후보:

- `outputs\paper_test\daily_action_plan_20260520.md`
- `outputs\paper_accounts\paper_orch_smoke_202606\daily_action_plan_20260608.md`
- `outputs\paper_accounts\paper_orch_smoke_202606\daily_action_plan_20260609.md`
- `outputs\paper_accounts\paper_pilot_202606\daily_action_plan_20260605.md`
- `outputs\paper_accounts\paper_pilot_202606\daily_action_plan_20260810.md`
- `outputs\paper_accounts\paper_pilot_202606\daily_action_plan_20260811.md`
- `outputs\paper_accounts\paper_pilot_202606\daily_action_plan_20260828.md`
- `outputs\paper_accounts\paper_pilot_202606\daily_action_plan_20260831.md`
- `outputs\paper_accounts\paper_pilot_202606\daily_action_plan_20260901.md`
- `outputs\paper_accounts\paper_sandbox\daily_action_plan_20260520.md`

이는 source artifact 기준 잠재 영향 범위다. 실제 Notion 페이지 조회, 수정, backfill은 수행하지 않았다.

# Test evidence

| Command | Result |
| --- | --- |
| `python -m pytest tests/test_notion_exporters.py -q` | 61 passed |
| `python -m pytest tests/test_export_paper_to_notion_cli.py tests/test_export_paper_to_notion_daily_ops_status_cli.py -q` | 16 passed |
| `python -m py_compile core/notion_exporters.py scripts/export_paper_to_notion.py` | PASS |
| actual 2026-09-01 official dry-run | PASS, correct external key, zero writes |
| historical read-only audit | 22 processed, 0 errors |
| `git diff --check` | PASS; pre-existing CRLF warnings only |

# Preserved boundaries

- DB/schema/data migration 없음
- protected DB 및 generated source artifact 쓰기 없음
- Stage A NO_ACTION, strategy, candidate generation, Stage B/C/D, gate, recovery 변경 없음
- Notion schema/property mapping 변경 없음
- live/broker 실행 없음
- reset/checkout/restore/clean/stash/commit/push 없음
- unrelated dirty/untracked 변경 보존

# Remaining limitations

- warning structured SSOT는 현재 산출물에 없어서 semantic Markdown fallback을 사용한다.
- historical Notion 실제 저장값은 읽지 않았으므로 backfill 필요 여부는 별도 검증 대상이다.
- 전체 repository suite 및 실제 runbook 재실행은 수행하지 않았다.
