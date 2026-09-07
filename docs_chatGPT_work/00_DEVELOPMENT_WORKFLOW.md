# StockScreener Development Workflow

이 문서는 StockScreener에서 사용자, ChatGPT, Codex가 MFU를 조사·구현·검증·리뷰·closeout하는 표준 개발 절차를 정의한다.

`AGENTS.md`는 안전·무결성·아키텍처 불변 규칙의 최상위 기준이며, 이 문서는 그 규칙을 반복하지 않고 개발 실행 사이클만 정의한다.

## 1. 문서와 역할의 책임 분리

| 대상 | 책임 |
| --- | --- |
| `AGENTS.md` | DB, 파일, 설정, 아키텍처, 안전, Git 등 저장소 불변 규칙 |
| `docs/DEVELOPMENT_WORKFLOW.md` | MFU/Phase, 테스트 escalation, review, commit, closeout의 표준 절차 |
| 공통 Codex 실행 프롬프트 | 세션 시작, 현재 branch/HEAD/status 확인, 작업지시문 로드, 재개 방식 |
| 개별 MFU/Phase 작업지시문 | 이번 작업의 목표, 확정 정책, 구현 범위, 테스트, Acceptance Criteria |
| `docs/ROADMAP_CURRENT.md` | 현재 initiative 상태와 공식 실행 우선순위 |
| `docs/work_results/` | 완료된 MFU의 Result/Review/Patch evidence |

같은 규칙을 여러 문서에 반복하지 않는다. task-specific 규칙만 개별 작업지시문에 적고, 공통 실행 규칙은 이 문서 또는 `AGENTS.md`에서 참조한다.

문서 간 충돌 우선순위는 `AGENTS.md`의 규칙을 따른다.

## 2. 기본 협업 사이클

StockScreener의 기본 개발 흐름은 다음과 같다.

```text
사용자 + ChatGPT가 정책/범위 결정
        ↓
ChatGPT가 MFU 또는 Phase 작업지시문 작성
        ↓
Codex가 현재 코드/상태 조사
        ↓
Codex가 최소 구현 + 검증
        ↓
최종 Phase에서 review bundle 생성
        ↓
사용자 + ChatGPT가 diff/evidence 독립 리뷰
        ↓
PASS / NEEDS REVISION
        ↓
PASS 후 필요한 경우 reviewed local commit
        ↓
다음 MFU 또는 initiative closeout
```

Codex의 자체 완료 보고만으로 MFU를 완료 처리하지 않는다. 최종 판정은 review bundle과 실제 diff를 바탕으로 사용자/ChatGPT가 내린다.

## 3. MFU 원칙

### 3.1 MFU 정의

Minimum Functional Unit(MFU)은 사용자 또는 시스템 관점에서 독립적으로 설명하고 검증할 수 있는 최소 기능 단위다.

한 MFU는 가능한 한 다음을 만족한다.

- 단일한 목적과 명확한 Acceptance Criteria가 있다.
- 실패해도 다른 영역으로 범위를 확장하지 않고 원인을 좁힐 수 있다.
- diff와 테스트가 review 가능한 크기다.
- 다음 MFU가 필요하면 reviewed 결과를 명확한 base로 사용할 수 있다.

큰 initiative는 여러 MFU로 나눈다. 예를 들어 계약 → writer closure → reader/output closure → isolation evidence처럼 책임 경계를 순서대로 닫을 수 있다.

### 3.2 MFU와 initiative 구분

- MFU PASS는 해당 변경 단위의 완료다.
- initiative COMPLETE는 필요한 MFU 전체가 PASS하고 closeout까지 끝난 상태다.
- 개별 MFU 완료를 더 큰 initiative 전체 완료로 확대 해석하지 않는다.

## 4. Phase 모델

복잡하거나 사용량이 큰 MFU는 기본적으로 세 Phase로 나눈다.

### Phase 1 — Investigation

목적은 현재 사실을 확정하고 남은 구현 범위를 좁히는 것이다.

주요 작업:

- branch / HEAD / `git status --short` 확인
- 현재 worktree와 diff 확인
- 기존 helper, SSOT, entry point, fixture, 관련 테스트 조사
- `DONE / PARTIAL / NOT STARTED / NEEDS REVIEW` 등 현재 상태 분류
- 구현 전에 필요한 최소 설계와 예상 변경 파일 확정

기본적으로 source/test를 수정하지 않는다. 필요한 경우 구조 이해를 위한 소수의 기존 테스트만 실행한다.

### Phase 2 — Implementation + Targeted Validation

Phase 1 결과를 바탕으로 남은 범위만 구현한다.

주요 원칙:

