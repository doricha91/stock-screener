# MFU-PAPER14-7A: Performance Summary 필요성 평가 및 Notion 잔여 범위 결정

## 목적

이번 PAPER14-7A는 Performance Summary 필요성 평가 및 Notion 잔여 범위 결정 작업이며, Performance Summary export 구현, Notion DB 생성, Python 코드 수정, Notion actual export는 수행하지 않았다.

이 문서는 PAPER14 Notion review layer에 별도 `Performance Summary` DB가 필요한지 평가하고, 남은 Notion 작업 범위를 정리하기 위한 조사 결과와 권고안을 담는다.

## 현재 Notion DB별 역할

현재 구현되었거나 설계가 확정된 Notion DB 역할은 아래와 같다.

### 1. Daily Plans

- 오늘 실행할 계획을 보여주는 읽기 전용 계획 계층
- 계획 날짜, 시장 국면, 확정 거래 수, 검토 항목 수, 경고 수를 제공
- page body는 운영자가 “오늘 무엇을 해야 하는지”를 빠르게 파악하도록 구성

### 2. Manual Executions

- 실제 체결 입력을 위한 staging/input 계층
- Python importer / validator / commit의 입력 원천
- source of truth는 아니며, CSV/SQLite에 반영되기 전 대기 장소 역할

### 3. Daily Review Summaries

- 하루 운영 결과를 요약하는 review 계층
- committed trade count, warning count, cash impact, position impact, source artifact 경로를 제공
- Daily Plan과 Manual Executions의 결과를 사람이 빠르게 검토하도록 구성

### 4. Account Snapshots

- 특정 snapshot date 기준 계좌 상태를 보여주는 상태 계층
- 현금, 총 equity, cash ratio, position count, symbols, valuation status를 제공
- 개별 날짜의 latest account 상태 확인에 적합

### 5. Weekly Reports

- 일정 기간의 운영 상태와 completeness를 요약하는 운영 rollup 계층
- End Equity, Equity Change %, Cash Ratio, Trade Count, Gap Count, Coverage Status, Overall Status를 제공
- “최근 일주일 운영이 정상적이었는가”를 판단하는데 적합

### 6. Benchmark Reports

- paper 성과를 SPY / QQQ / CASH와 비교하는 비교 계층
- Paper Return, benchmark return, excess return, paper MDD, benchmark MDD를 제공
- since-inception 또는 exploratory benchmark 비교에 적합

## Performance Summary 후보 역할

별도 `Performance Summary` DB가 담당할 수 있는 후보 역할은 아래와 같다.

- 전체 기간 누적 성과 요약
- 기간별 수익률 요약
- MDD / latest drawdown
- CAGR
- win rate
- profit factor
- 총 거래 수
- benchmark 대비 누적 초과수익
- 월간 / 분기별 성과 추세
- Notion 상단 dashboard anchor 역할

즉 후보 역할은 “운영 상태”보다 “장기 성과 해석”에 가깝다.

## 기존 DB와의 중복 항목

현재 DB와 기존 reports 기준으로 중복 여부를 정리하면 아래와 같다.

### 이미 기존 DB에서 직접 또는 거의 직접 확인 가능한 항목

- `Paper Return`
  - Benchmark Reports에서 제공
- `SPY / QQQ / CASH Return`
  - Benchmark Reports에서 제공
- `Excess Return`
  - Benchmark Reports에서 제공
- `MDD`
  - Benchmark Reports에 `Paper MDD`, `SPY MDD`, `QQQ MDD` 제공
- `End Equity`
  - Weekly Reports에서 제공
- `Equity Change %`
  - Weekly Reports에서 제공
- `Trade Count`
  - Weekly Reports 제공
  - Daily Review Summary도 일 단위 committed trade count 제공
- `Cash Ratio`
  - Weekly Reports와 Account Snapshots 제공
- `Position Count`
  - Account Snapshots 제공
- `Warning / Gap / Coverage Status`
  - Weekly Reports와 Daily Review Summary 제공

### 로컬 산출물에는 있으나 현재 Notion DB에는 직접 없는 항목

- `Primary Return From Start`
- `Latest Primary Drawdown`
- `Primary MDD`
- `Realized PnL / Unrealized PnL / Total PnL`의 요약 뷰
- `win_rate`
- `profit_factor`
- `CAGR`
- 장기 누적 성과 dashboard 성격의 summary

즉 성과 핵심 일부는 이미 Benchmark / Weekly / Account 조합으로 충분히 확인 가능하지만, 장기 누적 성과를 한 row로 모아 보여주는 용도는 아직 비어 있다.

