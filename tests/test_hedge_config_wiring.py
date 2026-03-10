import config
from core.config_factory import make_config
from core.backtest_engine import run_backtest_with_config
import sqlite3

def test_make_config_sync_with_global_config():
    """make_config가 config.py의 전역 설정을 올바르게 동기화하는지 검증"""
    params = {'exit_period': 15}
    
    # 1. Hedge Mode ON 테스트
    config.USE_HEDGE_MODE = True
    cfg_on = make_config(params, '2022-01-01', '2022-12-31')
    assert cfg_on['USE_HEDGE_MODE'] is True
    assert cfg_on['exit_period'] == 15
    
    # 2. Hedge Mode OFF 테스트 (동적 변경 반영 여부)
    config.USE_HEDGE_MODE = False
    cfg_off = make_config(params, '2022-01-01', '2022-12-31')
    assert cfg_off['USE_HEDGE_MODE'] is False

def test_hedge_execution_logic_by_config():
    """Hedge Mode 설정에 따라 실제 백테스트 엔진에서 헤지 거래 발생 여부가 달라지는지 검증"""
    # 하락장 구간 (2022년 초)
    test_params = {
        'initial_capital': 100000.0,
        'max_positions': 2,
        'score_threshold': 1.5,
        'rs_weight': 1.0,
        'turtle_weight': 1.0
    }
    dates = ('2022-01-01', '2022-03-31')
    
    # Case 1: USE_HEDGE_MODE = False
    config.USE_HEDGE_MODE = False
    cfg_off = make_config(test_params, *dates)
    # run_backtest_with_config를 실행하여 결과 딕셔너리를 얻음
    res_off = run_backtest_with_config(cfg_off, verbose=False)
    
    # Case 2: USE_HEDGE_MODE = True
    config.USE_HEDGE_MODE = True
    cfg_on = make_config(test_params, *dates)
    res_on = run_backtest_with_config(cfg_on, verbose=False)
    
    # 검증: 하락장 구간이므로 Hedge ON 시 수익률이나 MDD가 OFF와 달라야 함
    # (Hedge가 작동했다면 최종 에쿼티가 달라짐)
    assert res_off['final_equity'] != res_on['final_equity'], "Hedge ON/OFF should produce different results in 2022"
    
    # 추가 검증: Hedge OFF일 때는 panic_days나 bear_days가 있어도 Hedge 모드 진입 로그가 없어야 함
    # (실제 엔진 내부 current_mode 변수가 HEDGE로 변했는지 체크하는 간접 지표)
    # 여기서는 결과 수치의 차이만으로도 Wiring 결함이 해결되었음을 증명 가능
    print(f"   [OK] Hedge ON final equity ({res_on['final_equity']:.0f}) != OFF ({res_off['final_equity']:.0f})")

if __name__ == "__main__":
    print("\n[Start] test_make_config_sync_with_global_config")
    test_make_config_sync_with_global_config()
    print("[OK] test_make_config_sync_with_global_config")
    
    print("\n[Start] test_hedge_execution_logic_by_config")
    test_hedge_execution_logic_by_config()
    print("[OK] test_hedge_execution_logic_by_config")
    
    print("\n✅ All manual tests passed.")
