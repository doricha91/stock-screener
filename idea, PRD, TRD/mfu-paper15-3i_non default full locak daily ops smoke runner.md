BEGIN MFU-PAPER15-3I_FULL_LOCAL_DAILY_OPS_SMOKE_RUNNER

# MFU-PAPER15-3I 작업 지시문: Non-default Full Local Daily Ops Smoke Runner

## 목적

MFU-PAPER15-3I의 목표는 non-default 계좌 기준으로 local daily ops 전체 체인이 끊기지 않는지 higher-level smoke runner/test로 검증하는 것이다.

검증 대상 체인:

```text
plan
→ eod dry-run
→ manual execution commit fixture
→ reports
→ review-template
→ review-validate
→ review-append
→ status
```

이번 단계는 smoke runner/test 추가와 closeout 문서화가 목적이다.  
실제 운영 outputs/paper_accounts 생성, Notion actual sync/write, Notion row migration, broker/API, cloud runner, paper_default legacy migration은 포함하지 않는다.

반드시 명시:

```text
이번 PAPER15-3I는 non-default 계좌의 full local daily ops smoke runner/test이며, 실제 운영 outputs 생성, Notion actual sync/write, Notion row migration, broker/API, cloud runner, paper_default legacy migration은 포함하지 않는다.
```

## 배경

PAPER15-3H에서 아래 체인은 tmp_path 기준으로 검증됐다.

```text
status
→ reports
→ review-template
→ review-validate
→ review-append
→ status
```

이번 3I에서는 local daily ops 관점에서 더 넓은 체인을 묶어 검증한다.

```text
plan/eod/commit/reports/review/status
```

단, 실제 운영 명령을 프로젝트 outputs에 대해 실행하지 않는다.  
모든 write는 tmp_path 또는 명시적 test root 안에서만 수행한다.

## 핵심 정책

```text
1. smoke account_id는 paper_smoke 사용
2. 모든 산출물은 tmp_path 기반 account root 하위에만 생성
3. non-default가 outputs/paper_test를 참조하거나 쓰면 실패
4. paper_default는 기존 legacy outputs/paper_test 정책 유지
5. Notion actual write/sync는 절대 실행하지 않음
6. 실제 운영 paper.py 명령은 실행하지 않음
```

## 구현 범위

### 1. smoke runner/test 추가

우선순위는 테스트다.

추가 후보:

```text
tests/test_paper15_3i_full_local_daily_ops_smoke.py
```

선택적으로 dev smoke script를 추가할 수 있다.

```text
scripts/dev/paper_full_daily_ops_smoke.py
```

단, script를 추가한다면 기본 실행은 반드시 dry-run/test-root 전용이어야 한다.

금지:

```text
기본값으로 실제 outputs/paper_accounts를 쓰는 script 작성 금지
```

### 2. fixture 기반 account root 구성

테스트에서 tmp_path 아래에 아래 구조를 만든다.

```text
tmp_path/outputs/paper_accounts/paper_smoke/
```

필요한 최소 fixture를 생성한다.

```text
paper_execution_log.csv
paper_account_snapshot.csv
paper_position_snapshot.csv
paper_current_state_YYYYMMDD.json
daily_action_plan_YYYYMMDD.md 또는 plan fixture
reports/
reviews/
```

실제 코드가 요구하는 최소 컬럼과 schema를 현재 테스트/코드 기준으로 맞춘다.

### 3. full local daily ops chain 검증

아래 순서를 하나의 smoke test 또는 몇 개의 단계별 테스트로 검증한다.

```text
1. account_id=paper_smoke account_paths 생성
2. plan 또는 plan fixture가 account root 하위에 존재/생성됨
3. eod dry-run 또는 eod-like fixture가 account root 기준으로 동작
4. Manual Execution commit fixture가 account root에 execution log/current state/snapshot/sidecar를 기록
5. reports가 account_root/reports 하위에 생성됨
6. review-template이 account_root/reviews 하위에 생성됨
7. review-validate가 같은 reviews root를 읽고 validation report 생성
8. review-append가 같은 reviews root의 log에 append
9. status가 같은 account root를 읽고 chain 결과를 반영
```

실제 운영 `paper.py plan/eod/commit` 명령은 실행하지 않는다.  
가능한 경우 core 함수 또는 test helper 수준에서 검증한다.