## Performance Summary 고유 가치 후보

별도 DB가 있다면 아래 가치가 있을 수 있다.

### 1. 누적 성과 dashboard anchor

- `Daily Review Summary`는 하루 결과 중심
- `Weekly Reports`는 최근 기간 중심
- `Benchmark Reports`는 비교 중심
- `Performance Summary`는 “현재까지 전체 운영 성과”를 한 번에 보는 anchor가 될 수 있다

### 2. benchmark 비교와 운영 상태를 분리

- Benchmark Reports는 상대 성과 비교에 초점
- Performance Summary는 절대 성과, 손익 구성, 누적 drawdown, 자산배분 변화 등을 자체적으로 정리 가능

### 3. 월간/분기별 확장 기반

- 초기에는 latest summary만 export하더라도, 장기적으로 월간/분기별 archive DB로 확장할 수 있다

## source artifact 후보

현재 확인된 source artifact 후보:

- `outputs/paper_test/reports/paper_performance_summary.md`
- `outputs/paper_test/paper_account_snapshot.csv`
- `outputs/paper_test/paper_position_snapshot.csv`
- `outputs/paper_test/paper_execution_log.csv`
- `outputs/paper_test/reports/paper_benchmark_comparison.json`
- `outputs/paper_test/reports/paper_weekly_status_summary.json`

관찰:

- `paper_performance_summary.md`는 이미 존재하며 성과 요약, drawdown summary, PnL summary를 담고 있다.
- 하지만 현재 Notion export는 JSON 기반 또는 CSV 기반 structured payload를 우선 사용해 왔다.
- `paper_performance_summary.md`는 markdown 보고서이며, schema가 외부 consumer 용으로 고정돼 있다고 보기 어렵다.
- `config/notion_property_mapping.example.json`에는 `performance_summaries` 섹션이 있지만 현재 `latest_snapshot_date` 1개만 있어 실질 설계가 비어 있다.

즉 source artifact는 “전혀 없음”은 아니지만, Notion DB contract를 안정적으로 설계할 만큼 구조가 확정되었다고 보기도 어렵다.

## 구현 난이도와 리스크

### 구현 가치

- 장기 성과를 한 row로 요약하는 가치는 있다
- 운영자가 Weekly / Benchmark / Account를 여러 번 넘나들지 않아도 된다

### 중복 위험

- 기존 Benchmark / Weekly / Account / Daily Review와 상당 부분 겹친다
- 특히 현재 paper 데이터 구간이 짧을 때는 새 DB가 새로운 의사결정 정보를 많이 추가하지 못한다

### Notion 복잡도 증가

- 새 DB 추가
- property mapping 추가
- schema validation 추가
- actual export 검증 추가
- closeout / SOP 추가

### source artifact 안정성

- `paper_performance_summary.md`는 존재하지만 markdown 기반
- JSON contract가 아직 없다
- `win_rate`, `profit_factor`, `CAGR` 등은 현재 report limitations에 “아직 없음”으로 기록돼 있다

### 데이터 신뢰도

- 현재 `paper_performance_summary.md` 경고에도 snapshot row count가 작아 해석이 preliminary라고 적혀 있다
- 실제 long-horizon 성과 해석에는 데이터가 아직 적다

## 선택지 비교

### 권고 A: Performance Summary DB를 구현한다

장점:

- Notion 상에서 장기 성과 anchor를 제공
- absolute performance / drawdown / PnL 구성을 한곳에 모을 수 있음

단점:

- 기존 DB와 중복이 큼
- source artifact 구조가 아직 markdown 중심
- 현재 데이터량이 적어 판단 가치가 제한적

### 권고 B: 별도 DB는 만들지 않고 Weekly / Benchmark / Account view 개선으로 대체한다

장점:

- 새 DB 없이 복잡도 최소화
- 이미 있는 데이터로 화면만 재구성 가능

단점:

- “누적 성과 한 장 요약”이라는 요구는 약하게만 충족
- view 조합만으로는 dashboard anchor 역할이 부족할 수 있음

### 권고 C: 현재는 보류하고 forward/paper 데이터가 더 쌓인 뒤 재평가한다

장점:

- 현재 중복과 저데이터 문제를 피할 수 있음
- 나중에 누적 성과/월간 성과/benchmark 확장까지 함께 설계 가능
- source artifact를 markdown이 아니라 stable JSON로 먼저 정리할 기회를 확보

단점:

- 당장은 Notion에서 장기 성과 anchor가 없음

### 권고 D: Performance Summary는 만들지 않고 Notion closeout/SOP로 넘어간다

