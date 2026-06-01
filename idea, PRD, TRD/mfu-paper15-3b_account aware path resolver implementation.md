BEGIN MFU-PAPER15-3B_ACCOUNT_AWARE_PATH_RESOLVER_IMPLEMENTATION

# MFU-PAPER15-3B 작업 지시문: Account-aware Path Resolver Implementation

## 목적

MFU-PAPER15-3B의 목표는 PAPER15-3A에서 추가한 `PaperAccountProfile` 계층을 기반으로, 다중계좌용 account-aware paper path resolver를 구현하는 것이다.

이번 단계는 path resolver 구현과 단위 테스트만 포함한다.  
paper.py `--account-id` 적용, writer command 변경, Notion external key 변경, CSV migration은 하지 않는다.

반드시 명시:

```text
이번 PAPER15-3B는 account-aware path resolver 구현이며, paper CLI account scope 적용, writer command 변경, DB write, paper 원장 수정, Notion write/export, migration 구현은 포함하지 않는다.
```

## 확정 전제

아래 결정은 확정이다.

```text
1. 기존 outputs/paper_test는 account_id=paper_default인 legacy default account로 해석한다.
2. 신규 다중계좌 artifact root는 outputs/paper_accounts/{account_id}/를 사용한다.
3. paper_default resolver는 new root 우선, legacy fallback으로 간다.
4. account_id 규칙은 PAPER15-3A의 validate_account_id 정책을 사용한다.
5. read-only CLI부터 --account-id를 도입하되, 이번 3B에서는 CLI 적용을 하지 않는다.
```

## 구현 범위

### 1. 새 path resolver 모듈 추가

새 파일을 추가한다.

```text
core/paper_account_paths.py
```

필수 dataclass 후보:

```text
PaperAccountPaths
```

필수 함수 후보:

```text
resolve_paper_account_root(
    account_id: str | None = None,
    *,
    account_root: Path | None = None,
    allow_legacy_default: bool = True,
    create: bool = False,
) -> Path

build_paper_account_paths(
    account_id: str | None = None,
    *,
    account_root: Path | None = None,
    allow_legacy_default: bool = True,
    create: bool = False,
) -> PaperAccountPaths
```

`PaperAccountPaths`에 포함할 경로:

```text
account_id
root
execution_log_path
account_snapshot_path
position_snapshot_path
current_state_snapshot_path(date_str)
daily_action_plan_path(date_str)
reports_dir
reviews_dir
config_snapshots_dir
config_snapshot_path(date_str)
config_snapshot_archive_dir
replay_diff_dir
regenerated_daily_action_plan_path(date_str)
daily_plan_diff_report_path(date_str)
replay_diff_config_snapshot_path(date_str)
replay_diff_config_snapshot_archive_dir
```

### 2. root 정책 구현

기본 root 정책:

```text
legacy default root:
outputs/paper_test

new account root:
outputs/paper_accounts/{account_id}
```

resolver 정책:

```text
- account_id가 None이면 paper_default로 해석한다.
- account_id는 validate_account_id로 검증한다.
- account_id != paper_default이면 outputs/paper_accounts/{account_id}를 반환한다.
- account_id == paper_default이면:
  1. outputs/paper_accounts/paper_default가 존재하면 이를 우선 사용한다.
  2. 없고 allow_legacy_default=True이면 outputs/paper_test를 반환한다.
  3. 없고 allow_legacy_default=False이면 outputs/paper_accounts/paper_default를 반환한다.
- create=True이면 선택된 root 및 필요한 하위 디렉터리를 생성할 수 있다.
- create=False이면 outputs/paper_accounts를 새로 만들지 않는다.
```

주의:

```text
이번 단계에서 실제 outputs/paper_accounts를 생성하는 테스트는 tmp_path에서만 수행한다.
프로젝트 실제 outputs/ 하위에는 새 디렉터리를 만들지 않는다.
```

### 3. 기존 core/paths.py 변경 정책

이번 단계에서는 기존 paper path 함수의 동작을 바꾸지 않는다.

허용:

```text
core/paths.py에 PAPER_ACCOUNTS_DIR 상수 또는 helper를 추가하는 것은 허용
```

금지:

```text
기존 paper_execution_log_path(), paper_account_snapshot_path() 등 기존 함수의 반환값 변경 금지
기존 PAPER_TEST_DIR 동작 변경 금지
```

