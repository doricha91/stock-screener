# MFU-PAPER11-9 작업 지시문: commit safety guard 구현

## 목적

PAPER11-9의 목표는 `paper.py commit --date YYYYMMDD` 실행 시, 같은 날짜의 paper snapshot이 이미 존재하면 기본적으로 commit을 차단하는 safety guard를 추가하는 것이다.

이번 단계에서는 **same-date commit guard**를 구현한다.

반드시 명시:

```text
이번 PAPER11-9는 commit safety guard 구현이며, EOD commit 로직의 대규모 변경, dry-run evidence 강제, reports/review 실행은 포함하지 않는다.
```

## 배경

현재 `paper.py commit --date YYYYMMDD`는 `eod --commit`을 감싸는 운영용 shortcut이다.

실제 운영 중 같은 날짜로 commit을 다시 실행하면 다음 동작이 발생한다.

```text
paper_current_state_YYYYMMDD.json 재저장
paper_account_snapshot.csv 같은 날짜 row 교체
paper_position_snapshot.csv 같은 날짜 rows 교체
기존 파일 backup 생성
replaced_same_date=True
```

기능적으로는 중복 row를 막고 backup도 생성하지만, 운영 실수 방지 차원에서는 같은 날짜 commit 재실행을 기본 차단하는 것이 안전하다.

## 구현 파일

수정:

```text
scripts/paper.py
tests/test_paper_cli.py
docs/TRD/mfu_paper11_9_commit_safety_guard.md
```

필요 시 추가:

```text
core/paper_commit_guard.py
tests/test_paper_commit_guard.py
```

대규모 리팩토링은 금지한다.

## CLI 변경

기존:

```text
python scripts/paper.py commit --date YYYYMMDD
```

추가 옵션:

```text
python scripts/paper.py commit --date YYYYMMDD --replace
```

선택적으로 alias 허용:

```text
--force-replace
```

단, 하나만 구현해도 된다. 권장은 `--replace`.

## 동작 정책

### 1. 기본 commit

```text
python scripts/paper.py commit --date 20260520
```

동작:

```text
1. 같은 날짜 snapshot 존재 여부 확인
2. 이미 존재하면 commit 중단
3. 사용자에게 --replace 사용 안내
4. eod --commit 호출하지 않음
5. exit code 1 반환
```

차단 메시지 예:

```text
Commit blocked: snapshot for 2026-05-20 already exists.
Use --replace only if you intentionally want to replace same-date snapshots.
```

### 2. replace commit

```text
python scripts/paper.py commit --date 20260520 --replace
```

동작:

```text
1. 같은 날짜 snapshot 존재 여부 확인
2. 존재하더라도 replace 의도가 명시됐으므로 계속 진행
3. 기존 eod --commit 실행
4. 기존 backup/replaced_same_date 정책은 EOD 로직에 맡김
```

## 같은 날짜 snapshot 판단 기준

우선 아래 중 하나라도 존재하면 same-date commit exists로 판단한다.

```text
outputs/paper_test/paper_current_state_YYYYMMDD.json
paper_account_snapshot.csv 안에 snapshot_date == YYYY-MM-DD row 존재
paper_position_snapshot.csv 안에 snapshot_date == YYYY-MM-DD row 존재
```

구현 우선순위:

```text
1. paper_account_snapshot.csv의 snapshot_date 확인
2. paper_position_snapshot.csv의 snapshot_date 확인
3. paper_current_state_YYYYMMDD.json 존재 확인
```

CSV가 없으면 “존재하지 않음”으로 본다.  
CSV 파싱 실패는 error로 처리한다.

## paper.py commit 흐름

변경 후 흐름:

```text
paper.py commit
→ commit guard 실행
→ guard PASS 또는 --replace
→ 기존 eod --commit wrapper 실행
```

주의:

```text
eod --commit 자체의 기존 동작은 변경하지 않는다.
paper.py eod --date YYYYMMDD --commit 개별 명령은 이번 단계에서 guard 적용 여부를 결정한다.
```

권장 정책:

```text
operator shortcut인 paper.py commit에는 guard 적용
diagnostic command인 paper.py eod --commit에는 guard 미적용 또는 TODO
```

단, 안전성을 우선하려면 둘 다 적용해도 된다. 적용 범위는 TRD에 명확히 기록한다.

## 제외 범위

이번 단계에서 하지 않는다.

```text
dry-run evidence 강제
preview success marker 생성
freshness evidence 강제
reports 자동 실행
review 자동 실행
EOD commit 내부 로직 대규모 수정
paper_execution_log.csv append 정책 변경
snapshot replace 로직 변경
backup 로직 변경
front_test 관련 변경
```

향후 TODO:

```text
PAPER11-10 또는 별도 MFU에서 commit 전 preview/dry-run evidence 강제 여부 검토
```

## 안전 원칙

```text
기본 commit은 같은 날짜 snapshot 존재 시 중단한다.
replace는 반드시 명시 옵션이 있어야 한다.
replace 실행 시에도 기존 backup 생성 정책을 유지한다.
paper_execution_log.csv를 직접 수정하지 않는다.
paper_account_snapshot.csv를 guard가 직접 수정하지 않는다.
paper_position_snapshot.csv를 guard가 직접 수정하지 않는다.
outputs/front_test는 수정하지 않는다.
```

## 테스트

수정/추가 테스트:

```text
tests/test_paper_cli.py
tests/test_paper_commit_guard.py
```

필수 테스트:

```text
1. commit --date에서 기존 snapshot이 없으면 eod --commit 호출
2. paper_current_state_YYYYMMDD.json이 있으면 기본 commit 중단
3. account snapshot에 같은 날짜 row가 있으면 기본 commit 중단
4. position snapshot에 같은 날짜 row가 있으면 기본 commit 중단
5. --replace가 있으면 같은 날짜 snapshot이 있어도 eod --commit 호출
6. CSV 파일이 없으면 snapshot 없음으로 처리
7. CSV 파싱 실패는 error 처리
8. 중단 시 exit code 1
9. --replace 실행 시 exit code는 기존 eod 결과를 따른다
10. commit guard는 reports/review/prepare-data를 호출하지 않음
11. outputs/front_test를 수정하지 않음
```

테스트에서는 monkeypatch/mock을 사용한다.  
실제 `eod --commit`이 실행되면 안 된다.

## 검증 명령

```text
set PYTHONPATH=.

python -m pytest tests/test_paper_cli.py tests/test_paper_commit_guard.py -q
python -m py_compile scripts/paper.py
python -m py_compile core/paper_commit_guard.py

python scripts/paper.py --help
```

주의:

아래 명령은 실제 paper snapshot을 수정할 수 있으므로 검증 실행 여부를 결과 보고에 명확히 남긴다.

```text
python scripts/paper.py commit --date YYYYMMDD
python scripts/paper.py commit --date YYYYMMDD --replace
```

## 성공 기준

```text
paper.py commit에 same-date commit guard가 적용된다.
같은 날짜 snapshot이 있으면 기본 commit이 중단된다.
--replace가 있을 때만 같은 날짜 commit 재실행이 허용된다.
기존 EOD commit 내부 replace/backup 정책은 유지된다.
paper.py prepare/preview/review 동작은 변경되지 않는다.
paper 원장 CSV를 guard가 직접 수정하지 않는다.
outputs/front_test는 수정되지 않는다.
테스트가 통과한다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 변경 파일
3. 추가된 CLI 옵션
4. same-date snapshot 판단 기준
5. 기본 commit 차단 동작
6. --replace 동작
7. eod --commit 개별 명령 적용 여부
8. 제외한 항목
9. 테스트 결과
10. 실제 commit 명령 실행 여부
11. paper 원장 CSV 변경 여부
12. outputs/front_test 변경 여부
13. 다음 단계 제안
```

반드시 명시:

```text
이번 PAPER11-9는 commit safety guard 구현이며, dry-run evidence 강제와 reports/review 자동 실행은 포함하지 않는다.
```