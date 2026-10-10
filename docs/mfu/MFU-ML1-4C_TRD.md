# MFU-ML1-4C — Stage A shared-input integration

MFU-ML1-4B의 publication 형식과 validation을 재사용한다. `validate_shared_market_input`은 publication path safety를 먼저 검사하고 `_reuse`로 manifest schema/hash, frozen universe, participant binding/holdings, cutoff coverage를 검증한다. 생성/refresh/repair 또는 canonical market/universe lookup을 수행하지 않는다. 결과에는 data_date, canonical participant IDs, shared_preparation_id, request_identity, manifest/snapshot/universe path+SHA-256, validation_result가 들어간다.

진입 순서: PAPER/first-run guard → explicit participants split/trim/validate/deduplicate-reject/sort → shared ensure → consumer validation → existing context/pin 확인 → state init/load → artifacts.shared_input pin → Stage A RUNNING → Step 0~5. Shared failure는 state write 경계 앞에서 종료한다. `pin_shared_input`과 `save_state`가 기존 pin의 변경/삭제를 거부한다. 기존 binding schema는 유지한다. Dry-run은 ensure를 건너뛰고 consumer 검증 및 메모리 내 rendering만 수행한다.

Registry Step 1은 READ_ONLY `paper.py validate-shared-data`다. Step 2 freshness와 Step 3 Plan은 runbook-state-json으로 pin을 읽는다. Shared freshness는 4B의 실제 participant coverage/history/provenance 검증을 사용한다. Legacy freshness의 전체 DB 최신일/일반 universe 개수 조건은 frozen participant package에 적용하지 않는다. 독립 freshness와 prepare-data 경로는 그대로다.

Plan entrypoint는 runbook binding과 shared pin을 재검증한다. Portfolio state/HWM reader에 frozen DB를 전달한다. Generator는 명시적 `DataManager(db_path, read_only=True)`를 screener, holdings, indicator 및 RS 경로로 전달한다. Market analyzer와 benchmark loader에도 같은 DB/read_only 옵션을 전달한다. SQLite URI `mode=ro`로 쓰기를 거부하며 market status logging을 비활성화한다. HWM reader는 기존 read-only 연결을 재사용한다. 기존 SQL와 price-frame cutoff를 유지하므로 future row가 있는 snapshot에서도 DATA_DATE 이후 값을 계산에 쓰지 않는다. 계산식, 신호 및 체결 시점 가정은 변경하지 않는다.

Shared-snapshot binding의 universe는 publication의 universe.json에서 읽으며 live selector를 호출하지 않는다. Explicit-symbol binding은 기존 의미를 유지하고 market reads만 frozen DB로 전환한다. Generator의 shared_input에는 account binding이 필수다. Plan sidecar의 shared_input은 state pin과 같고 market/indicator/RS lineage source/revision은 snapshot 경로/해시다. Shared universe lineage도 frozen 경로/해시다. Runner는 Plan PASS 전에 pin 동등성, 기존 execution intent/as-of 계약, publication 재검증, frozen source/revision 동등성을 확인한다.

기존 subprocess import/preflight 경로의 DB 설정은 Stage A child env에만 `STOCK_SCREENER_MARKET_DB`를 전달한다. Parent 환경과 Stage E/F 호출에는 override를 적용하지 않는다. 새 전역 DB abstraction이나 schema migration은 없다.

운영 wrapper 변경은 root 01과 account template 두 파일이다. Daily wrapper는 byte-unchanged다. `_account.local.cmd`는 만들지 않는다. MFU-ML1-4B 문서의 당시 미구현 integration seam은 이 MFU에서 연결했다.

검증 한계: synthetic fixture에서 real shared validation/state/Plan 계산을 실행하고 외부 download/status/Notion 실행은 격리한다. OS ACL/WORM, 외부 프로세스의 동시 변조 방어, 전체 Stage B~F isolation은 제공하지 않는다. Historical Plan의 기존 immutable config snapshot 요구는 유지한다.
