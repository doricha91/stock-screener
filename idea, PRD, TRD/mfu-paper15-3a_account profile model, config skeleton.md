BEGIN MFU-PAPER15-3A_ACCOUNT_PROFILE_MODEL_CONFIG_SKELETON

# MFU-PAPER15-3A 작업 지시문: Account Profile Model / Config Skeleton

## 목적

MFU-PAPER15-3A의 목표는 다중계좌 도입을 위한 최소 account profile 모델과 config skeleton을 구현하는 것이다.

이번 단계는 account profile 정의, validation, config example, read-only loader 구현까지를 범위로 한다.  
실제 paper artifact path resolver 적용, paper.py --account-id 적용, writer command 변경, Notion external key 변경, CSV migration은 하지 않는다.

반드시 명시:

```text
이번 PAPER15-3A는 account profile model / config skeleton 구현이며, path resolver 적용, paper CLI account scope 적용, DB write, paper 원장 수정, Notion write/export, migration 구현은 포함하지 않는다.
```

## 확정된 전제

PAPER15-1, PAPER15-2 결과에 따라 아래 결정은 확정 전제로 둔다.

```text
1. 기존 outputs/paper_test는 account_id=paper_default인 legacy default account로 해석한다.
2. 신규 다중계좌 artifact root는 outputs/paper_accounts/{account_id}/ 방향으로 설계한다.
3. paper_default resolver는 new root 우선, legacy fallback 방향으로 간다.
4. account_id 규칙은 ^[a-z0-9][a-z0-9_-]{2,63}$ 를 사용한다.
5. Notion은 단일 DB + account_id property 방향으로 설계한다.
6. strategy_profile, universe_profile, benchmark_profile, notion_profile은 account identity core가 아니라 별도 profile/reference 계층으로 분리한다.
7. read-only CLI부터 --account-id를 도입하는 방향으로 간다. 단, 이번 3A에서는 CLI 적용을 하지 않는다.
```

## 배경

PAPER15-2에서 권장된 다음 구현 순서는 아래와 같다.

```text
MFU-PAPER15-3A: account profile model / config skeleton
MFU-PAPER15-3B: account-aware path resolver implementation
MFU-PAPER15-3C: paper.py --account-id read-only command support
MFU-PAPER15-3D: writer command account guard design
MFU-PAPER15-3E: Notion external key account namespace design
```

이번 3A는 이후 path resolver와 CLI account scope가 참조할 수 있는 최소 account profile 계층을 먼저 만든다.

## 구현 범위

### 1. account profile 모델 추가

새 파일을 추가한다.

```text
core/paper_account_profile.py
```

필수 dataclass 후보:

```text
PaperAccountProfile
PaperAccountProfileConfig
```

`PaperAccountProfile` 최소 필드:

```text
account_id: str
display_name: str
currency: str
initial_cash: float
account_type: str
is_default: bool
```

선택 profile/reference 필드:

```text
strategy_profile: str | None
universe_profile: str | None
benchmark_profile: str | None
notion_profile: str | None
```

기본 계좌:

```text
account_id = paper_default
display_name = Paper Default
currency = USD
initial_cash = 100000.0
account_type = paper
is_default = true
```

### 2. account_id validation 구현

아래 규칙을 적용한다.

```text
^[a-z0-9][a-z0-9_-]{2,63}$
```

금지 reserved id 후보:

```text
default
paper_test
front_test
reports
reviews
archive
config
outputs
```

필수 함수 후보:

```text
validate_account_id(account_id: str) -> str
is_valid_account_id(account_id: str) -> bool
```

잘못된 account_id는 명확한 ValueError 또는 전용 예외를 발생시킨다.

### 3. account profile config example 추가

새 example config를 추가한다.

```text
config/paper_account_profiles.example.json
```

예시 구조:

```json
{
  "schema_version": "paper_account_profiles.v1",
  "default_account_id": "paper_default",
  "accounts": [
    {
      "account_id": "paper_default",
      "display_name": "Paper Default",
      "currency": "USD",
      "initial_cash": 100000.0,
      "account_type": "paper",
      "is_default": true,
      "strategy_profile": null,
      "universe_profile": null,
      "benchmark_profile": null,
      "notion_profile": null
    }
  ]
}
```

실제 개인 config 파일은 만들지 않는다.

```text
config/paper_account_profiles.json 생성 금지
```