### 4. path safety 검증

반드시 확인한다.

```text
- non-default 산출물은 account_paths.root 하위에만 생성
- non-default가 outputs/paper_test를 target으로 잡으면 실패
- sidecar/report/review/log/snapshot 경로가 account root 밖으로 나가지 않음
```

### 5. Notion 계층 검증 범위

허용:

```text
- 기존 contract test 재사용
- fake/mock Notion payload 검증
- dry-run payload 구조 확인
```

금지:

```text
- Notion actual export
- Notion actual status sync
- Notion row migration
```

## 산출물

필수:

```text
tests/test_paper15_3i_full_local_daily_ops_smoke.py
docs/TRD/mfu_paper15_3i_full_local_daily_ops_smoke_runner.md
```

선택:

```text
scripts/dev/paper_full_daily_ops_smoke.py
```

script 추가 시 문서에 사용법과 안전장치를 반드시 적는다.

## 금지 사항

```text
실제 운영 outputs/paper_accounts 자동 생성 금지
실제 운영 paper.py plan/eod/commit/review-append 실행 금지
Notion actual sync/write 실행 금지
Notion row migration script 작성 금지
paper_default legacy migration 금지
broker/API 연동 금지
cloud runner 작업 금지
DB schema 변경 금지
git add . 금지
git add -A 금지
```

## 허용 사항

```text
tmp_path 기반 account root 생성
test fixture CSV/JSON/MD 생성
core 함수 기반 local writer smoke 검증
fake/mock Notion client 사용
dry-run payload 검증
smoke test 추가
TRD closeout 문서 추가
pytest 실행
```

## 검증 명령

Windows CMD 기준:

```cmd
python -m pytest tests\test_paper15_3i_full_local_daily_ops_smoke.py
python -m pytest tests\test_paper15_3h_non_default_daily_ops_smoke.py
python -m pytest tests\test_paper_writer_account_paths.py
python -m pytest tests\test_paper15_3e_4d_import_commit_sync_contract.py
python -m pytest tests\test_paper_reports_account_paths.py tests\test_paper_review_template_account_paths.py tests\test_paper_review_validate_account_paths.py
git diff -- tests\test_paper15_3i_full_local_daily_ops_smoke.py
git diff -- docs\TRD\mfu_paper15_3i_full_local_daily_ops_smoke_runner.md
git status --short
```

script를 추가한 경우:

```cmd
git diff -- scripts\dev\paper_full_daily_ops_smoke.py
```

실제 운영 writer 명령과 Notion actual sync/write는 실행하지 않는다.

## 성공 기준

```text
non-default full local daily ops chain이 tmp_path 기반으로 검증된다.
plan/eod/commit/reports/review-template/review-validate/review-append/status가 같은 account root를 공유한다.
Manual Execution commit fixture가 account root 하위에만 산출물을 만든다.
Review 관련 산출물이 account root/reviews 하위에만 생성된다.
Reports 산출물이 account root/reports 하위에만 생성된다.
status가 같은 account root 기준으로 결과를 반영한다.
non-default가 outputs/paper_test를 참조하거나 쓰는 경우 차단된다.
paper_default legacy 정책은 변경되지 않는다.
Notion actual sync/write, migration, broker/API는 변경되지 않는다.
실제 운영 outputs/paper_accounts는 생성되지 않는다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 생성/수정한 파일
3. smoke account_id
4. 검증한 full local daily ops chain
5. plan/eod 검증 방식
6. Manual Execution commit fixture 검증
7. reports/review-template/review-validate/review-append 검증
8. status 재조회 검증
9. path safety 결과
10. Notion actual sync/write 실행 여부
11. 실제 운영 outputs/paper_accounts 생성 여부
12. production code 변경 여부
13. 테스트 결과
14. 남은 리스크
15. 다음 MFU 제안
```

반드시 명시:

```text
이번 PAPER15-3I는 non-default 계좌의 full local daily ops smoke runner/test이며, 실제 운영 outputs 생성, Notion actual sync/write, Notion row migration, broker/API, cloud runner, paper_default legacy migration은 포함하지 않는다.
```

END MFU-PAPER15-3I_FULL_LOCAL_DAILY_OPS_SMOKE_RUNNER