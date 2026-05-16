# MFU-PAPER6 Final Summary

## 목적

PAPER6에서 완성한 official paper-test 운영 루프를 한 번에 정리하고, PAPER7 이후 phase로 안전하게 넘기기 위한 기준 문서다.

## 왜 paper_state를 공식 source of truth로 삼았는가

- `front_state`는 관찰용 sandbox라서 실운용 기준 계좌로 쓰기 어렵다.
- `paper_state`는 `outputs/paper_test/paper_execution_log.csv + reducer`로 재구성 가능해 state lineage가 명확하다.
- dry-run, commit, snapshot, replay 검토까지 같은 source를 공유할 수 있다.

## front_state / paper_state 역할 구분

- `front_state`
  - 기존 front-test 호환
  - 관찰용 sandbox
  - official paper account 아님
- `paper_state`
  - 공식 paper-test 계좌
  - daily plan / EOD / snapshot / continuity 검증 기준

## PAPER6 완료 후 확보한 운영 가치

- paper 계좌 기준 daily plan 생성 가능
- paper daily plan을 EOD dry-run / commit 루프로 연결
- duplicate append 방지와 paper virtual fill reason 추적 가능
- daily plan 재생성 시 account/screener/market/universe 입력의 as-of 재현성 기반 확보
- final config snapshot과 market/universe metadata를 남겨 이후 replay hardening의 출발점 마련

## 최종 완료 범위

1. paper 계좌 기반 daily plan 생성
2. paper daily plan → EOD dry-run 연결
3. `run_paper_eod_update.py` 기본 input을 paper daily plan으로 전환
4. `Rec_Shares / Rec_Price -> Act_Shares / Act_Price` fallback
5. `paper_virtual_fill` source/reason 기록
6. controlled commit smoke 성공
7. multi-day paper continuity 검증
8. switch 후보군을 backtest `buy_signal=True` 기준으로 정렬
9. same-day duplicate BUY 방지
10. daily plan용 paper account state as-of cutoff
11. screener/indicator `plan_date` cutoff
12. `market_status_log` write 방지
13. final config snapshot 저장
14. quarterly universe snapshot as-of 선택

## 확정 정책

- paper daily plan account state
  - `trade_date < plan_date`
- EOD/report state
  - commit 이후 상태 반영
  - 기존 EOD 의미 유지
- screener/indicator
  - `date <= plan_date` 데이터만 사용
- market_state
  - `get_market_state(target_date=plan_date, write_log=False)`
  - DB `market_status_log`에는 쓰지 않음
  - config snapshot JSON에 저장
- config snapshot
  - `outputs/paper_test/config_snapshots/paper_config_snapshot_YYYYMMDD.json`
  - regime 적용 후 final config 저장
  - 같은 날짜는 archive 후 replace
- universe snapshot
  - 같은 분기 내 `plan_date` 이하 최신 snapshot 우선
  - 없으면 이전 분기 이하 최신 snapshot + warning
  - `plan_date` 이후 snapshot 사용 금지
- switching
  - `max_positions` full gate 없음
  - `target_long_slots` gate 없음
  - switch-in 후보는 `buy_signal=True`만 허용
  - same-day duplicate BUY 금지

## 완료 상태

| MFU | 상태 | 핵심 결과 | 남은 리스크 |
| --- | --- | --- | --- |
| PAPER6-1~6-2 | Done | paper daily plan 진입점과 state provider 분리 | front/paper/live 통합 entrypoint는 아직 없음 |
| PAPER6-4A~6-4B | Done | symbol mapping/date normalize 안정화 | compact/dashed 정책의 다른 CLI 적용은 별도 |
| PAPER6-5~6-6C | Done | paper plan → EOD dry-run/parser/virtual fill 루프 연결 | preview 문구 세부 표현은 추가 정리 가능 |
| PAPER6-7 | Done | controlled commit smoke 성공 | 더 많은 날짜/케이스 운영 검증 필요 |
| PAPER6-8 | Done | multi-day continuity 확인 | 더 긴 기간 continuity는 아직 제한적 |
| PAPER6-9A~9C | Done | switch parity와 duplicate BUY 방지 | policy 변경 시 backtest/paper 재동기화 필요 |
| PAPER6-9D~9F | Done | account/screener as-of cutoff | 완전 replay는 아직 아님 |
| PAPER6-9G~9I | Done | market log write 방지, final config snapshot, quarterly universe as-of | config snapshot replay와 universe generation as-of는 미구현 |

## 남은 한계

- config snapshot을 replay 입력으로 강제 적용하지 않는다.
- universe snapshot 생성 시점 자체를 historical 기준으로 고정하지 않는다.
- full `run_paper_daily_plan.py`는 여전히 universe-wide screening으로 timeout 리스크가 있다.
- 동일 날짜 재생성 diff를 자동 비교하는 replay harness는 아직 없다.

## 다음 phase 제안

- PAPER7: replay / reproducibility hardening
  - 저장된 config snapshot replay 적용 여부 결정
  - plan input snapshot 통합
  - 동일 날짜 plan 재생성 diff 비교
  - full run timeout 개선 / fast mode
- PAPER8: paper performance reporting
  - equity curve
  - drawdown
  - MDD
  - benchmark 비교 전 기초 리포트
- PAPER9: trade analytics
  - closed position
  - realized trade journal
  - 종목별 성과 분석
