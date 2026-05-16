# MFU-PAPER7-1 Replay Reproducibility TRD

## 현재 기준점

PAPER6 종료 시점에 paper daily plan은 아래 입력을 일부 as-of로 고정한다.

- account state
  - `core/paper_state_provider.py`
  - `trade_date < plan_date`
- screener / indicator
  - `screener/screener.py`
  - `end_date=plan_date`
- market_state
  - `market_analyzer.get_market_state(target_date=plan_date, write_log=False)`
- config snapshot
  - `core/paper_config_snapshot.py`
- universe snapshot
  - `core/universe_manager.py`
  - quarterly as-of selection

## 현재 재현 가능 범위

- account state는 plan_date 직전 상태로 재구성 가능
- screener / indicator는 plan_date 이후 데이터를 차단 가능
- market_state는 DB log 오염 없이 재계산 가능
- final config와 market/universe metadata는 snapshot으로 저장 가능

## 현재 한계

- code snapshot은 저장하지 않는다
- config snapshot을 replay 입력으로 강제 적용하지 않는다
- universe metadata를 replay 입력으로 강제 적용하지 않는다
- plan input snapshot이 하나로 묶여 있지 않다
- regeneration diff harness가 없다
- DB 데이터 자체 변경을 차단하지 않는다
- full `run_paper_daily_plan.py`는 timeout 병목이 남아 있다

## replay 수준 정의

- Level 0
  - 기록 없음
- Level 1
  - account/config/market/universe 주요 입력 기록
- Level 2
  - 동일 날짜 regeneration diff 비교
- Level 3
  - 저장된 snapshot 기반 입력 강제 적용
- Level 4
  - 완전 감사 가능 replay

현재 위치:
- Level 1 일부 완료

## PAPER7-2로 넘길 기술 질문

- 최소 diff harness는 어떤 입력과 산출물을 비교해야 하는가
- full run timeout 없이 helper 수준 diff가 가능한가
- replay mode를 만들기 전에 어떤 snapshot을 필수 입력으로 묶어야 하는가

## PAPER8로 넘길 기준

- PAPER7-1 문서화 완료
- PAPER7-2 최소 diff harness 완료 또는 보류 결정
- 이후 performance reporting phase로 이동
