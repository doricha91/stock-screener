# Codex Task: MFU-PAPER4-4A current_state schema 조사

## 목표

`paper_current_state_YYYYMMDD.json`을 기존 front-test `current_state`와 호환되는 스키마로 저장하기 전에, 현재 코드가 기대하는 `current_state` 구조를 조사한다.

이번 단계는 **read-only 조사**다.  
코드 수정과 파일 write는 하지 않는다.

## 조사 대상

아래를 확인한다.

```text
outputs/front_test/current_state_*.json
core/portfolio_state_manager.py
core/daily_plan_generator.py
scripts/run_front_test.py
scripts/run_eod_update.py
```

필요하면 `current_state_snapshot_path()` 사용처도 확인한다.

## 확인할 것

1. 기존 `current_state_YYYYMMDD.json`의 실제 JSON 구조
2. 필수 필드
3. 선택 필드
4. cash 관련 필드명
5. positions 구조
6. highest_prices 구조
7. current_symbols 또는 holdings 관련 필드
8. total_equity가 저장되는지, 실행 중 계산되는지
9. front-test가 state에서 직접 읽는 필드
10. eod_update가 state에 쓰는 필드

## 특히 확인할 질문

아래 질문에 답한다.

```text
1. 기존 current_state는 dict인가, dataclass dump인가?
2. positions는 symbol -> object 구조인가, list 구조인가?
3. position에 shares / avg_price / highest_price가 들어가는가?
4. highest_prices는 별도 top-level dict인가?
5. cash는 어떤 이름으로 저장되는가?
6. initial_cash나 currency 필드가 기존 state에 있는가?
7. applied_trade_ids를 추가해도 기존 코드가 깨지지 않는가?
8. paper_current_state를 기존 current_state와 완전히 같은 구조로 만들려면 어떤 필드가 필요한가?
```

## 하지 말 것

이번 단계에서 금지:

```text
코드 수정
outputs 파일 수정
paper_current_state 생성
paper_execution_log 수정
DB 수정
run_paper_eod_update.py 수정
```

## 사용 가능한 read-only 명령

```powershell
git status --short
git grep "current_state"
git grep "highest_prices"
git grep "current_state_snapshot_path"
git grep "positions"
```

필요하면 특정 JSON 파일은 읽기만 한다.

## 보고 형식

아래 형식으로 보고한다.

```text
1. Summary
2. Files inspected
3. Existing current_state JSON schema
4. Required fields
5. Optional fields
6. Fields needed for paper_current_state
7. Compatibility risks
8. Recommended JSON schema for PAPER4-4B
9. Suggested next step
```

## 완료 기준

1. 기존 current_state 스키마가 정리됨
2. paper_current_state에 필요한 필드가 정리됨
3. 기존 코드 호환성 리스크가 정리됨
4. 어떤 파일도 수정하지 않음