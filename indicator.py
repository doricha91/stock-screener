# [ 📄 indicator.py (RSI, SMA, BB, MACD, BBS, DEMA 전략 추가 수정본) ]

import pandas as pd
import pandas_ta as ta


# config.py는 더 이상 여기서 임포트하지 않습니다.

# --- 1. 터틀 전략 지표 ---
# (기존 add_all_indicators에서 이름 변경)
def add_turtle_indicators(df, context):
    """
    DataFrame에 터틀 트레이딩 전략에 필요한 지표를 추가합니다.

    :param df: data_manager에서 가져온 원본 DataFrame (OHLCV)
    :param context: (dict) 백테스트 설정값 딕셔너리
    :return: 지표가 추가된 DataFrame
    """
    if df is None:
        return None

    # context 딕셔너리에서 설정값 불러오기
    entry_period = context.get('entry_period', 20)
    exit_period = context.get('exit_period', 10)
    atr_period = context.get('atr_period', 20)

    # 1. 터틀 채널 (진입/청산 기준) 추가
    df = add_turtle_channels(df, entry_period, exit_period)

    # 2. ATR (변동성) 추가
    df = add_atr(df, atr_period)

    return df


# --- 2. RSI 전략 지표 ---
def add_rsi_indicators(df, context):
    """
    DataFrame에 RSI 전략에 필요한 지표(RSI)와
    엔진의 리스크 관리에 필요한 지표(ATR)를 추가합니다.

    :param df: data_manager에서 가져온 원본 DataFrame (OHLCV)
    :param context: (dict) 백테스트 설정값 딕셔너리
    :return: 지표가 추가된 DataFrame
    """
    if df is None:
        return None

    # 1. RSI 지표 추가
    rsi_period = context.get('rsi_period', 14)  # config.py에 추가한 값
    try:
        # 'close' 컬럼을 기반으로 RSI 값을 계산하여 'rsi' 새 컬럼에 저장
        df['rsi'] = ta.rsi(df['close'], length=rsi_period)
    except Exception as e:
        print(f"[{context.get('symbol', 'TICKER')}] pandas_ta로 RSI 계산 중 오류: {e}")
        return None

    # --- [ (★) 오류 수정: ATR 지표도 함께 추가 ] ---
    # 엔진(engine.py)이 리스크 관리를 위해 ATR을 필요로 하므로,
    # RSI 전략 실행 시에도 ATR을 계산하여 추가해야 합니다.
    atr_period = context.get('atr_period', 20)
    df = add_atr(df, atr_period)  # (이 파일 하단에 이미 있는 헬퍼 함수 재사용)
    # ---------------------------------------------

    return df


# --- 3. SMA 골든 크로스 전략 지표 ---
def add_sma_indicators(df, context):
    """
    DataFrame에 SMA 골든 크로스 전략과 엔진 리스크 관리에 필요한
    지표(단기 SMA, 장기 SMA, ATR)를 추가합니다.

    :param df: data_manager에서 가져온 원본 DataFrame (OHLCV)
    :param context: (dict) 백테스트 설정값 딕셔너리
    :return: 지표가 추가된 DataFrame
    """
    if df is None:
        return None

    # 1. SMA 지표 추가
    short_period = context.get('sma_short_period', 50)
    long_period = context.get('sma_long_period', 200)

    try:
        # 'close' 컬럼을 기반으로 SMA 계산
        df['sma_short'] = ta.sma(df['close'], length=short_period)
        df['sma_long'] = ta.sma(df['close'], length=long_period)
    except Exception as e:
        print(f"[{context.get('symbol', 'TICKER')}] pandas_ta로 SMA 계산 중 오류: {e}")
        return None

    # 2. 엔진 리스크 관리를 위한 ATR 추가
    # (SMA 전략도 터틀과 동일한 리스크 관리 로직을 사용하기 위해 ATR 추가)
    atr_period = context.get('atr_period', 20)
    df = add_atr(df, atr_period)

    return df


