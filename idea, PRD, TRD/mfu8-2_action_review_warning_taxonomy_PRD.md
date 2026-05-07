# [PRD] MFU8-2: Action / Review / Warning Taxonomy 정리 v1.0

## 0. Context & Status

### 배경

MFU8의 전체 목표는 백테스트에 추가한 전략, 유니버스, 매매 판단이 프론트테스트에도 누락 없이 반영되는 체계를 만드는 것이다.

MFU8-1은 동일 `data_date` / 동일 `symbol` 기준으로 backtest-like와 fronttest-like 산출값인 `score`, `rs_val`, `buy/entry signal`을 비교하는 검증 자동화가 목적이다.

MFU8-2는 그 다음 단계로, front-test 리포트에서 표시되는 판단 항목을 다음 3가지로 명확히 분리한다.

```text
ACTION  = 확정 매매 지시
REVIEW  = 수동 검토 대상
WARNING = 정보성 경고 / 주의 항목
```

최근 front-test에서는 `rebalance.symbol_diff_removed` 기반 `STRATEGY_EXIT`가 immediate SELL에서 `REVIEW_EXIT`로 낮춰졌다. 이 변경은 실전 오매도 위험을 줄였지만, 앞으로 action/review/warning의 분류 기준이 명확하지 않으면 다시 drift가 발생할 수 있다.

### 현재 확인된 문제

- `BUY`, `SELL`, `REVIEW_EXIT` 같은 문자열이 코드와 리포트에 흩어질 수 있다.
- 어떤 항목이 journal row에 들어가야 하는지 기준이 명확하지 않다.
- `REVIEW_EXIT`는 수동 검토 대상인데, 향후 실수로 action/journal에 들어갈 위험이 있다.
- stale holding, universe removed holding, low buying power 등은 확정 action이 아니라 warning/review로 표시되어야 한다.
- front-test 리포트가 실제 매매 참고자료로 쓰이려면 “즉시 실행”과 “검토 필요”가 명확히 분리되어야 한다.

## 1. 목표

MFU8-2의 목표는 front-test 리포트와 내부 action item 생성 과정에서 다음 분류 체계를 확립하는 것이다.

```text
1. ACTION
   - 실제 매매 지시로 해석 가능한 항목
   - journal row에 포함 가능

2. REVIEW
   - 매매 여부를 사람이 검토해야 하는 항목
   - journal row에 포함하지 않음

3. WARNING
   - 데이터, 유니버스, 현금, 정책 관련 주의 항목
   - journal row에 포함하지 않음
```

이 단계는 trading policy를 바꾸지 않는다.  
이 단계는 report/action taxonomy를 정리하는 작업이다.

## 2. 범위

### In-Scope

- front-test action/review/warning 분류 기준 정의
- `core/daily_plan_generator.py` 내 action/review/warning 문자열 최소 상수화
- `REVIEW_EXIT`가 journal row에 들어가지 않도록 보장
- warning/review section을 리포트에서 명확히 분리
- 기존 report section과 journal header 유지
- action item과 review item의 내부 데이터 구조 기준 정의
- EOD update 또는 journal 복사/붙여넣기에서 혼동되지 않도록 출력 형식 정리

### Out-of-Scope

- backtest sell policy 변경
- front-test sell policy 변경
- `target_state` / `rebalance` 계산 변경
- `symbol_diff_removed` 계산 변경
- score / RS 계산 변경
- strategy signal 계산 변경
- broker 주문 연동
- DB schema 변경
- run_eod_update.py 구조 변경
- PortfolioDB와 current_state snapshot 통합
- full action execution engine 통합

## 3. 사용자 시나리오

### Scenario 1: 확정 매매가 있는 날

사용자는 Daily Action Plan을 확인한다.

리포트의 `## 4. 확정 매매 지시` 섹션에는 실제로 실행 가능한 BUY/SELL만 표시된다.

예:

```text
BUY NVDA | STRATEGY_ENTRY
SELL TSLA | TRAILING_STOP
SELL AAPL | SWITCH_OUT
```

이 항목들은 journal row에 들어갈 수 있다.

### Scenario 2: 리밸런싱 검토 대상이 있는 날

AAPL이 target portfolio에서 제외되었지만, 백테스트의 직접 SELL 경로와 일치하지 않는다.

리포트에는 다음처럼 표시된다.

```text
## 4-0. 리밸런싱 검토 필요
AAPL | REVIEW_EXIT
```

