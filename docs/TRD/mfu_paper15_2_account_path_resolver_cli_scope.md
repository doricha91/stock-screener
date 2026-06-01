# MFU-PAPER15-2 Account-aware Path Resolver / CLI Scope Audit

## 1. Purpose

이번 PAPER15-2는 account-aware path resolver 및 CLI account scope 조사/설계이며, 코드 구현, DB write, paper 원장 수정, Notion write/export, migration 구현은 포함하지 않는다.

이 문서는 PAPER15-1에서 정리한 단일계좌 전제를 바탕으로, 향후 다중계좌 구조를 도입하기 위한 output root 정책, legacy compatibility 정책, `core/paths.py` 영향 범위, CLI별 `--account-id` 필요 여부를 설계 관점에서 정리한다.

## 2. Scope / Non-scope

### Scope

- `outputs/paper_test` legacy root를 `paper_default`로 해석하는 정책 정리
- 신규 root `outputs/paper_accounts/{account_id}/` 설계
- `core/paths.py` 함수별 account-aware 필요 여부 분류
- `paper.py` 및 Notion 관련 CLI의 account scope 영향도 조사
- account selection precedence 제안
- 다음 구현 MFU 분할안 제안

### Non-scope

- path resolver 구현
- `--account-id` CLI 구현
- config file 추가
- migration 실행
- Notion external key 변경 구현
- artifact rename / move 실행

## 3. Confirmed Decisions from PAPER15-1

이번 설계는 아래 전제를 확정사항으로 둔다.

1. 기존 `outputs/paper_test`는 `account_id = paper_default`인 legacy default account로 해석한다.
2. 신규 다중계좌 artifact root는 `outputs/paper_accounts/{account_id}/` 방향으로 설계한다.
3. Notion은 계좌별 DB 분리가 아니라 단일 DB + `account_id` property 방향으로 설계한다.
4. `strategy_profile`, `universe_profile`, `benchmark_profile`, `notion_profile`은 account identity core가 아니라 별도 profile/reference 계층으로 분리한다.

## 4. Proposed Account-aware Output Root Policy

### 4.1 Root 구조 권장안

권장 구조:

```text
Legacy:
outputs/paper_test/

New:
outputs/paper_accounts/{account_id}/
```

예:

```text
outputs/paper_accounts/paper_default/
outputs/paper_accounts/paper_growth/
outputs/paper_accounts/paper_income/
```

### 4.2 설계 원칙

- 신규 구현은 원칙적으로 `paper_accounts/{account_id}`만 writer target으로 사용한다.
- legacy `paper_test`는 읽기 호환용 special case로만 취급한다.
- `paper_default`도 장기적으로는 신규 root 아래로 수렴시키는 방향이 맞다.

### 4.3 권장 장기 방향

장기 방향은 아래가 가장 일관적이다.

```text
paper_default 포함 모든 계좌를 outputs/paper_accounts/{account_id}/로 정규화
```

다만 migration 전 단계에서는:

- read path는 legacy + new root를 모두 인식
- write path는 단계적으로 new root로 제한

전략이 안전하다.

## 5. Legacy `paper_test` Compatibility Policy

### 5.1 왜 필요한가

필수다.

이유:

- 기존 writer와 report가 모두 `outputs/paper_test`에 누적되어 있다.
- `paper.py status`, weekly, benchmark, Notion export 등 다수 기능이 이 root를 기준으로 운영된다.
- 즉시 migration 없이 backward compatibility를 유지하려면 resolver가 legacy root를 읽을 수 있어야 한다.

### 5.2 권장 해석

권장 해석:

```text
outputs/paper_test == paper_default legacy root
```

### 5.3 read 우선순위 권장안

권장 우선순위:

1. 명시적 account root override가 있으면 그 경로 사용
2. `account_id != paper_default`이면 `outputs/paper_accounts/{account_id}`만 사용
3. `account_id == paper_default`이면
   - 우선 `outputs/paper_accounts/paper_default/`
   - 없으면 legacy `outputs/paper_test/`

