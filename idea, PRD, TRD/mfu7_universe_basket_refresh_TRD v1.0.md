# [TRD] MFU7: 유니버스 바스켓 주기 갱신 및 티커 위생 관리 기술 설계서 v1.0

## 1. 아키텍처 역할 (Architecture & Role)
이 MFU는 전략 점수 계산을 바꾸지 않고, 유니버스와 시세 데이터의 신선도를 관리하는 운영 계층을 추가하는 데 목적이 있다. 핵심 역할은 다음 3가지다.

- **유니버스 바스켓 동기화**: 원천 지수 구성 종목과 로컬 `tickers` 상태의 차이를 주기적으로 점검
- **stale 티커 감지**: `data_date` 기준 최신 가격이 오래된 종목을 식별
- **프론트테스트 보호**: stale 후보가 최종 판단 레이어에 들어가지 않도록 차단

## 2. 주요 모듈 및 책임 (Key Modules)

### 2.1 `screener/data_collector.py`
- 현재 역할:
  - 유니버스 종목 목록 수집
  - `daily_price` 업데이트
- 관찰 사항:
  - `df.empty` 시 `"데이터 없음"` 출력 후 계속 진행
  - inactive/delisted 상태를 저장하지 않음
- MFU7 관점:
  - 바스켓 갱신 실행 시점의 입력 소스로 재사용 가능
  - 단, 이번 초안에서는 DB 스키마 변경 없이 보고 기능 중심으로 시작

### 2.2 `screener/data_manager.py`
- 현재 역할:
  - `tickers` 목록 조회
  - `daily_price` 조회
- 관찰 사항:
  - `get_ticker_list()`는 사실상 `tickers` 전체를 그대로 반환
  - freshness / active 상태 필터가 없음
- MFU7 관점:
  - stale 계산용 read-only 조회 경로로 활용

### 2.3 `screener/screener.py`
- 현재 역할:
  - 각 ticker의 `df.iloc[-1]`를 최신 행으로 간주해 점수 계산
- 리스크:
  - latest row가 `data_date`와 멀어도 후보가 될 수 있음
- MFU7 관점:
  - 장기적으로 전역 freshness guard를 붙일 주요 위치
  - 단기적으로는 front-test 보호보다 영향 범위가 큼

### 2.4 `core/daily_plan_generator.py`
- 현재 역할:
  - front-test용 최종 후보 정리 및 action plan 생성
- MFU7 관점:
  - stale 후보를 front-test 최종 후보에서 제외하는 1차 보호 위치
  - 운영자에게 제외 사유를 리포트로 보여주는 관찰성 지점

## 2.5 신규 모듈 후보

### `core/universe_manager.py`

역할:
- 최신 바스켓 수집 결과 정규화
- 기존 tickers와 비교
- added / removed / kept 계산
- active universe snapshot 생성

### `scripts/update_universe.py`

역할:
- 운영자 실행 진입점
- 기본은 dry-run
- DB 수정 없이 summary 출력

## 3. 데이터 흐름 설계 (Data Flow)

### 3.1 바스켓 갱신 흐름
1. 원천 바스켓 목록 수집
2. 현재 `tickers` 목록과 비교
3. 신규 편입 / 이탈 / 유지 집합 계산
4. stale 티커 목록 병합
5. 운영 리포트 생성

### 3.2 stale 감지 흐름
1. `data_date` 결정
2. ticker별 `latest_price_date = max(daily_price.date)` 조회
3. `stale_days = data_date - latest_price_date`
4. `stale_days > threshold`면 stale 분류
5. front-test에서는 제외, 관리 리포트에는 기록

### 3.3 Universe Snapshot Format

초기 저장 경로:
outputs/universe/universe_snapshot_YYYYMMDD.json
예시:
{
  "as_of": "2026-05-04",
  "sources": {
    "SP500": ["AAPL", "MSFT"],
    "NASDAQ100": ["AAPL", "NVDA"]
  },
  "active_symbols": ["AAPL", "MSFT", "NVDA"],
  "added": ["..."],
  "removed": ["DAY"],
  "kept": ["AAPL"],
  "stale_summary": {
    "threshold_days": 7,
    "stale_count": 13
  }
}

## 4. 초기 기술 기준 (Initial Technical Policy)

### 4.1 stale 기준
- **1차 기준**: `stale_days > 7` calendar days
- 이유:
  - 주말/휴일 흡수 가능
  - 구현 단순
  - front-test 보호 목적에 충분

### 4.2 fix 위치 우선순위
1. `core/daily_plan_generator.py`
   - front-test만 안전하게 보호
   - 영향 범위 최소
2. `screener/screener.py`
   - stale 후보의 전역 노출 자체를 줄임
   - 다른 워크플로 영향도 함께 검토 필요
3. universe / ticker state 관리
   - 가장 근본적이나 범위 큼

## 5. 알려진 제약 (Known Limitations)
- `tickers` 스키마에 inactive/delisted 상태 필드가 없음
- 현재는 calendar days 기준 stale 계산만 상정
- 외부 바스켓 구성 변경과 로컬 DB 반영 시차가 존재할 수 있음
- 데이터 공급 실패와 실제 상장폐지를 자동 구분하지 못함

### 5.1 Backtest 주의사항
- 현재 바스켓 기준 active universe를 과거 백테스트에 그대로 적용하면 survivorship bias가 발생할 수 있다.
- 따라서 MFU7의 universe refresh는 우선 front-test/live-like 운영용으로 제한한다.
- 백테스트에서 historical membership을 사용하려면 별도의 MFU와 데이터 정책이 필요하다.

## 6. 검증 계획 (Validation Plan)
- read-only stale 분포 보고
- front-test 실행 시 stale 후보 제외 여부 확인
- 유니버스 바스켓 변경 리포트에서 신규/이탈/유지 집합 확인
- stale 제외가 전략 점수 공식, cash policy, hedge policy를 바꾸지 않았는지 확인

## 7. 후속 확장 포인트 (Next Steps)
- `tickers` 상태 필드 도입 검토
- 수집 실패 누적 횟수 기반 inactive 후보 제안
- `screener/screener.py`의 최신 행 freshness guard 적용
- 거래일 기준 stale 계산 고도화
