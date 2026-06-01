# MFU-PAPER13-1 작업 지시문: benchmark comparison 조사 및 설계

## 목적

PAPER13-1의 목표는 paper 성과를 SPY/QQQ/CASH benchmark와 비교하기 위한 데이터 소스, 기준일, 시작자산, 출력 구조, reset 정책을 조사하고 설계하는 것이다.

이번 단계는 조사/설계 전용이다.  
코드 구현, DB write, paper 원장 수정, reset 실행은 하지 않는다.

반드시 명시:

```text
이번 PAPER13-1은 benchmark comparison 조사 및 설계이며, 코드 구현, DB write, paper 원장 수정, reset 실행은 포함하지 않는다.
```

## 배경

PAPER11에서는 일일 운영 루프가 완성됐다.

```text
prepare
preview
commit
review
status
```

PAPER12에서는 weekly-status Markdown/JSON 리포트와 schema stabilization이 완료됐다.  
PAPER13에서는 paper 성과가 좋은지 나쁜지 판단하기 위한 benchmark comparison을 설계한다.

사용자 정책:

```text
1차 benchmark는 initial cash 기준 since-inception 비교로 시작한다.
period benchmark는 추후 확장한다.
월적립식 매수 benchmark도 추후 확장한다.
```

## 확정된 1차 정책

아래 정책을 기본 전제로 조사한다.

```text
benchmark symbols:
- SPY
- QQQ
- CASH

comparison mode:
- since_inception

starting capital:
- initial_cash

comparison dates:
- paper_account_snapshot.csv의 snapshot_date 기준

outputs:
- Markdown
- JSON

Notion 연동:
- 이번 단계 제외
```

## 조사 대상 파일

아래 파일과 모듈을 확인한다.

```text
outputs/paper_test/paper_account_snapshot.csv
outputs/paper_test/paper_position_snapshot.csv
outputs/paper_test/paper_execution_log.csv
outputs/paper_test/paper_current_state_*.json
outputs/market_data.db
core/paths.py
core/paper_status.py
core/paper_weekly_status.py
scripts/paper.py
scripts/generate_paper_weekly_status.py
market_analyzer.py
screener/data_manager.py
```

## 핵심 조사 질문

### 1. initial_cash source

아래 중 어디서 initial cash를 읽는 것이 가장 안전한지 조사한다.

```text
paper_current_state_*.json
paper_account_snapshot.csv
paper_execution_log.csv
config/default constant
기존 paper 초기화 로직
```

확인할 것:

```text
initial_cash가 명시적으로 저장되는 파일이 있는가?
paper_account_snapshot.csv에 initial_cash 컬럼이 있는가?
commit 출력에서 보이는 initial_cash: 100000.00이 어디서 오는가?
공식 paper 시작 시 initial_cash를 config로 고정해야 하는가?
```

### 2. official_start_date

benchmark 시작일을 어떻게 정할지 조사한다.

후보:

```text
첫 paper_account_snapshot.csv snapshot_date
첫 paper_execution_log.csv date
clean reset 이후 첫 snapshot_date
수동 설정한 official_start_date
```

권장안:

```text
clean reset 이후 첫 paper_account_snapshot.csv snapshot_date
```

단, 이번 단계에서는 reset을 실행하지 않고 정책만 정리한다.

### 3. clean reset 필요성

initial cash 기준으로 가기 위해 기존 paper 운용 데이터를 어떻게 처리할지 조사한다.

정리할 대상:

```text
paper_execution_log.csv
paper_account_snapshot.csv
paper_position_snapshot.csv
paper_current_state_*.json
daily_action_plan_*.md
reports/*
reviews/*
```

설계안 후보:

```text
A. 기존 데이터를 archive/reset_YYYYMMDD/로 이동 후 새 official run 시작
B. 기존 데이터를 유지하되 official_start_date 이후만 benchmark에 사용
C. benchmark config에 ignore_before 날짜를 둔다
```

이번 단계에서는 실행하지 말고 장단점과 권장안을 정리한다.

### 4. SPY/QQQ 가격 소스

`outputs/market_data.db`에서 benchmark 가격을 어디서 읽을지 조사한다.

확인할 것:

```text
market_index 테이블 존재 여부
SPY, QQQ symbol 존재 여부
date 컬럼 형식
close / adj_close / price 컬럼 여부
각 symbol별 MAX(date), MIN(date)
snapshot_date와 매칭 가능한가
```

정책 후보:

```text
1순위: adjusted close 계열 컬럼
2순위: close
3순위: 사용 가능한 market_index price 컬럼
```

컬럼명이 불명확하면 실제 schema를 조사해 TRD에 기록한다.

### 5. CASH benchmark 정의

CASH benchmark는 가격 데이터 없이 계산한다.

정책:

```text
CASH equity = initial_cash
return = 0
drawdown = 0
```

단, 이자/환율/예수금 수익은 이번 단계에서 제외한다.

### 6. paper equity 기준 컬럼

