MFU-PAPER14-NOTION-CLOSEOUT

MFU-PAPER14-Notion-closeout 작업 지시문: PAPER14 Notion 전체 closeout 문서화
목적

PAPER14에서 구현한 Notion 연동 전체 범위, 완료된 기능, source-of-truth 원칙, 운영 흐름, 보류 항목, 후속 과제를 하나의 closeout 문서로 정리한다.

이번 작업은 문서화 작업이다.

Python 코드 수정, Notion actual export/write 실행, ledger/review append 재실행은 수행하지 않는다.

반드시 명시한다.

이번 PAPER14-Notion-closeout은 PAPER14 Notion 연동 전체 범위를 정리하고 완료/보류/후속 범위를 문서화하는 작업이며, Python 코드 수정, Notion actual write/export, Manual Execution commit, Manual Review append, paper trading ledger 수정은 수행하지 않았다.

기준 커밋

기준 커밋:

ffd2350f5933376f4bc2b9fec26901d76f0b797d

최근 로그에 아래 커밋들이 있어야 한다.

5ed9982 PAPER14-7A: assess Performance Summary Notion scope
64f5ff5 PAPER14-7F: sync Manual Review status back to Notion
962ece8 PAPER14-7G: document Notion review operations SOP

작업 전 확인 명령:

cd /d D:\python\StockScreener
git rev-parse HEAD
git log --oneline -20
git status --short

기준 SHA 이후 상태가 아니면 중단하고 보고한다.

배경

PAPER14에서 Notion은 source of truth가 아니라 presentation / input / review layer로 정의됐다.

최종 원칙:

Notion = 입력 UI / 검토 UI / staging layer
CSV / JSON / Markdown / SQLite = source of truth
Python = validation / preview / commit / append / export 주체

완료된 주요 흐름:

Daily Plan Notion export
Manual Executions input → preview → commit → status sync
Account Snapshot export
Weekly Reports export
Benchmark Reports export
Daily Review Summary export
Manual Reviews input → preview → append → status sync
Review 포함 운영 SOP 보강
조사/참조 대상

아래 문서를 확인하고 closeout 문서에 요약한다.

docs/TRD/mfu_paper14_3b_notion_schema_contract.md
docs/TRD/mfu_paper14_4_daily_plan_notion_export.md
docs/TRD/mfu_paper14_5b_manual_executions_schema_contract.md
docs/TRD/mfu_paper14_5d_manual_execution_commit.md
docs/TRD/mfu_paper14_5e_notion_execution_status_sync.md
docs/TRD/mfu_paper14_6_daily_review_summary_notion_export.md
docs/TRD/mfu_paper14_7a_performance_summary_assessment.md
docs/TRD/mfu_paper14_7b_review_flow_assessment.md
docs/TRD/mfu_paper14_7c_manual_review_notion_schema_contract.md
docs/TRD/mfu_paper14_7d_manual_review_import_preview.md
docs/TRD/mfu_paper14_7e_manual_review_append_commit.md
docs/TRD/mfu_paper14_7f_manual_review_status_sync.md
docs/operations/paper_daily_ops.md
docs/operations/paper_notion_ops.md
config/notion_property_mapping.example.json
config/notion_settings.example.json

문서가 없거나 uncommitted 상태면 있는 그대로 확인하고 보고한다.

결과 문서

새 문서 추가:

docs/TRD/mfu_paper14_notion_closeout.md

필요 시 아래 문서에 짧은 링크만 추가한다.

docs/operations/paper_notion_ops.md
docs/operations/paper_daily_ops.md

단, 기존 운영 문서를 크게 재편집하지 않는다.

paper_daily_ops.md 리팩토링은 별도 MFU로 남긴다.

closeout 문서에 포함할 내용
1. 목적과 범위

다음을 정리한다.

PAPER14 Notion 연동의 목적
Notion의 역할
source of truth 원칙
PAPER14에서 완료된 범위
PAPER14에서 제외/보류한 범위
2. Notion DB별 역할

아래 DB별 역할을 정리한다.

Daily Plans
Manual Executions
Account Snapshots
Weekly Reports
Benchmark Reports
Daily Review Summaries
Manual Reviews

각 DB에 대해 아래 항목을 표로 정리한다.

역할
source artifact
write 방향
upsert key / external key
주요 status 필드
완료 상태
후속 리스크
3. 완료된 운영 흐름

최종 daily loop를 정리한다.

Prepare / preflight
→ Daily Plan 생성
→ Daily Plan Notion export
→ Notion에서 Daily Plan 확인
→ 실제 action 수행
→ Notion Manual Executions 입력
→ Manual Executions preview
→ execution commit
→ account / position / current_state 갱신
→ Manual Executions status sync
→ Daily Review Summary export
→ Notion에서 Daily Review Summary 확인
→ Notion Manual Reviews 입력
→ Manual Reviews preview
→ review append
→ Manual Reviews status sync
→ Weekly / Benchmark / Account Snapshot export

4. artifact flow

아래 흐름을 구분해 정리한다.

Daily Plan export flow
Manual Execution flow
Daily Review Summary flow
Manual Review flow
Weekly / Benchmark / Account Snapshot export flow

