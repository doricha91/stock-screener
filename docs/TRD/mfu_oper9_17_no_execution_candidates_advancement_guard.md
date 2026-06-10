BEGIN MFU-OPER9-17 NO-EXECUTION-CANDIDATES ADVANCEMENT GUARD

목적

* Daily Plan에 실행 후보가 0개인 날에도 Daily Ops Orchestrator가 같은 Manual Execution Template export 명령을 반복 추천하지 않도록 수정한다.
* 현재 2026-06-09 사이클에서 manual_execution_template export는 candidate_count=0, create/update/failed=0으로 정상 종료됐지만, Orchestrator가 이를 완료/no-op으로 인정하지 못하고 MANUAL_EXECUTION_TEMPLATE을 계속 READY로 추천한다.
* 목표는 “실행 후보 없음”을 정상 no-action 상태로 인식하고 Manual Execution 구간을 안전하게 건너뛰어 DAILY_REVIEW로 진행시키는 것이다.

현재 기준

* 최신 기준 branch: gemini_cli_update
* 최신 remote 확인 필요:
  git ls-remote origin gemini_cli_update
* 문제 재현 계좌/날짜:
  account_id=paper_orch_smoke_202606
  data_date=2026-06-08
  trade_date=2026-06-09

현재 확인된 상태

* DAILY_PLAN=DONE
* DAILY_PLAN_NOTION_EXPORT=DONE
* manual_execution_template export 실행 결과:
  candidate_count=0
  create_count=0
  update_count=0
  failed_count=0
  candidates=[]
* Orchestrator 현재 오판:
  current_step=MANUAL_EXECUTION_TEMPLATE
  next_command=export_paper_to_notion.py --manual-execution-template ...
* 실제 기대:
  current_step=DAILY_REVIEW
  next_command=python scripts\paper.py review --account-id paper_orch_smoke_202606 --date 2026-06-09

원인

* Orchestrator는 Manual Execution Template 완료 여부를 Notion row 존재 또는 local evidence sidecar 중심으로 판단한다.
* 실행 후보가 0개이면 Notion row가 생성되지 않으므로 notion_row_count=0이 정상인데, 이를 “아직 export 필요”로 오판한다.
* Daily Plan JSON의 items를 읽어 실행 후보가 0개인지 판단하는 guard가 부족하다.
* export 결과 candidate_count=0도 durable no-op evidence로 인정되지 않는다.

구현 범위

1. core/paper_daily_ops_orchestrator.py 수정

* Daily Plan JSON에서 실제 Manual Execution export 대상 후보 수를 계산하는 helper 추가.
  예:
  _daily_plan_execution_candidate_count(plan_json_path: Path) -> int | None
* 구체적인 후보 판정 기준은 export_paper_to_notion.py의 manual_execution_template 후보 생성 로직과 최대한 동일하게 맞춘다.
* 단순히 items 길이만 보지 말고 실제 export 대상 action/status/side 조건을 확인한다.
* 확실히 판단하기 어렵다면 conservative하게 None을 반환하고 기존 흐름을 유지한다.

2. no-execution-candidates 상태 정의

* Daily Plan이 DONE이고 실행 후보 count가 0이면:

  * MANUAL_EXECUTION_TEMPLATE = DONE 또는 SKIPPED_NO_CANDIDATES 성격의 DONE
  * MANUAL_EXECUTION_PREVIEW = DONE/SKIPPED_NO_CANDIDATES
  * MANUAL_EXECUTION_COMMIT = DONE/SKIPPED_NO_CANDIDATES
  * MANUAL_EXECUTION_STATUS_SYNC = DONE/SKIPPED_NO_CANDIDATES
  * next_command 반복 추천 금지
  * current_step=DAILY_REVIEW

3. export evidence가 있는 경우도 인정

* reports/manual_execution_template_export_YYYYMMDD.json이 존재하고 candidate_count=0, failed_count=0이면 no-op success로 인정한다.
* 단, 해당 evidence의 account_id/date가 현재 account_id/trade_date와 일치해야 한다.
* evidence 파일명은 YYYYMMDD compact 형식을 유지한다.
* evidence가 없다면 Daily Plan JSON 기반 후보 count로 no-op을 판단한다.

4. reconciliation 보강

* Notion row_count=0이어도 Daily Plan 후보가 0개이면 conflict/UNKNOWN으로 보지 않는다.
* rule 예:
  OPER9_17_EXEC_TEMPLATE_NO_CANDIDATES
  OPER9_17_EXEC_PREVIEW_SKIPPED_NO_CANDIDATES
* operator_summary에는 반복 export가 아니라 DAILY_REVIEW를 추천해야 한다.

5. JSON contract additive 유지
   필요 시 stage에 아래 필드 추가:

* no_execution_candidates: true/false
* execution_candidate_count
* no_action_reason
* plan_candidate_source: daily_plan_json / export_evidence / unknown

기존 필드 제거 금지.

명시적 제외 범위

* n8n workflow 생성 금지
* Notion write/export/sync 실행 금지
* import_notion_* --commit 실행 금지
* broker/API/order 실행 금지
* ledger/DB mutation 금지
* Daily Plan 생성 로직 변경 금지
* export_paper_to_notion.py 후보 생성 로직 변경은 원칙적으로 금지. 단, candidate_count=0 evidence 저장 누락이 확인되면 문서화만 하고 별도 작업으로 분리.
* generated outputs commit 금지
* .env/config secret 수정 금지

테스트 요구사항

1. no execution candidates from Daily Plan

