BEGIN MFU-PAPER15-3E-4A_IMPORTER_ACCOUNT_FILTER

# MFU-PAPER15-3E-4A 작업 지시문: Manual Execution / Review Importer Account Filter

## 목적

MFU-PAPER15-3E-4A의 목표는 Notion Manual Executions / Manual Reviews importer의 read-only preview 단계에 Account ID filter와 account-aware canonical key를 적용하는 것이다.

이번 단계는 importer preview/query account filter 구현에 한정한다.  
commit/append, status sync, Notion row migration, writer path 적용은 하지 않는다.

반드시 명시:

```text
이번 PAPER15-3E-4A는 Manual Execution / Review importer의 Account ID filter 및 preview namespace 구현이며, commit/append 변경, status sync 변경, Notion row migration, paper 원장 수정, writer path 적용은 포함하지 않는다.
```

## 배경

PAPER15-3E-3에서 read-only exporter 5종은 account-aware External Key를 사용하게 됐다.

적용 완료:

```text
Daily Plans
Account Snapshots
Weekly Reports
Benchmark Reports
Daily Review Summaries
```

아직 미적용:

```text
Manual Execution importer
Manual Review importer
Manual Execution status sync
Manual Review status sync
legacy Notion row migration preview
```

Manual Executions / Manual Reviews는 사용자가 직접 입력하는 staging DB이므로, Account ID filter가 없으면 다른 계좌의 READY row를 함께 읽을 수 있다.

## 구현 범위

### 1. 대상 파일

```text
core/notion_manual_execution_importer.py
core/notion_manual_review_importer.py
scripts/import_notion_executions.py
scripts/import_notion_reviews.py
core/notion_account_keys.py
tests/test_notion_manual_execution_importer.py
tests/test_notion_manual_review_importer.py
```

필요 시 추가:

```text
tests/test_import_notion_executions_cli.py
tests/test_import_notion_reviews_cli.py
docs/TRD/mfu_paper15_3e_4a_importer_account_filter.md
```

## 2. CLI에 --account-id 추가

아래 스크립트에 `--account-id`를 추가한다.

```text
scripts/import_notion_executions.py
scripts/import_notion_reviews.py
```

정책:

```text
--account-id 생략 시 paper_default
account_id는 validate_account_id 사용
preview/read-only import query에만 account scope 적용
```

중요:

```text
이번 단계에서 --commit / append commit 경로는 account-aware로 확장하지 않는다.
non-default account로 --commit을 시도하면 명확히 차단하거나, 기존 commit 경로가 account-less임을 알리는 에러를 낸다.
paper_default 기존 commit 호환성은 유지한다.
```

## 3. Notion READY query에 Account ID filter 추가

Manual Executions / Manual Reviews의 READY row query에 Account ID 조건을 추가한다.

권장 정책:

```text
account_id != paper_default:
  Account ID == {account_id} 인 row만 조회

account_id == paper_default:
  Account ID == paper_default OR Account ID is empty 인 row 조회 허용
```

이유:

```text
기존 legacy row는 Account ID가 비어 있어도 paper_default로 해석하기로 했기 때문이다.
```

주의:

```text
Account ID property가 없는 경우에는 schema/mapping 문제로 명확히 실패하거나 WARNING/FAIL 정책을 문서화한다.
단, 이번 단계에서 Notion schema migration은 하지 않는다.
```

## 4. account-aware canonical key 적용

Preview candidate의 canonical key를 account-aware로 확장한다.

Manual Execution:

```text
manual_execution:{account_id}:{execution_date}:{symbol}:{side}:{sequence}
```

Manual Review:

```text
manual_review:{account_id}:{review_date}:{symbol}:{question_id}
```

Preview payload에 아래 필드를 포함한다.

```text
account_id
canonical_key
legacy_canonical_key, if account_id == paper_default
legacy_key_compatible
```

legacy key 예:

```text
manual_execution:2026-05-25:AAPL:BUY:01
manual_review:2026-05-25:AAPL:Q001
```

## 5. preview JSON / Markdown 보강

preview JSON과 Markdown에 account 정보를 표시한다.

필수 포함:

```text
account_id
source_data_source_id
candidate_count
pass_count
warning_count
fail_count
append_or_import_allowed
canonical_key
legacy_canonical_key, if applicable
```

Manual Execution / Review 각각 기존 필드를 깨지 않도록 한다.

## 6. commit/append 경로 보호

이번 단계는 preview namespace 구현이 목적이다.

정책:

