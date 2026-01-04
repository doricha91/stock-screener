# run_live_trading.py (실전 알림 봇)

import pandas as pd
import json
import os
import requests
import data_manager
import indicator
import strategy
from datetime import datetime, timedelta

# ==========================================
# ⚙️ 실전 봇 설정 (LIVE_CONFIG)
# ==========================================
LIVE_CONFIG = {
    # 1. 텔레그램 설정 (본인의 토큰과 Chat ID로 변경 필요)
    'TELEGRAM_TOKEN': 'YOUR_BOT_TOKEN_HERE',
    'TELEGRAM_CHAT_ID': 'YOUR_CHAT_ID_HERE',

    # 2. 자금 및 포트폴리오 설정
    'MAX_POSITIONS': 5,  # 최대 보유 가능 종목 수
    'EQUAL_WEIGHT': 0.20,  # 종목당 비중 (1/5 = 20%)

    # 3. 전략 설정 (검증된 20/20 전략)
    'entry_period': 20,
    'exit_period': 20,
    'score_threshold': 2.0,
    'turtle_weight': 2.0,

    # 4. 보조지표 설정
    'atr_period': 20,
    'rsi_period': 14,
    'sma_short_period': 50,
    'sma_long_period': 200,
    'bbands_period': 20,
    'macd_fast_period': 12,
    'macd_slow_period': 26,
    'dema_short_period': 20
}

# 보유 종목 파일 경로 (현재 내가 가진 주식 목록)
PORTFOLIO_FILE = 'my_portfolio.json'


# ==========================================
# 🛠️ 헬퍼 함수: 텔레그램 전송 & 포트폴리오 관리
# ==========================================
def send_telegram_message(message):
    """텔레그램 메시지를 전송합니다."""
    token = LIVE_CONFIG['TELEGRAM_TOKEN']
    chat_id = LIVE_CONFIG['TELEGRAM_CHAT_ID']

    if token == 'YOUR_BOT_TOKEN_HERE':
        print("⚠️ 텔레그램 토큰이 설정되지 않아 콘솔에만 출력합니다.")
        print(message)
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {'chat_id': chat_id, 'text': message, 'parse_mode': 'Markdown'}

    try:
        response = requests.post(url, data=data)
        if response.status_code != 200:
            print(f"❌ 텔레그램 전송 실패: {response.text}")
    except Exception as e:
        print(f"❌ 텔레그램 에러: {e}")


def load_portfolio():
    """현재 보유 종목 리스트를 불러옵니다."""
    if not os.path.exists(PORTFOLIO_FILE):
        # 파일이 없으면 빈 템플릿 생성
        default_data = {"holdings": []}  # 예: ["AAPL", "NVDA"]
        with open(PORTFOLIO_FILE, 'w') as f:
            json.dump(default_data, f)
        return []

    with open(PORTFOLIO_FILE, 'r') as f:
        data = json.load(f)
        return data.get("holdings", [])


# ==========================================
# 🧠 핵심 로직: 종목 분석 (Analyze)
# ==========================================
def analyze_ticker(ticker):
    """개별 종목의 데이터를 가져와 매수/매도 신호를 분석합니다."""
    try:
        # [수정 전] 전체 데이터 로드 (느림)
        # df = data_manager.get_price_data(ticker)

        # [수정 후] 최근 365일 데이터만 로드 (빠름)
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        df = data_manager.get_price_data(ticker, start_date=start_date)

        if df is None or len(df) < 60: return None

        # 지표 계산
        context = LIVE_CONFIG.copy()
        context['symbol'] = ticker

        df = indicator.add_turtle_indicators(df, context)
        df = indicator.add_atr_indicators(df, context)
        df = indicator.add_rsi_indicators(df, context)
        df = indicator.add_sma_indicators(df, context)
        df = indicator.add_bollinger_band_indicators(df, context)
        df = indicator.add_macd_indicators(df, context)
        df = indicator.add_bbs_indicators(df, context)
        df = indicator.add_dema_indicators(df, context)

        df = strategy.apply_ensemble_strategy(df, context)

        # 점수 계산
        weights = {'turtle': 2.0, 'rsi': 1.0, 'sma': 1.0, 'bbands': 1.0, 'macd': 1.0, 'bbs': 1.5, 'dema': 1.0}
        current_score = 0
        latest = df.iloc[-1]  # 가장 최근 데이터(오늘 종가)

        for name, weight in weights.items():
            if f'signal_{name}' in df.columns:
                if latest[f'signal_{name}'] == 1:
                    current_score += weight

        # 신호 판단 (어제 종가 대비 오늘 위치)
        # Entry: 점수 만족 & 오늘 종가가 20일 고가 돌파 상태
        # Exit: 오늘 종가가 20일 저가 이탈 상태

        # entry_high는 shift(1) 되어 있으므로 '어제까지의 20일 고가'임.
        buy_signal = (current_score >= context['score_threshold']) and (latest['close'] > latest['entry_high'])
        sell_signal = latest['close'] < latest['exit_low']

        return {
            'symbol': ticker,
            'close': latest['close'],
            'atr': latest['atr'],
            'score': current_score,
            'buy_signal': buy_signal,
            'sell_signal': sell_signal,
            'vol_ratio': latest['volume'] / df['volume'].rolling(20).mean().iloc[-1] if len(df) > 20 else 1.0
        }

    except Exception as e:
        # print(f"Error analysing {ticker}: {e}")
        return None


