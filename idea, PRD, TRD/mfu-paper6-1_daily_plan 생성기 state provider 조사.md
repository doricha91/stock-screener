# MFU-PAPER6-1 작업 지시문: daily plan 생성기 state provider 조사

## 목적

현재 `run_front_test.py`와 daily plan 생성 로직이 어떤 계좌 state를 기준으로 동작하는지 조사한다.

이번 MFU의 핵심 전제는 아래와 같다.

```text
front_state = 관찰용 sandbox
paper_state = 공식 paper 계좌
```

따라서 목표는 front_state와 paper_state를 동등하게 동기화하는 것이 아니다.  
목표는 daily plan 생성 로직에서 `account_state_provider`를 분리하고, 지속적인 paper-test에서는 `paper_execution_log.csv + reducer` 기반 paper_state를 공식 source of truth로 사용할 수 있는지 확인하는 것이다.

이번 단계는 조사/설계 단계이며, production code 변경은 원칙적으로 하지 않는다.

## 현재 설계 결정

1. paper 계좌 source of truth:
   - `outputs/paper_test/paper_execution_log.csv`
   - `PaperAccountState` reducer

2. front_state 역할:
   - 공식 운용 계좌가 아님
   - 전략 관찰용 / sandbox / 기존 front-test 호환용

3. paper_state 역할:
   - 공식 paper-test 계좌
   - 지속적인 paper daily plan 생성 기준

4. paper daily plan 출력 후보:
   - `outputs/paper_test/daily_action_plan_YYYYMMDD.md`

5. state 변환 방향:
   - `PaperAccountState`
   - → `CurrentPortfolioState` 호환 dict 또는 객체

6. paper mode buying power:
   - `PaperAccountState.cash` 기준

7. 경로 분리:
   - front sandbox: `outputs/front_test/`
   - official paper: `outputs/paper_test/`

8. 확장성:
   - 향후 multi-market / multi-strategy / live account 확장을 막지 않도록 이름과 경계를 설계한다.

## 조사 대상 파일

아래 파일을 우선 조사한다.

```text
scripts/run_front_test.py
core/daily_plan_generator.py
core/portfolio_state_manager.py
core/paper_account_state.py
core/paper_current_state_serializer.py
scripts/run_paper_eod_update.py
core/paths.py
```

파일명이 다르면 실제 저장소 구조에 맞춰 관련 파일을 추적한다.

## 조사 질문

### 1. run_front_test.py의 현재 역할

다음을 확인한다.

- daily plan 생성까지만 하는지
- state를 어디서 읽는지
- 어떤 loader/path helper를 쓰는지
- 어떤 output 파일을 생성하는지
- `outputs/front_test`에 무엇을 쓰는지
- paper 관련 경로를 참조하는지
- front_state를 공식 계좌처럼 취급하는 부분이 있는지

### 2. daily plan 생성 로직의 state dependency

다음을 확인한다.

- daily plan 생성 핵심 함수가 어디에 있는지
- state를 함수 인자로 받는지, 내부에서 직접 load하는지
- 필요한 state 필드가 무엇인지

필수 후보:

```text
current_symbols
shares
avg_price
highest_prices
absolute_cash
current_cash_ratio
current_hedge_ratio
hedge_symbols
```

추가 확인:

```text
cash / buying power 계산 위치
Rec_Shares 계산 위치
보유 종목 BUY 중복 방지 위치
SELL 판단 시 참조하는 보유 상태
```

### 3. paper_state provider 가능성

다음을 확인한다.

- `paper_execution_log.csv`를 읽어 `PaperAccountState`를 재계산하는 기존 함수가 있는지
- `PaperAccountState`에서 daily plan에 필요한 필드를 모두 만들 수 있는지
- `paper_current_state_serializer`를 재사용할 수 있는지
- `absolute_cash = PaperAccountState.cash`로 주입 가능한지
- `shares`, `avg_price`, `highest_prices`를 어떻게 만들 수 있는지
- 부족한 필드가 있다면 무엇인지

### 4. account_state_provider 분리 가능성

아래 구조로 분리 가능한지 조사한다.

```text
front_state_provider
- outputs/front_test 기반
- 관찰용 sandbox

paper_state_provider
- paper_execution_log.csv + reducer 기반
- 공식 paper 계좌

future_live_state_provider
- broker account / broker fills 기반
- 이번 단계 구현 제외
```

확인할 것:

- daily plan generator가 provider 결과만 받도록 만들 수 있는지
- state loader를 외부에서 주입할 수 있는지
- 기존 front-test 기능을 깨지 않고 paper provider를 추가할 수 있는지

### 5. output path 분리 가능성

다음을 확인한다.

- daily plan output path를 인자로 받을 수 있는지
- front output과 paper output이 완전히 분리 가능한지

권장 경로:

```text
front sandbox:
outputs/front_test/daily_action_plan_YYYYMMDD.md

official paper:
outputs/paper_test/daily_action_plan_YYYYMMDD.md
```

### 6. 구현 후보 비교

아래 후보를 비교한다.

#### A안: run_front_test.py에 `--state-source front|paper` 추가

검토 항목:

- 수정 범위
- 기존 front-test 영향
- 경로 혼동 위험
- 장기 유지보수성

#### B안: scripts/run_paper_daily_plan.py 신규 생성

검토 항목:

- 기존 front-test 보존성
- paper 경로 분리 안전성
- daily plan 로직 중복 위험
- 단기 구현 안전성

#### C안: scripts/run_daily_plan.py로 장기 통합

검토 항목:

- 가장 깔끔한 장기 구조인지
- 현재 리팩토링 부담
- front/paper/live 확장성

## 추천 설계안에 포함할 것

결과 보고에는 다음을 반드시 포함한다.

```text
1. front_state를 sandbox로 격하하는 데 필요한 변경점
2. paper_state를 공식 paper 계좌로 쓰는 데 필요한 변경점
3. account_state_provider 분리 가능성
4. PaperAccountState → CurrentPortfolioState 호환 변환 가능성
5. buying power를 PaperAccountState.cash로 주입할 수 있는 위치
6. paper daily plan output path 분리 방법
7. A/B/C안 중 단기 추천안과 장기 추천안
```

## 절대 금지

- production code 대규모 수정 금지
- `outputs/front_test` 수정 금지
- `outputs/paper_test` 실제 파일 수정 금지
- DB 수정 금지
- 기존 paper_execution_log row 수정 금지
- performance report 기능 추가 금지
- benchmark / MDD / CAGR / Sharpe 추가 금지
- live broker 관련 구현 금지

## 산출물

결과 보고는 5,000자 이내로 작성한다.

포함할 항목:

1. Summary
2. 조사한 파일
3. 현재 run_front_test.py 역할
4. daily plan generator state dependency
5. front_state의 현재 역할과 sandbox화 가능성
6. paper_state provider 가능성
7. PaperAccountState 변환 가능성
8. cash / buying power 주입 위치
9. output path 분리 가능성
10. 구현 후보 A/B/C 비교
11. 추천 설계안
12. 남은 위험 / 다음 MFU 제안

## 성공 기준

- front_state와 paper_state의 역할이 명확히 분리됨
- daily plan 생성 로직이 어떤 state에 의존하는지 확인됨
- paper_execution_log + reducer 기반 paper_state를 daily plan에 주입할 수 있는지 판단 가능
- 기존 front-test를 깨지 않고 paper daily plan을 만들 수 있는 설계가 제안됨
- 다음 구현 단계인 MFU-PAPER6-2의 범위가 명확해짐