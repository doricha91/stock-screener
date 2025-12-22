# [ 📄 backtesting/metrics.py (DCA 수정본) ]

import pandas as pd
import numpy as np  # (DCA 로직에 필요)


def calculate_metrics(portfolio_history, trade_history, df_signals, initial_capital):
    """
    성과 통계, 벤치마크(B&H, DCA), 그리고 트레이딩 상세 지표(SQN, 손익비)를 계산합니다.

    :param portfolio_history: engine에서 반환된 일별 포트폴리오 DataFrame
    :param trade_history: engine에서 반환된 거래 내역 list
    :param df_signals: (신규) 원본 가격 데이터 (벤치마크 계산용)
    :param initial_capital: 초기 자본금
    :return: (dict) 통계 지표 딕셔너리
    """

    stats = {}

    # 1. 총 수익률 (Total Return) - (기존 코드)
    if not portfolio_history.empty:
        final_value = portfolio_history['portfolio_value'].iloc[-1]
        total_return_pct = (final_value / initial_capital) - 1
        stats['total_return_pct'] = total_return_pct
        stats['final_value'] = final_value

        # MDD
        portfolio_history['peak'] = portfolio_history['portfolio_value'].cummax()
        portfolio_history['drawdown'] = (portfolio_history['portfolio_value'] / portfolio_history['peak']) - 1
        max_drawdown = portfolio_history['drawdown'].min()
        stats['max_drawdown_pct'] = max_drawdown

        # [수정됨] Exposure (시장 노출도) 안전하게 계산
        # 'cash' 컬럼이 존재할 때만 계산, 없으면 0 처리
        if 'cash' in portfolio_history.columns:
            total_days = len(portfolio_history)
            # 현금 비중이 99% 미만인 날 = 주식 보유일
            invested_days = portfolio_history[portfolio_history['cash'] < (portfolio_history['portfolio_value'] * 0.99)].shape[0]
            exposure_pct = (invested_days / total_days) * 100.0
        else:
            exposure_pct = 0.0  # 'cash' 정보가 없으면 0으로 처리 (에러 방지)

        stats['exposure_pct'] = exposure_pct

    else:
        stats['total_return_pct'] = 0.0
        stats['final_value'] = initial_capital
        stats['max_drawdown_pct'] = 0.0
        stats['exposure_pct'] = 0.0

    # --- 2. 트레이딩 상세 지표 (승률, 손익비, SQN) ---
    total_trades = 0
    winning_trades = 0
    gross_profit = 0.0
    gross_loss = 0.0
    trade_returns = []  # SQN 계산용 수익률 리스트

    # trade_history 구조: {'date':..., 'type': 'Sell', 'price':..., 'pnl':...} 가정
    # engine.py에서 trade_history에 'pnl'(실현손익)을 넣어준다고 가정하고 계산합니다.
    # 만약 pnl이 없다면 기존 방식대로 계산합니다.

    # 기존 코드의 흐름을 살려 계산
    current_buy_price = 0.0

    for trade in trade_history:
        if trade['type'] == 'Buy':
            current_buy_price = trade['price']

        elif trade['type'] in ['Sell', 'Stop-Loss']:
            if current_buy_price > 0:
                total_trades += 1

                # 수익률 계산
                pnl_amount = trade['price'] - current_buy_price
                pnl_pct = pnl_amount / current_buy_price
                trade_returns.append(pnl_pct)

                # 승률 체크
                if pnl_amount > 0:
                    winning_trades += 1
                    gross_profit += pnl_amount
                else:
                    gross_loss += abs(pnl_amount)

                current_buy_price = 0.0

    # (1) 승률
    win_rate = (winning_trades / total_trades) if total_trades > 0 else 0.0
    stats['win_rate_pct'] = win_rate  # 0.55 (=55%)

    # (2) 손익비 (Profit Factor)
    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss
    else:
        profit_factor = gross_profit if gross_profit > 0 else 0.0  # 손실 0이면 수익 자체가 PF
    stats['profit_factor'] = profit_factor

    # (3) SQN (System Quality Number)
    sqn = 0.0
    if total_trades > 1:  # 표준편차 계산 위해 최소 2개 필요
        avg_return = np.mean(trade_returns)
        std_return = np.std(trade_returns)
        if std_return > 0:
            sqn = (avg_return / std_return) * np.sqrt(total_trades)
    stats['sqn'] = sqn

    stats['total_trades'] = total_trades

    # 4. 벤치마크: Buy & Hold 수익률 계산 - (기존 코드)
    if not df_signals.empty:
        first_close = df_signals['close'].iloc[0]
        last_close = df_signals['close'].iloc[-1]
        buy_and_hold_pct = (last_close / first_close) - 1
        stats['buy_and_hold_pct'] = buy_and_hold_pct
    else:
        stats['buy_and_hold_pct'] = 0.0

    # --- [ 5. (신규) 벤치마크: DCA (적립식) ] ---
    # (가정: 매월 100달러씩, 월초 첫 거래일에 매수)
    DCA_MONTHLY_AMOUNT = 100.0

    total_invested_cash = 0.0
    total_shares_held = 0.0
    last_month = -1

    if not df_signals.empty:
        for date, row in df_signals.iterrows():
            current_month = date.month

            # 1. 월이 바뀌었고,
            # 2. (선택) 데이터가 너무 적어(예: 100일) 월이 안 바뀌는 경우, 첫날 1회 매수
            if current_month != last_month or (last_month == -1 and total_invested_cash == 0):
                # $100로 현재 종가에 몇 주를 살 수 있는가
                shares_to_buy = DCA_MONTHLY_AMOUNT / row['close']

                total_shares_held += shares_to_buy
                total_invested_cash += DCA_MONTHLY_AMOUNT

                last_month = current_month

        # 최종 가치 계산
        final_dca_value = total_shares_held * df_signals['close'].iloc[-1]

        if total_invested_cash > 0:
            dca_return_pct = (final_dca_value / total_invested_cash) - 1
            stats['dca_return_pct'] = dca_return_pct
            stats['dca_total_invested'] = total_invested_cash
        else:
            stats['dca_return_pct'] = 0.0
            stats['dca_total_invested'] = 0.0
    else:
        stats['dca_return_pct'] = 0.0
        stats['dca_total_invested'] = 0.0

    # --- [ (★) 중요: DB 저장용 키 매핑 ] ---
    # run_optimization.py와 view_db.py가 사용하는 키 이름과 단위(%)를 맞춰줍니다.

    stats['total_return'] = stats['total_return_pct'] * 100.0
    stats['max_drawdown'] = stats['max_drawdown_pct'] * 100.0
    stats['buy_and_hold_return'] = stats['buy_and_hold_pct'] * 100.0
    stats['win_rate'] = stats['win_rate_pct']  # (0.55 형태, 출력시 *100 필요)

    # SQN, Exposure, Profit Factor는 그대로 전달
    # (이미 계산됨)

    return stats