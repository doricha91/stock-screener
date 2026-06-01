# PAPER15-3D: Writer Command Account Guard

## 1. Purpose

이번 PAPER15-3D는 writer path를 account-aware root로 바꾸기 전에, writer 또는 writer-like command가 다중계좌 환경에서 위험하게 실행되지 않도록 account guard를 추가하는 작업이다.

## 2. Scope / Non-scope

포함:
- writer account guard 모듈 추가
- `paper.py plan`, `paper.py eod`, `paper.py commit`, `paper.py review-append`에 `--account-id` 추가
- handler 진입 전 `paper_default` 허용 / non-default 차단

제외:
- writer path를 `outputs/paper_accounts/{account_id}`로 연결하는 작업
- `core/paths.py` 기존 writer path 변경
- paper 원장 migration
- Notion external key 변경
- Notion write/export 구조 변경

## 3. Writer Command Risk

현재 writer 계열은 여전히 single-account / legacy path 전제다.

대표 리스크:
- non-default account를 받아도 실제 write는 legacy `outputs/paper_test`로 갈 수 있음
- account context 없이 writer가 실행되면 다른 계좌와 artifact가 충돌할 수 있음
- path resolver가 read-only command에만 연결된 상태에서 writer를 먼저 풀면 잘못된 write를 허용할 수 있음

## 4. Guard Policy

기본 정책:
- `account_id` 생략 시 `paper_default`
- `paper_default`는 writer 허용
- non-default account는 기본 차단
- guard 결과는 아래를 포함
  - `account_id`
  - `account_root`
  - `legacy_default_used`
  - `command_name`
  - `write_allowed`
  - `message`

## 5. paper_default Behavior

`paper_default`는 기존 legacy writer 동작을 유지한다.

의미:
- 실제 writer path는 이번 단계에서 바꾸지 않는다.
- `paper_default`는 기존 `outputs/paper_test` 기반 write를 계속 허용한다.
- 다만 실행 전 guard message로 계좌 context를 명시한다.

## 6. Non-default Blocking Policy

non-default account는 이번 단계에서 차단한다.

차단 이유:
- 아직 writer path가 account-aware root로 바뀌지 않았다.
- `paper_default` 이외 계좌 write를 열면 cross-account overwrite 위험이 있다.
- 실제 account-aware write는 PAPER15-3F에서 다룬다.

## 7. Notion Writer / Sync Future Policy

이번 3D에서는 Notion 관련 script 코드를 바꾸지 않는다.

후속 정책:
- Notion actual write / sync는 `--account-id` 명시를 강하게 요구
- non-default account는 PAPER15-3E / 3F 이후에만 허용
- account namespace 없는 external key write는 장기적으로 금지

## 8. Relationship to PAPER15-3F

이번 단계는 write 허용 범위를 안전하게 제한하는 pre-guard 단계다.

다음 단계인 PAPER15-3F에서:
- writer path를 실제 account-aware root에 연결하고
- non-default account write 허용 조건을 다시 정의해야 한다.
