# [TRD] MFU8-2: Action / Review / Warning Taxonomy 정리 기술 설계서 v1.0

## 1. 기술 목표

MFU8-2의 기술 목표는 `core/daily_plan_generator.py`에서 생성되는 front-test 리포트 항목을 다음 3가지 계층으로 명확히 분리하는 것이다.

```text
ACTION  = 확정 매매 지시
REVIEW  = 수동 검토 대상
WARNING = 정보성 경고 / 주의 항목
```

이 작업은 매매 정책 변경이 아니다.

특히 다음 정책은 변경하지 않는다.

- score 계산
- RS 계산
- target_state 계산
- rebalance 계산
- trailing stop 계산
- switching 계산
- buy/sell 정책
- stale/universe guard 정책

MFU8-2는 기존 판단 결과를 리포트와 journal에 더 안전하게 표시하는 작업이다.

## 2. 현재 구조 요약

현재 front-test 주요 흐름은 다음과 같다.

```text
generate_daily_plan()
→ current_state 로드
→ market_state 계산
→ build_screener_results()
→ 후보 정규화 및 RS 계산
→ target_state 생성
→ rebalance decision 계산
→ switching 평가
→ trailing stop 확인
→ action_items 생성
→ rebalance_review_items 생성
→ journal_rows 생성
→ format_markdown_report()
```

현재 이미 개선된 점:

```text
rebalance.symbol_diff_removed
→ immediate SELL이 아니라
→ rebalance_review_items / REVIEW_EXIT로 이동
```

남은 문제:

```text
- action/review/warning 분류 기준이 코드상 충분히 명확하지 않음
- 문자열 하드코딩 drift 가능성 있음
- warning 계층이 명확히 분리되어 있지 않음
- journal_rows가 action_items만 기반으로 생성된다는 규칙을 테스트/코드상 명확히 보호해야 함
```

## 3. 수정 허용 파일

### 허용

```text
core/daily_plan_generator.py
```

선택적으로 허용:

```text
core/types.py
```

단, `core/types.py`는 정말 필요한 경우에만 생성한다.

### 수정 금지

```text
core/backtest_engine.py
core/target_portfolio_state.py
core/decision_core.py
scripts/run_front_test.py
screener/screener.py
screener/data_manager.py
screener/data_collector.py
market_analyzer.py
config.py
```

### 금지 사항

```text
DB schema 변경 금지
output DB 수정 금지
trading policy 변경 금지
buy/sell/switch logic 변경 금지
target/rebalance 계산 변경 금지
score/RS 계산 변경 금지
journal header 변경 금지
외부 dependency 추가 금지
```

## 4. 상수 설계

## 4.1 최소 local constants 권장

Small Safe Fix 관점에서는 `core/types.py`를 새로 만들기보다, 우선 `core/daily_plan_generator.py` 상단에 local constants를 두는 방식이 가장 작다.

권장 예시:

```python
ACTION_BUY = "BUY"
ACTION_SELL = "SELL"

REVIEW_EXIT = "REVIEW_EXIT"

WARNING_STALE_HOLDING = "WARNING_STALE_HOLDING"
WARNING_UNIVERSE_REMOVED_HOLDING = "WARNING_UNIVERSE_REMOVED_HOLDING"
WARNING_STALE_CANDIDATE = "WARNING_STALE_CANDIDATE"
WARNING_RS_CALC_FAILED = "WARNING_RS_CALC_FAILED"
WARNING_DATA_INSUFFICIENT = "WARNING_DATA_INSUFFICIENT"
```

## 4.2 Enum 사용은 후순위

Enum을 쓰는 경우 예시:

```python
from enum import Enum

class ActionType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class ReviewReason(str, Enum):
    REVIEW_EXIT = "REVIEW_EXIT"

class WarningReason(str, Enum):
    STALE_HOLDING = "WARNING_STALE_HOLDING"
    UNIVERSE_REMOVED_HOLDING = "WARNING_UNIVERSE_REMOVED_HOLDING"
```

단, Enum 도입으로 report formatting이나 journal table 값이 바뀌면 안 된다.

따라서 MFU8-2에서는 local constants를 우선한다.

## 5. 데이터 구조 설계

## 5.1 action_items

확정 매매 지시만 포함한다.

구조:

