# Front-Test 운영 절차서 (Front-test SOP)
**StockScreener: 실전 운용 전 점검 및 실행 가이드**

> **목적**: 백테스트로 검증한 로직을 front-test로 운영할 때,  
> 데이터 최신성, 포트폴리오 상태 스냅샷, 시장 국면 계산이 모두 정상인지 먼저 확인하고,  
> 그 이후에만 `run_front_test.py`를 실행하도록 표준 절차를 정리합니다.

---

## Phase 0: 최초 1회 세팅 또는 복구 시
다음 항목은 매일 반복이 아니라, **처음 세팅할 때** 또는 **snapshot이 없을 때** 실행합니다.

1. **초기 현재 상태(snapshot) 생성**
   - `current_state_YYYYMMDD.json`이 없으면 preflight의 `State Integrity`가 blocked 됩니다.
   - 최초 1회 아래 스크립트를 실행합니다.

   ```powershell
   $env:PYTHONPATH="."; python scripts/init_front_test_state.py
   ```

2. **DB 테이블 구조 확인**
   - 일반적으로 운영 중 반복 실행할 필요는 없지만, DB 초기화/복구 시 필요할 수 있습니다.
   - `data_processor.py`도 내부에서 `database.create_tables()`를 호출합니다.

---

## Phase 1: 장 시작 전 루틴 (Pre-Market)
**수행 시간: 08:00 ~ 09:00**

preflight가 PASS 되려면 최소한 아래 3가지가 준비되어 있어야 합니다.

- `daily_price` 최신화
- `daily_indicators` 최신화
- 최신 `current_state` snapshot 존재

### 1-1. 가격 데이터 최신화
`daily_price`와 일부 시장 데이터가 최신이어야 합니다.

```powershell
$env:PYTHONPATH="."; python screener/data_collector.py
```

### 1-2. 보조지표 최신화
**중요**: preflight의 `Data Freshness`는 현재 `daily_indicators` 최신일을 기준으로 판단합니다.  
즉, `daily_price`만 최신이어도 `daily_indicators`가 stale이면 blocked 됩니다.

```powershell
$env:PYTHONPATH="."; python data_processor.py
```

### 1-3. 유니버스 스냅샷 갱신 (권장)
preflight의 직접 PASS 조건은 아니지만, stale/removed 종목 차단 품질에 영향을 줍니다.

```powershell
$env:PYTHONPATH="."; python scripts/update_universe.py
```

### 1-4. preflight 단독 점검
front-test 본 실행 전에 checklist만 따로 점검합니다.

```powershell
$env:PYTHONPATH="."; python -m core.preflight_check
```

체크 항목:
- `Data Freshness`
- `State Integrity`
- `Regime Logic`

### 1-5. Action Plan 생성
preflight가 PASS 되면 아래를 실행합니다.

```powershell
$env:PYTHONPATH="."; python scripts/run_front_test.py
```

### 1-6. 생성된 계획서 확인
`outputs/front_test/daily_action_plan_YYYYMMDD.md`를 확인합니다.

중점 확인 항목:
- **1. 오늘의 시장 국면 및 정책**
- **3. 실시간 조건부 매도 감시 (Trailing Stop)**
- **4. 확정 매매 지시**
- **4-0. 리밸런싱 검토 필요**
- **4-1. 후보 필터 진단**

> [!IMPORTANT]
> `Data Freshness [BLOCKED]`가 뜨면,  
> 먼저 `screener/data_collector.py`와 `data_processor.py`가 모두 실행됐는지 확인해야 합니다.  
> 특히 `daily_price`는 최신인데 `daily_indicators`만 오래된 경우에도 blocked 됩니다.

---

## Phase 2: 장중 루틴 (Market Open)
**수행 시간: 09:30 ~ 15:30**

1. **자동 감시 설정**
   - 계획서의 **[3. Trailing Stop]** 가격을 기준으로 HTS/MTS에 감시 주문을 설정합니다.

