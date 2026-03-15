from __future__ import annotations

import csv
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


@dataclass
class Case:
    name: str
    args: list[str]


# 1차 확인용 최소 케이스
SMOKE_CASES: list[Case] = [
    Case("hedge_off", ["--hedge", "off", "--log"]),
    Case("hedge_on_default", ["--hedge", "on", "--log"]),
]

# 전체 실험 케이스
FULL_CASES: list[Case] = [
    # Case("hedge_off", ["--hedge", "off", "--log"]),
    # Case("hedge_on_default", ["--hedge", "on", "--log"]),
    Case("bear_01", ["--hedge", "on", "--hedge-bear-ratio", "0.1", "--log"]),
    Case("bear_02", ["--hedge", "on", "--hedge-bear-ratio", "0.2", "--log"]),
    Case("bear_03", ["--hedge", "on", "--hedge-bear-ratio", "0.3", "--log"]),
    Case("panic_03", ["--hedge", "on", "--hedge-panic-ratio", "0.3", "--log"]),
    Case("panic_05", ["--hedge", "on", "--hedge-panic-ratio", "0.5", "--log"]),
    Case("panic_07", ["--hedge", "on", "--hedge-panic-ratio", "0.7", "--log"]),
    Case("maintain_3", ["--hedge", "on", "--min-mode-maintain-days", "3", "--log"]),
    Case("maintain_5", ["--hedge", "on", "--min-mode-maintain-days", "5", "--log"]),
    Case("maintain_10", ["--hedge", "on", "--min-mode-maintain-days", "10", "--log"]),
]

# 현재 파일 위치: scripts/batch/run_hedge_batch.py
THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[2]

OUTPUTS_DIR = PROJECT_ROOT / "outputs"
BATCH_LOG_DIR = OUTPUTS_DIR / "batch_logs"
META_DIR = OUTPUTS_DIR / "meta"
SUMMARY_DIR = OUTPUTS_DIR / "summary"
DECISION_LOG_DIR = OUTPUTS_DIR / "logs"

RUN_OPTIMIZER_SCRIPT = PROJECT_ROOT / "scripts" / "run_optimizer.py"


def ensure_dirs() -> None:
    for path in [BATCH_LOG_DIR, META_DIR, SUMMARY_DIR, DECISION_LOG_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def latest_file(directory: Path, pattern: str, min_mtime: float) -> Path | None:
    candidates = [
        p for p in directory.glob(pattern)
        if p.is_file() and p.stat().st_mtime >= min_mtime
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def read_summary_row(summary_file: Path) -> dict[str, str] | None:
    try:
        with summary_file.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                return row
    except Exception:
        return None
    return None


def read_meta_file(meta_file: Path) -> dict | None:
    try:
        with meta_file.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def run_case(case: Case) -> int:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = BATCH_LOG_DIR / f"{case.name}_{timestamp}.log"

    cmd = [sys.executable, str(RUN_OPTIMIZER_SCRIPT), *case.args]

    print("\n" + "=" * 80)
    print(f"CASE: {case.name}")
    print("CMD :", " ".join(cmd))
    print(f"LOG : {log_file}")
    print("=" * 80)

    start_time = time.time()

    with log_file.open("w", encoding="utf-8") as f:
        process = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            stdout=f,
            stderr=subprocess.STDOUT,
            text=True,
        )

    end_time = time.time()

    if process.returncode != 0:
        print(f"[FAILED] {case.name}")
        print(f"실행 로그 확인: {log_file}")
        return process.returncode

    meta_file = latest_file(META_DIR, "meta_*.json", start_time - 1)
    summary_file = latest_file(SUMMARY_DIR, "summary_*.csv", start_time - 1)
    decision_file = latest_file(DECISION_LOG_DIR, "decision_*.csv", start_time - 1)

    print(f"[DONE] {case.name} ({end_time - start_time:.1f}초)")
    print(f"meta    : {meta_file if meta_file else 'NOT FOUND'}")
    print(f"summary : {summary_file if summary_file else 'NOT FOUND'}")
    print(f"decision: {decision_file if decision_file else 'NOT FOUND'}")

    if meta_file is None:
        print("[WARN] 메타데이터 파일을 찾지 못했습니다.")
    else:
        meta = read_meta_file(meta_file)
        if meta is None:
            print("[WARN] 메타데이터 파일을 읽지 못했습니다.")
        else:
            print("  meta.check:")
            for key in [
                "run_id",
                "use_hedge_mode",
                "hedge_ratio_bear",
                "hedge_ratio_panic",
                "min_mode_maintain_days",
            ]:
                if key in meta:
                    print(f"    - {key}: {meta[key]}")

    if summary_file is None:
        print("[WARN] 성과요약 파일을 찾지 못했습니다.")
    else:
        summary = read_summary_row(summary_file)
        if summary is None:
            print("[WARN] 성과요약 파일을 읽지 못했습니다.")
        else:
            print("  summary.check:")
            for key in [
                "run_id",
                "use_hedge_mode",
                "hedge_ratio_bear",
                "hedge_ratio_panic",
                "min_mode_maintain_days",
                "total_return",
                "cagr",
                "mdd",
                "sharpe",
                "mode_change_count",
                "order_blocked_count",
                "regime_change_count",
            ]:
                if key in summary:
                    print(f"    - {key}: {summary[key]}")

    return 0


def choose_cases() -> Iterable[Case]:
    print("실행 모드를 선택하세요:")
    print("1) 1차 확인용 2개 케이스")
    print("2) 전체 케이스")
    choice = input("입력 [1/2]: ").strip()

    if choice == "2":
        return FULL_CASES
    return SMOKE_CASES


def main() -> int:
    if not RUN_OPTIMIZER_SCRIPT.exists():
        print(f"[ERROR] run_optimizer.py를 찾을 수 없습니다: {RUN_OPTIMIZER_SCRIPT}")
        return 1

    ensure_dirs()

    cases = list(choose_cases())

    print("\n선택된 케이스:")
    for c in cases:
        print(f"- {c.name}: {' '.join(c.args)}")

    confirm = input("\n계속 실행할까요? [y/N]: ").strip().lower()
    if confirm != "y":
        print("실행 취소")
        return 0

    for idx, case in enumerate(cases, start=1):
        print(f"\n[{idx}/{len(cases)}] 실행 시작")
        rc = run_case(case)
        if rc != 0:
            print("\n배치 실행 중단")
            return rc

    print("\n모든 케이스 실행 완료")
    print("다음 폴더를 확인하세요:")
    print(f"- 메타데이터: {META_DIR}")
    print(f"- 성과요약 : {SUMMARY_DIR}")
    print(f"- 의사결정로그: {DECISION_LOG_DIR}")
    print(f"- 배치로그  : {BATCH_LOG_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())