```python
action_items.append({
    "type": ACTION_BUY or ACTION_SELL,
    "symbol": symbol,
    "shares": shares,
    "price": price,
    "reason": reason,
})
```

허용 reason:

```text
STRATEGY_ENTRY
TRAILING_STOP
SWITCH_OUT
SWITCH_IN
```

금지 reason:

```text
REVIEW_EXIT
WARNING_*
```

## 5.2 review_items 또는 rebalance_review_items

수동 검토 대상만 포함한다.

현재 `rebalance_review_items`가 이미 있다면 이름을 유지한다.  
새로운 일반 `review_items`로 바꾸는 것은 리팩토링 범위가 커질 수 있으므로 MFU8-2에서는 피한다.

구조:

```python
rebalance_review_items.append({
    "symbol": symbol,
    "shares": shares,
    "price": price,
    "reason": REVIEW_EXIT,
    "note": "Target portfolio에서 제외됨. 즉시 매도 지시가 아니라 수동 검토 대상.",
})
```

규칙:

```text
rebalance_review_items는 action_items에 병합하지 않는다.
rebalance_review_items는 journal_rows에 사용하지 않는다.
```

## 5.3 warning_items

새 list를 추가한다.

```python
warning_items = []
```

구조:

```python
warning_items.append({
    "symbol": symbol,
    "reason": WARNING_UNIVERSE_REMOVED_HOLDING,
    "severity": "MEDIUM",
    "note": "latest universe snapshot removed list에 포함되어 수동 확인 필요",
})
```

severity 후보:

```text
LOW
MEDIUM
HIGH
```

초기 기준:

```text
LOW    = 정보성
MEDIUM = 수동 확인 필요
HIGH   = 실행 전 반드시 확인
```

MFU8-2에서는 severity가 매매 판단을 바꾸지 않는다.  
표시용 필드로만 사용한다.

## 5.4 journal_rows

기존 로직을 유지한다.

```python
journal_rows = []
for item in action_items:
    journal_rows.append(...)
```

주의:

```text
review_items를 순회하지 않는다.
warning_items를 순회하지 않는다.
```

## 6. 리포트 렌더링 설계

## 6.1 `format_markdown_report()` 시그니처

현재 `rebalance_review_items`가 이미 전달되고 있다면 유지한다.

warning_items를 추가한다.

예시:

```python
def format_markdown_report(
    date_str: str,
    m_state: dict,
    cp_status: dict,
    action_items: List[dict],
    stop_alerts: List[dict],
    journal_rows: List[dict],
    rebalance_review_items: Optional[List[Dict[str, Any]]] = None,
    warning_items: Optional[List[Dict[str, Any]]] = None,
    ...
) -> str:
```

주의:

- 기존 인자 순서를 크게 바꾸지 않는다.
- optional 인자는 뒤쪽에 추가한다.
- 기존 호출부와 호환되게 default는 `None`으로 둔다.

## 6.2 섹션 순서

권장 순서:

```text
## 4. 확정 매매 지시 (Confirmed Actions)
## 4-0. 리밸런싱 검토 필요 (Not an Immediate Sell)
## 4-0-1. 경고 및 주의 항목 (Warnings)
## 4-1. 후보 필터 진단 (Candidate Filter Diagnostics)
## 5. 📝 프론트테스트 실행 기록 (Copy & Paste to Journal)
```

현재 `## 4-0`과 `## 4-1`이 이미 있다면, `## 4-0-1`을 그 사이에 삽입한다.

## 6.3 Warning section 예시

```markdown
## 4-0-1. 경고 및 주의 항목 (Warnings)

| Symbol | Severity | Reason | Note |
| :--- | :--- | :--- | :--- |
| AAPL | MEDIUM | WARNING_UNIVERSE_REMOVED_HOLDING | latest universe snapshot removed list에 포함되어 수동 확인 필요 |
```

warning이 없으면:

```markdown
| - | - | - | 경고 없음 |
```

또는:

```markdown
경고 없음.
```

표 형식이 parser에 영향이 없다면 표를 유지한다.

## 7. 기존 경고 항목 매핑

현재 코드에 존재하거나 존재할 수 있는 경고성 항목을 warning_items로 이동한다.

## 7.1 stale_holdings_alert

현재 `stale_holdings_alert`는 문자열 list로 관리된다.

MFU8-2에서는 가능하면 warning_items로 변환한다.

기존:

```python
stale_holdings_alert.append(s)
```