2. **확정 매매만 즉시 실행**
   - **[4. 확정 매매 지시]** 섹션에 있는 항목만 즉시 매매 대상으로 봅니다.
   - **[4-0. 리밸런싱 검토 필요]** 섹션은 즉시 매도 지시가 아니라 **수동 검토 대상**입니다.

3. **Active Switching 처리**
   - `SWITCH_OUT`, `SWITCH_IN`이 있을 경우에만 계획서 지시에 따라 순차적으로 처리합니다.

> [!WARNING]
> `REVIEW_EXIT`는 즉시 매도 주문이 아닙니다.  
> backtest의 실제 sell execution과 1:1로 대응되지 않을 수 있으므로 수동 판단이 필요합니다.

---

## Phase 3: 장 마감 후 루틴 (Post-Market)
**수행 시간: 장 마감 직후**

1. **실행 기록 작성**
   - `Daily Action Plan` 하단의 journal 섹션에 실제 체결 수량/가격을 기록합니다.

2. **EOD 상태 업데이트**
   - 다음 날 preflight의 `State Integrity`를 위해 최신 snapshot을 저장합니다.

   ```powershell
   $env:PYTHONPATH="."; python scripts/run_eod_update.py
   ```

3. **현금/체결 반영 확인**
   - `run_eod_update.py` 실행 중 실제 체결 결과와 현금 차이를 정확히 반영합니다.

> [!WARNING]
> 이 단계를 건너뛰면 다음 날 `current_state`가 오래되거나 어긋나서  
> `State Integrity`는 PASS 하더라도 실제 운용 상태와 front-test 추천이 불일치할 수 있습니다.

---

## Phase 4: 주간 점검 (Weekend Review)
**수행 시간: 매주 주말**

1. **리뷰 리포트 생성**

```powershell
$env:PYTHONPATH="."; python scripts/run_review.py --days 7
```

2. **점검 포인트**
- 지시 준수 여부
- 슬리피지
- 불필요한 turnover 여부
- REVIEW/WARNING 항목이 반복적으로 발생하는지

---

## Preflight 기준 요약

### 1. Data Freshness
- 기준 소스: `daily_indicators`
- 허용 기준: **EST 현재일 대비 4일 이하 차이**
- 필요 작업:
  1. `python screener/data_collector.py`
  2. `python data_processor.py`

### 2. State Integrity
- 기준 소스: `outputs/front_test/current_state_YYYYMMDD.json`
- 필요 작업:
  - 최초 1회: `python scripts/init_front_test_state.py`
  - 이후 매일 장 마감 후: `python scripts/run_eod_update.py`

### 3. Regime Logic
- `market_analyzer.get_market_state()`가 정상 계산되어야 함
- 사실상 아래 데이터가 최신이어야 정상 동작:
  - `daily_price`
  - `daily_indicators`
  - `market_index`

---

## blocked / warning 대응표

| 증상 | 원인 가능성 | 우선 실행 코드 |
| :--- | :--- | :--- |
| `Data Freshness [BLOCKED]` | `daily_indicators` stale | `python screener/data_collector.py` → `python data_processor.py` |
| `No current_state file found` | snapshot 없음 | `python scripts/init_front_test_state.py` |
| snapshot old warning | `run_eod_update.py` 누락 | `python scripts/run_eod_update.py` |
| `Regime calculation error` | 지표/시장 데이터 부족 | `python screener/data_collector.py` → `python data_processor.py` |

---

## 핵심 명령어 모음

```powershell
# 1) 가격 데이터 업데이트
$env:PYTHONPATH="."; python screener/data_collector.py

# 2) daily_indicators 업데이트
$env:PYTHONPATH="."; python data_processor.py

# 3) 유니버스 스냅샷 업데이트 (권장)
$env:PYTHONPATH="."; python scripts/update_universe.py

# 4) preflight 단독 점검
$env:PYTHONPATH="."; python -m core.preflight_check

# 5) front-test 실행
$env:PYTHONPATH="."; python scripts/run_front_test.py

# 6) 장 마감 후 snapshot 갱신
$env:PYTHONPATH="."; python scripts/run_eod_update.py
```
