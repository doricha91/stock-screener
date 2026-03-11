import os
import sys

# 프로젝트 루트 경로를 sys.path에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import io
import contextlib
import pandas as pd
import config as global_config
from core.optimizer_engine import run_optimization
from contextlib import contextmanager

@contextmanager
def patch_global_config(overrides: dict):
    old = {}
    try:
        for k, v in overrides.items():
            old[k] = getattr(global_config, k, None)
            setattr(global_config, k, v)
        yield
    finally:
        for k, prev in old.items():
            setattr(global_config, k, prev)

def capture_optimization_result(hedge_mode: bool):
    print(f"\n>>> Running Optimization with USE_HEDGE_MODE = {hedge_mode}...")
    
    # 안전장치를 모두 끈 상태로 설정
    safety_off = {
        "USE_CIRCUIT_BREAKER": False,
        "USE_MA_CROSS": False,
        "USE_MARKET_BREADTH": False,
        "USE_DRAWDOWN_TRIGGER": False,
        "USE_VIX_BREAKOUT": False,
        "USE_HEDGE_MODE": hedge_mode
    }
    
    # 캡처를 위한 스트림 설정
    f = io.StringIO()
    with contextlib.redirect_stdout(f):
        with patch_global_config(safety_off):
            run_optimization(fast_mode=True)
    
    output = f.getvalue()
    print(f">>> Completed USE_HEDGE_MODE = {hedge_mode}")
    return output

def parse_metrics(output):
    """
    출력 결과에서 최종 리포트 테이블을 찾아 핵심 지표를 추출합니다.
    [Train vs Test 비교 리포트] 섹션을 파싱합니다.
    """
    lines = output.split('\n')
    report_lines = []
    start_capture = False
    
    for line in lines:
        if "📊 [Train vs Test 비교 리포트]" in line:
            start_capture = True
            continue
        if start_capture and "====" in line and len(report_lines) > 2:
            break
        if start_capture:
            report_lines.append(line)
            
    if not report_lines:
        return None
        
    # 데이터프레임으로 변환 시도 (공백 기준 분리)
    # 첫 줄은 구분선, 두번째 줄은 헤더, 세번째 줄은 데이터
    try:
        header = report_lines[1].split()
        data = report_lines[2].split()
        # 숫자가 아닌 문자열 결합 처리 (예: 'Train Sharpe' -> 'TrainSharpe')
        # 단순화를 위해 컬럼 인덱스로 접근
        metrics = {
            'train_sharpe': data[0],
            'test_sharpe': data[1],
            'train_cagr': data[2],
            'test_cagr': data[3],
            'train_mdd': data[4],
            'test_mdd': data[5]
        }
        return metrics
    except:
        return None

if __name__ == "__main__":
    # 1. Hedge Mode OFF 실행
    off_output = capture_optimization_result(False)
    off_metrics = parse_metrics(off_output)
    
    # 2. Hedge Mode ON 실행
    on_output = capture_optimization_result(True)
    on_metrics = parse_metrics(on_output)
    
    # 3. 분석 보고서 작성
    report = []
    report.append("="*60)
    report.append("📢 Hedge Mode ON/OFF 비교 분석 보고서")
    report.append("="*60)
    report.append(f"날짜: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"테스트 기간 (In-Sample): {global_config.IN_SAMPLE_START} ~ {global_config.IN_SAMPLE_END}")
    report.append(f"테스트 기간 (Out-of-Sample): {global_config.OUT_OF_SAMPLE_START} ~ {global_config.OUT_OF_SAMPLE_END}")
    report.append("-" * 60)
    
    if off_metrics and on_metrics:
        report.append(f"{'Metric':<15} | {'Hedge OFF':<12} | {'Hedge ON':<12} | {'Diff':<10}")
        report.append("-" * 60)
        
        for key in ['train_sharpe', 'test_sharpe', 'train_cagr', 'test_cagr', 'train_mdd', 'test_mdd']:
            val_off = float(off_metrics[key].replace('%', ''))
            val_on = float(on_metrics[key].replace('%', ''))
            diff = val_on - val_off
            
            unit = "%" if "cagr" in key or "mdd" in key else ""
            report.append(f"{key:<15} | {val_off:>10.2f}{unit} | {val_on:>10.2f}{unit} | {diff:>+9.2f}{unit}")
            
        report.append("-" * 60)
        
        # 분석 의견
        mdd_diff = float(on_metrics['test_mdd'].replace('%', '')) - float(off_metrics['test_mdd'].replace('%', ''))
        cagr_diff = float(on_metrics['test_cagr'].replace('%', '')) - float(off_metrics['test_cagr'].replace('%', ''))
        
        report.append("\n[분석 의견]")
        if mdd_diff < 0:
            report.append(f"✅ Hedge Mode 적용 시 MDD가 {abs(mdd_diff):.2f}% 개선되었습니다. (방어 효과 확인)")
        else:
            report.append(f"❌ Hedge Mode 적용 시 MDD가 오히려 {mdd_diff:.2f}% 증가했습니다. (헤지 타이밍 재고 필요)")
            
        if cagr_diff > 0:
            report.append(f"✅ 수익률(CAGR) 또한 {cagr_diff:.2f}% 상승하여 방어와 수익을 동시에 잡았습니다.")
        elif cagr_diff < -5:
            report.append(f"⚠️ 수익률이 {abs(cagr_diff):.2f}% 하락했습니다. 방어 비용(헤지 비용)이 큰 편입니다.")
        else:
            report.append(f"ℹ️ 수익률 하락 폭이 {abs(cagr_diff):.2f}%로 크지 않아, 방어 효과 대비 합리적인 수준입니다.")

    else:
        report.append("❌ 데이터 파싱 실패. 원본 출력을 확인하세요.")
        report.append("\n[OFF Output Partial]\n" + off_output[-500:])
        report.append("\n[ON Output Partial]\n" + on_output[-500:])

    final_report_text = "\n".join(report)
    print("\n" + final_report_text)
    
    # 파일 저장
    report_path = "outputs/hedge_mode_analysis_report.txt"
    os.makedirs("outputs", exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(final_report_text)
    
    print(f"\n✅ 분석 보고서가 저장되었습니다: {report_path}")