특히 Manual Execution과 Manual Review는 아래 구조로 명시한다.

Notion input
→ Python read-only import
→ preview JSON
→ user-approved commit/append
→ local source-of-truth update
→ Notion status back-write

5. status와 safety 정책

아래 용어를 문서화한다.

READY
COMMITTED
SYNCED
PASS
WARNING
FAIL
created
updated
dry-run
--allow-warnings

정책:

FAIL 있으면 commit/append 금지
WARNING 있으면 기본 차단
--allow-warnings가 있을 때만 commit/append 허용
Notion sync 실패 시 원장 rollback하지 않고 status sync만 재실행
6. 스마트폰 / 로컬 PC 역할

스마트폰 가능:

Daily Plan 확인
Manual Executions 입력
Daily Review Summary 확인
Manual Reviews 입력
Notion status 확인

로컬 PC 필수:

preview
commit / append
ledger / review log / state 갱신
status back-write
Notion export / sync
7. 보류 / 제외 항목

아래를 명확히 기록한다.

Performance Summary: 7A 판단에 따라 현재 보류
Notion DB 자동 생성: 제외
Notion을 source of truth로 사용하는 구조: 제외
broker/API 연동: 제외
스마트폰 단독 commit/append 실행: 제외
GitHub Actions / cloud runner 운영: 보류
paper_daily_ops.md 전체 리팩토링: 후속 MFU
export_paper_to_notion.py --all 정책 정리: 후속 검토 가능
8. 남은 리스크

아래 리스크를 기록한다.

paper_daily_ops.md에 오래된 section과 최신 addendum이 병존
일부 Notion DB별 view policy는 TRD 문서를 함께 봐야 함
warning 허용 사유 기록이 운영자 습관에 의존
Notion API/network 실패 가능성
unrelated worktree 변경 누적
9. 최종 판정

아래 취지로 결론을 낸다.

PAPER14 Notion review/input layer는 Daily Plan, Manual Executions, Daily Review Summary, Manual Reviews, Account/Weekly/Benchmark export까지 1차 운영 가능한 상태로 closeout한다.

Performance Summary는 현재 보류한다.

이후 작업은 통합 명령 정책, 문서 리팩토링, 운영 SOP 압축, 모바일/원격 실행 검토로 분리한다.

제외 범위

이번 작업에서 하지 않는다.

Python 코드 수정 금지
config 수정 금지
Notion actual export/write 실행 금지
Manual Execution import/commit/status sync 재실행 금지
Manual Review import/append/status sync 재실행 금지
paper_execution_log.csv 수정 금지
paper_account_snapshot.csv 수정 금지
paper_position_snapshot.csv 수정 금지
paper_current_state_YYYYMMDD.json 수정 금지
paper_manual_review_log.csv 수정 금지
output 파일 수정/삭제 금지
DB/PNG 파일 수정/삭제 금지
git add . 금지
git add -A 금지
검증 명령

문서 작업이므로 테스트는 필수 아님.

cd /d D:\python\StockScreener
git status --short
git diff --name-only

문서 검색:

findstr /S /N /I "Daily Plans Manual Executions Daily Review Summary Manual Reviews Performance Summary source of truth READY COMMITTED allow-warnings" docs\TRD*.md docs\operations*.md

테스트를 실행하지 않았다면 결과 보고에 이유를 명시한다.

커밋 정책

문서만 커밋한다.

git add docs\TRD\mfu_paper14_notion_closeout.md

운영 문서에 링크만 추가한 경우에만 아래를 stage한다.

git add docs\operations\paper_notion_ops.md
git add docs\operations\paper_daily_ops.md

커밋 전 확인:

git diff --cached --name-only

문서 외 파일이 staged되어 있으면 커밋하지 말고 보고한다.

커밋 메시지:

git commit -m "PAPER14: document Notion closeout"

성공 기준
PAPER14 Notion 전체 범위가 하나의 closeout 문서에 정리된다.
Notion DB별 역할과 source artifact가 정리된다.
Manual Execution / Manual Review의 input-preview-commit-sync 구조가 정리된다.
source of truth 원칙이 명확히 기록된다.
Performance Summary 보류 판단이 기록된다.
스마트폰 가능 단계와 로컬 PC 필수 단계가 기록된다.
남은 리스크와 후속 MFU가 정리된다.
문서만 커밋된다.
결과 보고 형식

5천자 이내.

Summary
기준 커밋 확인 결과
변경 파일
closeout 문서에 정리한 범위
Notion DB별 역할 정리
완료된 운영 흐름 정리
source of truth 원칙
status/safety 정책 정리
Performance Summary 보류 기록
스마트폰/로컬 PC 역할 구분
제외/보류 항목
코드 수정 여부
CSV/output 수정 여부
테스트 실행 여부와 결과
커밋 hash와 message
stage하지 않은 파일
남은 리스크
다음 MFU 제안

반드시 명시:

이번 PAPER14-Notion-closeout은 PAPER14 Notion 연동 전체 범위를 정리하고 완료/보류/후속 범위를 문서화한 작업이며, Python 코드 수정, Notion actual write/export, Manual Execution commit, Manual Review append, paper trading ledger 수정은 수행하지 않았다.