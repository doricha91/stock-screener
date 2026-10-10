# MFU-ML1-5A — Two-account lifecycle isolation

두 explicit non-default Paper account가 동일 DATA_DATE/TRADE_DATE에서 daily 00→04 전체 lifecycle을 순서와 무관하게 완료한다. 검증 순서는 각각 독립된 fresh fixture의 A→B와 B→A이며, 한 계좌는 ACTION_REQUIRED, 다른 계좌는 NO_ACTION을 사용한다.

두 계좌는 같은 explicit participant set과 frozen shared publication을 사용한다. 각 fixture에서 첫 Stage A는 PREPARED, 둘째 Stage A는 REUSE이고 refresh는 한 번만 수행한다. shared preparation ID, manifest/snapshot/universe hash와 participant identity는 동일하며 Stage B~F가 shared package를 변경하지 않는다.

runbook state, Daily Plan, 계좌 snapshot/current state, ledger, execution/review/completion evidence, report와 idempotency/recovery identity는 계좌별로 격리한다. 먼저 완료한 계좌의 account root와 account-scoped workspace inventory는 두 번째 계좌 실행 뒤에도 byte-identical이어야 한다. Explicit account는 legacy/default root의 artifact를 선택하거나 기록하지 않는다.

다른 계좌의 runbook state, Daily Plan, execution evidence, review evidence 또는 Stage B recovery assessment를 주입하면 fail-closed 한다. Recovery logical operation과 idempotency key에는 account/runbook identity가 포함된다. 완료된 flow의 동일-account retry는 새 child command나 금융 artifact rewrite 없이 PASS한다.

NO_ACTION도 실행·리뷰 write 없이 Stage E/F와 terminal completion까지 진행한다. 정상적인 빈 position snapshot과 부재한 review ledger는 검증된 no-action proof 안에서만 허용한다. EOD replay는 해당 계좌 snapshot에 고정된 initial cash와 currency를 사용한다.

Stage A child만 frozen market DB override를 받고 parent와 Stage B~F는 원래 DB 환경을 유지한다. 실제 Notion, network download, broker/live Paper, n8n, scheduler는 호출하지 않는다. Daily 00~04와 root 00~10 wrapper numbering은 유지한다.
