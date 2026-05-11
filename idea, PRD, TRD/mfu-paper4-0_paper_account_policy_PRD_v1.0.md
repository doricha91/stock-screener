# MFU-PAPER4-0 Paper Account Policy PRD v1.0

## 1. 목적

`paper_execution_log.csv`를 기반으로 독립적인 paper account state를 만들기 전에,
초기 자본, 포지션 시작 상태, 거래 반영 규칙, 방어 정책을 명확히 확정한다.

이번 MFU의 목표는 정책 문서화이며, production code 구현은 포함하지 않는다.

## 2. 초기 상태

초기 paper account는 live/front-test state를 복사하지 않고, 완전히 독립적인 가상계좌로 시작한다.

- `initial_cash`: `100000.0`
- `currency`: `USD`
- `positions`: `{}`
- `applied_trade_ids`: empty
- `fee/slippage/tax`: `0`

정책상 paper account는 다음을 전제로 한다.

- live/front-test `current_state_YYYYMMDD.json`을 초기 state로 복사하지 않는다.
- live/front-test `execution_log.csv`를 직접 수정하지 않는다.
- paper account의 상태는 paper 전용 산출물로만 관리한다.

## 3. Trade 처리 정책

paper account는 `paper_execution_log.csv` 또는 이에 준하는 paper trade source를 순서대로 읽어 상태를 갱신한다.

### BUY

- `cash` 감소
- `shares` 증가
- 동일 종목 추가 매수 시 `avg_price`는 가중평균으로 갱신

### SELL

- `cash` 증가
- `shares` 감소

### 전량 SELL

- 종목의 `shares`가 0이 되면 해당 position 제거

### Duplicate 방지

- 이미 적용된 `trade_id`는 skip
- 동일한 `trade_id`를 중복 반영하지 않는다.

## 4. 방어 정책

paper account는 아래 조건을 에러로 처리한다.

- 현금 부족 상태에서 BUY 시도
- 보유 수량을 초과하는 SELL 시도
- `price <= 0`
- `shares == 0`

추가 안전 원칙:

- paper/live 경로는 계속 분리한다.
- paper state는 `outputs/paper_test/` 아래에서만 관리한다.
- live/front-test 파일에 write하지 않는다.

## 5. Non-goals

이번 단계에서 구현하지 않는 것:

- `paper_current_state_YYYYMMDD.json` 저장 구현
- `paper_account_snapshot.csv` 구현
- `paper_performance_report_*.md` 구현
- 수수료/슬리피지/세금 반영
- live/front-test `current_state` 복사
- `scripts/run_eod_update.py` 수정

## 6. 구현 경계

이번 MFU-PAPER4-0는 정책 문서화 단계다.

따라서 다음은 이번 범위에서 금지한다.

- Python production code 수정
- DB schema 수정
- `outputs/` 아래 산출물 수정
- `paper_execution_log.csv` 수정
- `run_paper_eod_update.py` 수정

## 7. 완료 기준

이번 문서 기준 완료 조건:

1. paper account 초기 정책이 문서화된다.
2. 초기 자본 `$100,000`이 명시된다.
3. live/front-test state를 복사하지 않는다고 명시된다.
4. 이번 단계에서 production code 변경이 없다.
5. 이번 단계에서 output/generated artifact 변경이 없다.
