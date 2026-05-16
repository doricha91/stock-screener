# MFU-PAPER7-1 Replay Reproducibility PRD

## 목적

사용자가 과거 날짜 paper daily plan을 다시 생성할 때, 현재 시스템이 어디까지 같은 결과를 재현할 수 있는지 명확히 이해하게 한다.

## 사용자 관점 요구사항

- 같은 날짜 plan 재생성 시 어떤 입력이 고정되는지 문서로 확인할 수 있어야 한다.
- 아직 고정되지 않은 입력과 결과 변동 가능성을 미리 알아야 한다.
- replay hardening의 최소 다음 단계가 무엇인지 알 수 있어야 한다.

## 현재 재현성 보강 범위

- paper account state as-of cutoff
  - daily plan 기준 `trade_date < plan_date`
- screener / indicator cutoff
  - `date <= plan_date`
- market_state DB write 방지
  - `write_log=False`
- final config snapshot 저장
- quarterly universe snapshot as-of 선택

## 현재 재현 불가 또는 미보장 범위

- 저장된 config snapshot replay 강제 적용 없음
- 저장된 universe metadata replay 강제 적용 없음
- plan input snapshot 통합 없음
- 동일 날짜 regeneration diff 자동 비교 없음
- DB 원본 변경에 대한 방어 없음
- full run timeout 리스크 존재

## replay 수준 정의

- Level 0: 기록 없음
- Level 1: 주요 입력 snapshot 저장
- Level 2: regeneration diff 비교
- Level 3: snapshot 기반 replay 강제 적용
- Level 4: 완전 감사 가능 replay

현재 위치:
- Level 1 일부 완료
- Level 2 이후 미완료

## PAPER7 최소 범위 제안

- PAPER7-1
  - 현재 재현성 수준 문서화
- PAPER7-2
  - same-date regeneration diff harness 최소안 조사 또는 구현

## 종료 기준

- PAPER7-1 완료
- PAPER7-2 완료 또는 보류 결정
- 이후 PAPER8 performance reporting으로 이동
