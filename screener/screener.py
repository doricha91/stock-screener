import pandas as pd
from tqdm import tqdm
import time
import sqlite3

# 만든 모듈들 임포트
import data_manager
import market_analyzer
import indicator
import strategy
import config  # 설정값 (필요시)

# ==========================================
# ⚙️ 앙상블 전략 설정 (가중치 및 기준점)
# ==========================================
# 각 전략이 매수 신호(1)를 낼 때 부여할 점수입니다.
STRATEGY_WEIGHTS = {
    'turtle': 2.0,  # 추세 추종 (가장 중요)
    'rsi': 1.0,  # 눌림목
    'sma': 1.0,  # 골든크로스
    'bbands': 1.0,  # 볼린저밴드 하단
    'macd': 1.0,  # 추세 반전
    'bbs': 1.5,  # 변동성 돌파
    'dema': 1.0  # 빠른 이평선
}

# 매수 추천을 위한 최소 합산 점수
# config.py에 있는 값을 우선 사용하고, 없으면 기본값 2.0 사용
SCORE_THRESHOLD = getattr(config, 'SCORE_THRESHOLD', 2.0)

# 지표 계산에 사용할 기본 파라미터 (백테스트 최적값 적용 가능)
DEFAULT_PARAMS = {
    'entry_period': 20, 'exit_period': 10, 'atr_period': 20,
    'rsi_period': 14, 'rsi_oversold': 30, 'rsi_overbought': 70,
    'sma_short_period': 50, 'sma_long_period': 200,
    'bbands_period': 20, 'bbands_std_dev': 2.0,
    'macd_fast_period': 12, 'macd_slow_period': 26, 'macd_signal_period': 9,
    'bbs_period': 20, 'bbs_std_dev': 2.0, 'bbs_squeeze_period': 120,
    'dema_short_period': 20, 'dema_long_period': 50
}


# ==========================================
# 🛠️ 내부 헬퍼 함수
# ==========================================

def _prepare_data_for_ensemble(df):
    """
    모든 전략의 지표를 계산하여 DataFrame에 추가합니다.
    """
    if df is None or df.empty: return None

    # 각 전략에 필요한 지표 함수들을 순차적으로 호출
    try:
        df = indicator.add_turtle_indicators(df, DEFAULT_PARAMS)
        df = indicator.add_rsi_indicators(df, DEFAULT_PARAMS)
        df = indicator.add_sma_indicators(df, DEFAULT_PARAMS)
        df = indicator.add_bollinger_band_indicators(df, DEFAULT_PARAMS)
        df = indicator.add_macd_indicators(df, DEFAULT_PARAMS)
        df = indicator.add_bbs_indicators(df, DEFAULT_PARAMS)
        df = indicator.add_dema_indicators(df, DEFAULT_PARAMS)
    except Exception as e:
        # 지표 계산 중 에러 발생 시 해당 종목 스킵
        return None

    return df


def _calculate_ensemble_score(latest_row):
    """
    최신 데이터 한 행(Row)을 받아 가중치 점수를 계산합니다.
    """
    total_score = 0.0
    triggered_strategies = []

    for strat_name, weight in STRATEGY_WEIGHTS.items():
        col_name = f'signal_{strat_name}'

        # 해당 전략의 신호 컬럼이 있고, 신호가 1(매수)인 경우
        if col_name in latest_row and latest_row[col_name] == 1:
            total_score += weight
            triggered_strategies.append(strat_name)

    return total_score, triggered_strategies


