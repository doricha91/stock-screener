BEGIN MFU-PAPER15-3C_READ_ONLY_PAPER_CLI_ACCOUNT_ID_SUPPORT

# MFU-PAPER15-3C 작업 지시문: Read-only paper.py --account-id Support

## 목적

MFU-PAPER15-3C의 목표는 PAPER15-3A/3B에서 추가한 account profile 및 account-aware path resolver를 `scripts/paper.py`의 read-only 계열 명령에 연결하는 것이다.

이번 단계는 아래 3개 명령에만 `--account-id`를 적용한다.

```text
python scripts\paper.py status
python scripts\paper.py weekly-status
python scripts\paper.py benchmark
```

이번 단계는 read-only/account-scope 검증 단계다.  
prepare, preview, commit, eod, review-append, Notion import/export/sync, writer command 변경은 하지 않는다.

반드시 명시:

```text
이번 PAPER15-3C는 read-only paper.py 명령에 --account-id를 연결하는 작업이며, writer command 변경, DB write, paper 원장 수정, Notion write/export, migration 구현은 포함하지 않는다.
```

## 확정 전제

```text
1. 기존 outputs/paper_test는 account_id=paper_default인 legacy default account로 해석한다.
2. 신규 root는 outputs/paper_accounts/{account_id}/를 사용한다.
3. paper_default는 new root 우선 + legacy fallback 정책을 따른다.
4. non-default account는 legacy fallback 없이 outputs/paper_accounts/{account_id}/만 사용한다.
5. 이번 3C는 read-only CLI만 적용한다.
```

## 구현 범위

### 1. paper.py read-only 명령에 --account-id 추가

아래 parser에 `--account-id` 옵션을 추가한다.

```text
status
weekly-status
benchmark
```

기본 동작:

```text
--account-id 생략 시 paper_default로 동작
```

금지:

```text
prepare / preview / commit / plan / eod / reports / review / review-template / review-validate / review-append에는 이번 단계에서 --account-id를 붙이지 않는다.
```

### 2. account-aware path 연결

PAPER15-3B에서 추가한 아래 API를 사용한다.

```text
from core.paper_account_paths import build_paper_account_paths
```

정책:

```text
status: account paths 기준으로 상태를 읽는다.
weekly-status: account paths 기준으로 snapshot/log/report를 읽고 계좌별 reports_dir에 결과를 쓴다.
benchmark: account paths 기준으로 account snapshot과 market data를 읽고 계좌별 reports_dir에 결과를 쓴다.
```

주의:

```text
weekly-status와 benchmark는 source-of-truth 원장 수정은 아니지만 report markdown/json을 생성할 수 있다.
이번 단계에서 report write는 허용하되, 반드시 선택된 account root 하위 reports_dir에만 써야 한다.
paper_execution_log.csv, paper_account_snapshot.csv, paper_position_snapshot.csv, paper_current_state_*.json은 수정하지 않는다.
```

### 3. core 함수 optional account_paths 지원

필요하면 아래 함수에 선택 인자를 추가한다.

```text
run_paper_status(date_str=None, account_paths=None)
generate_paper_weekly_status(..., account_paths=None)
generate_paper_benchmark_comparison(account_paths=None)
```

정책:

```text
account_paths가 None이면 기존 core.paths 기반 동작 유지
account_paths가 있으면 해당 계좌 root의 artifact 사용
기존 호출부가 깨지지 않아야 한다
```

### 4. non-default account root 없음 처리

read-only 명령에서 non-default account root가 없으면 자동 생성하지 않는다.

권장 동작:

```text
status --account-id paper_growth:
- root가 없으면 NO_DATA 또는 UNKNOWN_OR_INCOMPLETE 성격의 결과를 출력
- 단, 디렉터리를 자동 생성하지 않는다

weekly-status / benchmark --account-id paper_growth:
- 입력 snapshot/log가 없으면 명확한 no data / unavailable 결과
- 실제 root가 없으면 report write를 시도하지 않거나, 명확히 실패한다
```

중요:

```text
이번 단계에서 프로젝트 실제 outputs/paper_accounts/{account_id}를 자동 생성하지 않는다.
필요한 테스트는 tmp_path로만 수행한다.
```

### 5. 출력에 account 정보 포함

아래 출력에는 account_id와 account_root를 포함한다.

