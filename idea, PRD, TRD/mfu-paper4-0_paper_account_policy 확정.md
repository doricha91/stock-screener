# Codex Task: MFU-PAPER4-0 Paper Account Policy 확정

## 목표

paper account state 구현 전에 정책을 명확히 문서화한다.

초기 paper account는 live/front-test state를 복사하지 않고, 독립 가상계좌로 시작한다.

확정 정책:

```text
initial_cash = 100000.0
currency = USD
initial_positions = {}
fee/slippage/tax = 0
```

## 변경 파일

새 문서 추가:

```text
PRD/mfu_paper4_paper_account_policy_PRD_v1.0.md
```

가능하면 기존 문서 폴더 관례가 있으면 그 위치를 따른다.

## 작성 내용

문서에 아래 내용을 포함한다.

1. 목적
   - paper_execution_log.csv를 기반으로 독립 paper account state를 만들기 위한 정책 확정

2. 초기 상태
   - cash: 100000.0
   - currency: USD
   - positions: empty
   - applied_trade_ids: empty

3. trade 처리 정책
   - BUY: cash 감소, shares 증가, avg_price 가중평균 갱신
   - SELL: cash 증가, shares 감소
   - 전량 SELL 시 position 제거
   - duplicate trade_id는 skip

4. 방어 정책
   - 현금 부족 BUY는 error 처리
   - 보유 수량 초과 SELL은 error 처리
   - price <= 0 또는 shares == 0은 error 처리
   - paper/live 경로는 계속 분리

5. Non-goals
   - paper_current_state 파일 저장 구현 금지
   - paper_account_snapshot 구현 금지
   - performance report 구현 금지
   - 수수료/슬리피지/세금 반영 금지
   - live/front-test current_state 복사 금지
   - run_eod_update.py 수정 금지

## 하지 말 것

- Python production code 수정하지 말 것
- DB schema 수정하지 말 것
- outputs/ 아래 산출물 수정하지 말 것
- paper_execution_log.csv 수정하지 말 것
- run_paper_eod_update.py 수정하지 말 것

## 검증

문서만 추가한다.

가능하면 아래만 확인한다.

```powershell
git status --short
```

## 완료 기준

1. paper account 초기 정책이 문서화됨
2. 초기 자본 $100,000 명시
3. live/front-test state를 복사하지 않는다고 명시
4. 이번 단계에서 production code 변경 없음
5. 이번 단계에서 output/generated artifact 변경 없음

## 보고 형식

```text
1. Summary
2. Changed files
3. Policy decisions documented
4. Files intentionally not changed
5. Risks and limitations
6. Suggested next step
```