# Small Safe Fix: 시장별 날짜 기준 helper 추가 및 data_collector.py 날짜 오류 방지

## 목적

`data_collector.py` 실행 시 yfinance에서 아래 오류가 발생하는 문제를 방지한다.

```text
start date cannot be after end date
```

원인:
- 현재 코드는 `datetime.today()` 기준으로 오늘 날짜를 판단한다.
- 사용 환경은 한국시간이지만 수집 대상은 미국주식이다.
- 한국시간으로는 오늘이어도, 미국장 기준으로는 아직 오늘 일봉이 확정되지 않았을 수 있다.
- 그 결과 `start_date`가 Yahoo에서 제공 가능한 마지막 일봉 날짜보다 뒤가 되어 오류가 발생한다.

이번 작업은 **시장별 날짜 기준 helper를 추가하고, 현재 미국주식 collector인 `screener/data_collector.py`에서 US 기준 날짜를 사용하도록 바꾸는 small safe fix**다.

---

## 핵심 원칙

1. `US/Eastern`을 `data_collector.py` 내부에 직접 하드코딩하지 않는다.
2. 시장별 날짜 기준 helper를 별도 파일로 분리한다.
3. 현재 `data_collector.py`는 미국주식 collector로 보고 `region="US"`를 사용한다.
4. 향후 한국주식 collector는 별도 파일에서 `region="KR"`을 사용할 수 있게 한다.
5. 이번 작업에서 한국주식 collector는 만들지 않는다.
6. DB schema는 변경하지 않는다.
7. data collector 전체 리팩토링은 하지 않는다.
8. yfinance 호출 구조를 대규모로 바꾸지 않는다.

---

# 작업 범위

## 1. `core/market_time.py` 추가

신규 파일:

```text
core/market_time.py
```

아래 내용을 추가한다.

```python
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo


MARKET_TIMEZONE_BY_REGION = {
    "US": "US/Eastern",
    "KR": "Asia/Seoul",
    "JP": "Asia/Tokyo",
    "UTC": "UTC",
}


def get_market_today(region: str = "US") -> date:
    normalized_region = region.upper()
    timezone_name = MARKET_TIMEZONE_BY_REGION.get(normalized_region, "UTC")
    return datetime.now(ZoneInfo(timezone_name)).date()


def parse_date_yyyy_mm_dd(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def should_skip_download_start_date(
    start_date: str,
    region: str = "US",
    market_today: date | None = None,
) -> tuple[bool, str]:
    """
    Return whether a yfinance download should be skipped because start_date is
    not before the current market date for the target region.

    This prevents requesting today's not-yet-finalized daily bar.
    """
    start_dt = parse_date_yyyy_mm_dd(start_date)
    effective_market_today = market_today or get_market_today(region)

    if start_dt >= effective_market_today:
        return True, (
            f"start_date={start_date} is not before market_today={effective_market_today} "
            f"for region={region}. Today's market data may not be finalized."
        )

    return False, ""
```

---

## 2. `screener/data_collector.py`에 helper 적용

파일:

```text
screener/data_collector.py
```

상단 import에 추가한다.

```python
from core.market_time import should_skip_download_start_date
```

---

## 3. `update_market_indices()`의 날짜 체크 수정

기존 로직 중 아래와 비슷한 부분을 찾는다.

```python
if start_date > datetime.today().strftime('%Y-%m-%d'):
    print(f" - {symbol}: 이미 최신입니다.")
    continue
```

이를 아래처럼 바꾼다.

```python
should_skip, skip_reason = should_skip_download_start_date(start_date, region="US")
if should_skip:
    print(
        f" - {symbol}: 이미 최신이거나 오늘 미국장 데이터는 아직 확정 전입니다. "
        f"({skip_reason})"
    )
    continue
```

목적:

- `start_date == 미국 동부 기준 오늘`이면 yfinance 요청을 건너뛴다.
- `start_date > 미국 동부 기준 오늘`이어도 건너뛴다.
- 기존처럼 미래 날짜를 요청하지 않는다.

---

## 4. `update_stock_data()`에도 같은 로직 적용

`update_stock_data()` 안에서도 아래와 비슷한 로직을 찾는다.

```python
if start_date > datetime.today().strftime('%Y-%m-%d'):
    continue
```

아래처럼 변경한다.

```python
should_skip, skip_reason = should_skip_download_start_date(start_date, region="US")
if should_skip:
    print(
        f"[{i + 1}/{len(tickers)}] {ticker}: 이미 최신이거나 오늘 미국장 데이터는 아직 확정 전입니다. "
        f"({skip_reason})"
    )
    continue
```

주의:

- 현재 `data_collector.py`는 미국주식 중심 collector이므로 `region="US"`를 사용한다.
- 한국주식 collector는 이번 작업에서 만들지 않는다.

---

# 테스트 추가

## 신규 테스트 파일

```text
tests/test_market_time.py
```

## 테스트 케이스

### 1. `get_market_today()` 반환 타입 확인

```python
from datetime import date
from core.market_time import get_market_today

def test_get_market_today_returns_date():
    assert isinstance(get_market_today("US"), date)
    assert isinstance(get_market_today("KR"), date)
```

### 2. unknown region은 UTC fallback

```python
from datetime import date
from core.market_time import get_market_today

def test_get_market_today_unknown_region_fallback():
    assert isinstance(get_market_today("UNKNOWN"), date)
```

### 3. `start_date == market_today`이면 skip

```python
from datetime import date
from core.market_time import should_skip_download_start_date

def test_skip_when_start_date_equals_market_today():
    should_skip, reason = should_skip_download_start_date(
        "2026-05-08",
        region="US",
        market_today=date(2026, 5, 8),
    )

    assert should_skip is True
    assert "start_date=2026-05-08" in reason
```

### 4. `start_date > market_today`이면 skip

```python
from datetime import date
from core.market_time import should_skip_download_start_date

def test_skip_when_start_date_after_market_today():
    should_skip, _ = should_skip_download_start_date(
        "2026-05-09",
        region="US",
        market_today=date(2026, 5, 8),
    )

    assert should_skip is True
```

### 5. `start_date < market_today`이면 skip하지 않음

```python
from datetime import date
from core.market_time import should_skip_download_start_date

def test_do_not_skip_when_start_date_before_market_today():
    should_skip, reason = should_skip_download_start_date(
        "2026-05-07",
        region="US",
        market_today=date(2026, 5, 8),
    )

    assert should_skip is False
    assert reason == ""
```

---

# 검증 명령

아래 명령을 실행한다.

```powershell
$env:PYTHONPATH="."; python -m pytest tests/test_market_time.py -q
$env:PYTHONPATH="."; python -m py_compile core/market_time.py screener/data_collector.py
```

가능하면 실제 collector도 실행한다.

```powershell
$env:PYTHONPATH="."; python screener/data_collector.py
```

실행 시 기대:

- `start date cannot be after end date` 오류가 더 이상 발생하지 않아야 한다.
- DB가 이미 최신이고 미국장 오늘 데이터가 아직 확정 전이면 다운로드를 건너뛰어야 한다.
- 예시 메시지:

```text
SPY: 이미 최신이거나 오늘 미국장 데이터는 아직 확정 전입니다.
QQQ: 이미 최신이거나 오늘 미국장 데이터는 아직 확정 전입니다.
```

---

# 하지 말 것

이번 작업에서 하지 말 것:

1. 한국주식 collector 추가
2. `data_collector.py` 전체 리팩토링
3. `data_collector.py` 파일명 변경
4. DB schema 변경
5. yfinance 호출 구조 대규모 변경
6. 시장 휴장일 calendar 구현
7. `preflight_check.py` 수정
8. 프론트테스트/paper-test 로직 수정
9. 백테스트 로직 수정

---

# Acceptance Criteria

완료 조건:

1. `core/market_time.py`가 추가된다.
2. `get_market_today(region)`이 시장별 timezone 기준 날짜를 반환한다.
3. `should_skip_download_start_date()`가 `start_date >= market_today`일 때 skip한다.
4. `screener/data_collector.py`의 `update_market_indices()`가 해당 helper를 사용한다.
5. `screener/data_collector.py`의 `update_stock_data()`가 해당 helper를 사용한다.
6. 현재 미국주식 collector에서는 `region="US"`를 사용한다.
7. 기존 DB schema와 front-test/paper-test 흐름은 변경하지 않는다.
8. `tests/test_market_time.py`가 통과한다.
9. `py_compile`이 통과한다.
10. 가능하면 실제 `data_collector.py` 실행에서 yfinance 날짜 역전 오류가 사라진다.

---

# 보고 형식

작업 완료 후 아래 형식으로 보고한다.

```text
1. Summary
2. Changed files
3. Behavior changes
4. Tests run
5. Tests not run and why
6. Risks and limitations
7. Suggested next step
```

특히 다음을 명확히 보고한다.

- `US/Eastern`을 직접 하드코딩했는지 여부
- 향후 KR collector에서 `region="KR"`로 확장 가능한지 여부
- `data_collector.py`에서 어떤 날짜 체크를 교체했는지
- 실제 yfinance 날짜 오류가 재현/해결됐는지 여부