이유:

- 새 root가 존재하면 그 쪽이 canonical이어야 한다.
- `paper_default`만 legacy fallback을 허용해야 한다.
- 다른 계좌가 실수로 legacy root를 읽는 상황을 막아야 한다.

### 5.4 writer 정책 권장안

writer 단계 권장안:

- 초기 구현 단계:
  - `paper_default`는 legacy write 허용 여부를 별도 guard로 통제
- 목표 상태:
  - writer는 `outputs/paper_accounts/{account_id}`만 사용
  - legacy `outputs/paper_test`는 read-only compatibility root로 강등

## 6. Path Resolver Design

### 6.1 Resolver가 알아야 할 것

resolver는 최소 아래를 알아야 한다.

- `account_id`
- `legacy_default_allowed`
- optional explicit `account_root`

### 6.2 권장 account_id validation 규칙

권장 규칙:

- 허용 문자: `a-z`, `0-9`, `_`, `-`
- 소문자 canonical form 사용
- 길이: 3~64
- 금지:
  - 공백
  - path separator
  - `..`
  - reserved names like `archive`, `reports`, `reviews`

권장 regex:

```text
^[a-z0-9][a-z0-9_-]{2,63}$
```

### 6.3 잘못된 account_id 입력 시 error 원칙

권장 error:

- validation error는 조기에 fail
- 메시지는 명확하게 account scope를 설명

예:

```text
Invalid account_id 'Paper Default'. Use lowercase letters, digits, '_' or '-'.
```

존재하지 않는 계좌 root에 대해서는:

```text
Account root not found for account_id 'paper_growth': outputs/paper_accounts/paper_growth
```

### 6.4 Resolver shape 권장안

실제 구현 전 설계 수준 권장안:

- `resolve_paper_account_root(account_id, allow_legacy_default=True)`
- `build_paper_account_paths(account_id, account_root=None, allow_legacy_default=True)`

출력 예:

```text
account_root
reports_dir
reviews_dir
config_snapshots_dir
replay_diff_dir
archive_dir
execution_log_path
account_snapshot_path
position_snapshot_path
current_state_path(date)
daily_action_plan_path(date)
```

### 6.5 tests에서의 임시 root 주입

권장안:

- production path helpers는 account-aware resolver를 통해 root를 만들고
- tests는 `tmp_path / "paper_accounts" / "{account_id}"` 또는 explicit `account_root`를 주입한다.

이 방식의 장점:

- `PAPER_TEST_DIR` global을 monkeypatch하지 않아도 된다.
- read-only and writer 테스트 모두 isolated path를 만들 수 있다.

## 7. `core/paths.py` Impact Table

### A. 반드시 account-aware 필요

| 함수 | 이유 | 권장 방향 |
|---|---|---|
| `paper_current_state_snapshot_path` | current state는 계좌 종속 | `account_id` 또는 `account_root` 필요 |
| `paper_daily_action_plan_path` | daily plan은 계좌/전략 context 종속 | account-aware 필요 |
| `paper_execution_log_path` | ledger 자체가 계좌 종속 | account-aware 필요 |
| `paper_account_snapshot_path` | same-date replace가 계좌별로 분리돼야 함 | account-aware 필요 |
| `paper_position_snapshot_path` | holdings/valuation이 계좌 종속 | account-aware 필요 |
| `paper_reports_dir` | reports 전체가 계좌 대표물 | account-aware 필요 |
| `paper_reviews_dir` | review template/log가 계좌 종속 | account-aware 필요 |
| `paper_config_snapshots_dir` | config provenance가 계좌/plan context 종속 | account-aware 필요 |
| `paper_config_snapshot_path` | same-date config snapshot도 계좌별로 필요 | account-aware 필요 |
| `paper_config_snapshot_archive_dir` | archive도 계좌별 관리 필요 | account-aware 필요 |
| `paper_replay_diff_dir` | replay diff가 특정 계좌 plan 재생성에 종속 | account-aware 필요 |
| `paper_regenerated_daily_action_plan_path` | replay artifact가 계좌 종속 | account-aware 필요 |
| `paper_daily_plan_diff_report_path` | diff report도 계좌 종속 | account-aware 필요 |
| `paper_replay_diff_config_snapshot_path` | replay config artifact가 계좌 종속 | account-aware 필요 |
| `paper_replay_diff_config_snapshot_archive_dir` | replay archive도 계좌별 필요 | account-aware 필요 |