# --- 4. 볼린저 밴드 평균 회귀 전략 지표 ---
def add_bollinger_band_indicators(df, context):
    """
    DataFrame에 볼린저 밴드 평균 회귀 전략과 엔진 리스크 관리에
    필요한 지표(볼린저 밴드, ATR)를 추가합니다.

    :param df: data_manager에서 가져온 원본 DataFrame (OHLCV)
    :param context: (dict) 백테스트 설정값 딕셔너리
    :return: 지표가 추가된 DataFrame
    """
    if df is None:
        return None

    # 1. 볼린저 밴드 지표 추가
    bb_period = context.get('bbands_period', 20)  # config.py의 BBANDS_PERIOD
    bb_std_dev = context.get('bbands_std_dev', 2.0)  # config.py의 BBANDS_STD_DEV

    try:
        # pandas_ta.bbands는 여러 컬럼(하단, 중간, 상단 밴드 등)이
        # 포함된 DataFrame을 반환합니다.
        bb_df = ta.bbands(df['close'], length=bb_period, std=bb_std_dev)

        if bb_df is None or bb_df.empty:
            raise Exception("ta.bbands가 None 또는 빈 DataFrame을 반환했습니다.")

        # 전략 엔진에서 사용하기 쉽도록 'bbl', 'bbm', 'bbu'라는
        # 표준화된 이름으로 df에 추가합니다.

        # iloc[:, 0] : Lower Band (하단 밴드)
        # iloc[:, 1] : Middle Band (중심선)
        # iloc[:, 2] : Upper Band (상단 밴드)
        df['bbl'] = bb_df.iloc[:, 0]
        df['bbm'] = bb_df.iloc[:, 1]
        df['bbu'] = bb_df.iloc[:, 2]

    except Exception as e:
        print(f"[{context.get('symbol', 'TICKER')}] pandas_ta로 볼린저 밴드 계산 중 오류: {e}")
        return None

    # 2. 엔진 리스크 관리를 위한 ATR 추가
    atr_period = context.get('atr_period', 20)
    df = add_atr(df, atr_period)

    return df


# --- 5. (신규) MACD 크로스오버 전략 지표 ---
def add_macd_indicators(df, context):
    """
    DataFrame에 MACD 크로스오버 전략과 엔진 리스크 관리에
    필요한 지표(MACD, MACD Signal, ATR)를 추가합니다.

    :param df: data_manager에서 가져온 원본 DataFrame (OHLCV)
    :param context: (dict) 백테스트 설정값 딕셔너리
    :return: 지표가 추가된 DataFrame
    """
    if df is None:
        return None

    # 1. MACD 지표 추가
    fast_period = context.get('macd_fast_period', 12)
    slow_period = context.get('macd_slow_period', 26)
    signal_period = context.get('macd_signal_period', 9)

    try:
        # ta.macd()는 MACD, Histogram, Signal 3개 컬럼의 DataFrame을 반환
        macd_df = ta.macd(df['close'],
                          fast=fast_period,
                          slow=slow_period,
                          signal=signal_period)

        if macd_df is None or macd_df.empty:
            raise Exception("ta.macd가 None 또는 빈 DataFrame을 반환했습니다.")

        # 전략에 필요한 MACD 라인과 Signal 라인을 표준화된 이름으로 추가
        # iloc[:, 0] : MACD Line
        # iloc[:, 2] : Signal Line
        df['macd'] = macd_df.iloc[:, 0]
        df['macd_signal'] = macd_df.iloc[:, 2]

    except Exception as e:
        print(f"[{context.get('symbol', 'TICKER')}] pandas_ta로 MACD 계산 중 오류: {e}")
        return None

    # 2. 엔진 리스크 관리를 위한 ATR 추가
    atr_period = context.get('atr_period', 20)
    df = add_atr(df, atr_period)

    return df