paper 성과 비교에 사용할 equity 컬럼을 조사한다.

권장:

```text
1순위: total_equity_market_value
fallback: total_equity_cost_basis
```

확인할 것:

```text
paper_account_snapshot.csv에 해당 컬럼들이 있는가
valuation_status 또는 market_valuation_status가 있는가
valuation_price_date가 있는가
```

### 7. 결측 처리 정책

snapshot_date에 SPY/QQQ 가격이 없을 경우 정책을 제안한다.

후보:

```text
A. 같은 날짜 가격 없으면 이전 거래일 가격 사용
B. 같은 날짜 없으면 해당 benchmark unavailable
C. 전체 리포트 FAIL
```

권장안:

```text
이전 거래일 가격 사용 가능 여부를 조사하되,
사용 시 price_date와 staleness_days를 JSON에 명시한다.
```

### 8. 성과 지표

PAPER13-2에서 구현할 최소 지표를 설계한다.

1차 후보:

```text
paper_start_equity
paper_end_equity
paper_return
benchmark_start_equity
benchmark_end_equity
benchmark_return
excess_return
paper_max_drawdown
benchmark_max_drawdown
latest_gap
```

초기 제외:

```text
CAGR
Sharpe
Sortino
Calmar
volatility
monthly DCA benchmark
period benchmark
```

이유:

```text
초기 snapshot row가 적으면 통계 지표는 의미가 약하다.
```

## 추천 산출물 설계

PAPER13-2 구현 시 후보 파일:

```text
outputs/paper_test/reports/paper_benchmark_comparison.md
outputs/paper_test/reports/paper_benchmark_comparison.json
```

JSON top-level 후보:

```json
{
  "schema_version": "paper_benchmark_comparison.v1",
  "generated_at": "...",
  "comparison_mode": "since_inception",
  "starting_capital_source": "initial_cash",
  "initial_cash": 100000.0,
  "official_start_date": "YYYY-MM-DD",
  "latest_snapshot_date": "YYYY-MM-DD",
  "benchmarks": [],
  "paper_series": [],
  "benchmark_series": [],
  "summary": {},
  "source_files": {},
  "limitations": []
}
```

## 추천 CLI 설계

PAPER13-2 구현 시 후보:

```text
python scripts/paper.py benchmark
python scripts/paper.py benchmark --json
python scripts/paper.py benchmark --symbols SPY QQQ
python scripts/paper.py benchmark --start YYYYMMDD --end YYYYMMDD
```

1차 구현 권장:

```text
python scripts/paper.py benchmark
python scripts/paper.py benchmark --json
```

`--start/--end`와 period benchmark는 추후 확장으로 둔다.

## 제외 범위

이번 단계에서 하지 않는다.

```text
benchmark 계산 구현
paper.py benchmark 추가
Markdown/JSON 생성
DB write
paper 원장 CSV 수정
clean reset 실행
archive 이동 실행
Notion 연동
HTML/CSV 생성
월적립식 benchmark 구현
period benchmark 구현
```

## 허용 사항

```text
파일 읽기
CSV header/row count 확인
SQLite schema 확인
SPY/QQQ 존재 여부 확인
날짜 컬럼 확인
설계 문서 작성
```

## 산출물

조사/설계 문서 작성:

```text
docs/TRD/mfu_paper13_1_benchmark_comparison_design.md
```

## 검증 명령

read-only 명령만 허용한다.

예:

```text
python scripts/paper.py status
python scripts/paper.py weekly-status --json
```

SQLite schema 확인은 read-only로만 수행한다.

금지:

```text
prepare 실행 금지
preview 실행 금지
commit 실행 금지
review 실행 금지
reset 실행 금지
DB write 금지
paper 원장 CSV 수정 금지
```

## 성공 기준

```text
initial_cash source 후보와 권장안이 정리된다.
official_start_date 기준이 정리된다.
clean reset 정책 후보가 정리된다.
SPY/QQQ 가격 소스와 컬럼이 확인된다.
paper equity 기준 컬럼이 정리된다.
결측 benchmark 가격 처리 정책이 제안된다.
PAPER13-2 구현 범위가 명확해진다.
Markdown/JSON 출력 schema 초안이 정리된다.
코드와 원장 파일은 수정하지 않는다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 조사한 파일
3. initial_cash source 조사 결과
4. official_start_date 권장안
5. clean reset 정책 후보
6. SPY/QQQ 가격 소스
7. paper equity 기준 컬럼
8. 결측 가격 처리 정책
9. 1차 benchmark 지표
10. 추천 CLI
11. 추천 산출물/JSON schema
12. 제외한 항목
13. 코드 변경 여부
14. paper 원장 CSV 변경 여부
15. outputs/front_test 변경 여부
16. 다음 단계 제안
```

반드시 명시:

```text
이번 PAPER13-1은 benchmark comparison 조사 및 설계이며, 코드 구현과 reset 실행은 포함하지 않는다.
```