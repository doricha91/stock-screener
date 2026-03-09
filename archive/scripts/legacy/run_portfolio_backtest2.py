import pandas as pd
from screener import data_manager, strategy, indicator
from tqdm import tqdm
import sqlite3
from datetime import datetime

# ==========================================
# ⚙️ 포트폴리오 설정 (자금 관리)
# ==========================================
PORTFOLIO_CONFIG = {
    'initial_capital': 100000.0,  # 초기 자본 ($100,000)
    'risk_per_trade': 0.05,  # 1회 매매당 계좌의 2% 리스크 부담
    'max_positions': 5,  # 최대 보유 종목 수 (분산 투자)

    # 전략 설정 (확정된 20/20)
    'entry_period': 20,
    'exit_period': 20,
    'score_threshold': 2.0,
    'turtle_weight': 2.0,

    # 기타 지표 설정 (indicator.py 기본값과 일치시킴)
    'atr_period': 20,
    'rsi_period': 14,
    'sma_short_period': 50,
    'sma_long_period': 200,
    'bbands_period': 20,
    'macd_fast_period': 12,
    'macd_slow_period': 26,
    'dema_short_period': 20
}


# ==========================================
# 1. 데이터 전처리 (Pre-calculation)
# ==========================================
def prepare_market_data(tickers):
    """
    모든 종목의 지표, 신호, 강도(Strength)를 미리 계산하여
    날짜별로 조회하기 쉬운 딕셔너리 형태로 변환합니다.
    """
    print("⏳ 데이터 전처리 및 신호 생성 중... (시간이 좀 걸립니다)")

    all_signals = []
    error_counts = 0

    # 진행률 표시 (tqdm)
    for symbol in tqdm(tickers):
        try:
            # 1. 데이터 로드 (data_manager.py 사용)
            # - index: date (datetime)
            # - columns: open, high, low, close, volume, ...
            df = data_manager.get_price_data(symbol, start_date='2018-01-01')

            if df is None or len(df) < 100:
                continue

            # 2. 지표 및 신호 계산 (indicator.py 사용)
            context = PORTFOLIO_CONFIG.copy()
            context['symbol'] = symbol  # 에러 로그용

            # --- 지표 계산 (순서 중요하지 않음) ---
            df = indicator.add_turtle_indicators(df, context)
            df = indicator.add_atr_indicators(df, context)
            df = indicator.add_rsi_indicators(df, context)
            df = indicator.add_sma_indicators(df, context)
            df = indicator.add_bollinger_band_indicators(df, context)
            df = indicator.add_macd_indicators(df, context)
            df = indicator.add_bbs_indicators(df, context)
            df = indicator.add_dema_indicators(df, context)

            # 3. 전략 적용 (strategy.py 사용)
            # - 각 전략 함수가 signal_turtle, signal_rsi 등의 컬럼을 생성함
            df = strategy.apply_ensemble_strategy(df, context)

            # 4. 앙상블 점수 합산
            # (strategy.py가 생성한 signal_XXX 컬럼들을 사용)
            weights = {
                'turtle': context['turtle_weight'],
                'rsi': 1.0,
                'sma': 1.0,
                'bbands': 1.0,
                'macd': 1.0,
                'bbs': 1.5,
                'dema': 1.0
            }

            df['score'] = 0.0
            for name, weight in weights.items():
                col_name = f'signal_{name}'
                if col_name in df.columns:
                    # 1이면 가중치 더하고, 아니면 0
                    df['score'] += df[col_name].apply(lambda x: weight if x == 1 else 0)

            # 5. 강도(Strength) 계산 (우선순위용)
            # - 평소 거래량 대비 현재 거래량 비율
            df['vol_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
            df['symbol'] = symbol

            # 6. 최종 매매 신호 생성
            # - Buy: 점수 만족 AND (오늘 종가가 20일 고가 돌파)
            # - Sell: 오늘 종가가 10일(or 20일) 저가 이탈

            # indicator.py 코드를 보면 'entry_high', 'exit_low' 컬럼이 생성됨
            if 'entry_high' not in df.columns or 'exit_low' not in df.columns:
                continue  # 지표 생성 실패 시 스킵

            # shift(1)은 '어제까지의 고가'를 의미. 오늘 종가가 그걸 뚫어야 함.
            df['buy_signal'] = (df['score'] >= context['score_threshold']) & (df['close'] > df['entry_high'])
            df['sell_signal'] = df['close'] < df['exit_low']

            # === [핵심 수정] 날짜 인덱스를 컬럼으로 변환 ===
            # 이미 date가 컬럼에 있다면 reset_index를 하지 않음
            if 'date' not in df.columns:
                df = df.reset_index()

            # 컬럼명 소문자 통일 (Date -> date)
            df.rename(columns={'Date': 'date', 'index': 'date'}, inplace=True)

            # 필요한 컬럼만 추출 (메모리 절약)
            required_cols = ['date', 'symbol', 'open', 'high', 'low', 'close', 'atr', 'buy_signal', 'sell_signal',
                             'score', 'vol_ratio']

            # 없는 컬럼이 있으면 에러 나지 않게 필터링
            available_cols = [c for c in required_cols if c in df.columns]

            all_signals.append(df[available_cols])

        except Exception as e:
            error_counts += 1
            if error_counts <= 3:  # 처음 3개까지만 에러 출력
                print(f"\n⚠️ [Error - {symbol}] {e}")
            continue

    if not all_signals:
        print(f"\n❌ 모든 종목({len(tickers)}개) 처리 실패! 데이터를 확인해주세요.")
        return {}, []

    print(f"🔄 총 {len(all_signals)}개 종목 데이터 병합 중...")
    full_df = pd.concat(all_signals)

    # 날짜 형식 보장
    full_df['date'] = pd.to_datetime(full_df['date'])

    # 날짜별로 정렬 (백테스트는 시간 순서가 생명)
    full_df = full_df.sort_values(['date', 'symbol'])

    # 날짜별 그룹화 (백테스트 루프 속도 향상)
    # { '2024-01-02': DataFrame_of_that_day, ... }
    grouped = {date: data for date, data in full_df.groupby('date')}

    # 유니크한 날짜 리스트 반환
    unique_dates = full_df['date'].sort_values().unique()

    return grouped, unique_dates


# ==========================================
# 2. 포트폴리오 클래스 (계좌 관리)
# ==========================================
class Portfolio:
    def __init__(self, initial_cash, risk_pct, max_pos):
        self.initial_capital = initial_cash
        self.cash = initial_cash
        self.equity = initial_cash
        self.risk_pct = risk_pct
        self.max_positions = max_pos

        # 보유 종목 정보: { 'AAPL': {'shares': 10, 'stop_loss': 140, 'last_price': 150} }
        self.positions = {}
        self.history = []

    def update_equity(self, current_prices):
        """현재가 기준으로 총 자산(Equity) 평가"""
        pos_value = 0
        for symbol, info in self.positions.items():
            if symbol in current_prices:
                price = current_prices[symbol]
                pos_value += info['shares'] * price
                self.positions[symbol]['last_price'] = price  # 가격 업데이트
            else:
                # 오늘 데이터가 없으면(거래정지 등) 어제 가격 유지
                pos_value += info['shares'] * info['last_price']

        self.equity = self.cash + pos_value
        return self.equity

    def can_buy(self):
        """매수 가능 여부 확인 (슬롯 & 현금)"""
        return len(self.positions) < self.max_positions and self.cash > 0

    # def calculate_shares(self, price, atr):
    #     """
    #     [자금 관리] 변동성 조절 (Volatility Sizing)
    #     - ATR이 크면 조금 사고, 작으면 많이 산다.
    #     - 1회 손실 허용액 = 총자산 * 2%
    #     """
    #     if pd.isna(atr) or atr == 0: return 0
    #     risk_amount = self.equity * self.risk_per_trade
    #     stop_loss_gap = 2.0 * atr  # 손절폭 (2ATR)
    #     if stop_loss_gap == 0: return 0
    #     shares = int(risk_amount / stop_loss_gap)
    #     # 현금 부족 시 조정
    #     cost = shares * price
    #     if cost > self.cash:
    #         shares = int(self.cash / price)
    #     return shares

    def calculate_shares(self, price, atr):
        """
        [수정된 자금 관리] 동일 비중 (Equal Weight)
        - ATR 계산 없이, 정해진 슬롯만큼 균등하게 배분합니다.
        - 예: 5종목 제한이면, 한 종목당 내 자산의 20%씩 매수.
        """
        if price == 0: return 0

        # 1. 한 종목당 배정할 금액 (총자산 / 최대종목수)
        # 예: 1억 원 / 5종목 = 2,000만 원
        target_amount = self.equity / self.max_positions

        # 2. 매수 가능 수량 계산
        shares = int(target_amount / price)

        # 3. 현금 부족 시 조정 (자투리 현금으로 살 수 있는 만큼만)
        cost = shares * price
        if cost > self.cash:
            shares = int(self.cash / price)

        return shares

    @property
    def risk_per_trade(self):
        return self.risk_pct


# ==========================================
# 3. 백테스트 엔진 (Time Loop)
# ==========================================
def run_portfolio_simulation():
    tickers = data_manager.get_ticker_list()
    # tickers = tickers[:50] # (테스트용)

    # 1. 데이터 준비
    market_data, date_list = prepare_market_data(tickers)
    if not market_data: return

    # 2. 포트폴리오 초기화
    pf = Portfolio(
        PORTFOLIO_CONFIG['initial_capital'],
        PORTFOLIO_CONFIG['risk_per_trade'],
        PORTFOLIO_CONFIG['max_positions']
    )

    print(f"🚀 포트폴리오 시뮬레이션 시작 (기간: {len(date_list)}일)")

    for date in tqdm(date_list):
        # 오늘 날짜의 전체 종목 데이터 가져오기
        day_data = market_data[date]
        day_data = day_data.set_index('symbol')  # 심볼을 인덱스로 변환

        # A. 자산 평가 (Mark-to-Market)
        current_prices = day_data['close'].to_dict()
        pf.update_equity(current_prices)
        pf.history.append({'date': date, 'equity': pf.equity, 'cash': pf.cash})

        # B. 매도 (Sell)
        symbols_to_sell = []
        for symbol, info in pf.positions.items():
            # 오늘 데이터가 없으면 매도 불가
            if symbol not in day_data.index: continue

            row = day_data.loc[symbol]
            price = row['close']

            # 매도 조건: Exit 신호 OR 손절가 터치
            is_exit = row['sell_signal']
            # is_stop = price < info['stop_loss']

            if is_exit: # or is_stop:
                revenue = info['shares'] * price
                pf.cash += revenue
                symbols_to_sell.append(symbol)

        for sym in symbols_to_sell:
            del pf.positions[sym]

        # C. 매수 (Buy)
        if pf.can_buy():
            # 1. 매수 후보 찾기
            candidates = day_data[day_data['buy_signal'] == True]
            # 이미 보유한 종목 제외
            candidates = candidates[~candidates.index.isin(pf.positions.keys())]

            if not candidates.empty:
                # 2. 우선순위 정렬 (점수 -> 거래량강도)
                # candidates = candidates.sort_values(by=['score', 'vol_ratio'], ascending=[False, False])
                candidates = candidates.sort_values(by=['score', 'atr'], ascending=[False, True])

                # 3. 매수 집행
                for symbol, row in candidates.iterrows():
                    if not pf.can_buy(): break  # 슬롯 차면 중단

                    price = row['close']
                    # atr = row['atr']

                    shares = pf.calculate_shares(price, 0)

                    if shares > 0:
                        cost = shares * price
                        pf.cash -= cost

                        # 포트폴리오 등록
                        pf.positions[symbol] = {
                            'shares': shares,
                            'entry_price': price,
                            'stop_loss': 0,
                            'last_price': price
                        }

    # 4. 결과 분석
    analyze_results(pf)


def analyze_results(pf):
    if not pf.history:
        print("거래 내역이 없습니다.")
        return

    history_df = pd.DataFrame(pf.history)
    history_df['date'] = pd.to_datetime(history_df['date'])
    history_df.set_index('date', inplace=True)

    # 최종 결과 계산
    initial = pf.initial_capital
    final = history_df['equity'].iloc[-1]
    total_return = ((final - initial) / initial) * 100

    # MDD
    rolling_max = history_df['equity'].cummax()
    drawdown = (history_df['equity'] - rolling_max) / rolling_max
    mdd = drawdown.min() * 100

    # CAGR
    days = (history_df.index[-1] - history_df.index[0]).days
    if days > 0:
        cagr = ((final / initial) ** (365 / days) - 1) * 100
    else:
        cagr = 0.0

    print("\n" + "=" * 50)
    print(f"📊 [포트폴리오 백테스트 최종 결과]")
    print("=" * 50)
    print(f"📅 기간: {history_df.index[0].date()} ~ {history_df.index[-1].date()} ({days}일)")
    print(f"💰 초기 자본: ${initial:,.0f}")
    print(f"💰 최종 자본: ${final:,.0f}")
    print("-" * 50)
    print(f"🚀 총 수익률 : {total_return:.2f}%")
    print(f"📈 연평균(CAGR): {cagr:.2f}%")
    print(f"🛡️ MDD      : {mdd:.2f}%")
    print("-" * 50)

    save_portfolio_result(total_return, mdd, cagr, final)


def save_portfolio_result(ret, mdd, cagr, final):
    try:
        conn = sqlite3.connect("../../outputs/backtest_log.db")
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS portfolio_log (
                run_date TEXT,
                strategy TEXT,
                return_pct REAL,
                mdd_pct REAL,
                cagr_pct REAL,
                final_equity REAL
            )
        ''')
        cursor.execute("INSERT INTO portfolio_log VALUES (?, ?, ?, ?, ?, ?)",
                       (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'Ensemble_20_20_VarRatio', ret, mdd, cagr, final))
        conn.commit()
        conn.close()
        print("💾 결과가 DB(backtest_log.db)에 저장되었습니다.")
    except Exception as e:
        print(f"❌ DB 저장 실패: {e}")


if __name__ == "__main__":
    run_portfolio_simulation()