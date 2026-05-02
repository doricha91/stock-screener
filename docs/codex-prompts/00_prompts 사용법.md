# 각 prompts 역할
00 = 이해시키기
01 = 조사시키기
02 = 작게 고치기
03 = 테스트 남기기
04 = 검토시키기

# 기본 루틴
01_bug_investigation.md
→ 02_small_fix.md
→ 04_diff_review.md
→ 필요 시 03_test_addition.md

# codex 운영 원칙
1. 무엇을 할지
2. 어디까지 수정해도 되는지
3. 무엇은 절대 하면 안 되는지