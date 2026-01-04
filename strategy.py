# strategy.py, 개별 전략 관련 코드

import pandas as pd
import numpy as np


# --- 0. 공통 유틸리티 & Dispatcher ---

def _clean_signals(df):
    """
    (내부용) NaN 값을 0으로 채우고 정수형으로 변환합니다.
    """
    if 'signal' in df.columns:
        df['signal'] = df['signal'].fillna(0).astype(int)
    if 'position' in df.columns:
        df['position'] = df['position'].fillna(0).astype(int)
    return df


def execute_strategy(strategy_name, df, context):
    """
    [Dispatcher] 전략 이름(문자열)을 받아 해당 전략 함수를 실행합니다.
    스크리너나 백테스터에서 전략을 동적으로 호출할 때 사용합니다.

    :param strategy_name: 'turtle', 'rsi', 'sma' ...
    :param df: OHLCV 데이터프레임
    :param context: 파라미터 설정값
    :return: signal, position 컬럼이 추가된 DataFrame
    """
    strategy_map = {
        'turtle': generate_turtle_signals,
        'rsi': generate_rsi_signals,
        'sma': generate_sma_signals,
        'bbands': generate_bbands_signals,
        'macd': generate_macd_signals,
        'bbs': generate_bbs_signals,
        'dema': generate_dema_signals,
        'obv': generate_obv_signals,
        'mfi': generate_mfi_signals,
        'vol_spike': generate_vol_spike_signals
    }

    func = strategy_map.get(strategy_name.lower())
    if func:
        return func(df, context)
    else:
        print(f"❌ [Error] 알 수 없는 전략명: {strategy_name}")
        return df


def apply_ensemble_strategy(df, context):
    """
    [Ensemble] 정의된 모든 전략을 실행하여 각 전략별 신호를 별도 컬럼으로 저장합니다.
    (예: signal_turtle, signal_rsi ...)

    :return: 원본 df에 'signal_{전략명}' 컬럼들이 추가된 DataFrame
    """
    if df is None or df.empty:
        return df

    df_ensemble = df.copy()

    # 앙상블에 포함할 전략 리스트 정의
    strategies = ['turtle', 'rsi', 'sma', 'bbands', 'macd', 'bbs', 'dema', 'obv', 'mfi', 'vol_spike']
    for name in strategies:
        # 1. 각 전략 실행 (임시 DF 사용)
        temp_df = execute_strategy(name, df_ensemble.copy(), context)

        # 2. 결과 컬럼 이름 변경 (signal -> signal_turtle)
        if 'signal' in temp_df.columns:
            col_name = f"signal_{name}"
            df_ensemble[col_name] = temp_df['signal']

    return df_ensemble


# --- 1. 터틀 전략 (Trend Following) ---
def generate_turtle_signals(df, context):
    if df is None: return None
    df = df.copy()  # 안전한 처리를 위해 복사

    # 필수 컬럼 확인
    required = ['close', 'entry_high', 'exit_low']
    if not all(col in df.columns for col in required):
        return df

    entry_period = context.get('entry_period', 20)

    # 데이터가 너무 적으면 계산 불가
    if len(df) < entry_period:
        df['signal'] = 0
        df['position'] = 0
        return _clean_signals(df)

    # 신호 계산 (Loop)
    df['signal'] = 0
    df['position'] = 0
    current_position = 0

    for i in range(1, len(df)):
        price = df['close'].iloc[i]

        # Buy: 가격이 N일 신고가 돌파
        if (current_position == 0) and (price > df['entry_high'].iloc[i]):
            df.at[df.index[i], 'signal'] = 1
            current_position = 1

        # Sell: 가격이 N일 신저가 이탈
        elif (current_position == 1) and (price < df['exit_low'].iloc[i]):
            df.at[df.index[i], 'signal'] = -1
            current_position = 0

        df.at[df.index[i], 'position'] = current_position

    return _clean_signals(df)


