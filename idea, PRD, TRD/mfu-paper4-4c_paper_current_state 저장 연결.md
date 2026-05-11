# Codex Task: MFU-PAPER4-4C paper_current_state 저장 연결

## 목표

`run_paper_eod_update.py --commit` 실행 후, paper account preview에 사용한 `PaperAccountState`를 기존 front-test `current_state` 호환 JSON으로 변환하여 아래 경로에 저장한다.

```text
outputs/paper_test/paper_current_state_YYYYMMDD.json
```

이번 단계에서 저장하는 파일은 **paper EOD 공식 state**다.

## 현재 전제

완료된 작업:

```text
MFU-PAPER4-1: PaperAccountState reducer
MFU-PAPER4-2: paper_execution_log.csv 기반 account preview
MFU-PAPER4-4B: PaperAccountState → current_state 호환 dict serializer
```

사용자 결정:

```text
purpose: paper EOD 공식 state
save timing: --commit 이후
path: outputs/paper_test/paper_current_state_YYYYMMDD.json
schema: 기존 front-test current_state 호환
highest_price: trade_price 기준
existing file: archive 백업 후 overwrite
applied_trade_ids: 저장
validation failure: 저장 중단
```

## 변경 파일

예상 수정:

```text
scripts/run_paper_eod_update.py
core/paths.py 또는 기존 paper path helper 사용
```

필요 시 추가:

```text
core/paper_current_state_storage.py
tests/test_paper_current_state_storage.py
```

가능하면 serializer 파일은 수정하지 않는다.

```text
core/paper_current_state_serializer.py
```

## 구현 지시

### 1. 저장 helper 추가

가능하면 신규 파일로 분리한다.

```text
core/paper_current_state_storage.py
```

필수 함수 예시:

```python
def save_paper_current_state(
    state,
    date_str: str,
    output_path: Path,
    archive_dir: Path,
) -> Path:
    ...
```

동작:

1. `paper_account_state_to_current_state_dict(state, date_str)` 호출
2. 저장 경로가 `outputs/paper_test/` 아래인지 `assert_paper_path()`로 검증
3. 기존 `paper_current_state_YYYYMMDD.json`이 있으면 `outputs/paper_test/archive/`로 백업
4. 새 JSON 저장
5. 저장된 JSON을 다시 읽어 기본 필드 존재 검증

### 2. 백업 정책

기존 파일이 있으면 삭제하지 말고 archive로 이동/복사한다.

백업 예:

```text
outputs/paper_test/archive/paper_current_state_20260509_20260509_174638_backup.json
```

timestamp는 현재 시각 기반으로 한다.

### 3. run_paper_eod_update.py 연결

`--commit`일 때만 저장한다.

기대 동작:

```text
--commit 없음:
  paper_execution_log append 없음
  paper account preview 출력
  paper_current_state 저장 없음

--commit 있음:
  paper_execution_log append 또는 duplicate skip 처리
  최신 paper_execution_log.csv를 읽어 PaperAccountState 계산
  paper account preview 출력
  paper_current_state_YYYYMMDD.json 저장
```

주의:

- duplicate skip으로 rows_appended가 0이어도, `--commit` 모드라면 최신 log 기준 state 저장은 허용한다.
- reducer가 ValueError를 내면 저장하지 않는다.
- 저장 실패 시 명확한 error 출력 후 non-zero exit 처리한다.

### 4. round-trip 검증

저장된 JSON이 기존 front-test loader와 호환되는지 확인한다.

가능하면 테스트에서 `load_current_state()` 또는 현재 repo의 loader 함수를 사용한다.

검증할 필드:

```text
current_symbols
current_cash_ratio
current_hedge_ratio
absolute_cash
shares
avg_price
highest_prices
highest_price_meta
hedge_symbols
applied_trade_ids
```

단, `applied_trade_ids`는 extra field이므로 loader가 무시해도 된다. JSON에는 존재해야 한다.

## 하지 말 것

이번 작업에서 금지:

```text
outputs/front_test/* 수정
scripts/run_eod_update.py 수정
paper_account_snapshot.csv 생성
paper_performance_report 생성
DB schema 수정
paper_execution_log append/duplicate 로직 변경
position sizing 변경
data_collector 변경
market price 평가
unrealized PnL 계산
수수료/슬리피지/세금 반영
```

## 테스트

신규 테스트 권장:

```text
tests/test_paper_current_state_storage.py
```

필수 테스트:

1. 새 paper_current_state 저장
   - JSON 생성
   - 필수 필드 존재

2. 기존 파일이 있으면 archive 백업 후 overwrite
   - archive 파일 생성
   - 새 파일 생성

3. 저장 경로가 outputs/paper_test 밖이면 차단

4. serializer 결과에 positions top-level field가 없는지 확인

5. 저장된 JSON을 기존 loader로 읽을 수 있는지 확인  
   - loader가 extra field를 무시하는지 확인

## 검증 명령

```powershell
$env:PYTHONPATH="."; python -m pytest tests/test_paper_account_state.py -q
$env:PYTHONPATH="."; python -m pytest tests/test_paper_current_state_serializer.py -q
$env:PYTHONPATH="."; python -m pytest tests/test_paper_current_state_storage.py -q
$env:PYTHONPATH="."; python -m py_compile scripts/run_paper_eod_update.py core/paper_current_state_storage.py
```

실제 smoke:

```powershell
$env:PYTHONPATH="."; python scripts/run_paper_eod_update.py --date 20260509 --allow-empty-journal
$env:PYTHONPATH="."; python scripts/run_paper_eod_update.py --date 20260509 --allow-empty-journal --commit
```

기대:

```text
dry-run:
  paper_current_state write_performed: False

commit:
  paper_current_state write_performed: True
  path: outputs/paper_test/paper_current_state_20260509.json
```

## 완료 기준

1. `--commit` 이후에만 `paper_current_state_YYYYMMDD.json` 저장
2. 저장 경로는 `outputs/paper_test/` 아래
3. 기존 파일이 있으면 archive 백업 후 overwrite
4. JSON은 기존 current_state 호환 top-level schema
5. `applied_trade_ids` 저장
6. 저장된 JSON이 loader로 읽힘
7. dry-run에서는 저장 없음
8. `outputs/front_test/` 오염 없음
9. snapshot/performance는 아직 생성하지 않음

## 보고 형식

```text
1. Summary
2. Changed files
3. Save behavior
4. Backup behavior
5. Round-trip loader result
6. Tests run
7. Files changed under outputs/paper_test
8. Files intentionally not changed
9. Risks and limitations
10. Suggested next step
```

반드시 보고할 것:

```text
- paper_current_state 저장 경로
- archive 백업 파일 경로
- dry-run에서 저장이 안 됐는지
- commit에서 저장됐는지
- saved JSON 필드 목록
- loader round-trip 성공 여부
- outputs/front_test 오염 여부
```