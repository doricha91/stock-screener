# MFU-ML1-5A — Two-account lifecycle isolation integration

통합 fixture는 production `prepare_first_run`, `run_stage_a`, primary flows, Gate 1/2, Stage B reconciliation/commit, Stage D review, Stage E completion, Stage F export를 호출한다. 외부 경계만 synthetic market refresh와 in-memory Notion HTTP service로 대체하며 production account selection, path resolution, binding, state transition, evidence validation과 idempotency는 그대로 실행한다.

`_account.template.cmd`의 explicit participant assignment는 `read_account_local`이 기존 ACCOUNT_ID/ACCOUNT_MODE 순서 뒤의 `SHARED_PARTICIPANT_ACCOUNT_IDS` 하나와 공식 template comment만 허용해 읽는다. 알 수 없는 key, duplicate, 순서 변경, 임의 comment는 기존 strict local-file 계약대로 거부한다.

Fresh-account 판정은 workspace의 비-JSON sidecar를 validated runbook state가 소유한 다른 계좌의 canonical runbook-day directory 아래에서만 그 계좌 이력으로 귀속한다. Loose file, 알 수 없는 확장자, 손상·무소유 JSON, symlink와 현재 계좌 이력은 계속 차단한다. 이 규칙으로 먼저 완료한 A의 command/stage Markdown·CSV·log가 fresh B를 오염시키지 않으면서 출처 불명 이력은 fail-closed 한다.

EOD ledger replay seed는 account-root `paper_account_snapshot.csv`의 identity를 검증한 뒤 모든 row의 initial cash/currency가 하나로 일치하는 경우에만 사용한다. 기존 명시적 legacy-column 호환은 read-time backfill로 유지한다. 재생 state와 새 snapshot은 이 seed를 사용하므로 서로 다른 초기 자금 계좌가 100,000 고정값으로 수렴하지 않는다. 무보유 valuation의 정의되지 않은 unrealized percentage는 빈 값으로 직렬화한다.

성과 보고서 reader는 정확한 canonical header를 가진 빈 position snapshot만 `("", [])`로 수용한다. 최신 account snapshot이 open position을 보고하면 빈 position rows를 거부한다. Completion manifest는 canonical no-action proof가 있고 review ledger가 실제로 존재하지 않을 때만 `verified_no_action_absent` source를 생성한다. Symlink, directory, standard-action absence와 기존 파일의 schema 오류는 허용하지 않는다.

Stage B recovery isolation은 `build_stage_b_logical_operation`의 account/runbook payload와 `authorize_stage_b_recovery`의 frozen-context equality를 사용한다. A assessment를 B에, B assessment를 A에 전달하면 `assessment_context_mismatch`로 state mutation 전에 거부한다. Cross-account artifact tests는 target state를 매번 복원하고 source account inventory가 변하지 않았음을 확인한다.

Stage A command bridge는 frozen snapshot DB만 child scope에 주입한다. 이후 command records는 parent DB를 사용하며 parent environment는 변하지 않는다. 외부 HTTP 호출은 차단되고 fake Notion response는 실제 property type/plain-text 및 schema option contract를 제공한다. DB schema, 전략 계산식, wrapper 파일과 운영 설정은 변경하지 않는다.
