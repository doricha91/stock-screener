# MFU-ML1-4B Shared Market Preparation — PRD

동일 DATA_DATE를 사용하는 명시적 Paper 참여 계좌 전체의 시장 입력을 한 번 준비하고, 모든 계좌가 사용할 불변 입력 패키지를 발행한다. 첫 호출 계좌의 universe에 의존하지 않는다.

CLI는 `python scripts/paper.py prepare-shared-data --data-date YYYY-MM-DD --participant-account-id A --participant-account-id B [--json]`이다. 계좌 인자를 반복해 전체 참여 집합을 전달한다. 기본 계좌, 현재 활성 계좌, registry 전체 계좌를 자동 참여시키지 않는다. ID의 공백을 제거하고 canonical 소문자 ID를 검증한 뒤 정렬한다. 중복, unknown, 비-versioned profile, 잘못된 binding, 미초기화 계좌는 shared write 전에 차단한다.

모든 계좌의 versioned strategy/universe binding, DATA_DATE까지의 ledger로 재구성한 보유 종목, 진입 universe 밖 보유 종목, hedge/index/benchmark 입력, NASDAQ100 breadth와 regime 입력을 먼저 합성한다. 공통 universe snapshot이 필요하면 기존 as-of provenance 계약을 검증하고 원본 바이트를 고정한다. 이 경로는 universe를 live capture하거나 역사 입력을 만들어내지 않는다. 필요한 canonical 입력이 없으면 BLOCKED다.

결과는 PREPARED, REUSE, BLOCKED 중 하나다. PREPARED는 한 번의 기존 준비 코어 호출, SQLite snapshot과 frozen universe, coverage 검증, 마지막 manifest 발행까지 성공한 경우다. REUSE는 계좌 집합과 현재 binding/coverage가 일치하고 패키지 내용과 검증 결과가 일치할 때만 가능하며 refresh와 파일 재기록이 없다. 공개 후 source DB/universe가 변해도 기존 불변 패키지를 그대로 소비한다. 계좌 집합, binding reference/content, 보유 종목 또는 required coverage가 달라지면 확장하지 않고 차단한다.

다운로드 함수의 정상 종료만으로 완료를 선언하지 않는다. 요청 종목의 metadata와 DATA_DATE OHLCV, mandatory history/indicator, hedge/benchmark/index의 DATA_DATE까지 history를 snapshot에서 검증한다. 진입 전용 종목은 기존 screener의 200행 미만 exclusion을 명시적으로 기록할 수 있지만, 누락된 최신 가격·보유·breadth·필수 index 입력을 exclusion으로 숨기지 않는다. 신규 공유 gate의 보유/breadth history 요건은 200행이다. 이 gate는 기존 단일 계좌 prepare-data나 거래 전략을 변경하지 않는다.

실패/partial/corrupt/unknown/temp artifact는 증거를 보존하고 차단한다. 자동 cleanup/repair를 하지 않는다. shared preparation은 계좌 ledger, state, runbook lifecycle을 쓰지 않는다.

이 MFU는 CLI/core contract와 검증만 제공한다. daily/00~04 및 root 00~10 wrapper는 변경하지 않는다. **실제 다중 계좌 운영 전환은 아직 완료되지 않았다.** MFU-ML1-4C가 daily/01의 shared ensure, 성공 검증 후 계좌 state transition, Stage A consume-only 및 DATA_DATE cutoff를 함께 연결해야 한다. 4B 결과만으로 다중 계좌 운영을 시작하지 않는다.
