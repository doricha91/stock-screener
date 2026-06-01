# MFU-PAPER14-7E 작업 지시문: Manual Review validation / append commit

## 목적

PAPER14-7D에서 생성한 Manual Review preview JSON을 기준 artifact로 사용해 검증된 review candidate를 기존 Python Review 원장인 `paper_manual_review_log.csv`에 append commit한다.

이번 작업은 Review append commit 단계다.

반드시 명시:

```text
이번 PAPER14-7E는 Manual Review preview 결과를 paper_manual_review_log.csv에 append commit하는 작업이며, Notion status back-write, Notion actual write, Manual Execution commit, paper trading ledger 수정은 수행하지 않는다.
```

---

## 기준 커밋

기준 커밋:

```text
ffd2350f5933376f4bc2b9fec26901d76f0b797d
```

최근 로그에 아래 커밋이 있어야 한다.

```text
6752eec PAPER14-7D: add Manual Review import preview
```

작업 전 확인:

```cmd
cd /d D:\python\StockScreener
git rev-parse HEAD
git log --oneline -15
git status --short
```

기준 SHA 이후 상태가 아니면 중단하고 보고한다.

---

## 배경

PAPER14-7D에서 Manual Reviews Notion DB read-only import와 validation preview가 구현됐다.

실환경 preview 예시:

```text
candidate_count = 1
fail_count = 0
warning_count = 1
append_allowed = true_with_warnings
canonical_key = manual_review:2026-05-25:AAPL:Q001
```

이번 7E에서는 Notion을 다시 읽지 않는다.  
`--preview-json`으로 전달된 preview JSON만 append 기준 artifact로 사용한다.

---

## 구현 파일 후보

```text
core/notion_manual_review_importer.py
core/paper_manual_review_log_append.py
scripts/import_notion_reviews.py
tests/test_notion_manual_review_importer.py
tests/test_paper_manual_review_append_commit.py
docs/TRD/mfu_paper14_7e_manual_review_append_commit.md
```

가능하면 기존 review append helper를 재사용한다.

참조:

```text
core/paper_manual_review_log_validator.py
core/paper_manual_review_log_append.py
scripts/append_paper_manual_review_log.py
scripts/paper.py
```

---

## CLI 요구사항

기존 `scripts/import_notion_reviews.py`에 commit 옵션을 추가한다.

```cmd
python scripts\import_notion_reviews.py --date 2026-05-25 --preview --json

python scripts\import_notion_reviews.py --date 2026-05-25 --commit --preview-json outputs\paper_test\reports\manual_review_import_preview_20260525.json

python scripts\import_notion_reviews.py --date 2026-05-25 --commit --preview-json outputs\paper_test\reports\manual_review_import_preview_20260525.json --allow-warnings
```

정책:

```text
preview JSON 없음 → commit 금지
preview review_date와 --date 불일치 → commit 금지
fail_count > 0 → commit 금지
append_allowed = false → commit 금지
append_allowed = true_with_warnings 이고 --allow-warnings 없음 → commit 금지
append_allowed = true_with_warnings 이고 --allow-warnings 있음 → commit 허용
```

---

## Commit 대상

preview JSON의 candidates 중 아래 조건을 만족하는 row만 append한다.

```text
validation_status = PASS 또는 WARNING
fail severity 없음
canonical_key 존재
review_date / symbol / question_id 존재
manual_answer 존재
review_status 존재
```

Notion을 다시 query하지 않는다.  
Notion row가 바뀌었으면 preview를 다시 생성해야 한다.

---

## Review log mapping

Manual Review candidate → `paper_manual_review_log.csv`

기존 CSV schema에 맞춰 매핑한다.

기본 매핑 후보:

```text
review_date -> review_date
symbol -> symbol
question_id -> question_id
question_text -> question_text
manual_answer -> manual_answer
review_status -> review_status
follow_up_needed -> follow_up_needed
review_tag -> review_tag
reviewer_note -> reviewer_note
source_template_key 또는 source_worksheet_path -> source_worksheet_path / source key 관련 기존 컬럼
created_at -> created_at
```

중요:

```text
기존 paper_manual_review_log.csv 컬럼을 확장하지 않는다.
기존 append helper가 요구하는 컬럼명을 따른다.
누락된 optional 컬럼은 기존 validator/append 정책에 맞춰 빈 값 또는 기본값으로 처리한다.
```

---

## 중복 방지

중복 기준:

```text
review_date + symbol + question_id
```

또는 기존 helper가 사용하는 key가 있으면 그 규칙을 따른다.

정책:

```text
이미 paper_manual_review_log.csv에 같은 key가 있으면 append 금지 또는 SKIPPED
동일 preview JSON 내 중복이 있으면 commit 금지
append 전 pre-check row count와 append 후 count가 맞지 않으면 실패
```

---

## Commit report

append 결과 sidecar report를 생성한다.

출력 후보:

```text
outputs/paper_test/reports/manual_review_import_commit_YYYYMMDD.json
outputs/paper_test/reports/manual_review_import_commit_YYYYMMDD.md
```

포함 내용:

```text
review_date
preview_json_path
candidate_count
appended_count
skipped_count
failed_count
append_allowed
allow_warnings
canonical_key
page_id
review_date
symbol
question_id
validation warnings
append status
```

---

## Backup / rollback

append 전 기존 review log 백업을 만든다.

예:

```text
outputs/dev_backups/paper_manual_review_log_before_manual_review_commit_YYYYMMDD_HHMMSS.csv
```

정책:

```text
append 실패 시 backup으로 rollback
부분 append 방지
rollback 실패 시 명확히 보고
```

---

## Notion write 금지

이번 7E에서 아래는 하지 않는다.

```text
Validation Status back-write
Validation Message back-write
Import Status back-write
Imported At back-write
Synced At back-write
```

위 작업은 PAPER14-7F로 분리한다.

---

## 금지 사항

```text
Notion actual write 금지
Notion status back-write 금지
Manual Execution import/commit/status sync 재실행 금지
paper_execution_log.csv 수정 금지
paper_account_snapshot.csv 수정 금지
paper_position_snapshot.csv 수정 금지
paper_current_state_YYYYMMDD.json 수정 금지
paper_manual_review_log.csv schema 확장 금지
Notion DB schema 변경 금지
git add . 금지
git add -A 금지
```

review log append와 commit report 생성은 허용한다.  
단, output/CSV/backup 파일은 git commit에 포함하지 않는다.

---

## 테스트 요구사항

추가/수정 테스트:

```text
tests/test_paper_manual_review_append_commit.py
tests/test_notion_manual_review_importer.py
```

검증할 것:

```text
1. FAIL preview는 append 거부
2. WARNING preview는 --allow-warnings 없으면 append 거부
3. WARNING preview는 --allow-warnings 있으면 append 허용
4. PASS preview는 append 허용
5. preview date와 --date가 다르면 거부
6. 기존 review log 중복 key는 append 거부 또는 SKIPPED
7. paper_manual_review_log.csv schema는 확장하지 않음
8. commit report json/md가 생성됨
9. append 실패 시 rollback
10. Notion write는 호출하지 않음
```

---

## 검증 명령

Windows CMD 기준:

```cmd
cd /d D:\python\StockScreener
set PYTHONPATH=.

python -m py_compile core\notion_manual_review_importer.py
python -m py_compile core\paper_manual_review_log_append.py
python -m py_compile scripts\import_notion_reviews.py

python -m pytest tests\test_notion_manual_review_importer.py tests\test_paper_manual_review_append_commit.py -q
```

실환경 검증:

```cmd
python scripts\import_notion_reviews.py --date 2026-05-25 --preview --json
```

WARNING preview 기본 차단 확인:

```cmd
python scripts\import_notion_reviews.py --date 2026-05-25 --commit --preview-json outputs\paper_test\reports\manual_review_import_preview_20260525.json
```

기대:

```text
WARNING이 있으므로 --allow-warnings 없이 실패
```

명시 승인 append:

```cmd
python scripts\import_notion_reviews.py --date 2026-05-25 --commit --preview-json outputs\paper_test\reports\manual_review_import_preview_20260525.json --allow-warnings
```

중복 방지 확인:

```cmd
python scripts\import_notion_reviews.py --date 2026-05-25 --commit --preview-json outputs\paper_test\reports\manual_review_import_preview_20260525.json --allow-warnings
```

기대:

```text
이미 append된 review key이므로 중복 차단 또는 SKIPPED
```

---

## 문서화

추가 문서:

```text
docs/TRD/mfu_paper14_7e_manual_review_append_commit.md
```

포함 내용:

```text
목적
preview JSON 기준 append 원칙
WARNING 처리 정책
review log mapping
중복 방지 정책
backup / rollback 정책
commit report 구조
Notion back-write 제외
후속 7F 계획
```

---

## 커밋 정책

코드와 문서만 커밋한다.

```cmd
git add core\notion_manual_review_importer.py
git add core\paper_manual_review_log_append.py
git add scripts\import_notion_reviews.py
git add tests\test_notion_manual_review_importer.py
git add tests\test_paper_manual_review_append_commit.py
git add docs\TRD\mfu_paper14_7e_manual_review_append_commit.md
git diff --cached --name-only
git commit -m "PAPER14-7E: commit Manual Review preview to review log"
```

CSV/output/backup 파일은 stage하지 않는다.

---

## 성공 기준

```text
Manual Review preview JSON 기반 append commit이 가능하다.
WARNING preview는 기본 차단된다.
--allow-warnings가 있을 때만 WARNING preview append가 가능하다.
FAIL preview는 append되지 않는다.
paper_manual_review_log.csv에 review row가 append된다.
중복 append가 방지된다.
commit report가 생성된다.
Notion status back-write는 수행하지 않는다.
paper trading ledger 파일은 수정하지 않는다.
테스트가 통과한다.
```

---

## 결과 보고 형식

5천자 이내.

```text
1. Summary
2. 기준 커밋 확인 결과
3. 변경 파일
4. 추가된 commit CLI
5. preview JSON 기준 append 정책
6. WARNING 처리 정책
7. review log mapping
8. paper_manual_review_log.csv append 결과
9. commit report 생성 결과
10. 중복 append 방지 결과
11. Notion write 미수행 확인
12. paper trading ledger 수정 여부
13. 테스트 결과
14. 커밋 hash와 message
15. stage하지 않은 output/CSV/backup 파일
16. 남은 리스크
17. 다음 MFU 제안
```

반드시 명시:

```text
이번 PAPER14-7E는 Manual Review preview 결과를 paper_manual_review_log.csv에 append commit하는 작업이며, Notion status back-write, Notion actual write, Manual Execution commit, paper trading ledger 수정은 수행하지 않았다.
```