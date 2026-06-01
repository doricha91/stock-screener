BEGIN MFU-PAPER15-3H_NON_DEFAULT_DAILY_OPS_SMOKE_CLOSEOUT

# MFU-PAPER15-3H 작업 지시문: Non-default Daily Ops Smoke / Closeout

## 목적

MFU-PAPER15-3H의 목표는 non-default paper 계좌가 local daily ops 관점에서 실제 운영 가능한지 smoke/closeout 수준으로 검증하는 것이다.

이번 단계는 검증/문서화 중심이다.  
Notion actual sync/write, Notion row migration, broker/API, cloud runner, paper_default legacy migration은 포함하지 않는다.

반드시 명시:

```text
이번 PAPER15-3H는 non-default 계좌의 local daily ops smoke/closeout 검증이며, Notion actual sync/write, Notion row migration, broker/API, cloud runner, paper_default legacy migration은 포함하지 않는다.
```

## 배경

선행 작업 결과:

```text
3A: account profile model
3B: account-aware path resolver
3C: read-only paper.py --account-id
3D: writer account guard
3E: Notion Account ID / External Key namespace 정렬
3F: non-default local writer path 연결
3G: reports / review-template / review-validate 체인 account root 연결
```

PAPER15-3G 결과상 non-default reports/reviews/template 체인은 account root에 연결되었지만, 실제 daily ops 운영 체인은 아직 smoke 검증 전이다.

## 핵심 검증 대상

non-default account 예시는 아래를 사용한다.

```text
account_id = paper_smoke
```

단, 실제 운영 `outputs/paper_accounts/paper_smoke`를 만들지 않는다.  
테스트는 tmp_path 또는 별도 test root에서만 수행한다.

검증할 local chain:

```text
status
reports
review-template
review-validate
review-append
status
```

가능하면 Manual Execution flow도 mock/fixture 기반으로 확인한다.

```text
import_notion_executions preview
commit sidecar
status sync payload dry-run contract
```

실제 Notion API는 호출하지 않는다.

## 작업 범위

### 1. Smoke runner 또는 test 추가

새 테스트 파일 후보:

```text
tests/test_paper15_3h_non_default_daily_ops_smoke.py
```

필요 시 smoke helper 추가:

```text
scripts/dev/paper_account_smoke.py
```

단, 실제 운영 root를 건드리지 않도록 기본은 tmp_path/test root만 사용한다.

### 2. non-default local daily ops 체인 검증

아래 항목을 tmp_path 기반으로 검증한다.

```text
1. account_id=paper_smoke의 account root 생성
2. status가 해당 root를 읽음
3. reports가 account_root/reports 하위에 산출물 생성
4. review-template이 account_root/reviews 하위에 template 생성
5. review-validate가 같은 reviews root의 파일을 읽고 validation report 생성
6. review-append가 같은 reviews root의 log에 append 가능
7. append report에 account_id / canonical_key 유지
8. status 재조회 시 같은 account root 기준으로 동작
```

### 3. path safety 검증

반드시 확인한다.

```text
- non-default가 outputs/paper_test를 target으로 잡으면 실패
- non-default 산출물은 account root 하위에만 생성
- paper_default는 기존 outputs/paper_test legacy 정책 유지
```

### 4. Notion 계층 검증은 dry-run/contract만

허용:

```text
- fake/mock Notion client
- dry-run payload 생성
- Account ID / External Key contract 확인
```

금지:

```text
- Notion actual export
- Notion actual status sync
- Notion row migration
```

### 5. closeout 문서 작성

문서 추가:

```text
docs/TRD/mfu_paper15_3h_non_default_daily_ops_smoke_closeout.md
```

문서 포함 항목:

```text
1. Purpose
2. Scope / Non-scope
3. Smoke account assumptions
4. Verified local daily ops chain
5. Path safety results
6. Notion dry-run/contract status
7. Remaining limitations
8. Readiness decision
9. Next MFU recommendation
```

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
test fixture 기반 CSV/JSON/MD 생성
fake/mock Notion client 사용
dry-run payload 검증
smoke/contract 테스트 추가
TRD closeout 문서 추가
pytest 실행
read-only status 명령 실행
```

## 검증 명령

Windows CMD 기준:

```cmd
python -m pytest tests\test_paper15_3h_non_default_daily_ops_smoke.py
python -m pytest tests\test_paper_reports_account_paths.py tests\test_paper_review_template_account_paths.py tests\test_paper_review_validate_account_paths.py
python -m pytest tests\test_paper_writer_account_paths.py
python -m pytest tests\test_paper15_3e_4d_import_commit_sync_contract.py
python -m pytest tests\test_paper_account_paths.py tests\test_paper_account_profile.py
git diff -- tests\test_paper15_3h_non_default_daily_ops_smoke.py
git diff -- docs\TRD\mfu_paper15_3h_non_default_daily_ops_smoke_closeout.md
git status --short
```

실제 운영 writer 명령과 Notion actual sync/write는 실행하지 않는다.

## 성공 기준

```text
non-default daily ops local chain이 tmp_path 기반으로 검증된다.
reports → review-template → review-validate → review-append → status가 같은 account root를 공유한다.
non-default 산출물이 account root 밖에 쓰이지 않는다.
non-default가 outputs/paper_test를 target으로 잡는 경우 차단된다.
paper_default legacy path 정책은 유지된다.
Notion 관련 검증은 dry-run/contract 수준으로만 수행된다.
실제 운영 outputs/paper_accounts는 생성되지 않는다.
paper 원장, DB, Notion 실제 데이터는 수정되지 않는다.
non-default 계좌 운영 가능/불가능 판단과 남은 제한사항이 문서화된다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 생성/수정한 파일
3. smoke 검증 account_id
4. 검증한 daily ops chain
5. reports root 검증
6. review-template / validate / append root 검증
7. status 재조회 검증
8. path safety 결과
9. Notion actual sync/write 실행 여부
10. 실제 운영 outputs/paper_accounts 생성 여부
11. paper_default legacy 영향 여부
12. 테스트 결과
13. 남은 리스크
14. 다음 MFU 제안
```

반드시 명시:

```text
이번 PAPER15-3H는 non-default 계좌의 local daily ops smoke/closeout 검증이며, Notion actual sync/write, Notion row migration, broker/API, cloud runner, paper_default legacy migration은 포함하지 않는다.
```

END MFU-PAPER15-3H_NON_DEFAULT_DAILY_OPS_SMOKE_CLOSEOUT