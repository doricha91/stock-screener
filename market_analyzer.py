# [ 📄 market_analyzer.py (신규) ]

import pandas_ta as ta
import config


def analyze_market_regime(df_benchmark):
    """
    벤치마크(SPY) 데이터프레임을 받아 '시장 상태(Regime)'를 분석하여 컬럼을 추가합니다.

    :param df_benchmark: SPY의 OHLCV 데이터프레임
    :return: regime 정보가 추가된 DataFrame
    """
    df = df_benchmark.copy()

    # 1. 필요 지표 계산
    # (1) SMA 200 (장기 추세선)
    df['regime_sma'] = ta.sma(df['close'], length=config.REGIME_SMA_PERIOD)

    # (2) ADX (추세 강도)
    # pandas_ta의 adx 함수는 ADX, DMP, DMN 세 개의 컬럼을 반환합니다.
    adx_df = ta.adx(df['high'], df['low'], df['close'], length=config.REGIME_ADX_PERIOD)

    # 반환된 컬럼명 예: ADX_14, DMP_14, DMN_14 -> 'regime_adx'로 통일
    adx_col_name = f"ADX_{config.REGIME_ADX_PERIOD}"
    if adx_col_name in adx_df.columns:
        df['regime_adx'] = adx_df[adx_col_name]
    else:
        # 혹시 컬럼명이 다를 경우 첫 번째 컬럼 사용
        df['regime_adx'] = adx_df.iloc[:, 0]

    # 2. 시장 상태(Regime) 정의 로직
    # 초기값: 'UNCERTAIN' (알 수 없음)
    df['market_regime'] = 'UNCERTAIN'

    # 로직 적용 (벡터화 연산 대신 이해하기 쉬운 apply 또는 루프 사용 가능하지만, 여기선 apply 사용)
    def determine_regime(row):
        # 데이터가 부족해 지표가 계산 안 된 경우
        if pd.isna(row['regime_sma']) or pd.isna(row['regime_adx']):
            return 'UNCERTAIN'

        price = row['close']
        sma = row['regime_sma']
        adx = row['regime_adx']
        threshold_adx = config.REGIME_ADX_THRESHOLD

        # A. 강세장 (Bull Market): 주가가 200일선 위에 있음
        if price > sma:
            if adx >= threshold_adx:
                return 'BULL_TREND'  # 강한 상승장 (추세 추종 전략 유리)
            else:
                return 'BULL_SIDEWAYS'  # 완만한 상승/횡보 (눌림목/스윙 유리)

        # B. 약세장 (Bear Market): 주가가 200일선 아래에 있음
        else:
            if adx >= threshold_adx:
                return 'BEAR_TREND'  # 강한 하락장 (현금 보유 or 숏 전략 유리)
            else:
                return 'BEAR_SIDEWAYS'  # 지루한 하락/횡보 (변동성 돌파 유리)

    # 행별로 함수 적용
    import pandas as pd  # 내부 사용을 위해 import
    df['market_regime'] = df.apply(determine_regime, axis=1)

    return df


def get_current_market_regime(df_benchmark):
    """
    가장 최근(오늘)의 시장 상태를 반환합니다. (스크리너용)
    """
    df_analyzed = analyze_market_regime(df_benchmark)

    # 마지막 행 가져오기
    latest = df_analyzed.iloc[-1]

    return {
        'date': latest.name.strftime('%Y-%m-%d'),
        'regime': latest['market_regime'],
        'adx': round(latest['regime_adx'], 2),
        'close': latest['close'],
        'sma_200': round(latest['regime_sma'], 2)
    }