이 항목은 즉시 매도 지시가 아니며, journal row에 들어가지 않는다.

### Scenario 3: 경고 항목이 있는 날

보유 종목이 유니버스 removed list에 들어가거나 stale data 가능성이 있다.

리포트에는 다음처럼 표시된다.

```text
## 4-0-1. 경고 및 주의 항목
AAPL | WARNING_UNIVERSE_REMOVED_HOLDING
```

이 항목은 매매 지시가 아니며, journal row에 들어가지 않는다.

## 4. Taxonomy 정의

## 4.1 ACTION

ACTION은 즉시 실행 가능한 매매 지시다.

### ACTION Type

```text
BUY
SELL
```

### ACTION Reason 후보

```text
STRATEGY_ENTRY
TRAILING_STOP
SWITCH_OUT
SWITCH_IN
```

### Journal 포함 여부

```text
포함 가능
```

### 조건

ACTION은 다음 조건을 만족해야 한다.

- 백테스트 실행 경로와 의미상 대응 가능해야 한다.
- 매매 방향이 명확해야 한다.
- 수량과 기준 가격이 있어야 한다.
- 사용자가 journal에 복사해도 실제 매매 기록으로 오해되지 않아야 한다.

## 4.2 REVIEW

REVIEW는 매매 여부를 사람이 검토해야 하는 항목이다.

### REVIEW Reason 후보

```text
REVIEW_EXIT
TARGET_REMOVAL_ALERT
MANUAL_REVIEW_REQUIRED
```

### Journal 포함 여부

```text
포함하지 않음
```

### 조건

REVIEW는 다음 경우에 사용한다.

- target portfolio에서 제외되었지만 백테스트 직접 SELL 경로와 일치하지 않는 경우
- 전략 정책상 판단이 필요한 경우
- 확정 SELL로 표시하면 과도한 매도 위험이 있는 경우
- 사람이 추가 정보를 보고 판단해야 하는 경우

## 4.3 WARNING

WARNING은 정보성 경고 또는 데이터/운영 주의 항목이다.

### WARNING Reason 후보

```text
WARNING_STALE_HOLDING
WARNING_UNIVERSE_REMOVED_HOLDING
WARNING_STALE_CANDIDATE
WARNING_LOW_BUYING_POWER
WARNING_RS_CALC_FAILED
WARNING_DATA_INSUFFICIENT
```

### Journal 포함 여부

```text
포함하지 않음
```

### 조건

WARNING은 다음 경우에 사용한다.

- 데이터 신선도 문제가 있는 경우
- 유니버스 편출 가능성이 있는 경우
- RS 계산이 실패한 경우
- 현금 부족으로 주문이 생성되지 않은 경우
- 후보가 필터링되었지만 매매 지시가 아닌 경우

## 5. 데이터 구조 요구사항

## 5.1 action_items

`action_items`는 확정 매매 지시만 담는다.

필수 필드:

```python
{
    "type": "BUY" | "SELL",
    "symbol": str,
    "shares": int,
    "price": float,
    "reason": str,
}
```

허용 reason 예시:

```text
STRATEGY_ENTRY
TRAILING_STOP
SWITCH_OUT
SWITCH_IN
```

금지:

```text
REVIEW_EXIT
WARNING_*
```

## 5.2 review_items

`review_items`는 수동 검토 대상만 담는다.

필수 필드:

```python
{
    "symbol": str,
    "shares": int,
    "price": float,
    "reason": "REVIEW_EXIT" | "TARGET_REMOVAL_ALERT" | ...,
    "note": str,
}
```

주의:

- `review_items`는 `action_items`에 들어가면 안 된다.
- `review_items`는 `journal_rows`에 들어가면 안 된다.

## 5.3 warning_items

`warning_items`는 정보성 경고만 담는다.

필수 필드:

```python
{
    "symbol": str | None,
    "reason": str,
    "severity": "LOW" | "MEDIUM" | "HIGH",
    "note": str,
}
```

주의:

- `warning_items`는 `action_items`에 들어가면 안 된다.
- `warning_items`는 `journal_rows`에 들어가면 안 된다.

## 5.4 journal_rows

`journal_rows`는 `action_items`에서만 생성한다.

필수 원칙:

```text
journal_rows = confirmed action only
```

금지:

```text
REVIEW_EXIT를 journal_rows에 넣지 않는다.
WARNING_*를 journal_rows에 넣지 않는다.
```