```text
paper.py status
paper.py status --json
paper.py weekly-status --json
paper.py benchmark --json
```

권장 필드:

```text
account_id
account_root
legacy_default_used
```

가능하면 `PaperAccountPaths` 또는 resolver 결과에서 legacy fallback 여부도 표시한다.  
구현이 과하면 최소한 account_id/account_root만 포함한다.

## 테스트 추가/수정

테스트 후보:

```text
tests/test_paper_cli_account_scope.py
tests/test_paper_status_account_scope.py
tests/test_paper_weekly_status_account_scope.py
tests/test_paper_benchmark_account_scope.py
```

최소 테스트 항목:

```text
1. paper.py status --account-id paper_default가 기존 legacy root fallback을 사용
2. paper.py status --account-id valid_non_default가 account root를 참조
3. invalid --account-id는 실패
4. --account-id 생략 시 paper_default
5. weekly-status가 account_paths를 받을 수 있음
6. benchmark가 account_paths를 받을 수 있음
7. non-default account에서 create=False로 실제 outputs/paper_accounts를 만들지 않음
8. 기존 account_id 없는 함수 호출이 계속 동작
```

## 산출물

예상 수정 파일:

```text
scripts/paper.py
core/paper_status.py
core/paper_weekly_status.py
core/paper_benchmark_comparison.py
tests/...
```

선택 문서:

```text
docs/TRD/mfu_paper15_3c_read_only_paper_cli_account_id.md
```

선택 문서 포함 항목:

```text
1. Purpose
2. Scope / Non-scope
3. Supported commands
4. Account selection policy
5. Legacy fallback behavior
6. No-data behavior
7. Test coverage
8. Next MFU dependency
```

## 금지 사항

```text
prepare/preview/commit/plan/eod/reports/review/review-append account 적용 금지
writer command 수정 금지
paper 원장 CSV 수정 금지
paper_current_state 파일 수정 금지
DB write 금지
Notion API write 금지
Notion export 실행 금지
Notion status sync 실행 금지
migration script 작성 금지
config/paper_account_profiles.json 생성 금지
프로젝트 실제 outputs/paper_accounts 자동 생성 금지
git add . 금지
git add -A 금지
```

## 허용 사항

```text
read-only CLI 옵션 추가
status/weekly/benchmark의 optional account_paths 지원
계좌별 reports_dir에 weekly/benchmark report 생성 로직 조정
단위 테스트 추가
tmp_path 기반 테스트 디렉터리 생성
```

## 검증 명령

Windows CMD 기준:

```cmd
python -m pytest tests\test_paper_account_profile.py tests\test_paper_account_paths.py
python -m pytest tests\test_paper_cli_account_scope.py
python scripts\paper.py status --account-id paper_default --json
git diff -- scripts\paper.py core\paper_status.py core\paper_weekly_status.py core\paper_benchmark_comparison.py
git status --short
```

테스트 파일명이 다르면 실제 추가한 테스트 파일 기준으로 실행한다.

## 성공 기준

```text
paper.py status/weekly-status/benchmark에 --account-id가 추가된다.
--account-id 생략 시 paper_default로 동작한다.
paper_default는 legacy fallback으로 기존 outputs/paper_test를 읽을 수 있다.
non-default account는 account-aware root를 참조한다.
invalid account_id는 실패한다.
기존 account_id 없는 호출은 깨지지 않는다.
writer 계열 명령은 변경되지 않는다.
paper 원장 CSV와 DB는 수정되지 않는다.
Notion 동작은 변경되지 않는다.
프로젝트 실제 outputs/paper_accounts는 자동 생성되지 않는다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 생성/수정한 파일
3. --account-id 적용 명령
4. account selection 동작
5. paper_default legacy fallback 동작
6. non-default no-data/root-missing 동작
7. JSON 출력 변경 사항
8. 테스트 결과
9. 기존 호출 호환성
10. 금지 사항 준수 여부
11. outputs/paper_test 변경 여부
12. outputs/paper_accounts 생성 여부
13. 다음 MFU 제안
```

반드시 명시:

```text
이번 PAPER15-3C는 read-only paper.py 명령에 --account-id를 연결하는 작업이며, writer command 변경, DB write, paper 원장 수정, Notion write/export, migration 구현은 포함하지 않는다.
```

END MFU-PAPER15-3C_READ_ONLY_PAPER_CLI_ACCOUNT_ID_SUPPORT