* Daily Plan JSON에 실행 후보가 0개인 fixtures 생성.
* 기대:

  * MANUAL_EXECUTION_TEMPLATE이 반복 추천되지 않음
  * MANUAL_EXECUTION_PREVIEW/COMMIT/STATUS_SYNC가 BLOCKED로 남아 전체 진행을 막지 않음
  * operator_summary.current_step=DAILY_REVIEW
  * next_command=paper.py review ...
  * has_reconciliation_conflicts=false

2. no-op export evidence

* manual_execution_template_export_YYYYMMDD.json에 candidate_count=0, failed_count=0이 있으면 no-op success로 인정.
* account_id/date mismatch evidence는 인정하지 않음.

3. real candidates still require template/export/input

* Daily Plan에 실행 후보가 1개 이상이면 기존 흐름 유지:

  * MANUAL_EXECUTION_TEMPLATE 또는 WAIT_FOR_INPUT/preview 흐름이 깨지면 안 됨.

4. stale review artifact guard 유지

* OPER9-16에서 추가한 stale review artifact 테스트 유지.
* 2026-06-08 review artifact가 남아 있어도 2026-06-09 DAILY_REVIEW DONE으로 오판하지 않아야 함.

5. 기존 회귀 유지

* OPER9-13 Manual Execution DRAFT wait/post-sync tests 유지
* OPER9-14 Manual Review wait/preview/append tests 유지
* OPER9-15 terminal/status-sync tests 유지

검증 명령
Windows CMD 기준:

git log --oneline --decorate -n 10
git rev-parse HEAD
git ls-remote origin gemini_cli_update

python scripts\paper_daily_ops.py status --help

python scripts\paper_daily_ops.py status --account-id paper_orch_smoke_202606 --data-date 2026-06-08 --trade-date 2026-06-09 --json --include-notion-read > outputs\orch_status.json

python -c "import json; p=json.load(open(r'outputs\orch_status.json',encoding='utf-8')); print(json.dumps(p.get('operator_summary'),ensure_ascii=False,indent=2))"

python -c "import json; p=json.load(open(r'outputs\orch_status.json',encoding='utf-8')); names=['DAILY_PLAN','DAILY_PLAN_NOTION_EXPORT','MANUAL_EXECUTION_TEMPLATE','MANUAL_EXECUTION_PREVIEW','MANUAL_EXECUTION_COMMIT','MANUAL_EXECUTION_STATUS_SYNC','DAILY_REVIEW']; [print(json.dumps(next(s for s in p['stages'] if s['stage_name']==n),ensure_ascii=False,indent=2)) for n in names]"

python -m pytest tests\test_paper_daily_ops_orchestrator.py tests\test_paper_daily_ops_orchestrator_guard.py tests\test_paper_daily_plan_generation.py -q

git diff --check
git diff --cached --check
git status --short

중요: OPER9-16 결과보고에서 “예상 smoke 결과”로 보고된 점이 부족했다. 이번에는 반드시 실제 smoke 명령 결과를 보고에 포함한다.
중요: commit SHA 오기 방지를 위해 git rev-parse HEAD와 git ls-remote origin gemini_cli_update 결과를 모두 보고한다.

성공 기준

* 2026-06-09 current_step이 MANUAL_EXECUTION_TEMPLATE에 머물지 않는다.
* execution 후보 0개 상황에서 current_step=DAILY_REVIEW.
* manual_execution_template export 반복 추천이 사라진다.
* stale review artifact guard가 유지된다.
* 통합 pytest 통과.
* commit/push 완료.

구현 대상 파일

* core\paper_daily_ops_orchestrator.py
* tests\test_paper_daily_ops_orchestrator.py
* tests\test_paper_daily_ops_orchestrator_guard.py
* docs\TRD\mfu_oper9_17_no_execution_candidates_advancement_guard.md
* docs\operations\paper_daily_ops.md

필요 시:

* docs\TRD\mfu_oper9_daily_ops_orchestrator_closeout.md

stage:
git add core\paper_daily_ops_orchestrator.py
git add tests\test_paper_daily_ops_orchestrator.py
git add tests\test_paper_daily_ops_orchestrator_guard.py
git add docs\TRD\mfu_oper9_17_no_execution_candidates_advancement_guard.md
git add docs\operations\paper_daily_ops.md

필요 시 closeout 문서만 별도 add.

주의:

* git add . 금지
* git add -A 금지
* outputs\orch_status.json commit 금지
* outputs\paper_accounts\paper_orch_smoke_202606 commit 금지
* .env/config secret commit 금지
* DB/cache/generated output commit 금지
* 기존 dirty/untracked 파일은 건드리지 않는다.

commit 메시지:
git commit -m "fix: advance OPER9 when execution candidates are empty"

push:
git branch --show-current
git push origin <CURRENT_BRANCH>

결과 보고 형식

1. Summary
2. 기준 commit SHA
3. 생성/수정한 파일
4. 원인 분석
5. no-execution-candidates guard 정책
6. 실제 2026-06-09 smoke 결과

   * current_step
   * next_command
   * MANUAL_EXECUTION_TEMPLATE status
   * DAILY_REVIEW status
7. 추가/유지한 테스트
8. 통합 테스트 결과
9. git rev-parse HEAD / ls-remote 결과
10. commit/push 결과
11. 실제 Notion/API write/commit/append/ledger 변경 없음 근거
12. 남은 한계
13. 다음 추천 작업

END MFU-OPER9-17 NO-EXECUTION-CANDIDATES ADVANCEMENT GUARD