권장:

```text
가능하면 core/paths.py 변경을 최소화하고, 새 resolver 모듈 내부에서 OUTPUTS / "paper_accounts"를 참조한다.
```

### 4. 테스트 추가

새 테스트 파일을 추가한다.

```text
tests/test_paper_account_paths.py
```

테스트 항목:

```text
1. account_id=None이면 paper_default로 해석
2. paper_default + new root 없음 + allow_legacy_default=True이면 legacy root 반환
3. paper_default + new root 있음이면 new root 우선 반환
4. paper_default + allow_legacy_default=False이면 new root 반환
5. non-default account는 outputs/paper_accounts/{account_id} 반환
6. invalid account_id는 실패
7. create=False는 실제 root 생성하지 않음
8. create=True는 tmp_path 기준 필요한 하위 디렉터리 생성
9. date_str YYYYMMDD / YYYY-MM-DD 모두 clean date path 생성
10. reports/reviews/config_snapshots/replay_diff 경로가 account root 하위에 위치
```

테스트는 반드시 tmp_path를 사용해 실제 프로젝트 `outputs/`를 오염시키지 않는다.

## 산출물

필수 생성/수정 파일:

```text
core/paper_account_paths.py
tests/test_paper_account_paths.py
```

선택 문서:

```text
docs/TRD/mfu_paper15_3b_account_aware_path_resolver.md
```

선택 문서를 작성한다면 포함:

```text
1. Purpose
2. Scope / Non-scope
3. Resolver policy
4. Legacy paper_default fallback
5. Path list
6. Test coverage
7. Next MFU dependency
```

## 금지 사항

```text
paper.py --account-id 적용 금지
writer command 수정 금지
기존 paper path 함수 반환값 변경 금지
DB write 금지
paper 원장 CSV 수정 금지
outputs/paper_test 수정 금지
프로젝트 실제 outputs/paper_accounts 생성 금지
outputs/front_test 수정 금지
Notion API write 금지
Notion export 실행 금지
Notion status sync 실행 금지
migration script 작성 금지
config/paper_account_profiles.json 생성 금지
paper.py prepare/preview/commit/review/review-append 실행 금지
git add . 금지
git add -A 금지
```

## 허용 사항

```text
새 resolver 코드 추가
단위 테스트 추가
선택 문서 추가
tmp_path 기반 테스트 디렉터리 생성
read-only 파일 확인
pytest 단위 테스트 실행
```

## 검증 명령

Windows CMD 기준:

```cmd
python -m pytest tests\test_paper_account_profile.py tests\test_paper_account_paths.py
git diff -- core\paper_account_paths.py tests\test_paper_account_paths.py
git status --short
```

문서를 작성한 경우:

```cmd
git diff -- docs\TRD\mfu_paper15_3b_account_aware_path_resolver.md
```

## 성공 기준

```text
account-aware PaperAccountPaths 모델이 추가된다.
paper_default new root 우선 + legacy fallback 정책이 구현된다.
non-default account는 outputs/paper_accounts/{account_id} 경로로 resolve된다.
create=False에서는 실제 outputs 디렉터리를 생성하지 않는다.
tmp_path 기반 create=True 테스트가 통과한다.
기존 core/paths.py paper path 동작은 변경되지 않는다.
paper.py, writer command, Notion 동작은 변경되지 않는다.
outputs/paper_test와 실제 outputs/paper_accounts는 수정/생성되지 않는다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 생성/수정한 파일
3. path resolver 정책 요약
4. paper_default legacy fallback 동작
5. non-default account root 동작
6. create=True / create=False 정책
7. 테스트 결과
8. 기존 core/paths.py 동작 변경 여부
9. 금지 사항 준수 여부
10. outputs/paper_test 변경 여부
11. outputs/paper_accounts 생성 여부
12. 다음 MFU 제안
```

반드시 명시:

```text
이번 PAPER15-3B는 account-aware path resolver 구현이며, paper CLI account scope 적용, writer command 변경, DB write, paper 원장 수정, Notion write/export, migration 구현은 포함하지 않는다.
```

END MFU-PAPER15-3B_ACCOUNT_AWARE_PATH_RESOLVER_IMPLEMENTATION