### 4. read-only loader 구현

필수 함수 후보:

```text
default_paper_account_profile() -> PaperAccountProfile
load_paper_account_profiles(path: Path | None = None, allow_missing: bool = True) -> PaperAccountProfileConfig
resolve_paper_account_profile(account_id: str | None = None, config: PaperAccountProfileConfig | None = None) -> PaperAccountProfile
```

정책:

```text
- config 파일이 없고 allow_missing=True이면 paper_default 1개를 반환한다.
- account_id가 None이면 default_account_id를 사용한다.
- config의 default_account_id가 accounts에 없으면 에러 처리한다.
- is_default=true인 account가 여러 개면 에러 또는 warning 중 하나로 정책을 명확히 한다.
- 이번 단계에서는 환경변수 STOCK_SCREENER_PAPER_ACCOUNT_ID 처리는 구현하지 않아도 된다. 필요하면 후속 3C에서 처리한다.
```

### 5. 테스트 추가

새 테스트 파일 후보:

```text
tests/test_paper_account_profile.py
```

테스트 항목:

```text
1. paper_default 기본 profile 생성
2. valid account_id 통과
3. invalid account_id 실패
4. reserved account_id 실패
5. config missing + allow_missing=True이면 paper_default fallback
6. config에서 account_id로 profile resolve
7. default_account_id가 accounts에 없으면 실패
8. duplicate account_id가 있으면 실패
```

## 산출물

필수 생성/수정 파일:

```text
core/paper_account_profile.py
config/paper_account_profiles.example.json
tests/test_paper_account_profile.py
```

선택 문서:

```text
docs/TRD/mfu_paper15_3a_account_profile_model_config_skeleton.md
```

선택 문서를 작성한다면 아래를 포함한다.

```text
1. Purpose
2. Scope / Non-scope
3. Account profile schema
4. Validation policy
5. Default account policy
6. Backward compatibility
7. Next MFU dependency
```

## 금지 사항

```text
paper artifact path resolver 적용 금지
core/paths.py 기존 paper path 함수 변경 금지
scripts/paper.py --account-id 적용 금지
writer command 수정 금지
paper.py prepare/preview/commit/review/review-append 실행 금지
DB write 금지
paper 원장 CSV 수정 금지
outputs/paper_test 수정 금지
outputs/paper_accounts 생성 금지
outputs/front_test 수정 금지
Notion API write 금지
Notion export 실행 금지
Notion status sync 실행 금지
migration script 작성 금지
config/paper_account_profiles.json 생성 금지
git add . 금지
git add -A 금지
```

## 허용 사항

```text
코드 파일 추가
example config 추가
테스트 추가
문서 추가
read-only 파일 확인
pytest 단위 테스트 실행
```

## 검증 명령

Windows CMD 기준:

```cmd
python -m pytest tests\test_paper_account_profile.py
git diff -- core\paper_account_profile.py config\paper_account_profiles.example.json tests\test_paper_account_profile.py
git status --short
```

문서를 작성한 경우:

```cmd
git diff -- docs\TRD\mfu_paper15_3a_account_profile_model_config_skeleton.md
```

## 성공 기준

```text
PaperAccountProfile 모델이 추가된다.
paper_default 기본 profile이 코드로 표현된다.
account_id validation이 구현된다.
reserved account_id가 차단된다.
example config가 추가된다.
config missing 시 paper_default fallback이 동작한다.
profile resolve 테스트가 통과한다.
기존 paper path, CLI, writer, Notion 동작은 변경되지 않는다.
outputs/ 하위 파일은 수정되지 않는다.
```

## 결과 보고 형식

5천자 이내.

포함:

```text
1. Summary
2. 생성/수정한 파일
3. account profile 모델 요약
4. account_id validation 정책
5. default paper account 정책
6. config loading 정책
7. 테스트 결과
8. 코드 변경 범위
9. 금지 사항 준수 여부
10. outputs/paper_test 변경 여부
11. outputs/paper_accounts 생성 여부
12. 다음 MFU 제안
```

반드시 명시:

```text
이번 PAPER15-3A는 account profile model / config skeleton 구현이며, path resolver 적용, paper CLI account scope 적용, DB write, paper 원장 수정, Notion write/export, migration 구현은 포함하지 않는다.
```

END MFU-PAPER15-3A_ACCOUNT_PROFILE_MODEL_CONFIG_SKELETON