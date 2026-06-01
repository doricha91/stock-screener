BEGIN MFU-PAPER15-4I_ACCOUNT_BOOTSTRAP_INIT_COMMAND

# MFU-PAPER15-4I 작업 지시문: Account Bootstrap / Init Command

## 목적

MFU-PAPER15-4I의 목표는 신규 non-default paper 계좌를 안전하게 초기화하는 공식 bootstrap/init 명령을 구현하는 것이다.

현재 paper_sandbox 리허설에서는 초기 account snapshot seed가 수동으로 준비되었다. 이번 작업에서는 이를 명령화하여 새 계좌 생성 시 필요한 root, 디렉터리, 초기 CSV/JSON seed를 일관되게 생성한다.

이번 단계는 local account bootstrap 구현에 한정한다.  
Notion actual write/sync/export, broker/API, cloud runner, paper_default migration, 실제 투자 주문은 포함하지 않는다.

반드시 명시:

```text
이번 PAPER15-4I는 신규 non-default paper 계좌 bootstrap/init command 구현 작업이며, Notion actual write/sync/export, broker/API, cloud runner, paper_default migration, 실제 투자 주문은 포함하지 않는다.
```

## 배경

PAPER15-4A~4H에서 paper_sandbox 기준으로 아래가 검증됐다.

```text
local account root routing
Manual Execution commit
reports / review-template / review-validate
review-append
REVIEW_PARTIAL / REVIEW_DONE status semantics
Daily Ops Status actual create/update
```

Daily Ops Status는 같은 External Key 재실행 시 `action=update`, 동일 page_id, `sync_status=SYNCED`까지 확인됐다. :contentReference[oaicite:0]{index=0}

남은 핵심 빈칸은 신규 계좌를 수동 seed 없이 안전하게 시작하는 공식 init 절차다.

## 핵심 정책

```text
1. init 대상은 non-default account만 허용한다.
2. paper_default init / migration은 금지한다.
3. 기본 실행은 dry-run이어야 한다.
4. 실제 생성에는 --confirm-create가 필요하다.
5. 이미 account root나 핵심 파일이 있으면 기본적으로 실패한다.
6. --allow-existing은 read/validate 용도로만 신중히 허용한다.
7. --force overwrite 금지.
8. 모든 생성 파일은 outputs/paper_accounts/{account_id}/ 하위에만 있어야 한다.
```

## CLI 설계

대상:

```text
scripts/paper.py
```

추가 명령 후보:

```cmd
python scripts\paper.py init-account --account-id paper_growth --initial-cash 100000 --currency USD --date 20260601 --dry-run
python scripts\paper.py init-account --account-id paper_growth --initial-cash 100000 --currency USD --date 20260601 --confirm-create
```

필수 옵션:

```text
--account-id
--initial-cash
--currency
--date
```

옵션 정책:

```text
--account-id paper_default 금지
--initial-cash는 0보다 커야 함
--currency 기본값은 두지 말고 명시 요구
--date는 YYYYMMDD 또는 YYYY-MM-DD 허용 후 YYYY-MM-DD로 정규화
--dry-run은 write 없음
--confirm-create 없이는 실제 write 금지
--json 지원
```

## 생성 대상

account root:

```text
outputs/paper_accounts/{account_id}/
```

필수 디렉터리:

```text
reports/
reviews/
archive/
config_snapshots/
replay_diff/
```

필수 파일:

```text
paper_account_snapshot.csv
paper_position_snapshot.csv
paper_execution_log.csv
paper_current_state_{YYYYMMDD}.json
```

권장 초기 내용:

### paper_account_snapshot.csv

초기 1행 생성.

필수 후보 컬럼은 현재 writer/report 코드가 기대하는 schema를 조사해 맞춘다.

최소 의미:

```text
snapshot_date = init date
initial_cash = initial_cash
cash = initial_cash
total_equity_market_value = initial_cash
total_equity_cost_basis = 0
unrealized_pnl = 0
cash_ratio_market_value = 1.0
cash_ratio_cost_basis = 1.0
position_count = 0
symbols = ""
market_valuation_status = INIT
valuation_price_date = ""
```

### paper_position_snapshot.csv

header만 생성하거나, 현재 코드가 empty CSV를 허용하지 않으면 명시적인 empty-position row 정책을 문서화한다.

권장:

```text
header only
```

### paper_execution_log.csv

header만 생성한다.

### paper_current_state_{YYYYMMDD}.json

초기 current state를 생성한다.

필수 후보:

```json
{
  "account_id": "...",
  "snapshot_date": "YYYY-MM-DD",
  "cash": 100000,
  "positions": [],
  "source": "init-account",
  "schema_version": "paper_current_state.init.v1"
}
```

정확한 schema는 기존 current state reader/writer와 맞춘다.

## 구현 범위

### 1. core helper 추가

파일 후보:

```text
core/paper_account_bootstrap.py
```

함수 후보:

```python
build_account_bootstrap_plan(...)
initialize_paper_account(...)
validate_account_bootstrap_target(...)
```

dry-run 결과에는 아래를 포함한다.

```text
account_id
account_root
would_create_dirs
would_create_files
initial_cash
currency
snapshot_date
blocked_reason
```