```text
Manual Execution commit:
  기존 paper_default legacy preview commit은 유지
  non-default account-aware preview commit은 차단

Manual Review append:
  기존 paper_default legacy preview append는 유지
  non-default account-aware preview append는 차단
```

이유:

```text
writer path와 status sync가 아직 account-aware가 아니기 때문에 non-default commit/append를 열면 원장 오염 위험이 있다.
```

## 7. 테스트

테스트 항목:

```text
1. import_notion_executions.py --account-id paper_default preview query가 Account ID paper_default 또는 blank를 허용
2. import_notion_reviews.py --account-id paper_default preview query가 Account ID paper_default 또는 blank를 허용
3. non-default account는 Account ID == account_id만 조회
4. Manual Execution canonical_key가 account-aware 형식으로 생성
5. Manual Review canonical_key가 account-aware 형식으로 생성
6. preview payload에 account_id 포함
7. paper_default preview payload에 legacy_canonical_key 포함
8. invalid account_id 실패
9. non-default --commit 차단
10. 기존 account_id 없는 호출은 paper_default로 동작
```

Notion API 실제 호출은 fake/mock client로만 검증한다.

## 산출물

예상 수정/추가 파일:

```text
core/notion_manual_execution_importer.py
core/notion_manual_review_importer.py
scripts/import_notion_executions.py
scripts/import_notion_reviews.py
core/notion_account_keys.py
tests/test_notion_manual_execution_importer.py
tests/test_notion_manual_review_importer.py
```

문서 추가:

```text
docs/TRD/mfu_paper15_3e_4a_importer_account_filter.md
```

## 금지 사항

```text
Manual Execution commit account-aware 적용 금지
Manual Review append account-aware 적용 금지
status sync 로직 변경 금지
Notion API write 금지
Notion export actual 실행 금지
Notion status sync 실행 금지
legacy Notion row migration script 작성 금지
paper 원장 CSV 수정 금지
DB write 금지
outputs 하위 파일 수정 금지
writer path 적용 금지
core/paths.py writer path 변경 금지
git add . 금지
git add -A 금지
```

## 허용 사항

```text
importer read-only query filter 구현
preview candidate에 account_id 추가
preview canonical key account-aware 확장
preview JSON/Markdown 보강
CLI --account-id 추가
non-default commit/append 차단 guard 추가
fake/mock Notion client 테스트
pytest 실행
TRD 문서 추가
```

## 검증 명령

Windows CMD 기준:

```cmd
python -m pytest tests\test_notion_manual_execution_importer.py
python -m pytest tests\test_notion_manual_review_importer.py
python -m pytest tests\test_notion_account_keys.py
python -m pytest tests\test_notion_mapping.py tests\test_notion_schema_validator.py
git diff -- core\notion_manual_execution_importer.py core\notion_manual_review_importer.py scripts\import_notion_executions.py scripts\import_notion_reviews.py core\notion_account_keys.py
git diff -- docs\TRD\mfu_paper15_3e_4a_importer_account_filter.md
git status --short
```

실제 Notion API write/sync 명령은 실행하지 않는다.

## 성공 기준

```text
Manual Execution importer preview가 --account-id를 지원한다.
Manual Review importer preview가 --account-id를 지원한다.
paper_default는 Account ID blank legacy row를 paper_default로 해석할 수 있다.
non-default account는 Account ID가 일치하는 READY row만 조회한다.
preview canonical key가 account-aware 형식으로 생성된다.
preview payload에 account_id가 포함된다.
non-default commit/append는 writer/status sync 준비 전까지 차단된다.
status sync, writer path, Notion migration은 변경되지 않는다.
paper 원장, DB, outputs는 수정하지 않는다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 생성/수정한 파일
3. 적용 대상 importer
4. --account-id CLI 동작
5. READY query Account ID filter 정책
6. account-aware canonical key 형식
7. legacy paper_default blank Account ID 처리
8. non-default commit/append 차단 동작
9. preview JSON/Markdown 변경 사항
10. 테스트 결과
11. status sync 변경 여부
12. Notion write/export/sync 실행 여부
13. outputs 변경 여부
14. 다음 MFU 제안
```

반드시 명시:

```text
이번 PAPER15-3E-4A는 Manual Execution / Review importer의 Account ID filter 및 preview namespace 구현이며, commit/append 변경, status sync 변경, Notion row migration, paper 원장 수정, writer path 적용은 포함하지 않는다.
```

END MFU-PAPER15-3E-4A_IMPORTER_ACCOUNT_FILTER