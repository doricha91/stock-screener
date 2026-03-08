# tests/run_smoke_all.py
import sys
import os
import time
from pathlib import Path

# 1. 환경 설정
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["FAST_MODE"] = "1"
os.environ["SMOKE_TEST_ENV_READY"] = "1" # 로그 중복 방지

def run_test(test_name, module_path):
    print(f"\n{'='*60}")
    print(f"[RUN] Running: {test_name}")
    print(f"{'='*60}")
    
    start_time = time.time()
    try:
        # 서브프로세스로 실행하여 환경 고립 보장
        import subprocess
        
        # Create a copy of the environment and set PYTHONIOENCODING to utf-8
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        
        result = subprocess.run(
            [sys.executable, str(module_path)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            env=env
        )
        
        duration = time.time() - start_time
        
        # Always print output for transparency, especially if errors occur
        if result.stdout:
            print(result.stdout)
        
        if result.returncode == 0:
            print(f"[PASSED] {test_name} ({duration:.1f}s)")
            return True, None
        else:
            print(f"[FAILED] {test_name} ({duration:.1f}s)")
            if result.stderr:
                print(f"--- Error Output ---\n{result.stderr}")
            return False, result.stderr
            
    except Exception as e:
        print(f"[ERROR] {test_name} 실행 중 예외 발생: {e}")
        return False, str(e)

def main():
    test_suite = [
        ("Data Smoke Test", ROOT / "tests" / "test_smoke_data.py"),
        ("Analyzer Smoke Test", ROOT / "tests" / "test_smoke_analyzer.py"),
        ("Backtest Smoke Test", ROOT / "tests" / "test_smoke_backtest.py"),
        ("Optimizer Smoke Test", ROOT / "tests" / "test_smoke_optimizer.py"),
    ]
    
    total_start = time.time()
    results = []
    
    print("\n" + "[SEARCH] StockScreener Integrated Smoke Test Suite".center(60))
    print("="*60)
    
    for name, path in test_suite:
        success, error = run_test(name, path)
        results.append((name, success))
        
    # 최종 리포트
    print("\n" + "="*60)
    print("[SUMMARY] SMOKE TEST SUMMARY")
    print("-"*60)
    
    passed_count = 0
    for name, success in results:
        status = "PASS" if success else "FAIL"
        if success: passed_count += 1
        print(f"{name:<30} : {status}")
        
    duration = time.time() - total_start
    print("-"*60)
    print(f"TOTAL: {passed_count}/{len(test_suite)} Passed ({duration:.1f}s)")
    print("="*60 + "\n")
    
    if passed_count == len(test_suite):
        print("[SUCCESS] System is STABLE. Ready for development!\n")
        sys.exit(0)
    else:
        print("[WARN] Some tests FAILED. Please check the logs above.\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
