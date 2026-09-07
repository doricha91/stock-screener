저장소 루트의 `AGENTS.md`를 먼저 읽고 적용해줘.

그다음 `docs/DEVELOPMENT_WORKFLOW.md`를 읽고, 아래 작업지시문을 처음부터 끝까지 읽어 이번 작업의 기준으로 삼아줘.

`<작업지시문 경로>`

저장소는 `D:\python\StockScreener`이야.

문서/지시가 충돌하면 `AGENTS.md`의 우선순위 규칙을 따른다.

작업 시작 전에 다음만 확인해줘.

1. 작업지시문 경로와 제목
2. 현재 branch와 HEAD
3. `git status --short`
4. 작업을 실제로 막는 blocking condition이 있는지

중단된 작업을 재개하는 경우 이전 대화보다 현재 worktree와 `git diff`를 사실 기준으로 삼고, 이미 완료된 조사·구현·테스트를 반복하지 말고 남은 작업부터 진행해줘.

안전하게 진행 가능한 구현 선택지가 여러 개라면 별도 선택을 묻지 말고, 확정 정책 안에서 기존 구조와 helper/SSOT를 재사용하는 가장 작은 변경으로 진행해줘. 실제 blocking condition일 때만 중단하고 질문해줘.

현재 작업지시문의 Phase 범위와 검증 범위를 우선하고, 필요 없이 같은 조사·테스트나 전체 pytest를 반복하지 마.

최종 리뷰 Phase라면 별도 규칙이 없는 한 `DEVELOPMENT_WORKFLOW.md`의 표준 review bundle을 생성해줘.

commit, push, merge, rebase, force push, 다음 Phase/MFU 시작은 현재 작업지시문 또는 closeout 절차에서 명시적으로 허용한 경우에만 수행해줘.
