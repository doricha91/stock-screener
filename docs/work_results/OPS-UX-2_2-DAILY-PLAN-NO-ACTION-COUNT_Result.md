# Summary

OPS-UX-2.2의 실제 2026-09-01 NO_ACTION Daily Plan을 추적한 결과, Notion exporter가 표시용 Markdown 표의 placeholder 행을 실제 거래 및 경고로 세는 Case A가 원인이었다. `Confirmed Trade Count`는 canonical Daily Plan JSON의 검증된 `execution_intent.candidate_execution_count`를 우선 사용하고, 최신 structured contract가 없는 legacy 산출물은 의미 필드 기반 Markdown 판정으로 fallback하도록 수정했다. `Warning Count`는 structured warning collection이 실제 산출물에 없으므로 의미 필드 기반 Markdown 행만 센다. `Review Item Count` 계약은 변경하지 않았다.

# Changed files

- `core/notion_exporters.py`
  - 최신 Daily Plan JSON의 execution intent를 검증하고 Confirmed Trade Count의 SSOT로 사용한다.
  - confirmed/warning Markdown 행을 표시 문구가 아니라 의미 필드로 판정한다.
  - execution intent가 없는 legacy JSON은 기존 export를 깨지 않고 semantic Markdown fallback을 사용한다.
  - 명시된 최신 execution intent가 모순되면 fail-closed 한다.
  - `daily_plan_date`가 weekly export가 아니라 daily plan export로 전달되도록 바로잡았다.
- `tests/test_notion_exporters.py`
  - NO_ACTION placeholder, invalid canonical sidecar, legacy fallback, 날짜 전달 회귀 테스트를 추가했다.
- `docs/work_results/OPS-UX-2_2-DAILY-PLAN-NO-ACTION-COUNT_Result.md`
- `docs/work_results/OPS-UX-2_2-DAILY-PLAN-NO-ACTION-COUNT_Review_Evidence.md`

# Behavior changes

- 실제 2026-09-01 결과:
  - `Confirmed Trade Count`: 1 → 0
  - `Warning Count`: 1 → 0
  - `Review Item Count`: 10 유지
  - confirmed/warning body에서 placeholder 항목 제거
- 실제 실행 후보가 있는 최신 plan은 검증된 `candidate_execution_count`를 사용한다.
- warning은 `Symbol`, `Severity`, `Reason` 중 의미 값이 하나도 없는 표시용 행을 제외한다.
- confirmed의 legacy fallback은 Type/Symbol/Shares/Ref Price 계열 의미 필드가 모두 비어 있는 행을 제외한다.
- `"경고 없음"` 같은 특정 자연어를 찾아 감소시키는 규칙은 추가하지 않았다.
- `--date 2026-09-01`은 해당 daily plan을 정확히 선택한다.
- Stage A NO_ACTION 결정, execution candidate 생성, 전략, Stage B/C/D, gate, recovery, schema 및 DB 동작은 변경하지 않았다.

# Tests run

- `python -m pytest tests/test_notion_exporters.py -q`: 61 passed
- `python -m pytest tests/test_export_paper_to_notion_cli.py tests/test_export_paper_to_notion_daily_ops_status_cli.py -q`: 16 passed
- `python -m py_compile core/notion_exporters.py scripts/export_paper_to_notion.py`: PASS
- 실제 fixture 공식 dry-run:
  - `python scripts\export_paper_to_notion.py --account-id paper_pilot_202606 --daily-plan --date 2026-09-01 --dry-run --json`
  - `external_key=daily_plan:paper_pilot_202606:2026-09-01`, `action=dry_run`, `failed_count=0`
- 실제 2026-09-01 summarizer 재검증: confirmed 0, review 10, warning 0, placeholder body 0건
- historical read-only audit: 22건 처리, 오류 0건, 기존 raw count와 달라지는 잠재 영향 산출물 10건
- `git diff --check`: PASS; 기존 CRLF 변환 경고만 출력
- `git status --short`: 실행 완료, 기존 dirty/untracked 변경 보존

# Tests not run and why

- 전체 repository pytest suite는 실행하지 않았다. 변경 범위와 직접 연결된 exporter 및 CLI suite 77개를 선택했다.
- 실제 Notion write/update와 과거 페이지 backfill은 실행하지 않았다. dry-run 및 읽기 전용 감사만 작업 범위에 포함했다.
- backtest/optimizer는 전략 및 수치 계산 로직 변경이 없어 실행 대상이 아니다.
- 실제 runbook Stage A~F 재실행은 운영 workspace 상태를 변경하므로 실행하지 않고 기존 2026-09-01 산출물을 fixture로 검증했다.

# Risks and limitations

- Daily Plan JSON에 최신 `execution_intent`가 명시된 경우 그 계약은 엄격 검증된다. 손상되거나 모순된 최신 sidecar는 export를 중단한다.
- 현재 Daily Plan에는 canonical warning collection이 없어 Warning Count는 semantic Markdown fallback이다. 향후 structured warning SSOT가 추가되면 exporter가 이를 우선하도록 별도 변경할 수 있다.
- historical audit에서 10개 산출물이 잠재 영향 대상으로 확인됐지만, 실제 Notion 저장값을 조회하거나 수정하지 않았으므로 모든 해당 페이지가 과거에 잘못 저장됐다고 단정하지 않는다.
- 기존 dirty worktree의 다른 변경 및 protected DB는 건드리지 않았다.

# Suggested next step

이 번들을 검토한 뒤 필요할 경우 별도 승인과 범위를 정해 historical 대상 10건의 실제 Notion 값을 조회하고, 잘못된 페이지만 idempotent backfill하는 작업을 수행한다.