# ==========================================
# 🚀 메인 실행: 데일리 스캔
# ==========================================
def run_daily_scan():
    print("🔍 [Live Trading Bot] 시장 분석을 시작합니다...")

    # 1. 내 포트폴리오 로드
    my_holdings = load_portfolio()
    print(f"💼 현재 보유 종목: {my_holdings}")

    # 2. 전체 종목 리스트 로드
    tickers = data_manager.get_ticker_list()
    # tickers = tickers[:50] # 테스트용

    sell_candidates = []
    buy_candidates = []

    # 3. 전체 종목 스캔
    for ticker in tickers:
        result = analyze_ticker(ticker)
        if not result: continue

        # 보유 중인 종목 -> 매도 검사
        if ticker in my_holdings:
            if result['sell_signal']:
                sell_candidates.append(result)

        # 보유 중이지 않은 종목 -> 매수 검사
        else:
            if result['buy_signal']:
                buy_candidates.append(result)

    # 4. 매수 후보 정렬 (점수 높은 순 -> ATR 낮은 순)
    buy_candidates.sort(key=lambda x: (x['score'], -x['atr']), reverse=True)

    # 5. 리포트 생성 및 전송
    generate_report(my_holdings, sell_candidates, buy_candidates)


def generate_report(holdings, sells, buys):
    today_str = datetime.now().strftime('%Y-%m-%d')

    msg = f"🤖 *[System Trader 알림]*\n📅 날짜: {today_str}\n\n"

    # --- 매도 신호 ---
    if sells:
        msg += "🚨 *[매도 경보] Exit 신호 발생!* 🚨\n"
        for item in sells:
            msg += f"📉 *{item['symbol']}* (현재가 ${item['close']:.2f})\n"
            msg += "   └ 20일 신저가 이탈. 즉시 매도 추천.\n"
    else:
        msg += "✅ 보유 종목 중 매도 신호 없음 (Hold).\n"

    msg += "\n" + "-" * 20 + "\n\n"

    # --- 포트폴리오 상태 ---
    current_slots = len(holdings) - len(sells)  # 팔고 남은 슬롯
    empty_slots = LIVE_CONFIG['MAX_POSITIONS'] - current_slots

    msg += f"💼 *포트폴리오 상태*\n"
    msg += f"- 현재 보유: {len(holdings)}종목\n"
    msg += f"- 매도 예정: {len(sells)}종목\n"
    msg += f"- *남은 슬롯: {empty_slots}개*\n\n"

    # --- 매수 추천 ---
    if empty_slots > 0:
        msg += f"💎 *[매수 추천 Top {empty_slots}]*\n"

        # 남은 슬롯만큼만 추천
        targets = buys[:empty_slots]

        if targets:
            for item in targets:
                msg += f"🚀 *{item['symbol']}* (점수 {item['score']:.1f})\n"
                msg += f"   └ 진입가: ${item['close']:.2f} (종가매수)\n"
                msg += f"   └ 변동성(ATR): {item['atr']:.2f}\n"
        else:
            msg += "💤 살만한 종목이 없습니다 (조건 만족 X).\n"
    else:
        msg += "⛔ 포트폴리오가 꽉 찼습니다. 신규 매수 금지.\n"
        if buys:
            msg += f"(참고: {buys[0]['symbol']} 등 {len(buys)}개 포착됨)\n"

    # 전송
    print("\n" + msg)  # 콘솔 출력
    send_telegram_message(msg)  # 텔레그램 전송


if __name__ == "__main__":
    run_daily_scan()