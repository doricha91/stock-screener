# MFU-PAPER7-1 Replay Reproducibility Scope

## PAPER7의 목적

PAPER7은 paper-test 기능을 더 늘리는 단계가 아니다.  
핵심은 같은 날짜 daily plan을 나중에 다시 만들었을 때 결과가 달라지면, 무엇이 고정됐고 무엇이 아직 변할 수 있는지 추적 가능하게 만드는 것이다.

## 현재 재현 가능한 것

| 항목 | 현재 상태 | 근거 | 한계 |
| --- | --- | --- | --- |
| paper account state | as-of 가능 | `trade_date < plan_date` | EOD 상태와 의미 구분 필요 |
| screener / indicator | cutoff 가능 | `date <= plan_date` | full run timeout 리스크 남음 |
| market_state | DB write 없이 계산 | `write_log=False` | 저장된 snapshot replay 강제 적용은 없음 |
| config | snapshot 저장 | regime 적용 후 `final_config` 저장 | replay 시 강제 적용 안 함 |
| universe | as-of 선택 | quarterly policy | snapshot 생성 정책 자체는 별도 |

## 아직 재현 보장되지 않는 것

- 현재 코드가 바뀌면 같은 날짜 plan 결과가 바뀔 수 있다.
- config snapshot은 저장되지만 replay 입력으로 강제되지 않는다.
- universe metadata는 저장되지만 replay 입력으로 강제되지 않는다.
- plan input snapshot이 통합되어 있지 않다.
- DB 데이터 자체가 수정되면 과거 plan도 달라질 수 있다.
- full `run_paper_daily_plan.py`는 timeout 리스크가 있다.

## replay 수준 정의

- Level 0: 기록 없음
- Level 1: 주요 입력 snapshot 저장
- Level 2: 같은 날짜 regeneration diff 비교
- Level 3: snapshot 기반 replay 강제 적용
- Level 4: 완전 감사 가능 replay

현재 상태:
- Level 1 일부 완료
- Level 2 미구현
- Level 3 미구현

## PAPER7 최소 범위

- PAPER7-1
  - 현재 재현성 수준 문서화
- PAPER7-2
  - 동일 날짜 daily plan regeneration diff를 비교하는 최소 harness 조사 또는 구현
- PAPER7 이후
  - 필요할 때 snapshot 기반 replay 강제 적용 검토

## PAPER8로 넘길 기준

- PAPER7-1 문서화 완료
- PAPER7-2 최소 diff harness 완료 또는 보류 결정
- 이후 PAPER8 performance reporting으로 이동

## 메모

- PAPER6에서 확보한 것은 “재현성 기반”이지 완전 replay 시스템은 아니다.
- PAPER7은 범위를 좁게 유지해야 한다. replay hardening이 성과 리포트 개발을 장기간 막아서는 안 된다.