### 2. path safety

기존 account path resolver와 writer guard를 재사용한다.

필수 검증:

```text
non-default root는 outputs/paper_accounts/{account_id}/ 하위
paper_default는 차단
outputs/paper_test 접근 금지
target path가 account root 밖이면 FAIL
```

### 3. idempotency / existing guard

기본 정책:

```text
root가 없으면 생성 가능
root가 있고 핵심 파일이 없으면 명확한 WARNING 또는 FAIL
root가 있고 핵심 파일이 있으면 FAIL
```

`--allow-existing`을 추가하는 경우에도 overwrite는 금지한다.

```text
--allow-existing:
  이미 init된 계좌의 상태 확인만 허용
  새 파일 overwrite 금지
```

## 테스트

테스트 파일 후보:

```text
tests/test_paper_account_bootstrap.py
tests/test_paper_cli_init_account.py
```

필수 테스트:

```text
1. dry-run은 파일을 생성하지 않는다.
2. confirm-create는 tmp_path account root에 필수 디렉터리와 파일을 생성한다.
3. paper_account_snapshot.csv에 initial_cash/cash/snapshot_date가 들어간다.
4. paper_execution_log.csv는 header만 생성된다.
5. paper_position_snapshot.csv는 header only 또는 정의된 empty policy를 따른다.
6. paper_current_state_YYYYMMDD.json이 생성된다.
7. paper_default init은 실패한다.
8. invalid account_id는 실패한다.
9. existing initialized account에 재실행하면 실패한다.
10. target이 outputs/paper_test로 잡히면 실패한다.
11. 생성 후 run_paper_status(account_paths=...)가 UNKNOWN이 아니라 최소 PLAN_READY/COMMITTED 계열로 해석 가능한지 확인한다. 정확한 기대 상태는 현재 status semantics에 맞춘다.
```

테스트는 반드시 `tmp_path` 기반으로 수행한다. 실제 `outputs/paper_accounts` 생성 금지.

## 문서

추가 문서:

```text
docs/TRD/mfu_paper15_4i_account_bootstrap_init_command.md
```

문서 포함:

```text
1. Purpose
2. Scope / Non-scope
3. Init command syntax
4. Safety policy
5. Generated directory structure
6. Generated file schema
7. paper_default policy
8. Existing account policy
9. How this supports multi-account onboarding
10. Future SOP update notes
```

## 금지 사항

```text
paper_default init/migration 금지
outputs/paper_test 수정 금지
실제 outputs/paper_accounts에 운영 계좌 생성 금지
Notion actual write/sync/export 금지
Daily Ops Status actual export 실행 금지
broker/API 실행 금지
cloud runner 작업 금지
실제 투자 주문 금지
기존 paper_sandbox 파일 수정 금지
git add . 금지
git add -A 금지
```

## 허용 사항

```text
init-account CLI 구현
tmp_path 기반 account root 생성 테스트
core bootstrap helper 추가
문서 추가
pytest 실행
read-only status 확인
```

## 검증 명령

Windows CMD 기준:

```cmd
python -m pytest tests\test_paper_account_bootstrap.py
python -m pytest tests\test_paper_cli_init_account.py
python -m pytest tests\test_paper_account_paths.py tests\test_paper_account_profile.py
python -m pytest tests\test_paper_status.py tests\test_paper_status_review_workflow.py
git diff -- core\paper_account_bootstrap.py scripts\paper.py
git diff -- docs\TRD\mfu_paper15_4i_account_bootstrap_init_command.md
git status --short
```

선택 read-only 확인:

```cmd
python scripts\paper.py init-account --account-id paper_growth --initial-cash 100000 --currency USD --date 20260601 --dry-run --json
```

실제 운영 root 생성 명령은 실행하지 않는다.

## 성공 기준

```text
init-account 명령이 추가된다.
dry-run은 생성 예정 파일/디렉터리를 JSON으로 보여주고 실제 write하지 않는다.
--confirm-create가 있어야 실제 생성된다.
paper_default init은 차단된다.
non-default account root 하위에만 파일이 생성된다.
초기 account snapshot/current state/execution log/position snapshot seed가 생성된다.
기존 initialized account overwrite가 차단된다.
tmp_path 기반 테스트가 통과한다.
Notion, broker/API, cloud runner, paper_default migration은 변경되지 않는다.
실제 운영 outputs는 수정하지 않는다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 생성/수정한 파일
3. 추가한 CLI
4. dry-run 동작
5. confirm-create 동작
6. 생성 디렉터리/파일 목록
7. 초기 CSV/JSON schema 요약
8. paper_default 차단 여부
9. existing account guard
10. path safety 결과
11. 테스트 결과
12. Notion/export/broker 실행 여부
13. outputs 변경 여부
14. 남은 리스크
15. 다음 MFU 제안
```

반드시 명시:

```text
이번 PAPER15-4I는 신규 non-default paper 계좌 bootstrap/init command 구현 작업이며, Notion actual write/sync/export, broker/API, cloud runner, paper_default migration, 실제 투자 주문은 포함하지 않는다.
```

END MFU-PAPER15-4I_ACCOUNT_BOOTSTRAP_INIT_COMMAND