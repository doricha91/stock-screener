import pandas as pd
import config


def run_backtest(df_signals, initial_capital, context):
    """
    매매 신호(df_signals)를 기반으로 가상 매매를 실행합니다.
    (★) strategy_name에 따라 서로 다른 리스크 관리 로직을 적용합니다.
    """

    # 1. 초기 설정
    cash = initial_capital
    shares = 0
    portfolio_value = initial_capital

    portfolio_history = []
    trade_history = []

    buy_price = 0.0
    stop_loss_price = 0.0

    # 전략 이름 로드
    strategy_name = context.get('strategy_name', 'turtle')

    # 리스크 파라미터 로드
    risk_percent = context.get('risk_percent', 0.01)
    stop_loss_atr_multiplier = context.get('stop_loss_atr', 2.0)

    for date, row in df_signals.iterrows():

        current_equity = (shares * row['close']) + cash

        # --- [ (★) 핵심 수정 1: 신호 해석 로직 강화 ] ---
        # 숫자(1, -1)와 문자('Buy', 'Sell')를 모두 처리하도록 변수 통일
        raw_signal = row['signal']
        is_buy_signal = (raw_signal == 1) or (raw_signal == 'Buy')
        is_sell_signal = (raw_signal == -1) or (raw_signal == 'Sell')
        # -----------------------------------------------

        # ================================================================
        #  A. ATR 기반 리스크 관리 전략 (SMA 제외 나머지)
        # ================================================================
        if strategy_name in ['turtle', 'rsi', 'bbands', 'macd', 'bbs', 'dema']:

            # 1. Stop-Loss 실행 로직 (ATR 손절)
            if shares > 0 and row['low'] <= stop_loss_price:
                sell_price = stop_loss_price
                cash += sell_price * shares
                trade_history.append({
                    'date': date,
                    'type': 'Stop-Loss',
                    'price': sell_price,
                    'shares': shares,
                    'pnl': (sell_price - buy_price) * shares  # PnL 기록 추가
                })
                shares = 0
                buy_price = 0.0
                stop_loss_price = 0.0

            # 2. 'Buy' 신호 로직 (ATR 포지션 사이징)
            elif is_buy_signal and shares == 0:
                # ATR 값이 유효한지 확인 (NaN이 아니어야 함)
                if pd.notna(row.get('atr')) and row['atr'] > 0:
                    risk_amount = current_equity * risk_percent
                    atr = row['atr']
                    risk_per_share = atr * stop_loss_atr_multiplier

                    shares_to_buy = int(risk_amount / risk_per_share)
                    trade_cost = shares_to_buy * row['close']

                    if cash >= trade_cost and shares_to_buy > 0:
                        shares = shares_to_buy
                        cash -= trade_cost
                        buy_price = row['close']
                        stop_loss_price = buy_price - risk_per_share

                        trade_history.append({
                            'date': date,
                            'type': 'Buy',
                            'price': buy_price,
                            'shares': shares_to_buy,
                            'pnl': 0
                        })

            # 3. 'Sell' 신호 로직
            elif is_sell_signal and shares > 0:
                sell_price = row['close']
                cash += sell_price * shares
                trade_history.append({
                    'date': date,
                    'type': 'Sell',
                    'price': sell_price,
                    'shares': shares,
                    'pnl': (sell_price - buy_price) * shares  # PnL 기록 추가
                })
                shares = 0
                buy_price = 0.0
                stop_loss_price = 0.0

        # ================================================================
        #  B. SMA 전략 (100% 매수/매도)
        # ================================================================
        elif strategy_name == 'sma':

            # 1. 'Buy' 신호 로직 (100% 매수)
            if is_buy_signal and shares == 0:
                shares_to_buy = int(cash / row['close'])

                if shares_to_buy > 0:
                    trade_cost = shares_to_buy * row['close']
                    shares = shares_to_buy
                    cash -= trade_cost
                    buy_price = row['close']  # 수익 계산용

                    trade_history.append({
                        'date': date,
                        'type': 'Buy',
                        'price': row['close'],
                        'shares': shares_to_buy,
                        'pnl': 0
                    })

            # 2. 'Sell' 신호 로직
            elif is_sell_signal and shares > 0:
                sell_price = row['close']
                cash += sell_price * shares
                trade_history.append({
                    'date': date,
                    'type': 'Sell',
                    'price': sell_price,
                    'shares': shares,
                    'pnl': (sell_price - buy_price) * shares  # PnL 기록 추가
                })
                shares = 0

        # 4. 일별 포트폴리오 가치 기록
        # --- [ (★) 핵심 수정 2: metrics.py 호환성 확보 ] ---
        # cash, shares, total_asset 컬럼을 명시적으로 추가해야 metrics가 계산됩니다.
        portfolio_value = (shares * row['close']) + cash
        portfolio_history.append({
            'date': date,
            'portfolio_value': portfolio_value,  # 기존 호환
            'total_asset': portfolio_value,  # metrics 호환
            'cash': cash,  # Exposure 계산용
            'shares': shares,
            'close': row['close']
        })

    df_portfolio = pd.DataFrame(portfolio_history).set_index('date')

    return df_portfolio, trade_history