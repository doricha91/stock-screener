# 조사 프롬프트: run_paper_daily_plan.py 중심 paper 운영 실행 체인 조사

## 목적

현재 stock-screener 프로젝트에서 `scripts/run_paper_daily_plan.py`를 중심으로 paper 운영 루프의 실제 실행 순서를 조사한다.

이번 작업은 조사 전용이다.  
코드 수정, 리팩토링, 새 파일 생성은 하지 않는다.

## 핵심 질문

아래 질문에 답하라.

1. `run_paper_daily_plan.py`는 paper 운영 루프에서 어떤 역할인가?
2. 이 스크립트 실행 전에 반드시 선행되어야 하는 파일/스크립트/데이터는 무엇인가?
3. 이 스크립트 실행 후 이어서 실행해야 하는 스크립트는 무엇인가?
4. `preflight_check.py`가 존재한다면, 현재 무엇을 검사하고 어디에 위치하는가?
5. `preflight_check.py`는 `run_paper_daily_plan.py` 전에 실행되는 것이 맞는가, 아니면 다른 단계용인가?
6. 현재 paper 운영 루프에서 plan → eod → reports → review 흐름이 실제 코드상 어떻게 연결되는가?
7. 운영 자동화를 하려면 새 orchestrator를 만들기 전에 어떤 기존 스크립트를 재사용해야 하는가?
8. 어떤 스크립트가 원본 paper CSV를 수정하고, 어떤 스크립트가 read-only report만 생성하는가?
9. `outputs/paper_test`와 `outputs/front_test` 경로 분리는 어디서 보장되는가?
10. 지금 단계에서 “daily pipeline orchestrator”를 만들기 전에 추가 조사가 필요한 부분은 무엇인가?

## 조사 대상

우선 아래 파일을 확인한다.

```text
scripts/run_paper_daily_plan.py
scripts/run_paper_eod_update.py
scripts/preflight_check.py
preflight_check.py
core/preflight_check.py
core/daily_plan_generator.py
core/paper_state_provider.py
core/paths.py
```

존재하지 않는 파일은 “not found”로 기록한다.

추가로 아래 패턴을 검색한다.

```text
preflight
paper_daily_action_plan_path
load_official_paper_state_for_daily_plan
generate_daily_plan
run_paper_eod_dry_run
paper_execution_log_path
paper_account_snapshot_path
paper_position_snapshot_path
PAPER_TEST_DIR
FRONT_TEST
front_test
```

## 조사 범위

허용:
- 파일 읽기
- 함수 호출 관계 추적
- argparse 옵션 확인
- 출력 파일 경로 확인
- read-only 조사 리포트 작성

금지:
- 코드 수정
- 새 orchestrator 구현
- preflight_check.py 수정
- paper_execution_log.csv 수정
- paper_account_snapshot.csv 수정
- paper_position_snapshot.csv 수정
- outputs/front_test 수정
- DB 수정
- --commit 실행
- 대규모 리팩토링

## 반드시 정리할 것

### 1. 현재 실행 체인 후보

아래 형식으로 정리한다.

```text
Step 1. 선행 데이터/상태 준비
- 관련 파일:
- 관련 스크립트:
- read/write 여부:

Step 2. run_paper_daily_plan.py
- 입력:
- 출력:
- 내부 호출 함수:
- read/write 여부:

Step 3. run_paper_eod_update.py dry-run
- 입력:
- 출력:
- read/write 여부:

Step 4. run_paper_eod_update.py --commit
- 입력:
- 출력:
- 수정 파일:

Step 5. reports regeneration
- 관련 스크립트:
- 입력:
- 출력:
- read/write 여부:

Step 6. review workflow
- template:
- validator:
- append:
- 수정 파일:
```

### 2. preflight_check.py 조사 결과

아래를 반드시 포함한다.

```text
- 파일 존재 여부
- 실제 위치
- 현재 검사 항목
- 호출하는 곳이 있는지
- run_paper_daily_plan.py와 직접 연결되어 있는지
- paper 운영 자동화에 재사용 가능한지
- 부족한 검사 항목
```

### 3. read/write 구분

각 스크립트를 아래로 분류한다.

```text
read-only
paper output writer
review output writer
dangerous writer
unknown
```

특히 아래 파일을 수정하는 스크립트는 명확히 표시한다.

```text
outputs/paper_test/paper_execution_log.csv
outputs/paper_test/paper_account_snapshot.csv
outputs/paper_test/paper_position_snapshot.csv
outputs/paper_test/reviews/paper_manual_review_log.csv
outputs/front_test/*
```

### 4. 운영 자동화 전 권장 결론

마지막에 아래 중 하나로 판단한다.

```text
A. 기존 preflight_check.py를 확장해도 충분함
B. 기존 preflight_check.py는 유지하고 paper.py에서 호출하는 게 좋음
C. 기존 preflight_check.py와 별도로 paper 운영용 preflight가 필요함
D. preflight_check.py 역할이 불명확하므로 추가 정리가 필요함
```

## 산출물

조사 리포트만 작성한다.

권장 경로:

```text
docs/TRD/mfu_paper11_0_paper_daily_pipeline_investigation.md
```

## 검증 명령

코드 수정이 없으므로 필수 테스트는 없다.

다만 문법 확인이 필요한 경우 아래만 실행한다.

```text
python -m py_compile scripts/run_paper_daily_plan.py
python -m py_compile scripts/run_paper_eod_update.py
```

`--commit` 명령은 절대 실행하지 않는다.

## 결과 보고 형식

5천자 이내.

포함:

1. Summary
2. 조사한 파일
3. run_paper_daily_plan.py 역할
4. 선행 실행 필요 항목
5. 후속 실행 필요 항목
6. preflight_check.py 조사 결과
7. 현재 paper daily pipeline 후보
8. read/write 위험 구분
9. outputs/front_test 오염 가능성
10. 운영 자동화 전 권장 방향
11. 추가 결정 필요 사항

반드시 명시:

```text
이번 작업은 paper 운영 자동화 구현 전 조사이며, 코드 수정과 --commit 실행은 하지 않는다.
```