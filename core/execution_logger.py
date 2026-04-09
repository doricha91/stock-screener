# core/execution_logger.py
import os
import re
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from core.paths import FRONT_TEST_DIR

EXECUTION_LOG_PATH = FRONT_TEST_DIR / "execution_log.csv"

def clean_numeric(text: str) -> str:
    """문자열에서 숫자와 소수점을 제외한 모든 문자를 제거합니다."""
    return re.sub(r"[^0-9.]", "", text)

def parse_journal_from_markdown(file_path: Path) -> List[Dict[str, Any]]:
    """
    마크다운 리포트에서 저널 테이블을 파싱합니다.
    - [ ] 빈칸 감지 시 ValueError 발생
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Markdown report not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    journal_data = []
    table_started = False
    
    # 헤더 정의 (순서 중요)
    columns = [
        "Date", "Regime", "Symbol", "Type", "Rec_Shares", 
        "Rec_Price", "Act_Shares", "Act_Price", "Reason", "Notes"
    ]

    for line in lines:
        # 저널 섹션 시작 탐색
        if "## 5. 📝 프론트테스트 실행 기록" in line:
            table_started = True
            continue
        
        if table_started and "|" in line:
            # 헤더나 구분선(| --- |)은 건너뜀
            if "Date" in line or "---" in line:
                continue
            
            # 데이터 행 분리
            parts = [p.strip() for p in line.split("|") if p.strip()]
            
            # 'No Action' 행 처리 (예외 케이스)
            if len(parts) >= 3 and "WAIT" in parts[3]:
                continue

            if len(parts) < 9: # Notes는 비어있을 수 있으므로 최소 9개 컬럼 확인
                continue

            # 데이터 정제 (Bold 표시 제거 등)
            row = {}
            for i, col in enumerate(columns):
                val = parts[i].replace("**", "").strip() if i < len(parts) else ""
                
                # 지침 2: 미입력 빈칸 검증
                if col in ["Act_Shares", "Act_Price", "Reason"] and ("[ ]" in val or not val):
                    raise ValueError(f"❌ [Fail-safe] {col} is empty for symbol {parts[2]}. Please fill the journal first.")
                
                row[col] = val
            
            journal_data.append(row)
            
        elif table_started and line.strip() == "" and journal_data:
            # 테이블 종료 (빈 줄 발견 시)
            break

    return journal_data

def append_to_execution_log(new_entries: List[Dict[str, Any]]):
    """실제 체결 내역을 CSV 파일에 누적 적재합니다."""
    df_new = pd.DataFrame(new_entries)
    
    # 지침 2: 중복 제거 로직 삭제 (분할 매매 데이터 유실 방지)
    if EXECUTION_LOG_PATH.exists():
        df_old = pd.read_csv(EXECUTION_LOG_PATH)
        df_combined = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df_combined = df_new
        
    df_combined.to_csv(EXECUTION_LOG_PATH, index=False, encoding="utf-8-sig")
    print(f"✅ Execution log updated: {len(new_entries)} rows added to {EXECUTION_LOG_PATH.name}")

def map_journal_to_trades(journal_entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """저널 데이터를 FT3 상태 업데이트용 포맷으로 변환합니다."""
    trades = []
    for j in journal_entries:
        # 지침 1: SELL 타입인 경우 수량을 음수로 변환
        raw_shares = int(clean_numeric(j["Act_Shares"]))
        is_sell = j["Type"].upper() in ["SELL", "매도"]
        actual_shares = -abs(raw_shares) if is_sell else abs(raw_shares)
        
        trades.append({
            "symbol": j["Symbol"],
            "type": j["Type"],
            "shares": actual_shares,
            "price": float(clean_numeric(j["Act_Price"]))
        })
    return trades