### B. account-aware 권장

| 함수 | 이유 | 권장 방향 |
|---|---|---|
| `paper_performance_summary_path` | summary는 reports 하위라 account-aware가 자연스러움 | reports dir 파생으로 일반화 |

### C. 공통 유지 가능

| 함수 | 이유 | 권장 방향 |
|---|---|---|
| `dev_backups_dir` | 공통 backup staging dir로 유지 가능 | 대신 backup filename에 `account_id` 포함 권장 |

### D. 추가 조사 필요

| 함수 | 이유 | 추가 포인트 |
|---|---|---|
| `current_state_snapshot_path` | front_test 전용 path | multi-account front-test도 필요한지 별도 판단 필요 |
| `front_daily_action_plan_path` | front_test 전용 path | environment/account 이중축 설계 필요 여부 |

## 8. CLI Account Scope Impact Table

### 8.1 `paper.py`

| 명령 | `--account-id` 필요 여부 | 이유 | 권장 단계 |
|---|---|---|---|
| `prepare` | 권장 | prepare가 이후 plan/preview 흐름의 계좌 context를 정해야 함 | read-only 단계부터 |
| `preview` | 필수 | wrong account ledger/state를 읽으면 의미가 완전히 바뀜 | 1차 도입 |
| `commit` | 필수 | writer command이므로 account 오조작 위험 큼 | 1차 도입 |
| `status` | 필수 | dashboard/status는 계좌별로 봐야 함 | 1차 도입 |
| `weekly-status` | 필수 | weekly summary는 계좌별 집계여야 함 | 1차 도입 |
| `benchmark` | 필수 | benchmark baseline과 equity curve가 계좌 종속 | 1차 도입 |
| `plan` | 필수 | plan artifact가 계좌별로 달라질 수 있음 | 1차 도입 |
| `eod` | 필수 | writer/derived artifact 갱신이 계좌 종속 | 1차 도입 |
| `reports` | 필수 | reports chain이 계좌 root 전체를 읽고 씀 | 1차 도입 |
| `review` | 필수 | review chain이 계좌 review root를 다룸 | 1차 도입 |
| `review-template` | 필수 | template가 계좌 holdings/performance에 종속 | 1차 도입 |
| `review-validate` | 필수 | 어떤 account review template를 검증하는지 명확해야 함 | 1차 도입 |
| `review-append` | 필수 | writer command이므로 필수 | 1차 도입 |

결론:

- `paper.py` 계열은 사실상 전부 `--account-id` 대상이다.
- read-only라도 wrong account root를 읽으면 status/weekly/benchmark가 오염된다.

### 8.2 Notion 관련 CLI

| 명령 | `--account-id` 필요 여부 | 이유 | 권장 정책 |
|---|---|---|---|
| `scripts/export_paper_to_notion.py` | 필수 | external key/account summary/report export가 계좌 종속 | account_id 없으면 차단 또는 explicit default |
| `scripts/import_notion_executions.py` | 필수 | preview/commit이 계좌 ledger/cash/holdings를 읽음 | writer path 보호 위해 필수 |
| `scripts/import_notion_reviews.py` | 필수 | review template/log root가 계좌 종속 | writer path 보호 위해 필수 |
| `scripts/sync_notion_execution_status.py` | 필수 | commit report와 external key namespace가 계좌 종속이어야 함 | sidecar와 함께 account scope 확인 |
| `scripts/sync_notion_review_status.py` | 필수 | review commit report namespace가 계좌 종속 | sidecar와 함께 account scope 확인 |

결론:

- Notion import/export/sync는 계좌 구분이 없는 상태로 두면 row 충돌과 잘못된 sync 가능성이 크다.
- 따라서 `paper_default` fallback을 둘 수는 있어도, operator-visible CLI surface에는 `--account-id`를 두는 편이 안전하다.

## 9. Account Selection Precedence

권장 우선순위:

1. CLI `--account-id`
2. 환경변수 `STOCK_SCREENER_PAPER_ACCOUNT_ID`
3. account profile config의 default
4. fallback `paper_default`

### 권장 해석

- CLI가 가장 강하다.
- 자동화/배치 환경에서는 env var가 유용하다.
- config default는 운영 기본 계좌를 선언하는 용도다.
- 마지막 fallback은 backward compatibility 보존용이다.

### Notion 관련 CLI 정책

권장안:

- 초기 transition 단계에서는 `paper_default` fallback 허용 가능
- 그러나 non-dry-run writer/sync는 경고를 강하게 주거나 explicit `--account-id`를 요구하는 것이 안전하다

실무 권장:

```text
read-only status/report preview 계열:
  fallback paper_default 허용 가능

writer / sync 계열:
  explicit account_id 권장 또는 필수
```

## 10. Risks / Open Questions

### 주요 리스크

1. `PAPER_TEST_DIR`를 직접 import하는 모듈이 많아 resolver 도입 시 영향 범위가 넓다.
2. 일부 스크립트는 `paper_root` override를 이미 받지만, CLI surface가 이를 노출하지 않는다.
3. `dev_backups_dir()`가 공통 dir이기 때문에 filename namespace를 안 바꾸면 계좌 간 백업 구분이 흐려질 수 있다.
4. Notion external key를 account-aware로 바꾸기 전까지는 단일 DB에서 row 충돌 위험이 남는다.
5. tests 상당수가 `PAPER_TEST_DIR` 문자열 자체를 기대하고 있어 fixture 전략 재정비가 필요하다.

### Open questions

1. `paper_default` writer를 언제 legacy root에서 new root로 전환할지
2. `STOCK_SCREENER_PAPER_ACCOUNT_ID`를 전역 default로 쓰는 것이 안전한지
3. account profile config 파일을 어디에 둘지
4. `front_test`도 동일한 account-aware resolver 패턴으로 일반화할지
5. dry-run/report/status처럼 read-only인 명령도 explicit `--account-id`를 강제할지

## 11. Recommended Implementation MFUs

### MFU-PAPER15-3A

`account profile model / config skeleton`

범위:

- `account_id`, `display_name`, `currency`, `initial_cash`, `account_type`, `is_default`
- default account resolution
- env/config precedence skeleton

### MFU-PAPER15-3B

`account-aware path resolver implementation`

범위:

- legacy `paper_test` compatibility read path
- new `outputs/paper_accounts/{account_id}` resolver
- validation / error messages

### MFU-PAPER15-3C

`paper.py --account-id read-only command support`

범위:

- `status`
- `weekly-status`
- `benchmark`

이 3개를 먼저 account-aware로 만드는 것이 안전하다.

### MFU-PAPER15-3D

`writer command account guard design / implementation`

범위:

- `plan`
- `preview`
- `commit`
- `reports`
- `review*`

writer 계열은 explicit account guard가 필요하다.

### MFU-PAPER15-3E

`Notion external key account namespace design`

범위:

- account-aware external key 규칙
- account_id property policy
- sync/import/export sidecar namespace 정리

## 12. 결론

권장 방향은 아래와 같다.

- path resolver는 `paper_default legacy compatibility + new account root` 이중 지원이 필요하다.
- `core/paths.py`의 paper 계열 함수는 대부분 account-aware로 일반화돼야 한다.
- `paper.py`와 Notion import/export/sync CLI는 거의 전부 `--account-id` 영향을 받는다.
- precedence는 `CLI > env > config default > paper_default fallback`이 가장 현실적이다.
- 구현 순서는 read-only 계층부터 시작하고, writer와 Notion namespace는 그 다음 단계로 분리하는 것이 안전하다.

