# PAPER16-2 Operator Command Map 및 Rerun Policy

## 목적

PAPER16-1 dashboard 설계를 기반으로 Daily Ops Status의 운영자 command map, actual export rerun policy, 수동 Notion view 정리 절차를 정의한다.

이번 MFU는 문서 전용이다. Python 코드를 수정하지 않고, Notion view를 생성/수정하지 않으며, Notion actual write/export를 실행하지 않고, outputs/paper source-of-truth 산출물을 변경하지 않는다.

## 범위 / 비범위

범위:

- `workflow_status`, `review_progress_status`, `sync_status`별 운영자 행동
- 상태별 허용/금지 로컬 명령
- actual export 및 status sync rerun policy
- source-of-truth rollback 금지 정책
- 수동 Notion view 설정 절차
- PAPER16-3 readiness checklist

비범위:

- 신규 status 구현
- 신규 CLI 또는 wrapper CLI 구현
- Notion actual write/export
- Notion DB 또는 view create/update
- multi-account bulk export
- `paper_default` actual export
- broker/API, cloud runner, Alert, Replay, Schema Drift, Universe, Strategy 작업

## Source-of-truth 원칙

CSV, JSON, Markdown, SQLite가 source-of-truth다. Notion은 input, review, staging, presentation layer다.

로컬 commit/append가 성공한 뒤 Notion sync/export가 실패하더라도 local source-of-truth를 rollback하지 않는다. 동일한 source-of-truth report, `account_id`, `status_date`, `External Key` 기준으로 Notion sync/export 경로만 재시도한다.

## 현재 CLI 기준

확인된 로컬 명령:

- `python scripts\paper.py status --account-id <account_id> --json`
- `python scripts\paper.py plan --date <YYYYMMDD> --account-id <account_id>`
- `python scripts\paper.py eod --date <YYYYMMDD> --account-id <account_id> --dry-run`
- `python scripts\paper.py reports --account-id <account_id>`
- `python scripts\paper.py review-template --account-id <account_id>`
- `python scripts\paper.py review-validate --account-id <account_id>`
- `python scripts\paper.py review-append --account-id <account_id>`
- `python scripts\export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --dry-run --json`
- `python scripts\export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --confirm-actual --json`

현재 Daily Ops Status actual export guard:

- `--daily-ops-status`에는 `--dry-run` 또는 `--confirm-actual`이 필요하다.
- `--daily-ops-status`는 다른 export target과 함께 사용할 수 없다.
- actual Daily Ops Status export는 현재 `account_id=paper_sandbox`로 제한된다.

## Operator Command Map

### Workflow Status

| Status Area | Status Value | Classification | 의미 | 허용 Action | 금지 Action | Next Recommended Command | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| workflow_status | `NO_PLAN` | current | daily plan이 없다. | 해당 account/date의 plan 생성. | commit, review append, 완료 상태로 actual export. | `python scripts\paper.py plan --date <YYYYMMDD> --account-id <account_id>` | non-default 계좌는 의도한 account root인지 확인한다. |
| workflow_status | `PLAN_READY` | current | plan은 있지만 같은 날짜 state/snapshot이 없다. | EOD dry-run 또는 execution flow 확인. | committed/reviewed로 취급. | `python scripts\paper.py eod --date <YYYYMMDD> --account-id <account_id> --dry-run` | actual execution commit은 별도 guarded workflow다. |
| workflow_status | `COMMITTED` | current | source-of-truth는 갱신됐지만 reports/review가 준비되지 않았다. | reports 생성 및 review template 준비. | review done으로 표시. | `python scripts\paper.py reports --account-id <account_id>` 이후 `python scripts\paper.py review-template --account-id <account_id>` | reports 실패 시 snapshot/log artifact 누락을 확인한다. |
| workflow_status | `REVIEW_READY` | current | reports와 validation이 준비됐고 review append가 남아 있다. | review 입력을 완료하고 준비되면 review append 실행. | append 전 closeout 완료 처리. | `python scripts\paper.py review-append --account-id <account_id>` | manual review field가 불완전하면 먼저 입력을 보완한다. |
| workflow_status | `REVIEW_PARTIAL` | current | 일부 review row는 append됐지만 pending row가 남아 있다. | pending row 완료, validation, 남은 row append. | 해당 날짜를 완전히 닫힌 것으로 취급. | `python scripts\paper.py review-validate --account-id <account_id>` 이후 `python scripts\paper.py review-append --account-id <account_id>` | pending row가 남아 있으면 closeout 완료가 아니다. |
| workflow_status | `REVIEW_DONE` | current | review row가 완료됐다. | 허용된 경우 Daily Ops Status dry-run/actual export 확인. | idempotency 확인 없이 review append 재실행. | `python scripts\export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --dry-run --json` | actual export는 현재 paper_sandbox 전용 guard다. |
| workflow_status | `UNKNOWN_OR_INCOMPLETE` | current | 상태를 안전하게 분류할 수 없다. | local artifact와 blocking reason 확인. | commit, append, actual export를 성공 상태로 진행. | `python scripts\paper.py status --account-id <account_id> --json` | 누락 artifact를 해결한 뒤 진행한다. |

