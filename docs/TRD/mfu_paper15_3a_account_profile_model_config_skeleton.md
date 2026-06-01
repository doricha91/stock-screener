# MFU-PAPER15-3A Account Profile Model / Config Skeleton

## 1. Purpose

이번 PAPER15-3A는 account profile model / config skeleton 구현이며, path resolver 적용, paper CLI account scope 적용, DB write, paper 원장 수정, Notion write/export, migration 구현은 포함하지 않는다.

이 문서는 다중계좌 도입 전 단계로, 이후 path resolver와 CLI scope가 참조할 수 있는 최소 account profile 계층을 정리한다.

## 2. Scope / Non-scope

### Scope

- `PaperAccountProfile` dataclass 추가
- `PaperAccountProfileConfig` dataclass 추가
- `account_id` validation 함수 추가
- example config skeleton 추가
- read-only loader / resolver 추가
- account profile 단위 테스트 추가

### Non-scope

- `core/paths.py` account-aware 적용
- `paper.py --account-id` 적용
- writer command account guard
- Notion external key namespace 변경
- CSV migration

## 3. Account Profile Schema

최소 core 필드:

- `account_id`
- `display_name`
- `currency`
- `initial_cash`
- `account_type`
- `is_default`

선택 profile/reference 필드:

- `strategy_profile`
- `universe_profile`
- `benchmark_profile`
- `notion_profile`

기본 계좌:

- `account_id = paper_default`
- `display_name = Paper Default`
- `currency = USD`
- `initial_cash = 100000.0`
- `account_type = paper`
- `is_default = true`

## 4. Validation Policy

`account_id` regex:

```text
^[a-z0-9][a-z0-9_-]{2,63}$
```

reserved id:

- `default`
- `paper_test`
- `front_test`
- `reports`
- `reviews`
- `archive`
- `config`
- `outputs`

config validation policy:

- `default_account_id`는 반드시 존재해야 한다.
- `default_account_id`는 `accounts` 안의 실제 `account_id`와 매칭되어야 한다.
- duplicate `account_id`는 허용하지 않는다.
- `is_default=true`는 정확히 1개만 허용한다.
- `is_default=true` account는 `default_account_id`와 일치해야 한다.

## 5. Default Account Policy

config 파일이 없고 `allow_missing=True`이면 loader는 `paper_default` 단일 계좌 구성을 반환한다.

이 fallback은 PAPER15-1 / 15-2에서 확정한 legacy compatibility와 맞물린다.

- legacy `outputs/paper_test`
- logical account id `paper_default`

## 6. Backward Compatibility

이번 단계에서는 artifact migration을 하지 않는다.

호환 전략:

- profile config가 없어도 기존 단일계좌 환경은 `paper_default`로 해석 가능
- 이후 3B path resolver와 3C CLI scope는 이 default profile을 참조해 legacy root를 읽게 된다

## 7. Next MFU Dependency

후속 권장 순서:

1. `PAPER15-3B`: account-aware path resolver implementation
2. `PAPER15-3C`: read-only `paper.py --account-id` support
3. `PAPER15-3D`: writer command account guard
4. `PAPER15-3E`: Notion account namespace design