- 기존 helper/SSOT/API를 우선 재사용한다.
- 동일 정책을 여러 경계에 복제하지 않는다.
- 새 schema/validator/helper는 기존 구조로 표현할 수 없을 때만 최소 추가한다.
- 실제 current-scope defect만 수정한다.
- targeted test와 직접 관련된 focused regression부터 실행한다.

### Phase 3 — Broad Regression + Review Bundle

구현을 더 넓히는 단계가 아니라 최종 검증과 리뷰 증거 생성 단계다.

주요 작업:

- 해당 MFU/initiative 관련 broad regression superset 실행
- 남은 failure 분류
- 필요한 경우에만 reviewed base reproduction
- `py_compile`, 정적 검사, `git diff --check`, final status 확인
- Result Evidence / Review Evidence / Changes Patch 생성

### 4.1 Phase를 의식적으로 생략하거나 합칠 수 있는 경우

모든 작업을 기계적으로 3단계로 쪼개지는 않는다.

- 영향 범위가 작고 현재 구조가 명확하면 Phase 1과 2를 합칠 수 있다.
- 문서/증거만 만드는 작업이면 구현 Phase가 없을 수 있다.
- 조사 결과 production 변경이 불필요하면 테스트/evidence만 추가할 수 있다.

단, 큰 범위·중단 가능성·불명확한 연결부가 있는 작업은 조사와 구현을 분리한다.

## 5. 중단 후 재개 규칙

Codex 세션이 끊기거나 사용량 제한으로 중단되면 이전 대화 기억보다 현재 저장소 상태를 사실 기준으로 사용한다.

재개 시 최소 확인:

```text
현재 branch
현재 HEAD
git status --short
git diff
현재 생성된 파일/테스트 결과
```

이미 완료된 조사·구현·테스트를 이유 없이 반복하지 않는다. 현재 diff에서 남은 작업만 이어간다.

## 6. 구현 의사결정 원칙

안전하게 진행 가능한 구현 선택지가 여러 개 있을 때마다 사용자에게 선택을 요구하지 않는다.

기본 우선순위:

```text
기존 사용자 작업 보존
→ 확정 정책 준수
→ 기존 helper / SSOT / validator 재사용
→ 가장 작은 안전한 변경
→ fail-closed
→ 결정론적 동작
→ 되돌리기 쉬운 구현
```

실제 blocking condition은 다음처럼 현재 작업을 안전하게 계속할 수 없는 경우다.

- 기존 사용자 변경 손상 위험
- 서로 양립할 수 없는 확정 정책 충돌
- 필수 입력/기준이 없어 결과가 달라질 수 있음
- `AGENTS.md`가 별도 승인을 요구하는 작업

단순 dirty 상태, 구현 선택지 존재, unrelated test failure만으로는 자동 중단하지 않는다.

## 7. 검증 escalation

검증은 가장 좁은 범위에서 시작해 필요할 때만 확장한다.

```text
1. targeted test
   ↓
2. focused regression
   ↓
3. MFU/initiative 관련 broad regression superset
   ↓
4. 판단에 필요한 failure만 reviewed base reproduction
   ↓
5. 전체 repository suite는 명확한 필요가 있을 때만
```

원칙:

- 같은 조사나 테스트를 Phase마다 반복하지 않는다.
- 전체 pytest를 안전함의 상징처럼 무조건 실행하지 않는다.
- production source가 바뀌지 않은 evidence-only Phase는 영향 범위에 맞게 검증한다.
- 테스트를 실행하지 않았다면 이유를 기록한다.

## 8. Failure classification

실패는 숨기지 않고 현재 작업과의 관계를 분류한다.

| 분류 | 의미 | 기본 처리 |
| --- | --- | --- |
| `CURRENT-SCOPE` / `<PHASE>-SCOPE` | 이번 구현 자체의 defect | 수정 후 관련 regression 재실행 |
| `REGRESSION` | 이전 reviewed 계약의 회귀 | 현재 작업 blocker로 처리 |
| `NEXT-PHASE` | 이미 합의된 다음 Phase 책임 | 현 Phase에서 수정하지 않고 evidence에 기록 |
| `UNRELATED` | 현재 MFU와 무관 | 범위 확장 없이 기록 |
| `PRE-EXISTING` | reviewed base에서도 동일 | 필요할 때만 base reproduction으로 입증 |
| `ENVIRONMENT` | temp, path, credential, 외부 환경 문제 | 안전한 격리 환경에서 한 번 재실행 후 기록 |

모든 failure를 base에서 반복 재현하지 않는다. PASS/NEEDS REVISION 판단에 영향을 주는 경우에만 base reproduction을 수행한다.

## 9. Review bundle과 승인

최종 리뷰 Phase의 표준 bundle은 다음 3개다.

### Result Evidence