# --- 2. RSI 전략 (Momentum / Reversal) ---
def generate_rsi_signals(df, context):
    if df is None: return None
    df = df.copy()

    if 'rsi' not in df.columns: return df

    rsi_oversold = context.get('rsi_oversold', 30)
    rsi_overbought = context.get('rsi_overbought', 70)

    df['signal'] = 0
    df['position'] = 0
    current_position = 0

    for i in range(1, len(df)):
        if pd.isna(df['rsi'].iloc[i]): continue

        rsi_val = df['rsi'].iloc[i]

        # Buy: 과매도 구간 진입 (RSI < 30)
        if (current_position == 0) and (rsi_val < rsi_oversold):
            df.at[df.index[i], 'signal'] = 1
            current_position = 1

        # Sell: 과매수 구간 진입 (RSI > 70)
        elif (current_position == 1) and (rsi_val > rsi_overbought):
            df.at[df.index[i], 'signal'] = -1
            current_position = 0

        df.at[df.index[i], 'position'] = current_position

    return _clean_signals(df)


# --- 3. SMA 전략 (Golden Cross) ---
def generate_sma_signals(df, context):
    if df is None: return None
    df = df.copy()

    if not all(col in df.columns for col in ['sma_short', 'sma_long']): return df

    df['signal'] = 0
    df['position'] = 0
    current_position = 0

    for i in range(1, len(df)):
        s_prev = df['sma_short'].iloc[i - 1]
        l_prev = df['sma_long'].iloc[i - 1]
        s_curr = df['sma_short'].iloc[i]
        l_curr = df['sma_long'].iloc[i]

        if pd.isna(s_prev) or pd.isna(l_prev): continue

        # Buy: 단기선이 장기선을 상향 돌파
        if (current_position == 0) and (s_prev <= l_prev) and (s_curr > l_curr):
            df.at[df.index[i], 'signal'] = 1
            current_position = 1

        # Sell: 단기선이 장기선을 하향 돌파
        elif (current_position == 1) and (s_prev >= l_prev) and (s_curr < l_curr):
            df.at[df.index[i], 'signal'] = -1
            current_position = 0

        df.at[df.index[i], 'position'] = current_position

    return _clean_signals(df)


# --- 4. 볼린저 밴드 전략 (Mean Reversion) ---
def generate_bbands_signals(df, context):
    if df is None: return None
    df = df.copy()

    if not all(col in df.columns for col in ['low', 'high', 'bbl', 'bbu']): return df

    df['signal'] = 0
    df['position'] = 0
    current_position = 0

    for i in range(1, len(df)):
        if pd.isna(df['bbl'].iloc[i]): continue

        # Buy: 저가가 하단 밴드 터치/이탈
        if (current_position == 0) and (df['low'].iloc[i] < df['bbl'].iloc[i]):
            df.at[df.index[i], 'signal'] = 1
            current_position = 1

        # Sell: 고가가 상단 밴드 터치/이탈
        elif (current_position == 1) and (df['high'].iloc[i] > df['bbu'].iloc[i]):
            df.at[df.index[i], 'signal'] = -1
            current_position = 0

        df.at[df.index[i], 'position'] = current_position

    return _clean_signals(df)


# --- 5. MACD 전략 (Trend Reversal) ---
def generate_macd_signals(df, context):
    if df is None: return None
    df = df.copy()

    if not all(col in df.columns for col in ['macd', 'macd_signal']): return df

    df['signal'] = 0
    df['position'] = 0
    current_position = 0

    for i in range(1, len(df)):
        m_prev = df['macd'].iloc[i - 1]
        s_prev = df['macd_signal'].iloc[i - 1]
        m_curr = df['macd'].iloc[i]
        s_curr = df['macd_signal'].iloc[i]

        if pd.isna(m_prev) or pd.isna(s_prev): continue

        # Buy: MACD선이 시그널선을 상향 돌파
        if (current_position == 0) and (m_prev <= s_prev) and (m_curr > s_curr):
            df.at[df.index[i], 'signal'] = 1
            current_position = 1

        # Sell: MACD선이 시그널선을 하향 돌파
        elif (current_position == 1) and (m_prev >= s_prev) and (m_curr < s_curr):
            df.at[df.index[i], 'signal'] = -1
            current_position = 0

        df.at[df.index[i], 'position'] = current_position

    return _clean_signals(df)


