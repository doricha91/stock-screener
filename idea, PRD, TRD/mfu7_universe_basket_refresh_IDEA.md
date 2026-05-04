# [IDEA] MFU7: 유니버스 바스켓 주기 갱신 및 티커 위생 관리

1) 누가 왜 쓰는지 (User / Persona)
- 프론트테스트 운영자: 오늘 아침 스크리너 결과에 상장폐지/거래중단 의심 종목이 섞이지 않길 원하는 사용자
- 전략 개발자: 유니버스 변화가 전략 문제인지 데이터 문제인지 빠르게 구분하고 싶은 사용자

2) 어디에 붙는 기능인지 (Market / Venue / Product)
- 대상 시장: 미국 주식 바스켓(SP500, NASDAQ100 등)
- 적용 계층:
  - 종목 유니버스 관리
  - 데이터 수집 파이프라인
  - 프론트테스트 후보 생성 전 위생 점검

3) 왜 필요한지 (Problem / Benchmark)
- 현재 구조에서는 `tickers` 테이블에 남아 있는 종목이면 스크리너가 마지막 존재 행(`df.iloc[-1]`)을 그대로 사용한다.
- 그 결과 `DAY`처럼 `data_date` 대비 수십 일 오래된 종목도 후보로 보일 수 있다.
- 이 문제는 전략 점수의 우열이 아니라, 유니버스와 시세 신선도 관리가 분리돼 있지 않아서 생긴다.

4) 반드시 있어야 하는 기능 (Must-have)
- 바스켓 스냅샷 관리
  - SP500, NASDAQ100 등 원천 바스켓을 주기적으로 재수집한다.
  - 초기에는 `outputs/universe/`에 날짜별 snapshot 파일로 저장한다.
  - DB 기반 시점별 membership history는 후속 단계에서 검토한다.
- stale / inactive 감지
  - `data_date` 기준 최신 가격이 일정 기간 이상 오래된 종목 탐지
  - 데이터 없음 / delisted 의심 / 장기 미갱신 종목 목록화
- 운영 레이어 보호
  - 프론트테스트에서 stale 종목을 최종 후보에서 제외
  - 제외 이유를 로그/리포트로 남김
- 관리 요약
  - 신규 편입 / 이탈 / stale 종목 수를 콘솔에 출력한다.
  - 상세 리포트 파일은 stale 문제가 반복될 때 후속 단계로 확장한다.

5) 이번 단계에서 굳이 안 해도 되는 기능 (Won't-have)
- 자동 매매 브로커 연동
- 상장폐지 판단의 완전 자동화
- 백테스트 전체 유니버스 재작성
- 거래일 단위의 완벽한 index membership backfill

6) 성공 기준 (Idea-level Success Metrics)
- 바스켓 갱신 작업 이후 신규 편입 / 이탈 / stale 목록을 일관된 형식으로 확인할 수 있다.
- 데이터 수집 실패와 유니버스 이탈이 구분되어 관찰된다.

## 7) 추천 구현 방향

### Phase 0: 이미 완료된 보호막
- front-test stale 후보 제외
- 후보별 필터 사유 로그
- daily action plan 내 stale 제외 사유 표시

### Phase 1: MFU7-1 Universe Refresh Dry-run
- 최신 SP500/NASDAQ100 바스켓 수집
- 기존 tickers와 비교
- added / removed / kept 콘솔 출력
- DB 수정 없음

### Phase 2: MFU7-2 Universe Snapshot 저장
- `outputs/universe/`에 날짜별 JSON 저장
- latest snapshot을 읽을 수 있게 준비
- 아직 screener 기본 동작은 변경하지 않음

### Phase 3: MFU7-3 Screener Freshness Guard
- screener 출력 단계에서도 stale 후보 제외
- front-test와 동일한 stale threshold 사용

### Phase 4: MFU7-4 Data Collector 실패 종목 추적
- 반복 `df.empty` 종목 집계
- 자동 삭제하지 않고 inactive/delisted 의심으로 표시

### Phase 5: MFU7-5 Persistent Ticker State
- 필요 시 DB migration
- active/inactive 상태 관리
- 별도 승인 후 진행
