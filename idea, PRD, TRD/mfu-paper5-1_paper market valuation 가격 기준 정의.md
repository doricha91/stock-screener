# MFU-PAPER5-1 작업 지시문: paper market valuation 가격 기준 정의

## 목적

paper_account_snapshot.csv는 현재 cost_basis 기준으로 저장된다.  
다음 단계에서 market value, unrealized PnL, performance report를 만들기 전에 “공식 평가 가격 기준”을 문서와 테스트 관점에서 먼저 정의한다.

이번 단계는 구현보다 정책 확정/문서화가 목적이다.

## 배경

현재 완료 상태:
- paper_execution_log.csv 원장화 완료
- PaperAccountState reducer 완료
- paper_current_state_YYYYMMDD.json 저장 완료
- paper_account_snapshot.csv cost_basis 저장 완료

아직 없는 것:
- market value
- unrealized PnL
- total market equity
- performance report
- benchmark 비교
- MDD / CAGR / Sharpe

## 이번 단계에서 결정할 것

1. 평가 가격 source
- 1순위 후보: 기존 DB daily_price
- 외부 yfinance 실시간 호출은 이번 단계에서 제외 권장
- 이유: 재현성, 테스트 안정성, 장마감 전/후 데이터 흔들림 방지

2. 평가일 기준
- snapshot_date의 해당 종목 종가를 사용
- 해당 날짜 가격이 없으면 가장 최근 거래일 종가를 사용할지, error 처리할지 결정

3. 가격 누락 정책
- A안: 누락 시 error로 중단
- B안: 최근 available close 사용
- C안: avg_price fallback 사용
권장: 이번 정책 문서에서는 B안 또는 A안을 명확히 선택하되, avg_price fallback은 성과 왜곡 위험이 있어 비추천

4. 휴장일/주말 처리
- snapshot_date가 비거래일이면 직전 거래일 종가를 사용할지 결정
- 단, 실제 EOD pipeline에서는 거래일 기준 실행을 원칙으로 한다

5. 저장 컬럼 후보
후속 MFU에서 추가할 수 있는 컬럼:
- positions_market_value
- total_equity_market_value
- unrealized_pnl
- unrealized_pnl_pct
- valuation_price_date
- valuation_method

6. 이번 단계 제외
- 실제 market value 계산 구현
- performance report 생성
- benchmark 비교
- MDD / CAGR / Sharpe
- DB schema 변경

## 산출물

문서 추가 또는 업데이트:
- idea/ 또는 PRD/TRD 하위에 MFU-PAPER5-1 가격 기준 정의 문서 작성

권장 문서명:
- PRD/mfu-paper5-1_market_valuation_policy_PRD.md
- TRD/mfu-paper5-1_market_valuation_policy_TRD.md

문서에 반드시 포함:
1. valuation 목적
2. price source
3. valuation date rule
4. missing price rule
5. holiday/weekend rule
6. excluded scope
7. 후속 MFU 목록

## 절대 금지

- outputs/front_test 수정 금지
- DB 파일 수정 금지
- paper_account_snapshot.csv 구조 변경 금지
- market value 계산 코드 추가 금지
- performance report 생성 금지
- yfinance 실시간 호출 추가 금지

## 성공 기준

- 가격 기준 정책이 문서화됨
- market value 계산에 필요한 의사결정 항목이 정리됨
- 구현은 하지 않음
- outputs/front_test 변경 없음
- DB 변경 없음
- 기존 테스트 영향 없음

## 결과 보고 형식

5,000자 이내로 보고한다.

포함할 항목:
1. Summary
2. 작성/수정 문서
3. 확정한 가격 기준
4. 누락 가격 처리 정책
5. 휴장일 처리 정책
6. 제외한 범위
7. 다음 MFU 제안