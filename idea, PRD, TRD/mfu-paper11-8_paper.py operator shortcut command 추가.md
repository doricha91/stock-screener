# MFU-PAPER11-8 작업 지시문: paper.py operator shortcut command 추가

## 목적

PAPER11-8의 목표는 `scripts/paper.py`에 실제 운영자가 매일 사용할 상위 shortcut command를 추가하는 것이다.

이번 단계에서는 기존 개별 명령을 삭제하지 않고, 운영용 shortcut 4개만 추가한다.

```text
prepare
preview
commit
review
```

반드시 명시:

```text
이번 PAPER11-8은 paper.py operator shortcut command 구현이며, 기존 개별 명령 삭제, EOD 자동 commit, review append 자동 실행은 포함하지 않는다.
```

## 배경

현재 `paper.py`에는 아래 개별 명령이 있다.

```text
prepare-data
data-freshness
preflight
plan
eod
reports
review-template
review-validate
review-append
```

개별 명령은 디버깅/진단용으로 유지한다.  
실제 운영용 명령은 4개 shortcut으로 제한한다.

## 추가할 운영용 shortcut

### 1. prepare

명령:

```text
python scripts/paper.py prepare --date YYYYMMDD
python scripts/paper.py prepare --date YYYYMMDD --universe
python scripts/paper.py prepare --date YYYYMMDD --allow-warnings
```

동작:

```text
1. prepare-data --date YYYYMMDD 실행
2. data-freshness --date YYYYMMDD 실행
3. data-freshness 결과가 PASS이면 성공
4. PASS_WITH_WARNINGS이면 기본 중단
5. --allow-warnings가 있으면 PASS_WITH_WARNINGS도 성공 처리
6. FAIL이면 실패
```

정책:

```text
--universe는 prepare-data에만 전달
prepare는 DB writer command다
plan은 자동 실행하지 않는다
```

### 2. preview

명령:

```text
python scripts/paper.py preview --date YYYYMMDD
python scripts/paper.py preview --date YYYYMMDD --allow-warnings
```

동작:

```text
1. data-freshness --date YYYYMMDD 실행
2. PASS이면 계속
3. PASS_WITH_WARNINGS이면 기본 중단
4. --allow-warnings가 있으면 계속
5. plan --date YYYYMMDD 실행
6. eod --date YYYYMMDD --dry-run 실행
```

정책:

```text
preview는 prepare-data를 자동 실행하지 않는다
preview는 EOD commit을 실행하지 않는다
```

### 3. commit

명령:

```text
python scripts/paper.py commit --date YYYYMMDD
```

동작:

```text
1. eod --date YYYYMMDD --commit 실행
```

정책:

```text
commit은 반드시 별도 shortcut으로 유지한다
preview 이후 자동 commit은 금지한다
이번 단계에서는 dry-run evidence 강제는 구현하지 않는다
향후 PAPER11-9에서 dry-run evidence 정책을 다룬다
```

### 4. review

명령:

```text
python scripts/paper.py review
python scripts/paper.py review --allow-warnings
```

동작:

```text
1. reports 실행
2. review-template 실행
3. review-validate 실행
```

정책:

```text
review-append는 실행하지 않는다
review-append는 사람이 작성한 row를 누적 log에 넣는 writer이므로 명시 실행으로 유지한다
```

## allow-warnings 정책

기본 정책:

```text
PASS -> 계속 진행
PASS_WITH_WARNINGS -> 중단
FAIL -> 중단
```

옵션:

```text
--allow-warnings
```

이 옵션이 있을 때만 PASS_WITH_WARNINGS에서도 계속 진행한다.

주의:

```text
daily_indicators stale warning은 plan 품질에 영향을 줄 수 있으므로 기본 무시하면 안 된다
```

## 구현 방식

권장:

```text
scripts/paper.py 내부에 shortcut handler 추가
기존 개별 handler 함수를 재사용
subprocess보다 기존 paper.py 내부 wrapper 함수를 우선 재사용
```

내부 helper 예:

```text
run_prepare_shortcut(date, universe, allow_warnings)
run_preview_shortcut(date, allow_warnings)
run_commit_shortcut(date)
run_review_shortcut(allow_warnings)
```

## 절대 금지

```text
기존 개별 명령 삭제 금지
prepare-data를 preview에 자동 포함 금지
commit을 preview에 자동 포함 금지
review-append를 review에 자동 포함 금지
run-all/daily 전체 자동 실행 command 추가 금지
EOD commit 자동 실행 금지
market data 수집을 preflight에 포함 금지
paper_execution_log.csv 직접 수정 금지
paper_account_snapshot.csv 직접 수정 금지
paper_position_snapshot.csv 직접 수정 금지
outputs/front_test 수정 금지
DB schema 변경 금지
setup_db.py 호출 금지
```

## 테스트

수정 테스트:

```text
tests/test_paper_cli.py
```

필수 테스트:

```text
1. --help에 prepare/preview/commit/review 표시
2. prepare가 prepare-data 후 data-freshness를 호출
3. prepare에서 PASS_WITH_WARNINGS는 기본 실패
4. prepare --allow-warnings는 PASS_WITH_WARNINGS도 성공
5. prepare --universe가 prepare-data에 전달됨
6. preview가 data-freshness -> plan -> eod dry-run 순서로 실행
7. preview는 prepare-data를 호출하지 않음
8. preview는 eod commit을 호출하지 않음
9. preview PASS_WITH_WARNINGS는 기본 실패
10. preview --allow-warnings는 계속 진행
11. commit은 eod --commit만 호출
12. review는 reports -> review-template -> review-validate 순서로 실행
13. review는 review-append를 호출하지 않음
14. 기존 개별 명령이 유지됨
```

테스트에서는 mock/monkeypatch를 사용해 실제 DB write, API 호출, EOD commit, review append가 실행되지 않게 한다.

## 검증 명령

```text
set PYTHONPATH=.

python -m pytest tests/test_paper_cli.py -q
python -m py_compile scripts/paper.py

python scripts/paper.py --help
```

주의:

아래 명령은 실제 DB write 또는 paper 원장 변경 가능성이 있으므로 검증 실행 여부를 결과 보고에 명확히 남긴다.

```text
python scripts/paper.py prepare --date YYYYMMDD
python scripts/paper.py commit --date YYYYMMDD
```

## 성공 기준

```text
운영용 shortcut 4개가 추가된다
prepare/preview/commit/review가 명확히 분리된다
PASS_WITH_WARNINGS는 기본 중단된다
--allow-warnings가 동작한다
commit은 별도 명령으로만 가능하다
review-append는 shortcut review에 포함되지 않는다
기존 개별 명령은 유지된다
테스트가 통과한다
outputs/front_test는 수정되지 않는다
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 변경 파일
3. 추가된 shortcut
4. prepare 동작
5. preview 동작
6. commit 동작
7. review 동작
8. allow-warnings 정책
9. 제외한 항목
10. 테스트 결과
11. 실제 실행한 명령
12. DB write 여부
13. paper 원장 CSV 변경 여부
14. outputs/front_test 변경 여부
15. 다음 단계 제안
```

반드시 명시:

```text
이번 PAPER11-8은 paper.py operator shortcut command 구현이며, 자동 commit과 review append 자동 실행은 포함하지 않는다.
```