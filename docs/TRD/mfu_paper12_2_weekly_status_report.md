# MFU-PAPER12-2 Weekly Status Report

## Summary

이번 PAPER12-2는 weekly-status Markdown/JSON 리포트 구현이며, Notion/HTML/CSV 연동과 paper 원장 수정은 포함하지 않는다.

구현 범위:

- `core/paper_weekly_status.py`
- `scripts/generate_paper_weekly_status.py`
- `scripts/paper.py weekly-status`
- Markdown/JSON 산출물 생성

제외 범위:

- Notion 연동
- HTML 대시보드
- CSV 산출물
- DB write
- `paper_execution_log.csv`, `paper_account_snapshot.csv`, `paper_position_snapshot.csv` 수정

## Input Policy

Primary sources:

- `paper_account_snapshot.csv`
- `paper_position_snapshot.csv`

Auxiliary sources:

- `paper_execution_log.csv`
- `daily_action_plan_YYYYMMDD.md`
- `paper_current_state_YYYYMMDD.json`
- latest review/report artifacts

설계 원칙:

- 기준축은 `snapshot_date`
- 최근 `N`개 snapshot row 또는 `--start/--end` 범위를 사용
- latest overwrite report는 historical source가 아니라 latest auxiliary source로만 사용

## Output Files

- `outputs/paper_test/reports/paper_weekly_status_summary.md`
- `outputs/paper_test/reports/paper_weekly_status_summary.json`

## CLI

```bash
python scripts/paper.py weekly-status
python scripts/paper.py weekly-status --days 5
python scripts/paper.py weekly-status --start 20260512 --end 20260520
python scripts/paper.py weekly-status --json
python scripts/generate_paper_weekly_status.py --days 5
```

## Included Sections

- Period
- Overall Status
- Operation Coverage
- Account Summary
- Position Summary
- Trade Summary
- Review / Warning Summary
- Operation Gaps
- Recommended Next Actions
- Limitations

## Operation Gap Policy

High:

- account snapshot exists but position snapshot missing
- current_state exists but snapshot set incomplete
- workflow status is `UNKNOWN_OR_INCOMPLETE`
- review validation failed

Medium:

- committed date without latest reports
- committed date without latest review template
- high priority review items without manual review rows

Low:

- execution log row count is zero for a snapshot date

no-trade day는 자동 error가 아니며, complete snapshot이 있으면 정상 가능 상태로 본다.
