# PAPER14 Daily Notion Ops Cheat Sheet

## 1. Purpose

이번 MFU-PAPER14-DAILY-NOTION-CHEAT-SHEET는 `paper_daily_ops.md`와 `paper_notion_ops.md`를 기반으로 일간 통합 운영 cheat sheet를 추가하는 작업이며, Python 코드 수정, Notion mapping/schema 변경, Notion actual write/export, Manual Execution commit, Manual Review append, paper trading ledger 수정은 수행하지 않는다.

이 문서는 매일 실제 운영자가 따라볼 최소 절차만 압축한 1페이지용 가이드다.

## 2. 절대 원칙

- Notion = 입력 UI / 검토 UI / staging layer
- CSV / JSON / Markdown / SQLite = source of truth
- Python = validation / preview / commit / append / export 주체
- preview 없이 commit / append 금지
- FAIL 있으면 commit / append 금지
- WARNING 있으면 기본 차단
- `--allow-warnings`가 있을 때만 허용
- source-of-truth commit 성공 후 Notion sync 실패 시 rollback 금지
- 같은 commit report로 status sync만 재실행

## 3. 오늘의 운영 순서

- [ ] Prepare / preflight
- [ ] Daily Plan 생성
- [ ] Daily Plan Notion export
- [ ] Notion에서 Daily Plan 확인
- [ ] 실제 action 수행
- [ ] Notion Manual Executions 입력
- [ ] Manual Executions preview
- [ ] execution commit
- [ ] account / position / current_state 갱신 확인
- [ ] Manual Executions status sync
- [ ] Daily Review Summary export
- [ ] Notion에서 Daily Review Summary 확인
- [ ] Notion Manual Reviews 입력
- [ ] Manual Reviews preview
- [ ] review append
- [ ] Manual Reviews status sync
- [ ] Weekly / Benchmark / Account Snapshot export

세부 명령은 [paper_notion_ops.md](/D:/python/StockScreener/docs/operations/paper_notion_ops.md)를 참조한다.

## 4. 스마트폰에서 할 일

- Daily Plan 확인
- Manual Executions 입력
- Daily Review Summary 확인
- Manual Reviews 입력
- Notion status 확인

## 5. 로컬 PC에서 할 일

- preview 실행
- commit / append 실행
- ledger / review log / state 갱신 확인
- status back-write
- Notion export / sync

## 6. commit / append 전 확인

- 오늘 날짜와 preview 대상 날짜가 맞는가
- preview JSON 경로가 맞는가
- candidate 수와 예상 row 수가 맞는가
- duplicate 또는 stale preview 가능성이 없는가
- commit / append 대상이 source-of-truth에 아직 반영되지 않았는가
- warning 허용이 필요한 경우 사유를 남길 준비가 되어 있는가

## 7. WARNING / FAIL 처리

- PASS = 다음 단계 진행 가능
- WARNING = 기본 차단, `--allow-warnings` 필요
- FAIL = commit / append 금지
- WARNING 허용 시 사유 기록
- 동일 preview 재사용 시 duplicate / stale 여부 확인

## 8. Notion sync 실패 시 처리

- source-of-truth commit / append가 성공했다면 Notion sync 실패는 원장 실패가 아니다
- ledger / review log rollback 금지
- 같은 commit report로 status sync만 재실행
- 재실행 전 `page_id`, `canonical_key`, commit report 경로 확인

## 9. 오늘 마감 전 확인

- Manual Executions가 commit 또는 sync까지 반영됐는가
- Daily Review Summary를 Notion에서 확인했는가
- 거래/경고/계획 이탈이 있으면 Manual Reviews를 입력했는가
- Manual Reviews가 append 또는 sync까지 반영됐는가
- Weekly / Benchmark / Account Snapshot export가 필요한 날인지 확인했는가

## 10. 자세한 문서 링크

- [paper_daily_ops.md](/D:/python/StockScreener/docs/operations/paper_daily_ops.md)
  - canonical daily operation guide
- [paper_notion_ops.md](/D:/python/StockScreener/docs/operations/paper_notion_ops.md)
  - Notion DB별 세부 입력 / 확인 / 동기화 SOP
- [mfu_paper14_notion_closeout.md](/D:/python/StockScreener/docs/TRD/mfu_paper14_notion_closeout.md)
  - PAPER14 Notion 범위 / 완료 / 보류 / 후속 결정 기록
