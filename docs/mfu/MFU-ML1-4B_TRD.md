# MFU-ML1-4B Shared Market Preparation — TRD

`core/paper_shared_market_prepare.py`는 participant resolution → coverage union → 기존 preparation 1회 → SQLite backup → snapshot 검증 → frozen universe → manifest LAST를 담당한다. 계좌 state/runbook orchestration과 분리된 작은 계약 모듈이다. `scripts/paper.py`는 입력/출력/exit code만 연결한다.

`core.paths.shared_market_preparations_dir()`는 디렉터리를 생성하지 않고 `outputs/shared_market_preparations`를 반환한다. 날짜별 `<YYYY-MM-DD>/` 패키지는 `market.sqlite3`, 필요한 경우 `universe.json`, 마지막 ready marker `manifest.json`으로 구성된다. 상대 경로만 identity에 넣는다. 계좌별 DB 사본을 만들지 않는다.

참여 계좌는 `paper_account_profiles.v2`와 기존 binding resolver로 검증한다. profile/account type은 paper, canonical initialized artifacts는 필수다. 초기 account_snapshot의 cash/currency와 DATA_DATE까지 execution ledger로 holdings를 재구성하며 시장 가격을 읽어 holdings를 추론하지 않는다. bootstrap 값과 profile 초기 자본은 서로 다른 의미로 보존한다. reference는 digest와 별도로 고정한다. 현재 runtime에 resolver가 없는 non-null benchmark_profile은 조용히 무시하지 않고 BLOCKED이며, benchmark symbol은 frozen shared policy의 MARKET_BENCHMARK_SYMBOL을 사용한다.

shared_snapshot universe는 기존 quarterly-as-of selector와 StageA universe provenance validator로 선택한다. 기존 market calendar의 다음 거래일을 provenance context에 사용한다. breadth membership은 canonical DB의 tickers.listing_board=NASDAQ100을 준비 전에 읽고 identity에 넣는다. refresh 후 snapshot에서 membership이 달라졌다면 coverage conflict다. source universe는 처음 읽은 원본 bytes의 SHA-256으로 고정하므로 읽기/해시 사이 변경도 혼합 입력으로 발행하지 않는다.

`run_paper_prepare_data`에 optional required_symbols / required_index_symbols를 추가한다. 지정 stock union은 live constituent 조회 대신 사용하고 universe capture와 동시 사용을 거부한다. 가격/metadata/indicator update 순서는 유지한다. `data_collector.update_market_indices(additional_symbols=...)`는 기존 기본 index/hedge 목록에 custom benchmark/index를 추가하는 작은 확장이다. 기존 무인자 호출과 downloader 종료일 semantics는 유지한다. 반복 계좌별 refresh와 전역 config patch는 사용하지 않는다.

index 최소 history는 binding에서 계산한다. 기본 SPY/QQQ/^VIX, hedge, benchmark를 포함하고, regime 활성 시 SMA 기간, 활성 MA-cross/DD/circuit-breaker 기간, VIX 평균 기간을 합성한다. benchmark는 rs_lookback+1행이다. stock 조회 시작일은 기존 screener의 DEFAULT_SCREEN_START_DATE를 재사용한다. entry-only 200행 미만은 missing_market_data exclusion으로 기록한다. 보유/breadth는 exclusion 불가이며 200행과 최신 SMA200/ATR20/RSI14를 요구한다. 모든 stock에 최신 metadata/OHLCV, 모든 index에 최소 history와 최신 DATA_DATE close를 요구한다. market_status_log table/read contract도 검증하되 이전 regime 기록이 없는 초기 상태는 기존 정책대로 허용한다.

source DB를 읽기 전용 URI로 열고 sqlite3.Connection.backup을 temporary SQLite DB에 수행한다. WAL의 committed 입력을 포함하며 파일 byte-copy를 하지 않는다. destination journal_mode는 DELETE로 고정해 독립 snapshot이 WAL sidecar에 의존하지 않게 한다. quick_check와 coverage는 이 snapshot만 검증한다. source DB의 이후 변화를 validation에 섞지 않는다. DATA_DATE 이후 row는 보존하되 검증 query는 cutoff 이하만 사용한다. 4C 소비자 역시 cutoff를 보존해야 한다.

versioned manifest `paper_shared_market_preparation.v1`은 implementation MFU-ML1-4B.v1, data_date, 정렬된 participant IDs 및 profile/binding/entry/holdings/hedge/benchmark 증거, required_coverage와 digest, frozen universe source identity/hash, snapshot relative_path/hash, versioned validation/entry exclusions, created_at을 포함한다. request_identity는 semantic plan digest이고 shared_preparation_id는 request identity와 snapshot hash 및 validation digest로 정해진다. 생성 시각과 machine absolute path는 semantic identity에 들어가지 않는다.

publication 전 모든 participant를 resolve한다. parent를 만든 다음 날짜 디렉터리를 exclusive mkdir로 claim한다. 기존 first-run의 exclusive 생성/temporary publication 원리를 조사했으며, account-local lock을 shared namespace에 가져오지 않고 날짜 claim 하나만 사용한다. claim 충돌은 refresh 없이 차단한다. 실패한 claim은 증거로 보존한다. 복잡한 parallel framework나 cross-date source writer lock은 추가하지 않는다.

temporary snapshot/frozen universe → 검증/flush/fsync → durable rename → participant drift 재검증 → manifest.tmp flush/fsync → manifest.json rename 순서다. manifest가 마지막 ready marker다. schema/필드 집합, 고정 상대 경로, content hashes, coverage와 reference identity, validator evidence를 REUSE마다 검증한다. 이름이 알려지지 않은 artifact, temp artifact, symlink, partial/corrupt manifest와 누락 파일은 차단한다. exact retry는 source DB/source universe를 읽지 않고 frozen 입력과 현재 participant 계약만 검증하므로 파일 내용은 변하지 않는다.

불변성은 consumer contract와 hash validation으로 보장한다. OS 수준 ACL/WORM, 서명, 디렉터리 fsync에 의한 모든 storage의 power-loss 보장, 외부 프로세스의 임의 변조 및 동시 날짜 간 source refresh 직렬화는 제공하지 않는다. participant gate는 역사 metadata를 재구축하지 않는다. 현재 canonical breadth membership을 freeze하는 방식이며 breadth membership 자체에 역사 provenance를 새로 부여하지 않는다. 전체 병렬 계좌 운영은 범위 밖이다.

4C integration seam은 run_shared_market_prepare의 결과 및 manifest_path/shared_preparation_id다. daily/01은 explicit participant set으로 ensure를 호출하고 PREPARED/REUSE 및 manifest 검증 성공 이후에만 계좌 runbook state를 만들거나 transition해야 한다. 기존 Stage A writer를 제거하고 frozen SQLite/universe를 소비하도록 전환하는 작업은 아직 수행하지 않았다.