무엇을 구현했고 어떤 검증을 했는지 기록한다.

최소 포함:

- base / branch / HEAD
- changed files
- 구현 결과
- targeted / broad validation
- 남은 failure와 분류
- 범위 밖 작업 미수행 확인

### Review Evidence

Acceptance Criteria별 판단 근거를 정리한다.

상태는 ChatGPT 리뷰 전까지 기본적으로:

```text
PENDING_CHATGPT_REVIEW
```

으로 유지한다.

### Changes Patch

reviewed base SHA 대비 source/test 전체 unified diff다.

- Evidence 자체는 source/test patch와 분리한다.
- temp/cache/DB/sandbox artifact를 포함하지 않는다.

### 9.1 Evidence 생성 시점

별도 요구가 없다면 Phase 1/2에서 매번 review bundle을 재생성하지 않는다. 최종 리뷰 Phase에서 한 번 만든다.

## 10. Review 결과와 local commit

ChatGPT 리뷰 결과는 기본적으로 다음 중 하나다.

```text
PASS
NEEDS REVISION
```

기본 원칙:

- review 전에는 자동 commit하지 않는다.
- 다음 MFU가 reviewed 변경을 base로 필요로 할 때 PASS된 변경만 local commit으로 고정할 수 있다.
- local reviewed commit은 다음 MFU의 명시적 base SHA로 사용한다.
- 구현 commit과 initiative 전체 push는 별개 단계다.

## 11. Git/worktree lifecycle

### 11.1 Dirty original worktree 보호

원래 integration worktree에 사용자 dirty 변경이 있으면 그것을 정리하려고 하지 않는다.

- stash/reset/clean으로 제거하지 않는다.
- unrelated 변경을 stage하지 않는다.
- 필요하면 별도 branch/worktree에서 MFU를 진행한다.
- 재개 시 현재 worktree/diff를 사실 기준으로 사용한다.

### 11.2 Staging

commit이 허용된 단계에서는 필요한 파일만 명시적으로 stage한다. unrelated 변경을 포함할 수 있는 광범위 staging은 피한다.

### 11.3 Initiative closeout

모든 필요한 MFU가 PASS한 뒤 별도 closeout 단계에서:

```text
reviewed final diff 확인
→ final local commit
→ MFU commit ancestry 확인
→ git fetch origin
→ remote divergence 확인
→ fast-forward 가능 여부 확인
→ 원격 integration branch push
→ push 후 remote SHA 확인
→ 필요한 ROADMAP 상태 최소 갱신
→ GitHub remote 상태 재확인
→ 임시 worktree 정리
```

원격에 예상하지 못한 변경이 있으면 자동 merge/rebase/force-push하지 않고 중단해 divergence를 보고한다.

## 12. Closeout 검증

중요 initiative의 closeout은 Codex의 `push success` 보고만으로 끝내지 않는다.

가능하면 GitHub에서 다음을 독립 확인한다.

- remote integration branch HEAD
- MFU commit chain / ancestry
- ahead / behind 관계
- roadmap 상태 반영
- 필요한 경우 CI/status 유무

CI가 없으면 이를 별도 사실로 기록하되, 해당 initiative의 기존 Acceptance Criteria에 CI가 없었다면 그 자체를 closeout 실패로 간주하지 않는다.

## 13. 완료 상태의 구분

다음 상태는 서로 독립적으로 기록한다.

```text
Code / Contract COMPLETE
≠ Migration COMPLETE
≠ Operational Activation COMPLETE
```

예를 들어 코드 계약이 완료돼도 실제 데이터 migration이나 운영 활성화가 별도 승인 작업이면 initiative는 코드 기준으로 닫고 migration/activation은 `NOT PERFORMED`로 유지할 수 있다.

## 14. 표준 완료 보고

개별 작업지시문이 별도 형식을 요구하지 않으면 다음을 보고한다.

```text
Summary
Changed files
Behavior changes
Tests run
Tests not run and why
Remaining failures / classification
Risks and limitations
Current review/closeout status
Suggested next step
```

최종 리뷰 Phase면 review bundle 경로를 함께 기록한다.

## 15. 작업지시문 작성 원칙

개별 작업지시문은 공통 규칙을 반복하지 않고 이번 작업의 차이만 적는다.

좋은 작업지시문은 다음에 집중한다.

- 이번 Phase의 목표
- 확정 정책
- 실제 연결부
- 예상 변경 파일
- 구현 순서
- task-specific edge/failure 규칙
- 필수 테스트와 검증 범위
- 범위 밖
- Acceptance Criteria

내용 자체가 많아서 긴 것은 허용하지만, 같은 정책을 여러 섹션에서 반복해 길어지는 것은 피한다.