# --- 6. (신규) 볼린저 밴드 스퀴즈 전략 지표 ---
def add_bbs_indicators(df, context):
    """
    DataFrame에 볼린저 밴드 스퀴즈 전략과 엔진 리스크 관리에
    필요한 지표(볼린저 밴드, 밴드폭(BBW), 밴드폭 N일 최저치, ATR)를 추가합니다.

    :param df: data_manager에서 가져온 원본 DataFrame (OHLCV)
    :param context: (dict) 백테스트 설정값 딕셔너리
    :return: 지표가 추가된 DataFrame
    """
    if df is None:
        return None

    # 1. 볼린저 밴드 스퀴즈 관련 지표 추가
    bb_period = context.get('bbs_period', 20)
    bb_std_dev = context.get('bbs_std_dev', 2.0)
    squeeze_period = context.get('bbs_squeeze_period', 120)

    try:
        # ta.bbands()는 밴드폭(BBW)까지 계산해줍니다 (iloc[:, 3])
        bb_df = ta.bbands(df['close'], length=bb_period, std=bb_std_dev)

        if bb_df is None or bb_df.empty:
            raise Exception("ta.bbands가 None 또는 빈 DataFrame을 반환했습니다.")

        # 돌파(Breakout) 신호 확인을 위한 밴드
        df['bbl'] = bb_df.iloc[:, 0]
        df['bbm'] = bb_df.iloc[:, 1]
        df['bbu'] = bb_df.iloc[:, 2]

        # '응축' 상태 확인을 위한 밴드폭(Bandwidth)
        df['bbw'] = bb_df.iloc[:, 3]

        # 밴드폭(BBW)이 'squeeze_period' 동안의 최저 수준인지 확인하기 위한 지표
        df['bbw_min_low'] = df['bbw'].rolling(window=squeeze_period).min()

    except Exception as e:
        print(f"[{context.get('symbol', 'TICKER')}] pandas_ta로 볼린저 밴드 스퀴즈 계산 중 오류: {e}")
        return None

    # 2. 엔진 리스크 관리를 위한 ATR 추가
    atr_period = context.get('atr_period', 20)
    df = add_atr(df, atr_period)

    return df


# --- 7. (신규) DEMA 크로스오버 전략 지표 ---
def add_dema_indicators(df, context):
    """
    DataFrame에 DEMA 골든 크로스 전략과 엔진 리스크 관리에 필요한
    지표(단기 DEMA, 장기 DEMA, ATR)를 추가합니다.

    :param df: data_manager에서 가져온 원본 DataFrame (OHLCV)
    :param context: (dict) 백테스트 설정값 딕셔너리
    :return: 지표가 추가된 DataFrame
    """
    if df is None:
        return None

    # 1. DEMA 지표 추가 (TEMA도 동일한 방식으로 ta.tema 사용 가능)
    short_period = context.get('dema_short_period', 20)
    long_period = context.get('dema_long_period', 50)

    try:
        # 'close' 컬럼을 기반으로 DEMA 계산
        df['dema_short'] = ta.dema(df['close'], length=short_period)
        df['dema_long'] = ta.dema(df['close'], length=long_period)
    except Exception as e:
        print(f"[{context.get('symbol', 'TICKER')}] pandas_ta로 DEMA 계산 중 오류: {e}")
        return None

    # 2. 엔진 리스크 관리를 위한 ATR 추가
    atr_period = context.get('atr_period', 20)
    df = add_atr(df, atr_period)

    return df


# --- 8. 지표 계산 헬퍼 함수 (공용) ---
# (이하 함수들은 기존과 동일합니다)

def add_turtle_channels(df, entry_period, exit_period):
    """
    N일 신고가 (entry_high)와 N일 신저가 (exit_low)를 계산하여 추가합니다.
    (기존과 동일)
    """
    df['entry_high'] = df['high'].rolling(window=entry_period, min_periods=entry_period).max().shift(1)
    df['exit_low'] = df['low'].rolling(window=exit_period, min_periods=exit_period).min().shift(1)

    return df


def add_atr(df, atr_period):
    """
    ATR (Average True Range)을 계산하여 추가합니다.
    (기존과 동일)
    """
    try:
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=atr_period)
    except Exception as e:
        print(f"pandas_ta로 ATR 계산 중 오류: {e}. pandas로 대체합니다.")
        df = _add_atr_pandas_only(df, atr_period)

    return df


def _add_atr_pandas_only(df, atr_period):
    """
    순수 Pandas로 ATR을 계산하는 내부 함수 (pandas_ta 대용)
    (기존과 동일)
    """
    df_temp = df.copy()
    df_temp['high-low'] = df_temp['high'] - df_temp['low']
    df_temp['high-prev_close'] = abs(df_temp['high'] - df_temp['close'].shift(1))
    df_temp['low-prev_close'] = abs(df_temp['low'] - df_temp['close'].shift(1))

    df_temp['tr'] = df_temp[['high-low', 'high-prev_close', 'low-prev_close']].max(axis=1)

    df['atr'] = df_temp['tr'].ewm(alpha=1 / atr_period, min_periods=atr_period, adjust=False).mean()

    return df