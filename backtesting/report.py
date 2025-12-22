# [ 📄 backtesting/report.py (최종 수정본) ]

def show_console_report(stats, context):
    """
    계산된 통계(stats) 및 벤치마크 비교를 콘솔에 출력합니다.
    (전략 이름에 따라 동적 리포트 제목 생성)

    :param stats: metrics.py에서 계산된 통계 딕셔너리
    :param context: (dict) 백테스트 설정값 딕셔너리
    """

    # --- [ 1. (수정) context에서 값 로드 ] ---
    symbol = context.get('symbol', 'UNKNOWN')
    strategy_name = context.get('strategy_name', 'unknown')
    # -----------------------------------------

    # --- 2. (신규) 전략 이름에 따라 리포트 제목 동적 생성 ---
    report_title = f"종목: {symbol} / 전략: {strategy_name.upper()}"
    if strategy_name == 'turtle':
        strategy_period = context.get('entry_period', '?')
        report_title = f"종목: {symbol} / 전략: 터틀 (Entry: {strategy_period}일)"
    elif strategy_name == 'rsi':
        strategy_period = context.get('rsi_period', '?')
        report_title = f"종목: {symbol} / 전략: RSI (Period: {strategy_period}일)"
    # ------------------------------------------------

    total_return_pct = stats.get('total_return_pct', 0.0) * 100
    final_value = stats.get('final_value', 0.0)
    total_trades = stats.get('total_trades', 0)
    win_rate_pct = stats.get('win_rate_pct', 0.0) * 100
    max_drawdown_pct = stats.get('max_drawdown_pct', 0.0) * 100
    strategy_sells = stats.get('strategy_sells', 0)
    stop_loss_sells = stats.get('stop_loss_sells', 0)

    buy_and_hold_pct = stats.get('buy_and_hold_pct', 0.0) * 100
    dca_return_pct = stats.get('dca_return_pct', 0.0) * 100
    dca_total_invested = stats.get('dca_total_invested', 0.0)

    alpha = total_return_pct - buy_and_hold_pct

    # --- 3. (수정) 동적 제목 출력 ---
    print(report_title)
    # -----------------------------

    print("-" * 30)
    print(f"전략 총 수익률: {total_return_pct:+.2f}%")

    print(f"Buy & Hold 수익률: {buy_and_hold_pct:+.2f}%")
    print(f"DCA (월 $100) 수익률: {dca_return_pct:+.2f}%")
    print(f"  (총 투자 원금: ${dca_total_invested:,.2f})")
    print(f"B&H 대비 초과 수익 (Alpha): {alpha:+.2f}%")

    print("-" * 30)
    print(f"최종 자산 가치 (전략): ${final_value:,.2f}")
    print(f"최대 손실폭 (MDD): {max_drawdown_pct:.2f}%")
    print("-" * 30)
    print(f"총 거래 횟수: {total_trades}회")
    print(f"  - 전략 매도 (Exit): {strategy_sells}회")
    print(f"  - 손절 매도 (Stop): {stop_loss_sells}회")
    print(f"승률 (Win Rate): {win_rate_pct:.2f}%")
    print("-" * 30)