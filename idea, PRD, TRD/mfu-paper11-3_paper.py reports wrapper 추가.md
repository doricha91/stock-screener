# MFU-PAPER11-3 작업 지시문: paper.py reports wrapper 추가

## 기준

브랜치: gemini_cli_update

## 목적

PAPER11-3의 목표는 `scripts/paper.py`에 `reports` subcommand를 추가해서, PAPER9 계열 report generator들을 올바른 순서로 한 번에 실행하는 것이다.

이번 단계는 reports wrapper 추가만 한다.

반드시 명시:

```text
이번 PAPER11-3은 paper.py reports wrapper 구현이며, market-data, review append, EOD commit은 포함하지 않는다.
```

## 배경

현재 상태:

- PAPER11-1에서 paper-specific preflight가 구현됐다.
- PAPER11-2에서 `scripts/paper.py`가 추가됐고, `preflight`, `plan`, `eod` subcommand가 연결됐다.
- `paper.py plan`과 `paper.py eod`는 실행 전 preflight를 자동 실행한다.
- reports command는 아직 없다.

PAPER11-3에서는 `python scripts/paper.py reports` 명령으로 기존 PAPER9 report chain을 재생성할 수 있게 한다.

## 구현 파일

수정:

```text
scripts/paper.py
tests/test_paper_cli.py
docs/TRD/mfu_paper11_3_paper_reports_wrapper.md
```

필요 시 추가 가능:

```text
core/paper_reports_runner.py
tests/test_paper_reports_runner.py
```

단, 대규모 리팩토링은 금지한다.

## CLI 요구사항

추가 명령:

```text
python scripts/paper.py reports
python scripts/paper.py reports --strict
```

동작:

1. 내부적으로 paper preflight `stage=reports`를 먼저 실행한다.
2. preflight 결과가 FAIL이면 reports 실행을 중단한다.
3. PASS 또는 PASS_WITH_WARNINGS이면 기존 report generator chain을 순서대로 실행한다.
4. 각 report script 실행 결과를 콘솔에 요약한다.
5. 하나라도 실패하면 즉시 중단하고 exit code 1을 반환한다.

`--strict`가 있으면 preflight warning도 error처럼 취급한다.

## report generator 실행 순서

기존 파일명을 실제 저장소에서 확인한 뒤, dependency 순서에 맞춰 실행한다.

권장 순서:

```text
1. generate_paper_equity_curve.py
2. generate_paper_performance_summary.py
3. generate_paper_realized_trade_journal.py
4. generate_paper_symbol_realized_performance.py
5. generate_paper_realized_ranking_report.py
6. generate_paper_symbol_unrealized_performance.py
7. generate_paper_symbol_side_by_side_performance.py
8. generate_paper_symbol_review_buckets.py
9. generate_paper_symbol_review_worksheet.py
10. generate_paper_daily_review_summary.py
```

주의:

- 실제 파일명이 다르면 현재 저장소 기준으로 맞춘다.
- drawdown 생성이 별도 script라면 equity/performance summary보다 앞 또는 함께 실행한다.
- `paper_daily_review_summary.py`는 마지막에 실행한다.
- review append는 실행하지 않는다.

## 구현 방식

우선순위:

1. 기존 generator script의 public function이 있으면 함수 호출
2. 함수 호출 구조가 불안정하면 subprocess로 기존 script 실행

단, 어떤 방식이든 기존 generator script의 내부 동작은 수정하지 않는다.

권장 내부 helper:

```python
REPORT_STEPS = [
    ("equity_curve", "scripts/generate_paper_equity_curve.py"),
    ...
]
```

각 step 결과:

```text
step_name
command_or_function
status: success / failed
exit_code
message
```

## 안전 원칙

reports command는 원본 paper CSV를 수정하면 안 된다.

수정 금지:

```text
outputs/paper_test/paper_execution_log.csv
outputs/paper_test/paper_account_snapshot.csv
outputs/paper_test/paper_position_snapshot.csv
outputs/front_test/*
```

허용 출력:

```text
outputs/paper_test/reports/*
```

review 영역은 이번 단계에서 수정하지 않는다.

```text
outputs/paper_test/reviews/*
```

단, 기존 report generator 중 worksheet 생성이 reports 아래에 쓰는 것은 허용한다.

## 절대 금지

```text
market-data / prepare-data command 추가 금지
review-template / validate / append command 추가 금지
shortcut dry-run / commit / review command 추가 금지
run-all / daily command 추가 금지
EOD dry-run 실행 금지
EOD --commit 실행 금지
paper_execution_log.csv 수정 금지
paper_account_snapshot.csv 수정 금지
paper_position_snapshot.csv 수정 금지
review log append 금지
outputs/front_test 수정 금지
DB 수정 금지
기존 generator 대규모 리팩토링 금지
```

## 테스트

수정/추가 테스트:

```text
tests/test_paper_cli.py
```

필수 테스트:

```text
1. paper.py --help에 reports subcommand 표시
2. reports subcommand가 stage=reports preflight를 먼저 호출
3. preflight FAIL이면 report chain 실행 중단
4. preflight PASS이면 report chain 실행
5. preflight PASS_WITH_WARNINGS이면 non-strict에서는 실행
6. --strict에서 warning이 있으면 실행 중단
7. report step 하나가 실패하면 전체 exit code 1
8. report step들이 정의된 순서대로 실행
9. reports command가 eod commit을 호출하지 않음
10. reports command가 review append를 호출하지 않음
11. market-data/prepare-data command는 아직 없음
```

테스트에서는 monkeypatch/mock을 사용해 실제 report 파일 생성을 최소화한다.  
원본 CSV가 수정되면 안 된다.

## 검증 명령

```text
set PYTHONPATH=.

python -m pytest tests/test_paper_cli.py -q
python -m py_compile scripts/paper.py

python scripts/paper.py --help
python scripts/paper.py reports
```

주의:

```text
python scripts/paper.py reports
```

는 `outputs/paper_test/reports/*`를 재생성할 수 있다. 결과 보고에 실제 실행 여부를 명확히 남긴다.

아래는 절대 실행하지 않는다.

```text
python scripts/paper.py eod --date YYYYMMDD --commit
```

## 성공 기준

```text
paper.py reports subcommand가 추가된다.
reports 실행 전 stage=reports preflight가 자동 실행된다.
preflight FAIL이면 reports chain이 실행되지 않는다.
기존 PAPER9 report generator들이 순서대로 실행된다.
daily review summary가 마지막에 재생성된다.
원본 paper CSV는 수정되지 않는다.
outputs/front_test는 수정되지 않는다.
review append는 실행되지 않는다.
테스트가 통과한다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 변경 파일
3. 추가된 CLI subcommand
4. reports 실행 전 preflight 방식
5. 실행한 report generator 순서
6. strict 옵션 동작
7. 실패 시 중단 정책
8. 제외한 항목
9. 테스트 결과
10. 실제 실행한 명령
11. 원본 CSV 변경 여부
12. outputs/front_test 변경 여부
13. 다음 단계 제안
```

반드시 명시:

```text
이번 PAPER11-3은 paper.py reports wrapper 구현이며, EOD commit, market-data, review append는 포함하지 않는다.
```