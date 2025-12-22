import pandas as pd
import numpy as np


# [유틸리티] 신호 데이터 정제 함수 (NaN -> 0, 정수 변환)
def _clean_signals(df):
    # NaN(계산 불가 구간)을 0(Hold)으로 채우고 정수로 변환
    df['signal'] = df['signal'].fillna(0).astype(int)
    return df


# --- 1. 터틀 전략 ---
def generate_turtle_signals(df, context):
    if df is None: return None
    if not all(col in df.columns for col in ['close', 'entry_high', 'exit_low']):
        return None

    # 숫자형 초기화 (0: Hold, 1: Buy, -1: Sell)
    df['signal'] = 0
    df['position'] = 0
    current_position = 0

    # 데이터 부족 시 오류 방지
    entry_period = context.get('entry_period', 20)
    if len(df) < entry_period:
        return _clean_signals(df)

    for i in range(1, len(df)):
        # Buy
        if (current_position == 0) and (df['close'].iloc[i] > df['entry_high'].iloc[i]):
            df.at[df.index[i], 'signal'] = 1
            current_position = 1
        # Sell
        elif (current_position == 1) and (df['close'].iloc[i] < df['exit_low'].iloc[i]):
            df.at[df.index[i], 'signal'] = -1
            current_position = 0

        df.at[df.index[i], 'position'] = current_position

    return _clean_signals(df)


# --- 2. RSI 전략 ---
def generate_rsi_signals(df, context):
    if df is None: return None
    if 'rsi' not in df.columns: return None

    rsi_oversold = context.get('rsi_oversold', 30)
    rsi_overbought = context.get('rsi_overbought', 70)

    df['signal'] = 0
    df['position'] = 0
    current_position = 0

    for i in range(1, len(df)):
        # NaN 체크
        if pd.isna(df['rsi'].iloc[i]): continue

        # Buy
        if (current_position == 0) and (df['rsi'].iloc[i] < rsi_oversold):
            df.at[df.index[i], 'signal'] = 1
            current_position = 1
        # Sell
        elif (current_position == 1) and (df['rsi'].iloc[i] > rsi_overbought):
            df.at[df.index[i], 'signal'] = -1
            current_position = 0

        df.at[df.index[i], 'position'] = current_position

    return _clean_signals(df)


# --- 3. SMA 전략 ---
def generate_sma_signals(df, context):
    if df is None: return None
    if not all(col in df.columns for col in ['sma_short', 'sma_long']): return None

    df['signal'] = 0
    df['position'] = 0
    current_position = 0

    for i in range(1, len(df)):
        s_prev = df['sma_short'].iloc[i - 1]
        l_prev = df['sma_long'].iloc[i - 1]
        s_curr = df['sma_short'].iloc[i]
        l_curr = df['sma_long'].iloc[i]

        if pd.isna(s_prev) or pd.isna(l_prev): continue

        # 골든 크로스 (Buy)
        if (current_position == 0) and (s_prev <= l_prev) and (s_curr > l_curr):
            df.at[df.index[i], 'signal'] = 1
            current_position = 1
        # 데드 크로스 (Sell)
        elif (current_position == 1) and (s_prev >= l_prev) and (s_curr < l_curr):
            df.at[df.index[i], 'signal'] = -1
            current_position = 0

        df.at[df.index[i], 'position'] = current_position

    return _clean_signals(df)


# --- 4. 볼린저 밴드 전략 ---
def generate_bbands_signals(df, context):
    if df is None: return None
    if not all(col in df.columns for col in ['low', 'high', 'bbl', 'bbu']): return None

    df['signal'] = 0
    df['position'] = 0
    current_position = 0

    for i in range(1, len(df)):
        if pd.isna(df['bbl'].iloc[i]): continue

        # Buy (하단 터치)
        if (current_position == 0) and (df['low'].iloc[i] < df['bbl'].iloc[i]):
            df.at[df.index[i], 'signal'] = 1
            current_position = 1
        # Sell (상단 터치)
        elif (current_position == 1) and (df['high'].iloc[i] > df['bbu'].iloc[i]):
            df.at[df.index[i], 'signal'] = -1
            current_position = 0

        df.at[df.index[i], 'position'] = current_position

    return _clean_signals(df)


# --- 5. MACD 전략 ---
def generate_macd_signals(df, context):
    if df is None: return None
    if not all(col in df.columns for col in ['macd', 'macd_signal']): return None

    df['signal'] = 0
    df['position'] = 0
    current_position = 0

    for i in range(1, len(df)):
        m_prev = df['macd'].iloc[i - 1]
        s_prev = df['macd_signal'].iloc[i - 1]
        m_curr = df['macd'].iloc[i]
        s_curr = df['macd_signal'].iloc[i]

        if pd.isna(m_prev) or pd.isna(s_prev): continue

        # Buy
        if (current_position == 0) and (m_prev <= s_prev) and (m_curr > s_curr):
            df.at[df.index[i], 'signal'] = 1
            current_position = 1
        # Sell
        elif (current_position == 1) and (m_prev >= s_prev) and (m_curr < s_curr):
            df.at[df.index[i], 'signal'] = -1
            current_position = 0

        df.at[df.index[i], 'position'] = current_position

    return _clean_signals(df)


# --- 6. BBS (스퀴즈) 전략 ---
def generate_bbs_signals(df, context):
    if df is None: return None
    if not all(col in df.columns for col in ['close', 'bbu', 'bbm', 'bbw', 'bbw_min_low']): return None

    df['signal'] = 0
    df['position'] = 0
    current_position = 0

    for i in range(1, len(df)):
        if pd.isna(df['bbw_min_low'].iloc[i]): continue

        is_squeeze = (df['bbw'].iloc[i] <= df['bbw_min_low'].iloc[i])

        # Buy (스퀴즈 + 상단 돌파)
        if (current_position == 0) and is_squeeze and (df['close'].iloc[i] > df['bbu'].iloc[i]):
            df.at[df.index[i], 'signal'] = 1
            current_position = 1
        # Sell (중심선 이탈)
        elif (current_position == 1) and (df['close'].iloc[i] < df['bbm'].iloc[i]):
            df.at[df.index[i], 'signal'] = -1
            current_position = 0

        df.at[df.index[i], 'position'] = current_position

    return _clean_signals(df)


# --- 7. DEMA 전략 ---
def generate_dema_signals(df, context):
    if df is None: return None
    if not all(col in df.columns for col in ['dema_short', 'dema_long']): return None

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