### Review Progress Status

| Status Area | Status Value | Classification | 의미 | 허용 Action | 금지 Action | Next Recommended Command | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| review_progress_status | `NOT_STARTED` | current | review가 answer/append되지 않았다. | review row 작성 및 validation. | review complete 표시. | `python scripts\paper.py review-validate --account-id <account_id>` | valid review input 이후에만 append한다. |
| review_progress_status | `PARTIAL` | current | 일부 review row는 완료됐고 pending row가 남아 있다. | pending row 완료 및 남은 valid row append. | closeout 완료 처리. | `python scripts\paper.py review-validate --account-id <account_id>` | `REVIEW_PARTIAL` 운영 상태와 대응된다. |
| review_progress_status | `DONE` | current | review 진행이 완료됐다. | status/export presentation 확인. | duplicate risk 확인 없이 re-append. | `python scripts\paper.py status --account-id <account_id> --json` | Daily Ops Status export는 허용된 target/account에서만 실행한다. |
| review_progress_status | `NOT_APPLICABLE` | current | 아직 review progress가 적용될 단계가 아니다. | workflow status를 따른다. | review append 강제 실행. | workflow별 명령 사용. | 보통 upstream plan/commit/report가 준비되지 않은 상태다. |
| review_progress_status | `UNKNOWN` | candidate/future | 진행도를 판단할 수 없다. | template/log 정합성 확인. | commit/append/export 성공 상태 처리. | `python scripts\paper.py status --account-id <account_id> --json` | 이해될 때까지 blocking으로 취급한다. |
| review_progress_status | `READY` | candidate/future | validated-ready 상태 표현을 위한 future 후보. | future SOP 확정 후 따른다. | 완료로 가정. | TBD | 현재 안정적인 local status semantic은 아니다. |

### Sync Status

| Status Area | Status Value | Classification | 의미 | 허용 Action | 금지 Action | Next Recommended Command | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| sync_status | `DRY_RUN` | current | Notion write 없이 payload만 생성됐다. | payload 확인, 허용된 경우에만 actual 실행. | Notion row가 갱신됐다고 가정. | `python scripts\export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --confirm-actual --json` | actual은 paper_sandbox 전용 guard다. |
| sync_status | `SYNCED` | current | Notion presentation row가 create/update됐다. | 필요하면 local status와 표시 필드를 비교. | Notion을 source-of-truth로 취급. | `python scripts\paper.py status --account-id <account_id> --json` | source-of-truth는 여전히 local이다. |
| sync_status | `FAILED` | current/operator concept | export/sync 실패 또는 failure summary가 생성됐다. | schema/mapping/client 문제를 해결하고 같은 External Key로 재시도. | local ledger/review state rollback. | 문서화된 schema/mapping validator 명령이 있으면 먼저 실행하고, 없으면 schema/mapping을 수동 점검한 뒤 dry-run을 재실행한다. | Daily Ops Status actual rerun은 계속 guarded 상태여야 한다. |
| sync_status | `SKIPPED` | candidate/future | sync를 의도적으로 생략했다. | skip reason 확인. | bulk rerun. | TBD | future exporter가 안정적으로 emit할 때까지 후보로 둔다. |
| sync_status | `NOT_SYNCED` | candidate/future | Notion row가 아직 sync되지 않았다. | dry-run 먼저 실행, 허용된 경우에만 actual 실행. | bulk actual export. | `python scripts\export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --dry-run --json` | 현재 code mapping option은 아니며 operator concept로만 사용한다. |
| sync_status | `SYNC_FAILED` | candidate/future | sync failure를 부르는 operator label이다. | `FAILED`와 동일하게 취급. | source-of-truth rollback. | schema/mapping을 먼저 점검하고, actual retry 전에 dry-run을 재실행한다. | Notion select option에서는 mapped value `FAILED`를 우선 사용한다. |

## Blocking / Warning Policy

- `FAIL`, `FAILED`, 구체적인 `Blocking Reason`은 원인이 해결될 때까지 commit, append, actual export를 막는다.
- `WARNING`은 해당 명령에 명시적인 allow option이 문서화돼 있지 않으면 기본적으로 commit/append/export를 막는다.
- `REVIEW_PARTIAL`은 pending review row가 남아 있으므로 full closeout을 막는다.
- `REVIEW_DONE`은 review closeout으로 해석 가능하지만, Notion presentation이 sync됐다는 뜻은 아니다.
- `SYNC_FAILED` / `FAILED`는 성공한 local commit/append를 무효화하지 않는다.
- future migration procedure가 아닌 한 Notion에서 `External Key`를 수동 수정하지 않는다.