# ==========================================
# 💾 DB 저장 함수 (신규 추가)
# ==========================================
def save_results_to_db(df_result):
    """
    스크리닝 결과를 DB의 'screener_history' 테이블에 저장합니다.
    """
    if df_result is None or df_result.empty:
        return

    # DB 경로 (config 혹은 하드코딩)
    db_path = getattr(config, 'BACKTEST_DB_NAME', '../outputs/market_data.db')
    # 주의: market_data.db에 저장할지, backtest_log.db에 저장할지 선택 필요.
    # 여기서는 데이터 관리를 위해 'market_data.db'를 기본으로 추천합니다.
    if hasattr(config, 'MARKET_DB_NAME'):
        db_path = config.MARKET_DB_NAME
    else:
        db_path = '../outputs/market_data.db'

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print(f"\n💾 DB 저장 중... ({db_path})")

    saved_count = 0
    try:
        # 테이블이 없으면 생성 (혹시 모르니 안전장치)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS screener_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE,
                symbol TEXT,
                price REAL,
                score REAL,
                strategies TEXT,
                market_regime TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(date, symbol)
            )
        """)

        # 데이터 삽입
        for _, row in df_result.iterrows():
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO screener_history 
                    (date, symbol, price, score, strategies, market_regime)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    row['Date'],
                    row['Symbol'],
                    float(row['Price']),
                    float(row['Score']),
                    row['Strategies'],
                    row['Market']
                ))
                saved_count += 1
            except Exception as e:
                print(f"   ⚠️ {row['Symbol']} 저장 실패: {e}")

        conn.commit()
        print(f"✅ 총 {saved_count}건의 추천 종목이 DB에 저장되었습니다.")

    except Exception as e:
        print(f"❌ DB 연결/저장 오류: {e}")
    finally:
        conn.close()


# ==========================================
# 🚀 메인 스크리너 함수
# ==========================================

def run_screener():
    """
    1. 시장 상태 확인 (Market Check)
    2. 전체 종목 순회 (Loop)
    3. 앙상블 점수 계산 (Scoring)
    4. 결과 리포트 반환 (Reporting)
    """
    print("\n" + "=" * 50)
    print("🕵️  STOCK SCREENER v5.3 (The Brain Edition)")
    print("=" * 50)

    # 1. 시장 상태 확인 [수정됨]
    print("\n[Step 1] 시장 날씨 확인 중...")

    # 수정: analyze_market_status() -> get_market_regime()
    try:
        regime, rule = market_analyzer.get_market_regime()
        status_code = regime
        description = rule.get('description', '')
    except AttributeError:
        # 혹시라도 구버전 파일이 있을 경우를 대비한 예외처리
        print("⚠️ market_analyzer 업데이트가 필요해 보입니다. (구버전 함수 호출 시도)")
        return []

    print(f" 👉 현재 시장: {status_code} | {description}")

    # [필터] 공포장(PANIC)이나 하락장(BEAR)이면 매수 추천을 하지 않음 (안전 제일)
    if status_code in ['PANIC']:
        print("\n⛔ 경고: 공포장(PANIC) 상태입니다. 모든 매수를 중단합니다.")
        return []

    if status_code == 'BEAR':
        print("\n⚠️ 주의: 하락장(BEAR)입니다. 보수적으로 접근하세요 (현금 비중 확대).")
        # 하락장에서도 스크리닝은 하되, 기준 점수를 높일 수도 있음 (선택 사항)

    # 2. 종목 리스트 가져오기
    print("\n[Step 2] 분석 대상 종목 로딩 중...")
    tickers = data_manager.get_ticker_list()
    # 테스트용으로 10개만 돌려보고 싶다면 아래 주석 해제
    # tickers = tickers[:10]
    print(f" 👉 총 {len(tickers)}개 종목 분석 시작")

    recommendations = []

    # 3. 전체 종목 순회 (tqdm으로 진행률 표시)
    print("\n[Step 3] 전략 앙상블 가동...")
    time.sleep(0.5)  # UX를 위한 짧은 대기

    for symbol in tqdm(tickers):
        try:
            # (1) 데이터 가져오기 (DB)
            # 최근 300일 치만 가져와도 충분 (속도 최적화)
            df = data_manager.get_price_data(symbol, start_date="2023-01-01")

            if df is None or len(df) < 200:  # 데이터가 너무 짧으면 패스
                continue

            # (2) 모든 지표 계산
            df = _prepare_data_for_ensemble(df)
            if df is None: continue

            # (3) 모든 전략 신호 생성 (strategy.py의 앙상블 함수 사용)
            df = strategy.apply_ensemble_strategy(df, DEFAULT_PARAMS)

            # (4) 점수 채점 (오늘 날짜 기준)
            latest_row = df.iloc[-1]
            score, reasons = _calculate_ensemble_score(latest_row)

            # (5) 합격자 선발
            if score >= SCORE_THRESHOLD:
                # 결과 저장
                rec = {
                    'Symbol': symbol,
                    'Date': latest_row.name.strftime('%Y-%m-%d'),
                    'Price': latest_row['close'],
                    'Score': score,
                    'Strategies': ", ".join(reasons),  # 어떤 전략들이 추천했는지 기록
                    'Market': status_code
                }
                recommendations.append(rec)

        except Exception as e:
            # 개별 종목 에러는 무시하고 계속 진행
            # print(f"Error analyzing {symbol}: {e}")
            continue

    # 4. 결과 정렬 및 출력
    print("\n[Step 4] 최종 결과 집계 중...")

    if not recommendations:
        print("\n🤷 조건에 부합하는 종목을 찾지 못했습니다.")
        return []

    # 점수 높은 순으로 정렬
    df_result = pd.DataFrame(recommendations)
    df_result = df_result.sort_values(by='Score', ascending=False).reset_index(drop=True)

    print(f"\n🎉 총 {len(df_result)}개 유망 종목 발견!\n")
    print(df_result[['Symbol', 'Price', 'Score', 'Strategies']].to_string())

    # [수정] DB 저장 함수 호출
    save_results_to_db(df_result)

    # 결과를 CSV로 저장 (선택)
    df_result.to_csv("screener_results.csv", index=False)
    print("\n💾 (백업) 결과가 'screener_results.csv' 파일로도 저장되었습니다.")

    return df_result


# 테스트용 실행
if __name__ == "__main__":
    run_screener()