# MFU-PAPER9-1 작업 지시문: closed trade / realized trade journal 사전 조사

## 기준

브랜치: gemini_cli_update  
기준 SHA: c6ed2bce27a8f08afc64c882d8c7abe05849c303

이번 단계는 구현이 아니라 조사 전용이다.  
목표는 paper_execution_log.csv와 reducer 구조를 분석해서, PAPER9-2에서 closed trade journal / realized trade journal을 안전하게 만들 수 있는지 판단하는 것이다.

## 배경

PAPER8까지는 계좌 단위 성과 리포팅을 완료했다.

완료된 공식 산출물:
- outputs/paper_test/reports/paper_equity_curve.csv
- outputs/paper_test/reports/paper_drawdown.csv
- outputs/paper_test/reports/paper_performance_summary.md

PAPER9부터는 계좌 단위가 아니라 거래/종목 단위 성과 분석으로 넘어간다.

우선 조사할 대상:
- outputs/paper_test/paper_execution_log.csv
- core/paper_account_state.py
- core/paper_execution_log.py
- scripts/run_paper_eod_update.py
- core/paper_account_snapshot.py
- core/paper_position_snapshot.py
- 기존 PAPER8 관련 report generation script

## 조사 목적

아래 질문에 답할 수 있어야 한다.

1. paper_execution_log.csv의 실제 컬럼과 BUY/SELL row 구조는 무엇인가?
2. BUY shares는 양수, SELL shares는 음수로 일관되는가?
3. trade_id는 closed trade linking에 사용할 만큼 안정적인가?
4. 현재 reducer가 open position만 계산하는지, closed trade까지 계산 가능한 구조인지 확인한다.
5. 현재 실현손익은 어느 함수에서 어떤 방식으로 계산되는가?
6. FIFO 방식인지, average cost 방식인지 확인한다.
7. partial SELL과 full SELL이 현재 어떻게 처리되는지 확인한다.
8. realized_pnl_by_symbol은 있지만, 거래별 realized_pnl 기록이 없는지 확인한다.
9. closed trade journal 생성을 위해 추가로 필요한 컬럼/계산값을 정의한다.
10. PAPER9-2 구현 전에 리팩토링이 필요한지, 독립 스크립트로 충분한지 판단한다.

## 조사 범위

읽기 전용으로만 진행한다.

허용:
- 코드 읽기
- CSV 헤더/샘플 row 확인
- reducer 흐름 분석
- 문서/리포트 작성
- 테스트 없이 py_compile 수준 확인 가능

금지:
- paper_execution_log.csv 수정 금지
- paper_account_snapshot.csv 수정 금지
- paper_position_snapshot.csv 수정 금지
- outputs/front_test 수정 금지
- DB 수정 금지
- --commit 실행 금지
- closed trade journal 생성 금지
- realized trade journal 생성 금지
- symbol performance CSV 생성 금지
- 대규모 리팩토링 금지

## 권장 산출물

조사 리포트만 생성한다.

추천 경로:
- docs/TRD/mfu_paper9_1_closed_trade_journal_investigation.md

또는 기존 문서 체계와 맞다면:
- docs/PRD/mfu_paper9_trade_level_performance_PRD_v0.1.md
- docs/TRD/mfu_paper9_1_closed_trade_journal_investigation_TRD_v0.1.md

이번 단계에서는 outputs/paper_test/reports/ 아래에 성과 CSV를 만들지 않는다.  
성과 report가 아니라 구현 전 조사 문서이기 때문이다.

## 리포트에 반드시 포함할 내용

1. Summary
2. 확인한 파일 목록
3. paper_execution_log.csv 컬럼 목록
4. BUY/SELL row 샘플 구조
5. 현재 reducer 흐름 요약
6. realized_pnl 계산 위치
7. realized_pnl 계산 방식
   - FIFO인지
   - average cost인지
   - 기타 방식인지
8. partial SELL 처리 방식
9. full SELL 처리 방식
10. 현재 구조로 closed trade journal 생성이 가능한지
11. 불가능하거나 애매한 부분
12. PAPER9-2에서 추가할 것을 권장하는 함수/스크립트
13. closed trade journal 후보 컬럼
14. symbol performance 후보 컬럼
15. 구현 리스크
16. 다음 단계 제안

## 특히 검증할 핵심 포인트

현재 구조가 average cost 기반이라면 명확히 적는다.

예상되는 closed trade journal 최소 후보 컬럼:
- close_date
- symbol
- shares_closed
- entry_price_basis
- exit_price
- realized_pnl
- realized_return_pct
- holding_days
- close_trade_id
- source
- reason

단, open_date와 holding_days는 현재 execution_log만으로 정확히 산출 가능한지 별도 검증한다.  
평균단가 방식에서 여러 BUY가 섞여 있으면 단일 open_date 정의가 애매할 수 있으므로, 이 한계를 반드시 문서화한다.

## 권장 명령

```bat
set PYTHONPATH=.

python -m py_compile core/paper_account_state.py
python -m py_compile core/paper_execution_log.py
python -m py_compile scripts/run_paper_eod_update.py
```

필요 시 read-only 확인:

```bat
python scripts/run_paper_eod_update.py --date 20260513 --allow-empty-journal
```

단, --commit은 절대 사용하지 않는다.

## 성공 기준

- closed trade journal 구현 전에 필요한 구조 조사가 완료된다.
- 현재 realized PnL 계산 방식이 명확히 정리된다.
- FIFO / average cost 여부가 명확히 정리된다.
- partial SELL / full SELL 처리 방식이 문서화된다.
- PAPER9-2 구현 범위가 과도하게 커지지 않도록 최소 구현 방향이 제안된다.
- 어떤 파일도 수정하지 않는다.
- outputs/front_test를 수정하지 않는다.

## 결과 보고 형식

5천자 이내로 보고한다.

포함:
1. Summary
2. 조사한 파일
3. 현재 구조 판단
4. realized PnL 계산 방식
5. closed trade journal 가능 여부
6. 애매하거나 위험한 부분
7. PAPER9-2 추천 구현안
8. 변경 파일 여부
9. 실행한 명령과 결과