## Actual Export / Sync Rerun Policy

일반 정책:

- actual export 전에는 항상 dry-run을 먼저 실행한다.
- actual write/export는 명시적 confirm flag 또는 문서화된 승인 명령이 있을 때만 허용한다.
- schema/property mismatch가 의심되면 actual export를 중단한다. 문서화된 schema/mapping validator 명령이 있으면 실행하고, 없으면 schema/mapping을 수동 점검한 뒤 dry-run을 재실행한다.
- 동일 `External Key` 기준 idempotent update를 우선한다.
- duplicate row audit과 bulk policy가 완료되기 전에는 multi-account bulk export를 실행하지 않는다.
- 신규 multi-account Daily Ops Status 흐름에서 `paper_default` actual export는 실행하지 않는다.

Daily Ops Status 현재 정책:

- 검증된 actual target: `paper_sandbox`
- 검증된 key 예: `daily_ops_status:paper_sandbox:2026-05-20`
- dry-run 명령: `python scripts\export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --dry-run --json`
- guarded actual 명령: `python scripts\export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --confirm-actual --json`

Manual Execution / Manual Review status sync:

- local commit/append report가 있고 source-of-truth update가 성공했다면, Notion status sync 실패는 presentation-layer 실패다.
- 같은 commit/append report에서 status sync를 재실행한다.
- Notion sync 실패만으로 local ledger/review log를 재생성하거나 rewrite하지 않는다.
- sync script가 `--dry-run`을 지원하면 먼저 dry-run을 사용한다.

Duplicate safety:

- actual export가 duplicate row를 만들었을 가능성이 있으면 bulk rerun을 중단한다.
- `External Key`, `Account ID`, `Status Date`로 candidate duplicate를 수동 점검한다.
- duplicate row cleanup은 future duplicate row audit procedure로 넘긴다.

## 수동 Notion View 정리 절차

이 절차는 Codex 작업 완료 후 사용자가 직접 Notion에서 수행한다. Codex는 Notion UI 작업을 하지 않는다.

1. 기존 `Daily Ops Status` DB를 연다.
2. 새 DB를 만들지 않는다.
3. linked database를 사용하는 경우 같은 `Daily Ops Status` DB를 바라보는지 확인한다.
4. database duplicate로 별도 DB를 만들지 않는다.
5. view 이름을 정확히 아래와 같이 만들거나 rename한다.
   - `Today Ops`
   - `By Account`
   - `Needs Action`
   - `Recent Sync`
   - `Review Closeout`
6. `mfu_paper16_daily_ops_status_dashboard_design.md`에 정의된 filter, sort, group, visible fields, hidden fields를 적용한다.
7. `External Key`, `Account ID`, `Status Date`, `Workflow Status`, `Review Progress Status`, `Sync Status`는 최소 하나의 troubleshooting view에서 보이게 둔다.
8. internal/debug field는 view layer에서만 숨기고 property 자체를 삭제하지 않는다.
9. `External Key`를 수동 수정하지 않는다.
10. 정리 후 view 이름과 표시 필드가 SOP 및 PAPER16-1 dashboard design과 일치하는지 비교한다.

## PAPER16-3 Readiness Checklist

사용자가 view 정리를 완료하면 PAPER16-3에서 Notion 화면 정합성을 점검할 수 있다.

체크리스트:

- `Today Ops`가 존재하고 selected-date account status를 보여준다.
- `By Account`가 account history를 group 또는 sort로 보여준다.
- `Needs Action`이 done이 아닌 workflow row와 failed sync row를 보여준다.
- `Recent Sync`가 `External Key`, `Sync Status`, `Synced At`을 보여준다.
- `Review Closeout`이 review progress와 pending count를 보여준다.
- duplicate Daily Ops Status DB가 만들어지지 않았다.
- `External Key`가 수동 수정되지 않았다.
- `paper_default` actual export가 여전히 비활성이다.
- multi-account bulk export가 실행되지 않았다.

## Risks / Open Questions

- `NOT_SYNCED`, `SYNC_FAILED`, `READY`는 operator concept 또는 future candidate이며, 현재 모든 코드 경로에서 안정적으로 emit되는 값은 아니다.
- 두 개 이상의 non-default 계좌가 운영되면 상태별 명령을 한 번 더 정교화해야 한다.
- 기존 SOP 파일에는 legacy encoding artifact가 남아 있다. 이번 MFU는 전체 재작성 대신 최소 addendum만 추가한다.