## 6. 리포트 섹션 요구사항

기존 report section은 유지한다.

권장 섹션 순서:

```text
## 4. 확정 매매 지시 (Confirmed Actions)
## 4-0. 리밸런싱 검토 필요 (Review Only)
## 4-0-1. 경고 및 주의 항목 (Warnings)
## 4-1. 후보 필터 진단 (Candidate Filter Diagnostics)
## 5. 프론트테스트 실행 기록 (Copy & Paste to Journal)
```

### 6.1 확정 매매 지시

- `action_items`만 표시한다.
- action이 없으면 “오늘 실행할 확정 매매 없음”을 표시한다.

### 6.2 리밸런싱 검토 필요

- `review_items`만 표시한다.
- 즉시 매도 지시가 아니라는 안내 문구를 포함한다.
- 검토 대상이 없으면 “검토 대상 없음”을 표시한다.

### 6.3 경고 및 주의 항목

- `warning_items`만 표시한다.
- 경고가 없으면 “경고 없음”을 표시한다.
- severity를 표시한다.

### 6.4 Journal

- `journal_rows`만 표시한다.
- 기존 journal header를 유지한다.

기존 header:

```text
Date | Regime | Symbol | Type | Rec_Shares | Rec_Price | Act_Shares | Act_Price | Reason | Notes
```

## 7. 수용 기준

1. `REVIEW_EXIT`는 `action_items`에 들어가지 않는다.
2. `REVIEW_EXIT`는 `journal_rows`에 들어가지 않는다.
3. `WARNING_*` 항목은 `action_items`에 들어가지 않는다.
4. `WARNING_*` 항목은 `journal_rows`에 들어가지 않는다.
5. `TRAILING_STOP` SELL은 기존처럼 확정 action으로 남는다.
6. `SWITCH_OUT` SELL은 기존처럼 확정 action으로 남는다.
7. `SWITCH_IN` BUY는 기존처럼 확정 action으로 남는다.
8. `STRATEGY_ENTRY` BUY는 기존처럼 확정 action으로 남는다.
9. 기존 markdown report section과 journal header는 유지된다.
10. `python scripts/run_front_test.py` 실행이 성공해야 한다.
11. action/review/warning 분리 후에도 EOD update가 journal rows를 오해하지 않아야 한다.
12. action/reason 문자열 상수화가 기존 리포트 출력을 깨지 않아야 한다.

## 8. 비기능 요구사항

- DB write 금지
- DB schema 변경 금지
- 외부 dependency 추가 금지
- broker 관련 코드 변경 금지
- 기존 CLI behavior 유지
- 기존 report/journal 포맷 유지
- trading policy 변경 금지
- look-ahead bias 유발 금지
- action/review/warning drift를 줄이기 위한 최소 상수화 허용

## 9. 검증 명령

```bash
python -m py_compile core/daily_plan_generator.py
python -c "import core.daily_plan_generator; print('daily_plan_generator import ok')"

python scripts/run_front_test.py
```

리포트 확인:

```bash
python -c "from pathlib import Path; files=sorted(Path('outputs/front_test').glob('daily_action_plan_*.md')); p=files[-1]; txt=p.read_text(encoding='utf-8'); print(p); print('## 4. 확정 매매 지시' in txt); print('## 4-0. 리밸런싱 검토 필요' in txt); print('## 4-1. 후보 필터 진단' in txt); print('## 5. 📝 프론트테스트 실행 기록' in txt); print('Date | Regime | Symbol | Type | Rec_Shares | Rec_Price | Act_Shares | Act_Price | Reason | Notes' in txt)"
```

REVIEW/WARNING journal 오염 확인:

```bash
python -c "from pathlib import Path; files=sorted(Path('outputs/front_test').glob('daily_action_plan_*.md')); p=files[-1]; txt=p.read_text(encoding='utf-8'); start=txt.find('## 5.'); journal=txt[start:] if start!=-1 else ''; print('REVIEW_EXIT in journal:', 'REVIEW_EXIT' in journal); print('WARNING_' in journal)"
```

## 10. 후속 단계

MFU8-2 완료 후 다음을 진행한다.

- MFU8-3: SELL path parity 검증
- MFU8-4: 신규 전략 추가 체크리스트 및 자동 검증 강화
- MFU8-5: 신규 유니버스 추가 체크리스트 및 universe parity 검증