권장:

```python
warning_items.append({
    "symbol": s,
    "reason": WARNING_UNIVERSE_REMOVED_HOLDING,
    "severity": "MEDIUM",
    "note": "latest universe snapshot removed list에 포함되어 수동 확인 필요",
})
```

단, 기존 `stale_holdings_notice`가 리포트 상단에 필요하다면 유지해도 된다.  
중복 표시가 과하면 상단 notice는 유지하고 warning section에도 동일 정보를 표시하되, 후속 cleanup 대상으로 보고한다.

## 7.2 stale_exclusions

`stale_exclusions`는 후보 필터 진단과 연결되어 있으므로 MFU8-2에서 무리하게 warning_items로 옮기지 않는다.

기존 candidate diagnostics 흐름을 유지한다.

## 7.3 removed_candidate_exclusions

`removed_candidate_exclusions`도 후보 필터 진단 성격이 강하므로 기존 흐름을 유지한다.

필요하면 warning section에 요약만 추가할 수 있으나, scope가 커지면 보류한다.

## 8. 안전장치

## 8.1 journal contamination 방지

코드상 다음이 유지되어야 한다.

```python
for item in action_items:
    journal_rows.append(...)
```

금지:

```python
for item in rebalance_review_items:
    journal_rows.append(...)

for item in warning_items:
    journal_rows.append(...)
```

## 8.2 reason guard

가능하면 journal row 생성 직전 다음 방어 로직을 추가한다.

```python
if str(item.get("reason", "")).startswith("REVIEW") or str(item.get("reason", "")).startswith("WARNING"):
    raise ValueError("Review/Warning item must not enter journal_rows")
```

단, 실제 운영에서 예외로 front-test 전체가 멈추는 것이 부담되면 warning print로 대체한다.

권장:

```python
if reason.startswith("REVIEW") or reason.startswith("WARNING"):
    print(f"[WARN] Skipping non-action item from journal: {symbol} {reason}")
    continue
```

## 9. 검증 계획

## 9.1 Syntax / Import

```bash
python -m py_compile core/daily_plan_generator.py
python -c "import core.daily_plan_generator; print('daily_plan_generator import ok')"
```

## 9.2 Front-test smoke

```bash
python scripts/run_front_test.py
```

## 9.3 Report section check

```bash
python -c "from pathlib import Path; files=sorted(Path('outputs/front_test').glob('daily_action_plan_*.md')); p=files[-1]; txt=p.read_text(encoding='utf-8'); print(p); print('## 4. 확정 매매 지시' in txt); print('## 4-0. 리밸런싱 검토 필요' in txt); print('## 4-0-1. 경고 및 주의 항목' in txt); print('## 4-1. 후보 필터 진단' in txt); print('## 5. 📝 프론트테스트 실행 기록' in txt)"
```

## 9.4 Journal contamination check

```bash
python -c "from pathlib import Path; files=sorted(Path('outputs/front_test').glob('daily_action_plan_*.md')); p=files[-1]; txt=p.read_text(encoding='utf-8'); start=txt.find('## 5.'); journal=txt[start:] if start!=-1 else ''; print('REVIEW_EXIT in journal:', 'REVIEW_EXIT' in journal); print('WARNING_ in journal:', 'WARNING_' in journal)"
```

Expected:

```text
REVIEW_EXIT in journal: False
WARNING_ in journal: False
```

## 10. 구현 순서

1. `core/daily_plan_generator.py` 상단에 최소 constants 추가
2. `warning_items = []` 추가
3. stale/universe holding warning을 warning_items에 추가
4. `format_markdown_report()`에 `warning_items` optional 인자 추가
5. `## 4-0-1. 경고 및 주의 항목` section 추가
6. journal_rows가 action_items만 기반으로 생성되는지 확인
7. py_compile / import / run_front_test 검증
8. report section / journal contamination 검증

## 11. 완료 기준

- ACTION / REVIEW / WARNING의 내부 list가 분리된다.
- `REVIEW_EXIT`는 journal에 들어가지 않는다.
- `WARNING_*`는 journal에 들어가지 않는다.
- report에 warning section이 추가된다.
- 기존 확정 action section이 유지된다.
- 기존 review section이 유지된다.
- 기존 candidate diagnostics section이 유지된다.
- 기존 journal section과 header가 유지된다.
- trading policy는 변경되지 않는다.