# --- 6. BBS 전략 (Volatility Breakout) ---
def generate_bbs_signals(df, context):
    if df is None: return None
    df = df.copy()

    if not all(col in df.columns for col in ['close', 'bbu', 'bbm', 'bbw', 'bbw_min_low']): return df

    df['signal'] = 0
    df['position'] = 0
    current_position = 0

    for i in range(1, len(df)):
        if pd.isna(df['bbw_min_low'].iloc[i]): continue

        # Squeeze 조건: 현재 밴드폭이 N일 최저 밴드폭보다 작거나 같음 (힘의 응축)
        is_squeeze = (df['bbw'].iloc[i] <= df['bbw_min_low'].iloc[i])

        # Buy: Squeeze 상태에서 상단 밴드 돌파
        # (주의: 돌파 시점에 밴드가 확장되어 Squeeze가 False가 될 수도 있으나, 여기선 동시 만족 기준)
        if (current_position == 0) and is_squeeze and (df['close'].iloc[i] > df['bbu'].iloc[i]):
            df.at[df.index[i], 'signal'] = 1
            current_position = 1

        # Sell: 중심선 이탈 시 청산
        elif (current_position == 1) and (df['close'].iloc[i] < df['bbm'].iloc[i]):
            df.at[df.index[i], 'signal'] = -1
            current_position = 0

        df.at[df.index[i], 'position'] = current_position

    return _clean_signals(df)


# --- 7. DEMA 전략 (Fast Moving Average) ---
def generate_dema_signals(df, context):
    if df is None: return None
    df = df.copy()

    if not all(col in df.columns for col in ['dema_short', 'dema_long']): return df

    df['signal'] = 0
    df['position'] = 0
    current_position = 0

    for i in range(1, len(df)):
        s_prev = df['dema_short'].iloc[i - 1]
        l_prev = df['dema_long'].iloc[i - 1]
        s_curr = df['dema_short'].iloc[i]
        l_curr = df['dema_long'].iloc[i]

        if pd.isna(s_prev) or pd.isna(l_prev): continue

        # Buy
        if (current_position == 0) and (s_prev <= l_prev) and (s_curr > l_curr):
            df.at[df.index[i], 'signal'] = 1
            current_position = 1
        # Sell
        elif (current_position == 1) and (s_prev >= l_prev) and (s_curr < l_curr):
            df.at[df.index[i], 'signal'] = -1
            current_position = 0

        df.at[df.index[i], 'position'] = current_position

    return _clean_signals(df)


# 8. OBV 전략 (추세 확인)
def generate_obv_signals(df, context):
    if df is None: return None
    df = df.copy()
    if not all(col in df.columns for col in ['obv', 'obv_sma']): return df

    df['signal'] = 0

    # OBV가 OBV 이동평균보다 높으면 '매집 중'으로 판단 (가산점)
    # 청산 신호는 따로 없음 (0)
    df.loc[df['obv'] > df['obv_sma'], 'signal'] = 1

    return _clean_signals(df)


# 9. MFI 전략 (자금 유입)
def generate_mfi_signals(df, context):
    if df is None: return None
    df = df.copy()
    if 'mfi' not in df.columns: return df

    df['signal'] = 0

    # MFI > 80: 자금이 강력하게 유입되는 '슈퍼 모멘텀' 구간
    # 과매수(매도)가 아니라 추세 강화(매수) 신호로 해석
    df.loc[df['mfi'] > 80, 'signal'] = 1

    return _clean_signals(df)


# 10. 거래량 폭발 전략 (Volume Spike)
def generate_vol_spike_signals(df, context):
    if df is None: return None
    df = df.copy()
    if 'vol_spike_ratio' not in df.columns: return df

    df['signal'] = 0

    # 평소 대비 거래량이 2배(2.0) 이상 터지면 강력한 신호
    # (단, 가격이 양봉일 때만 유효하다고 가정할 수도 있으나 여기선 거래량 자체만 봄)
    df.loc[df['vol_spike_ratio'] >= 2.0, 'signal'] = 1

    return _clean_signals(df)