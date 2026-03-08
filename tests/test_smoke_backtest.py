# tests/test_smoke_backtest.py
import conftest
from core.backtest_engine import run_backtest_with_config

def test_backtest_engine():
    print("\n[Smoke Test] Backtest Engine 시작...")
    
    # 1. 테스트용 초경량 설정 생성 (conftest 유틸리티 사용)
    config = conftest.get_test_config()
    print(f"   - 기간: {config['start_date']} ~ {config['end_date']}")
    print(f"   - 종목: {config['target_tickers']}")
    
    try:
        # 2. 데이터 준비 단계 미리 확인
        from core.backtest_engine import prepare_market_data
        m_data, dates = prepare_market_data(config)
        if not m_data or len(dates) == 0:
            print(f"   [FAIL] 데이터 준비 실패: data_count={len(m_data)}, date_count={len(dates)}")
            return False
        print(f"   [OK] 데이터 준비 완료: {len(dates)}일치 데이터 확보")

        # 3. 백테스트 실행
        result = run_backtest_with_config(config, verbose=False)
        
        # 3. 결과 객체 검증
        if result is None:
            print("   [FAIL] 백테스트 결과가 반환되지 않았습니다 (None).")
            return False
            
        # 필수 지표 확인
        required_metrics = ['return', 'cagr', 'mdd', 'final_equity', 'sharpe', 'safety_stats']
        for metric in required_metrics:
            if metric not in result:
                print(f"   [FAIL] 필수 지표 누락: {metric}")
                return False
        
        print(f"   [OK] 백테스트 완주: Final Equity=${result['final_equity']:,.0f}, MDD={result['mdd']:.2f}%")
        return True

    except Exception as e:
        print(f"   [FAIL] 백테스트 중 런타임 에러 발생: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_backtest_engine()
    if success:
        print("[PASSED] Backtest Smoke Test")
        exit(0)
    else:
        print("[FAILED] Backtest Smoke Test")
        exit(1)
