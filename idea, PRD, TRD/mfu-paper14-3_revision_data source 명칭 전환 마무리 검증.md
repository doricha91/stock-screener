# MFU-PAPER14-3A_revision 작업 지시문: Data Source 명칭 전환 마무리 검증

## 목적

MFU-PAPER14-3A에서 수행한 Notion 설정 레이어의 database id → data source id 명칭 전환 작업을 마무리 검증한다.

이번 revision은 기능 확장이 아니라, 아래 항목을 확인·보완하는 작업이다.

1. database_key / database id 표현 잔존 여부 점검
2. data_source_key / data source id 표현으로 문서와 출력 정리
3. 기존 호환성 유지 여부 확인
4. 실제 token / data source id 노출 방지 확인
5. 실제 Notion write 없이 dry-run과 테스트만 수행

반드시 명시:

이번 MFU-PAPER14-3A_revision은 Notion 설정 명칭 전환 마무리 검증이며, Weekly / Benchmark / Account Snapshot의 실제 Notion export는 포함하지 않는다.

---

## 배경

PAPER14-3A 결과 보고에 따르면 아래 작업이 완료됐다.

```text
- 공식 설정 키를 data_sources로 전환
- load_notion_settings()는 data_sources를 우선 읽고 databases를 deprecated fallback으로 허용
- NotionSettings.data_sources를 공식 필드로 전환
- NotionSettings.databases는 deprecated alias로 유지
- get_notion_data_source_id() 추가
- get_notion_database_id()는 호환 wrapper로 유지
- env override 우선순위 유지
- exporter 결과 summary 필드를 database_key에서 data_source_key로 정리
- 실제 Notion write/export는 미수행