장점:

- 범위를 가장 빨리 닫을 수 있음
- 운영 복잡도를 늘리지 않음

단점:

- 장기 누적 성과 요약의 필요가 나중에 다시 나올 가능성이 큼
- 현재 보류 이유와 재평가 조건을 남기지 않으면 의사결정이 애매해짐

## 최종 권고안

권고 C: 현재는 보류하고 forward/paper 데이터가 더 쌓인 뒤 재평가한다.

이유:

1. 현재 Benchmark Reports와 Weekly Reports가 이미 핵심 성과 비교와 운영 요약을 제공한다.
2. Account Snapshots와 Daily Review Summaries가 일별 상태와 거래 결과를 보강한다.
3. `paper_performance_summary.md`는 존재하지만, Notion DB contract를 바로 설계할 만큼 안정적인 structured source라고 보기는 어렵다.
4. 현재 paper snapshot row count가 작아 장기 누적 성과 summary의 의사결정 가치가 아직 제한적이다.
5. 지금 새 DB를 추가하면 Notion schema / validator / exporter / closeout / SOP 범위가 늘어나는데, 추가 가치가 중복 대비 크지 않다.

## 반론과 검증

### 반론 1. 그래도 한눈에 보는 누적 성과 화면은 필요하지 않나

맞다. 장기적으로는 필요할 수 있다.

하지만 현재는 아래 조합으로 대부분 대체 가능하다.

- `Benchmark Reports`
  - paper return, excess return, MDD
- `Weekly Reports`
  - end equity, equity change %, trade count, gaps
- `Account Snapshots`
  - latest equity, cash, positions
- `Daily Review Summaries`
  - 일별 execution impact

즉 “누적 성과 한 row”의 convenience는 부족하지만, 정보 자체는 상당 부분 이미 노출되어 있다.

### 반론 2. local report에 `paper_performance_summary.md`가 있는데 바로 export하면 되지 않나

문제는 source 안정성이다.

- 현재 artifact는 markdown 중심
- JSON schema가 고정되어 있지 않음
- report limitations에 benchmark / sharpe / sortino / CAGR 부재가 명시돼 있음

즉 export 자체는 만들 수 있어도, 지금 시점의 DB contract는 쉽게 흔들릴 가능성이 있다.

### 반론 3. 그냥 최소 DB로 시작할 수도 있지 않나

가능하다. 다만 그 경우에도 사실상 `Benchmark + Account + Weekly`의 재포장 성격이 강하다.

따라서 지금은 “성급한 최소 DB 구현”보다 “보류 + 재평가 조건 명시”가 더 안전하다.

## Notion 잔여 범위 결정

Performance Summary를 보류하는 전제에서 남은 Notion 작업 범위는 아래 순서가 적절하다.

### 다음 단계 1: Performance Summary 보류

- 별도 DB 구현은 당장 진행하지 않음
- 재평가 조건:
  - paper 데이터 기간이 더 쌓일 것
  - stable JSON source artifact가 필요할 것
  - 월간/분기별 성과 요약 요구가 생길 것

### 다음 단계 2: `export_paper_to_notion.py --all` 정책 정리

- 현재 대상별 export는 개별 실행 정책이 섞여 있다
- 어떤 DB를 `--all`에 포함할지, 어떤 것은 개별 실행만 둘지 정리할 필요가 있다

### 다음 단계 3: DB별 view policy 문서화 정리

- Daily Plans / Manual Executions는 상대적으로 문서가 정리되어 있음
- Weekly / Benchmark / Account / Daily Review도 view policy와 UI 표시 원칙을 더 명시할 수 있다

### 다음 단계 4: PAPER14 Notion closeout 문서화

- 지금까지의 export / validation / actual export verification / status sync / daily review 흐름을 한 번에 닫는 closeout 문서가 있으면 좋다

### 다음 단계 5: 운영 SOP 문서화 보강

- 이미 일부 SOP는 있으나, Manual Executions와 Daily Review까지 포함한 end-to-end 운영 절차를 다시 정리할 가치가 있다

## 다음 MFU 제안

권장 순서:

1. `PAPER14-7B`: `export_paper_to_notion.py --all` 범위 및 정책 정리
2. `PAPER14-7C`: Notion DB별 view / UI policy 정리
3. `PAPER14-7D`: PAPER14 Notion closeout
4. `PAPER14-7E`: 운영 SOP 보강

Performance Summary는 위 작업 이후, 데이터가 더 쌓이고 stable source가 준비되면 별도 MFU로 재평가하는 것이 적절하다.
