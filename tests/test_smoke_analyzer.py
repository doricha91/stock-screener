# tests/test_smoke_analyzer.py
import conftest
import market_analyzer

def test_market_analyzer():
    print("\n[Smoke Test] Market Analyzer 시작...")
    
    # 1. 특정 테스트 날짜 설정 (데이터가 확실히 있는 과거 날짜)
    test_date = '2025-01-02'
    print(f"   - Testing Date: {test_date}")
    
    try:
        # 2. 시장 상태 조회
        state = market_analyzer.get_market_state(target_date=test_date)
        
        # 3. 필수 키 존재 여부 검증
        required_keys = ['regime', 'trade_halted', 'vix_value', 'triggers', 'plan']
        for key in required_keys:
            if key not in state:
                print(f"   [FAIL] 필수 키 누락: {key}")
                return False
        
        # 4. 국면 값 유효성 검증
        valid_regimes = ['BULL', 'BEAR', 'PANIC', 'UNSTABLE']
        if state['regime'] not in valid_regimes:
            print(f"   [FAIL] 유효하지 않은 국면 값: {state['regime']}")
            return False
            
        print(f"   [OK] 분석 결과 정상: Regime={state['regime']}, Halted={state['trade_halted']}")
        return True

    except Exception as e:
        print(f"   [FAIL] 시장 분석 중 오류 발생: {e}")
        return False

if __name__ == "__main__":
    success = test_market_analyzer()
    if success:
        print("[PASSED] Analyzer Smoke Test")
        exit(0)
    else:
        print("[FAILED] Analyzer Smoke Test")
        exit(1)
