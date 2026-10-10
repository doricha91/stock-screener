# MFU-ML1-4C — Stage A shared input

Stage A는 같은 DATA_DATE의 명시적 참여 계좌가 하나의 검증된 시장 입력을 사용한다. 계좌 context의 `SHARED_PARTICIPANT_ACCOUNT_IDS=account_a,account_b`를 root 01 wrapper가 Stage A CLI에 전달한다. 각 계좌 context에는 같은 전체 집합을 지정한다. 순서는 무관하며 중복, 잘못된 ID, active account 누락은 refresh 전에 차단한다. 실제 local context 생성/변경과 운영 활성화는 별도 작업이다.

daily 00→01→02→03→04와 root 00~10 번호는 유지한다. PAPER/first-run guard 이후 shared ensure가 PREPARED 또는 REUSE를 반환하고 published input 검증이 성공해야 계좌 state를 생성하거나 진행한다. 처음 실행한 계좌에서 한 번 refresh하고 다음 계좌는 같은 publication을 재사용한다. Shared 실패는 새 state/Plan을 만들지 않으며 기존 READY state를 그대로 보존한다.

Stage A의 Step 0~5는 status, shared validation, snapshot freshness, Daily Plan, Notion Plan export, execution template export다. Stage A에서는 prepare-data를 호출하지 않는다. 독립 prepare-data CLI는 계속 지원한다. 각 계좌 Plan은 frozen SQLite와 해당 binding의 frozen universe 또는 explicit symbols를 사용한다. 계산에는 DATA_DATE까지의 row만 사용한다.

State와 Plan에 shared preparation ID, 참여 집합, manifest/snapshot/universe 경로와 해시를 기록한다. 같은 pin 재사용은 허용하고 변경은 차단한다. Plan의 identity와 frozen market/universe lineage를 확인한 뒤에만 다음 export로 진행한다.

Dry-run은 기존 valid publication만 검증하고 명령을 렌더링한다. Publication이 없으면 BLOCKED이며 refresh, state 생성/진행, 명령 실행을 하지 않는다. Stage E/F의 TRADE_DATE 평가 의미는 유지한다.

검증은 synthetic account/DB로 Stage-A-only A→B와 B→A, refresh 1회, 원본 변경 후 frozen 입력 유지, SQL 쓰기 거부, 바이트/해시 보존, pin 충돌 차단을 다룬다. 전체 계좌 lifecycle, 실제 Notion/Paper 운영, 병렬 실행 및 ML1-5는 범위 밖이다.
